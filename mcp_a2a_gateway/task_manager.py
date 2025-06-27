# mcp_a2a_gateway/task_manager.py (수정됨)
import asyncio
import uuid
from typing import Dict, Any, Optional, AsyncGenerator, List, Literal
from enum import Enum
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
    TaskStatusUpdateEvent,
    TaskStatus,
)
from .agent_manager import AgentManager

logger = logging.getLogger(__name__)

# --- 상수 정의 ---
DEFAULT_TIMEOUT = 30.0  # 에이전트 통신 시 기본 타임아웃을 30초로 설정


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
    # TaskState Enum 값을 문자열로 변환
    state_value = (
        task.status.state.value
        if isinstance(task.status.state, Enum)
        else task.status.state
    )
    response = {
        "request_status": "success",
        "session_id": task.contextId,
        "state": state_value,
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
        self._background_tasks = set()

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

    async def _poll_and_update_task(self, task_id: str):
        """(백그라운드 실행) 작업이 완료될 때까지 폴링하고 상태를 업데이트합니다."""
        logger.info(f"[BG Task] Started polling for task {task_id}.")
        while True:
            try:
                task = self.get_task(task_id)
                if not task or task.status in ["completed", "error", "cancelled"]:
                    logger.info(
                        f"[BG Task] Polling stopped for task {task_id} as it is in a final state."
                    )
                    break

                await self.get_task_result(task_id, history_length=None)

                # get_task_result 이후 다시 상태 확인
                if task.status in ["completed", "error", "cancelled"]:
                    logger.info(
                        f"[BG Task] Polling finished for task {task_id}. Final status: {task.status}."
                    )
                    break

                await asyncio.sleep(2)  # 2초 간격으로 폴링

            except Exception as e:
                logger.error(f"[BG Task] Error polling for task {task_id}: {e}")
                task = self.get_task(task_id)
                if task:
                    task.update_status(
                        "error",
                        {"request_status": "error", "message": f"Polling failed: {e}"},
                    )
                break

        # 태스크 완료 후 전역 태스크 세트에서 제거
        self._background_tasks.discard(asyncio.current_task())

    async def send_message(
        self,
        agent_url: str,
        message_text: str,
        session_id: Optional[str],
    ) -> Dict[str, Any]:
        """
        에이전트에게 메시지를 보냅니다.
        - 즉시 응답 시: 완료된 결과를 반환합니다.
        - 비동기 작업 시: 백그라운드 폴링을 시작하고 'running' 상태를 즉시 반환합니다.
        """
        agent_info = self.agent_manager.get_agent(agent_url)
        if not agent_info:
            raise ValueError(f"Agent not registered: {agent_url}")

        task_id = str(uuid.uuid4())

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as http_client:
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

                # CASE 1: 에이전트가 즉시 Message를 반환 (동기 작업)
                if isinstance(response.root, SendMessageSuccessResponse) and isinstance(
                    response.root.result, Message
                ):
                    logger.info(
                        f"Received immediate message response from {agent_url}."
                    )
                    result = response.root.result
                    message_content = " ".join(
                        p.root.text
                        for p in result.parts
                        if isinstance(p.root, TextPart)
                    )
                    task_response = {
                        "request_status": "success",
                        "message": message_content,
                    }

                    stored_task = StoredTask(
                        task_id=task_id,
                        agent_url=agent_url,
                        agent_name=agent_info.card.name,
                        request_message=message_text,
                        status="completed",
                        result=task_response,
                    )
                    self.tasks[task_id] = stored_task
                    return stored_task.model_dump(mode="json")

                # CASE 2: 에이전트가 Task를 반환 (비동기 작업)
                elif isinstance(
                    response.root, SendMessageSuccessResponse
                ) and isinstance(response.root.result, Task):
                    logger.info(
                        f"Received task from {agent_url}. Starting background polling."
                    )
                    result_task = response.root.result

                    # 에이전트가 다른 task_id를 반환한 경우, 교체
                    final_task_id = result_task.id if result_task.id else task_id

                    stored_task = StoredTask(
                        task_id=final_task_id,
                        agent_url=agent_url,
                        agent_name=agent_info.card.name,
                        request_message=message_text,
                        status=result_task.status.state.value,
                        result=format_task_response(result_task),
                    )
                    self.tasks[stored_task.task_id] = stored_task

                    # 백그라운드에서 폴링 시작
                    bg_task = asyncio.create_task(
                        self._poll_and_update_task(stored_task.task_id)
                    )
                    self._background_tasks.add(bg_task)
                    bg_task.add_done_callback(self._background_tasks.discard)

                    # 클라이언트에게는 초기 상태를 즉시 반환
                    return stored_task.model_dump(mode="json")

                # CASE 3: 에러 응답
                elif isinstance(response.root, JSONRPCErrorResponse):
                    error = response.root.error
                    error_response = {
                        "request_status": "error",
                        "message": f"Agent Error: {error.message} (Code: {error.code})",
                    }
                    stored_task = StoredTask(
                        task_id=task_id,
                        agent_url=agent_url,
                        agent_name=agent_info.card.name,
                        request_message=message_text,
                        status="error",
                        result=error_response,
                    )
                    self.tasks[task_id] = stored_task
                    return stored_task.model_dump(mode="json")

                raise TypeError(
                    f"Unexpected success response type: {type(response.root)}"
                )

        except Exception as e:
            logger.error(f"Error during send_message to {agent_url}: {e}")
            error_response = {"request_status": "error", "message": str(e)}
            stored_task = StoredTask(
                task_id=task_id,
                agent_url=agent_url,
                agent_name=agent_info.card.name,
                request_message=message_text,
                status="error",
                result=error_response,
            )
            self.tasks[task_id] = stored_task
            return stored_task.model_dump(mode="json")

    async def get_task_result(
        self, task_id: str, history_length: Optional[int]
    ) -> Dict[str, Any]:
        stored_task = self.get_task(task_id)
        if not stored_task:
            raise ValueError(f"Task ID not found: {task_id}")

        if stored_task.status in ["completed", "error", "cancelled"]:
            return stored_task.model_dump(mode="json")

        agent_info = self.agent_manager.get_agent(stored_task.agent_url)
        if not agent_info:
            raise ValueError(f"Agent for task {task_id} not found.")

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as http_client:
                client = A2AClient(httpx_client=http_client, agent_card=agent_info.card)
                params = TaskQueryParams(id=task_id, historyLength=history_length)
                request = GetTaskRequest(id=task_id, params=params, method="tasks/get")
                response: GetTaskResponse = await client.get_task(request)

                if isinstance(response.root, GetTaskSuccessResponse):
                    task_response = format_task_response(response.root.result)
                    new_state = task_response.get("state", "running")
                    if stored_task.status != new_state:
                        logger.info(
                            f"Task {task_id} status changed from '{stored_task.status}' to '{new_state}'."
                        )
                        stored_task.update_status(new_state, task_response)

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
            stored_task.update_status(
                "error", {"request_status": "error", "message": str(e)}
            )
            return stored_task.model_dump(mode="json")

    async def cancel_task(self, task_id: str) -> Dict[str, Any]:
        # (이 메소드는 변경되지 않았습니다.)
        stored_task = self.get_task(task_id)
        if not stored_task:
            raise ValueError(f"Task ID not found: {task_id}")

        agent_info = self.agent_manager.get_agent(stored_task.agent_url)
        if not agent_info:
            raise ValueError(f"Agent for task {task_id} not found.")

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as http_client:
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
        # (이 메소드는 변경되지 않았습니다.)
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

        streamed_content = []
        final_task_status: Optional[TaskStatus] = None

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as http_client:
                client = A2AClient(httpx_client=http_client, agent_card=agent_info.card)
                params = MessageSendParams(
                    message=Message(
                        role="user",
                        parts=[Part(root=TextPart(text=message_text))],
                        messageId=str(uuid.uuid4()),
                    )
                )
                request = SendStreamingMessageRequest(id=task_id, params=params)

                async for event_wrapper in client.send_message_streaming(request):
                    event = event_wrapper.root
                    yield event.model_dump(mode="json")

                    if isinstance(event, TaskStatusUpdateEvent):
                        final_task_status = event.status
                        if (
                            event.status
                            and event.status.message
                            and event.status.message.parts
                        ):
                            for part in event.status.message.parts:
                                if isinstance(part.root, TextPart):
                                    streamed_content.append(part.root.text)

            if final_task_status:
                result_message = "".join(streamed_content)
                if final_task_status.message and final_task_status.message.parts:
                    result_message = " ".join(
                        p.root.text
                        for p in final_task_status.message.parts
                        if isinstance(p.root, TextPart)
                    )

                result_payload = {
                    "request_status": "success",
                    "state": final_task_status.state.value,
                    "message": result_message,
                    "artifacts": [],
                }
                stored_task.update_status("completed", result_payload)
            else:
                stored_task.update_status(
                    "completed",
                    {"request_status": "success", "message": "".join(streamed_content)},
                )

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
        # (이 메소드는 변경되지 않았습니다.)
        tasks = list(self.tasks.values())

        if status != "all":
            tasks = [task for task in tasks if task.status == status]

        reverse = sort == "Descending"
        tasks.sort(key=lambda t: t.updated_at, reverse=reverse)

        return tasks[:number]

    def get_tasks_for_saving(self) -> Dict[str, dict]:
        # (이 메소드는 변경되지 않았습니다.)
        return {
            task_id: task.model_dump(mode="json")
            for task_id, task in self.tasks.items()
        }

    def load_tasks_from_data(self, data: Dict[str, dict]):
        # (이 메소드는 변경되지 않았습니다.)
        for task_id, task_data in data.items():
            try:
                self.tasks[task_id] = StoredTask.model_validate(task_data)
            except Exception as e:
                logger.error(f"Failed to load task data for {task_id}: {e}")
        logger.info(f"Loaded {len(self.tasks)} tasks.")
