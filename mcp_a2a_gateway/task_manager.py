# mcp_a2a_gateway/task_manager.py (수정됨)
import uuid
from typing import Dict, Any, Optional, AsyncGenerator, List, Literal
import logging
import httpx
from pydantic import BaseModel, Field
from datetime import datetime, timezone

from a2a.client import A2AClient
from a2a.types import (
    Message,
    TextPart,
    Part,
    Task,
    SendMessageRequest,
    SendMessageResponse,
    SendMessageSuccessResponse,
    SendStreamingMessageRequest,
    GetTaskRequest,
    GetTaskResponse,
    GetTaskSuccessResponse,
    CancelTaskRequest,
    CancelTaskResponse,
    CancelTaskSuccessResponse,
    JSONRPCErrorResponse,
    MessageSendParams,
    TaskQueryParams,
    TaskIdParams,
)
from .agent_manager import AgentManager

logger = logging.getLogger(__name__)


class StoredTask(BaseModel):
    """서버에 저장되는 작업의 상세 정보를 담는 모델"""

    task_id: str = Field(description="The unique identifier for the task.")
    agent_url: str = Field(description="The URL of the agent handling the task.")
    agent_name: str = Field(description="The name of the agent handling the task.")
    request_message: str = Field(
        description="The initial message that started the task."
    )
    status: str = Field(
        description="The current status of the task (e.g., pending, running, completed, error)."
    )
    result: Optional[Dict[str, Any]] = Field(
        None, description="The final result of the task, if completed."
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def update_status(self, status: str, result: Optional[Dict[str, Any]] = None):
        """Helper to update task status and timestamp."""
        self.status = status
        if result:
            self.result = result
        self.updated_at = datetime.now(timezone.utc)

    class Config:
        arbitrary_types_allowed = True


def format_task_response(task: Task) -> Dict[str, Any]:
    """A2A Task 객체를 응답용 dict로 변환합니다."""
    response = {
        "request_status": "success",  # 'status' -> 'request_status'
        # 'task_id' is already in the parent object, so we remove it here.
        "session_id": task.contextId,
        "state": task.status.state,
        "message": None,
        "artifacts": [],
    }
    if task.status.message and task.status.message.parts:
        response["message"] = " ".join(
            part.root.text
            for part in task.status.message.parts
            if isinstance(part.root, TextPart)
        )
    if task.artifacts:
        response["artifacts"] = [a.model_dump(mode="json") for a in task.artifacts]
    return response


class TaskManager:
    def __init__(self, agent_manager: AgentManager):
        self.tasks: Dict[str, StoredTask] = {}
        self.agent_manager = agent_manager

    def get_task(self, task_id: str) -> Optional[StoredTask]:
        """저장된 작업 정보를 가져옵니다."""
        return self.tasks.get(task_id)

    def remove_tasks_for_agent(self, url: str) -> int:
        """특정 에이전트에 할당된 모든 작업을 제거합니다."""
        tasks_to_remove = [
            task_id for task_id, task in self.tasks.items() if task.agent_url == url
        ]
        for task_id in tasks_to_remove:
            del self.tasks[task_id]
        logger.info(f"Removed {len(tasks_to_remove)} tasks for agent {url}.")
        return len(tasks_to_remove)

    async def send_message(
        self, agent_url: str, message_text: str, session_id: Optional[str]
    ) -> Dict[str, Any]:
        """에이전트에게 메시지를 보내고, 항상 task_id를 포함한 응답을 반환합니다."""
        agent_info = self.agent_manager.get_agent(agent_url)
        if not agent_info:
            raise ValueError(f"Agent not registered: {agent_url}")

        task_id = str(uuid.uuid4())
        # Add agent_name and request_message on creation
        stored_task = StoredTask(
            task_id=task_id,
            agent_url=agent_url,
            agent_name=agent_info.card.name,
            request_message=message_text,
            status="pending",
        )
        self.tasks[task_id] = stored_task

        try:
            async with httpx.AsyncClient() as http_client:
                client = A2AClient(httpx_client=http_client, agent_card=agent_info.card)
                params = MessageSendParams(
                    message=Message(
                        role="user",
                        parts=[Part(root=TextPart(text=message_text))],
                        messageId=str(uuid.uuid4()),
                    ),
                    contextId=session_id,
                )
                request = SendMessageRequest(id=task_id, params=params)
                response: SendMessageResponse = await client.send_message(request)

                logger.info(f"Message sent successfully to {agent_url}: {response}")

                if isinstance(response.root, SendMessageSuccessResponse):
                    result = response.root.result
                    if isinstance(result, Task):
                        task_response = format_task_response(result)
                        stored_task.update_status(
                            task_response.get("state", "completed"), task_response
                        )
                        # Ensure task_id consistency if agent returns a different one
                        if result.id and result.id != task_id:
                            self.tasks[result.id] = self.tasks.pop(task_id)
                            stored_task.task_id = result.id
                        # Return the full stored task for a consistent response structure
                        return stored_task.model_dump(mode="json")
                    elif isinstance(result, Message):
                        message_content = " ".join(
                            p.root.text
                            for p in result.parts
                            if isinstance(p.root, TextPart)
                        )
                        task_response = {
                            "request_status": "success",
                            "message": message_content,
                        }
                        stored_task.update_status("completed", task_response)
                        return stored_task.model_dump(mode="json")

                elif isinstance(response.root, JSONRPCErrorResponse):
                    error = response.root.error
                    error_response = {
                        "request_status": "error",
                        "message": f"Agent Error: {error.message} (Code: {error.code})",
                    }
                    stored_task.update_status("error", error_response)
                    # Return the full task object even on error
                    return stored_task.model_dump(mode="json")

                raise TypeError(f"Unexpected response type: {type(response.root)}")

        except Exception as e:
            logger.error(f"Error sending message to {agent_url}: {e}")
            error_response = {"request_status": "error", "message": str(e)}
            stored_task.update_status("error", error_response)
            raise

    async def get_task_result(
        self, task_id: str, history_length: Optional[int]
    ) -> Dict[str, Any]:
        """저장된 작업 결과를 가져오거나, 에이전트에 직접 요청합니다."""
        stored_task = self.get_task(task_id)
        if not stored_task:
            raise ValueError(f"Task ID not found: {task_id}")

        # Always return the full stored task object for consistency
        if stored_task.status in ["completed", "error"]:
            return stored_task.model_dump(mode="json")

        agent_info = self.agent_manager.get_agent(stored_task.agent_url)
        if not agent_info:
            raise ValueError(f"Agent for task {task_id} not found.")

        try:
            async with httpx.AsyncClient() as http_client:
                client = A2AClient(httpx_client=http_client, agent_card=agent_info.card)
                params = TaskQueryParams(id=task_id, historyLength=history_length)
                request = GetTaskRequest(id=task_id, params=params, method="tasks/get")
                response: GetTaskResponse = await client.get_task(request)

                if isinstance(response.root, GetTaskSuccessResponse):
                    task_response = format_task_response(response.root.result)
                    stored_task.update_status(
                        task_response.get("state", "completed"), task_response
                    )
                elif isinstance(response.root, JSONRPCErrorResponse):
                    error = response.root.error
                    error_response = {
                        "request_status": "error",
                        "message": f"Agent Error: {error.message} (Code: {error.code})",
                    }
                    stored_task.update_status("error", error_response)
                else:
                    raise TypeError(f"Unexpected response type: {type(response.root)}")

                return stored_task.model_dump(mode="json")
        except Exception as e:
            logger.error(f"Error retrieving task {task_id}: {e}")
            raise

    async def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """실행 중인 작업을 취소합니다."""
        stored_task = self.get_task(task_id)
        if not stored_task:
            raise ValueError(f"Task ID not found: {task_id}")

        agent_info = self.agent_manager.get_agent(stored_task.agent_url)
        if not agent_info:
            raise ValueError(f"Agent for task {task_id} not found.")

        try:
            async with httpx.AsyncClient() as http_client:
                client = A2AClient(httpx_client=http_client, agent_card=agent_info.card)
                params = TaskIdParams(id=task_id)
                request = CancelTaskRequest(
                    id=task_id, params=params, method="tasks/cancel"
                )
                response: CancelTaskResponse = await client.cancel_task(request)

                if isinstance(response.root, CancelTaskSuccessResponse):
                    task_response = format_task_response(response.root.result)
                    stored_task.update_status("cancelled", task_response)
                    return stored_task.model_dump(mode="json")
                elif isinstance(response.root, JSONRPCErrorResponse):
                    error = response.root.error
                    # Return a consistent error structure
                    return {
                        "request_status": "error",
                        "message": f"Agent Error: {error.message} (Code: {error.code})",
                    }
                raise TypeError(f"Unexpected response type: {type(response.root)}")
        except Exception as e:
            logger.error(f"Error cancelling task {task_id}: {e}")
            raise

    async def send_message_stream(
        self, agent_url: str, message_text: str, session_id: Optional[str]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """메시지를 보내고 응답을 스트리밍합니다."""
        agent_info = self.agent_manager.get_agent(agent_url)
        if not agent_info:
            yield {"status": "error", "message": f"Agent not registered: {agent_url}"}
            return

        task_id = str(uuid.uuid4())
        stored_task = StoredTask(
            task_id=task_id,
            agent_url=agent_url,
            agent_name=agent_info.card.name,
            request_message=message_text,
            status="streaming",
        )
        self.tasks[task_id] = stored_task

        try:
            async with httpx.AsyncClient() as http_client:
                client = A2AClient(httpx_client=http_client, agent_card=agent_info.card)
                params = MessageSendParams(
                    message=Message(
                        role="user",
                        parts=[Part(root=TextPart(text=message_text))],
                        messageId=str(uuid.uuid4()),
                    )
                )
                request = SendStreamingMessageRequest(id=task_id, params=params)

                async for event in client.send_message_streaming(request):
                    yield event.model_dump(mode="json")
                stored_task.update_status("completed")

        except Exception as e:
            logger.error(f"Error streaming message to {agent_url}: {e}")
            stored_task.update_status("error", {"message": str(e)})
            yield {"status": "error", "message": str(e), "task_id": task_id}

    def get_task_list(
        self,
        status: Literal[
            "all", "completed", "running", "error", "pending", "streaming", "cancelled"
        ] = "all",
        sort: Literal["Descending", "Ascending"] = "Descending",
        number: int = 10,
    ) -> List[StoredTask]:
        """Gets a list of tasks, with optional filtering and sorting."""
        tasks = list(self.tasks.values())

        if status != "all":
            tasks = [task for task in tasks if task.status == status]

        reverse = sort == "Descending"
        tasks.sort(key=lambda t: t.updated_at, reverse=reverse)

        return tasks[:number]

    def get_tasks_for_saving(self) -> Dict[str, dict]:
        """저장을 위해 직렬화된 작업 데이터를 반환합니다."""
        return {
            task_id: task.model_dump(mode="json")
            for task_id, task in self.tasks.items()
        }

    def load_tasks_from_data(self, data: Dict[str, dict]):
        """파일에서 작업 데이터를 불러옵니다."""
        for task_id, task_data in data.items():
            try:
                self.tasks[task_id] = StoredTask.model_validate(task_data)
            except Exception as e:
                logger.error(f"Failed to load task data for {task_id}: {e}")
        logger.info(f"Loaded {len(self.tasks)} tasks.")
