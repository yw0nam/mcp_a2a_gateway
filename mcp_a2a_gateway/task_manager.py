# mcp_a2a_gateway/task_manager.py (수정됨)
import uuid
from typing import Dict, Any, Optional, AsyncGenerator
import logging
import httpx
from pydantic import BaseModel, Field

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
    status: str = Field(
        description="The current status of the task (e.g., pending, running, completed, error)."
    )
    result: Optional[Dict[str, Any]] = Field(
        None, description="The final result of the task, if completed."
    )

    class Config:
        arbitrary_types_allowed = True


def format_task_response(task: Task) -> Dict[str, Any]:
    """A2A Task 객체를 응답용 dict로 변환합니다."""
    response = {
        "status": "success",
        "task_id": task.id,
        "session_id": task.contextId,
        "state": task.status.state,
        "message": None,
        "artifacts": [],
    }
    # 수정된 파싱 로직
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
        stored_task = StoredTask(task_id=task_id, agent_url=agent_url, status="pending")
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
                        stored_task.status = task_response.get("state", "completed")
                        stored_task.result = task_response
                        if result.id and result.id != task_id:
                            self.tasks[result.id] = self.tasks.pop(task_id)
                            stored_task.task_id = result.id
                        return task_response
                    elif isinstance(result, Message):
                        # 수정된 파싱 로직
                        message_content = " ".join(
                            p.root.text
                            for p in result.parts
                            if isinstance(p.root, TextPart)
                        )
                        task_response = {
                            "status": "success",
                            "task_id": task_id,
                            "message": message_content,
                        }
                        stored_task.status = "completed"
                        stored_task.result = task_response
                        return task_response

                elif isinstance(response.root, JSONRPCErrorResponse):
                    error = response.root.error
                    error_response = {
                        "status": "error",
                        "task_id": task_id,
                        "message": f"Agent Error: {error.message} (Code: {error.code})",
                    }
                    stored_task.status = "error"
                    stored_task.result = error_response
                    return error_response

                raise TypeError(f"Unexpected response type: {type(response.root)}")

        except Exception as e:
            logger.error(f"Error sending message to {agent_url}: {e}")
            error_response = {"status": "error", "task_id": task_id, "message": str(e)}
            stored_task.status = "error"
            stored_task.result = error_response
            raise

    async def get_task_result(
        self, task_id: str, history_length: Optional[int]
    ) -> Dict[str, Any]:
        """저장된 작업 결과를 가져오거나, 에이전트에 직접 요청합니다."""
        stored_task = self.get_task(task_id)
        if not stored_task:
            raise ValueError(f"Task ID not found: {task_id}")

        if stored_task.status in ["completed", "error"] and stored_task.result:
            return stored_task.result

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
                    stored_task.status = task_response.get("state", "completed")
                    stored_task.result = task_response
                    return task_response
                elif isinstance(response.root, JSONRPCErrorResponse):
                    error = response.root.error
                    error_response = {
                        "status": "error",
                        "message": f"Agent Error: {error.message} (Code: {error.code})",
                    }
                    stored_task.status = "error"
                    stored_task.result = error_response
                    return error_response

                raise TypeError(f"Unexpected response type: {type(response.root)}")
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
                    stored_task.status = "cancelled"
                    stored_task.result = task_response
                    return task_response
                elif isinstance(response.root, JSONRPCErrorResponse):
                    error = response.root.error
                    return {
                        "status": "error",
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
            task_id=task_id, agent_url=agent_url, status="streaming"
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
                stored_task.status = "completed"

        except Exception as e:
            logger.error(f"Error streaming message to {agent_url}: {e}")
            stored_task.status = "error"
            yield {"status": "error", "message": str(e), "task_id": task_id}

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
