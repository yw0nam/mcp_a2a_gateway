import asyncio
import uuid
from typing import Dict, Any, Optional, AsyncGenerator, List, Literal
from enum import Enum
import logging
import httpx
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from fastapi import BackgroundTasks

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
from .agent_manager import AgentManager, AgentInfo

logger = logging.getLogger(__name__)

# --- 상수 정의 ---
DEFAULT_TIMEOUT = 30.0
# IMMEDIATE_RESPONSE_TIMEOUT = 2.0  # 이 값은 유지하되, 로직을 변경합니다.


class StoredTask(BaseModel):
    """서버에 저장되는 작업의 상세 정보를 담는 모델"""

    # ⭐️ [변경] agent_task_id 필드 추가
    agent_task_id: Optional[str] = Field(
        None, description="The task ID provided by the agent, if different."
    )
    task_id: str = Field(description="The unique identifier for the task (gateway ID).")
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

    # ⭐️ [핵심 수정] _process_agent_response 함수 수정
    async def _process_agent_response(
        self,
        response: SendMessageResponse,
        gateway_task_id: str,  # 이름을 명확하게 변경
        agent_url: str,
        agent_info: AgentInfo,
        message_text: str,
    ) -> StoredTask:
        """에이전트 응답을 처리하고 항상 gateway_task_id를 기준으로 태스크를 업데이트합니다."""
        stored_task = self.get_task(gateway_task_id)
        if not stored_task:
            # This can happen if the background task runs after a long delay
            # and the task has been removed.
            logger.warning(
                f"Task {gateway_task_id} not found while processing agent response."
            )
            # Create a new one to log the response, though it's disconnected.
            stored_task = StoredTask(
                task_id=gateway_task_id,
                agent_url=agent_url,
                agent_name=agent_info.card.name,
                request_message=message_text,
                status="unknown",  # Initial status
            )

        try:
            if isinstance(response.root, SendMessageSuccessResponse):
                status = "completed"
                logger.info(f"Agent {agent_url} completed the task successfully.")
                result_data = response.root.result
                message_content = " ".join(
                    p.root.text
                    for p in result_data.parts
                    if isinstance(p.root, TextPart)
                )
                result = {
                    "request_status": status,
                    "message": message_content,
                }
            elif isinstance(response.root, Task):
                # This case might occur if the agent immediately returns a task object
                # instead of a direct message. We treat it as 'running'.
                status = "running"
                logger.info(
                    f"Agent {agent_url} returned a task object. Now running in background."
                )
                message_content = (
                    " ".join(
                        p.root.text
                        for p in result_data.parts
                        if isinstance(p.root, TextPart)
                    )
                    if result_data.parts
                    else "Running task in background."
                )
                result = {
                    "request_status": status,
                    "message": message_content,
                }
            elif isinstance(response.root, JSONRPCErrorResponse):
                logger.error(
                    f"Agent {agent_url} returned an error: {response.root.error.message}"
                )
                status = "error"
                error = response.root.error
                result = {
                    "request_status": "error",
                    "message": f"Agent Error: {error.message} (Code: {error.code})",
                }
            else:
                # Fallback for unexpected response types
                status = "error"
                result = {
                    "request_status": "error",
                    "message": f"Unexpected response type: {type(response.root)}",
                }
                logger.error(result["message"])

            stored_task.update_status(status, result)
            return stored_task
        except Exception as e:
            logger.error(
                f"Error processing agent response for {gateway_task_id}: {e}",
                exc_info=True,
            )
            stored_task.update_status(
                "error", {"request_status": "error", "message": str(e)}
            )
            return stored_task

    async def send_message_async(
        self,
        agent_url: str,
        message_text: str,
        session_id: Optional[str],
    ) -> Dict[str, Any]:
        """
        백그라운드에서 에이전트 요청을 시작하고,
        즉시 'pending' 상태의 태스크와 task_id를 반환합니다.
        """
        agent_info = self.agent_manager.get_agent(agent_url)
        if not agent_info:
            raise ValueError(f"Agent not registered: {agent_url}")

        gateway_task_id = str(uuid.uuid4())

        # 1. 백그라운드에서 실제 통신을 처리할 코루틴을 정의합니다.
        async def _send_and_update_task():
            try:
                # StoredTask 객체를 찾아 상태를 업데이트합니다.
                task_record = self.tasks[gateway_task_id]
                timeout_config = httpx.Timeout(30.0, connect=5.0)
                http_client = httpx.AsyncClient(timeout=timeout_config)
                client = A2AClient(httpx_client=http_client, agent_card=agent_info.card)
                request = SendMessageRequest(
                    id=gateway_task_id,
                    params=MessageSendParams(
                        message=Message(
                            role="user",
                            parts=[Part(root=TextPart(text=message_text))],
                            messageId=str(uuid.uuid4()),
                        ),
                        sessionId=session_id,
                    ),
                )
                # 실제 에이전트와 통신 (이 부분이 오래 걸릴 수 있습니다)
                response = await client.send_message(request)

                # 성공 시 태스크 상태 업데이트
                task_record = await self._process_agent_response(
                    response,
                    gateway_task_id,
                    agent_url,
                    agent_info,
                    message_text,
                )
                self.tasks[gateway_task_id] = task_record
            except Exception as e:
                logger.error(f"Task {gateway_task_id} failed: {e}", exc_info=True)
                if "task_record" in locals():
                    task_record.update_status("error", {"message": str(e)})
            finally:
                if "http_client" in locals():
                    await http_client.aclose()

        # 2. 'pending' 상태의 태스크를 먼저 생성하고 저장합니다.
        pending_task = StoredTask(
            task_id=gateway_task_id,
            agent_url=agent_url,
            agent_name=agent_info.card.name,
            request_message=message_text,
            status="pending",
            result={"message": "Task is being processed."},
        )

        self.tasks[gateway_task_id] = pending_task
        # 3. 백그라운드 작업을 시작시킵니다. await 하지 않습니다!
        asyncio.create_task(_send_and_update_task())

        # 4. 'pending' 태스크 정보를 즉시 반환합니다.
        return pending_task.model_dump(mode="json")

    async def get_task_result(self, task_id: str) -> Dict[str, Any]:
        """게이트웨이 task_id를 사용하여 태스크 결과를 폴링합니다."""
        stored_task = self.get_task(task_id)
        if not stored_task:
            return {"status": "error", "message": f"Task ID not found: {task_id}"}

        # if stored_task.status == "completed":
        # 이미 완료된 태스크는 즉시 결과를 반환합니다.
        return stored_task.model_dump(mode="json")
        # For pending tasks, we can try a quick fetch to see if it's done.
        # elif stored_task.status in ["pending", "running"] and stored_task.agent_task_id:
        #     logger.info(f"Polling agent for latest status of task {task_id}")
        #     try:
        #         agent_info = self.agent_manager.get_agent(stored_task.agent_url)
        #         async with httpx.AsyncClient() as http_client:
        #             client = A2AClient(
        #                 httpx_client=http_client, agent_card=agent_info.card
        #             )
        #             req = GetTaskRequest(
        #                 params=TaskQueryParams(taskId=stored_task.agent_task_id)
        #             )
        #             response = await client.get_task(req)
        #             stored_task = await self._process_agent_response(
        #                 response,  # This is not the right type
        #                 task_id,
        #                 stored_task.agent_url,
        #                 agent_info,
        #                 stored_task.request_message,
        #             )

        #     except Exception as e:
        #         logger.error(f"Error during polling for task {task_id}: {e}")
        #         # Don't change the status, just return what we have.
        # return stored_task.model_dump(mode="json")

    # async def send_message_stream(
    #     self, agent_url: str, message_text: str, session_id: Optional[str]
    # ) -> AsyncGenerator[Dict[str, Any], None]:
    #     # (이 메소드는 변경되지 않았습니다.)
    #     agent_info = self.agent_manager.get_agent(agent_url)
    #     if not agent_info:
    #         yield {"status": "error", "message": f"Agent not registered: {agent_url}"}
    #         return

    #     task_id = str(uuid.uuid4())
    #     stored_task = StoredTask(
    #         task_id=task_id,
    #         agent_url=agent_url,
    #         agent_name=agent_info.card.name,
    #         request_message=message_text,
    #         status="streaming",
    #     )
    #     self.tasks[task_id] = stored_task

    #     streamed_content = []
    #     final_task_status: Optional[TaskStatus] = None

    #     try:
    #         async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as http_client:
    #             client = A2AClient(httpx_client=http_client, agent_card=agent_info.card)
    #             params = MessageSendParams(
    #                 message=Message(
    #                     role="user",
    #                     parts=[Part(root=TextPart(text=message_text))],
    #                     messageId=str(uuid.uuid4()),
    #                 )
    #             )
    #             request = SendStreamingMessageRequest(id=task_id, params=params)

    #             async for event_wrapper in client.send_message_streaming(request):
    #                 event = event_wrapper.root
    #                 yield event.model_dump(mode="json")

    #                 if isinstance(event, TaskStatusUpdateEvent):
    #                     final_task_status = event.status
    #                     if (
    #                         event.status
    #                         and event.status.message
    #                         and event.status.message.parts
    #                     ):
    #                         for part in event.status.message.parts:
    #                             if isinstance(part.root, TextPart):
    #                                 streamed_content.append(part.root.text)

    #         if final_task_status:
    #             result_message = "".join(streamed_content)
    #             if final_task_status.message and final_task_status.message.parts:
    #                 result_message = " ".join(
    #                     p.root.text
    #                     for p in final_task_status.message.parts
    #                     if isinstance(p.root, TextPart)
    #                 )

    #             result_payload = {
    #                 "request_status": "success",
    #                 "state": final_task_status.state.value,
    #                 "message": result_message,
    #                 "artifacts": [],
    #             }
    #             stored_task.update_status("completed", result_payload)
    #         else:
    #             stored_task.update_status(
    #                 "completed",
    #                 {"request_status": "success", "message": "".join(streamed_content)},
    #             )

    #     except Exception as e:
    #         logger.error(f"Error streaming message to {agent_url}: {e}")
    #         stored_task.update_status("error", {"message": str(e)})
    #         yield {"status": "error", "message": str(e), "task_id": task_id}

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
