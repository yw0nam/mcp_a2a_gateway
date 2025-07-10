import asyncio
import uuid
from typing import Dict, Any, Optional, List, Literal
import logging
import httpx
import os
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from dotenv import load_dotenv
from a2a.client import A2AClient
from a2a.types import (
    Message,
    TextPart,
    Part,
    Task,
    SendMessageRequest,
    SendMessageResponse,
    SendMessageSuccessResponse,
    JSONRPCErrorResponse,
    MessageSendParams,
)
from mcp_a2a_gateway.agent_manager import AgentManager, AgentInfo

logger = logging.getLogger(__name__)
load_dotenv()

MCP_REQUEST_TIMEOUT = int(os.getenv("MCP_REQUEST_TIMEOUT", "30"))
MCP_REQUEST_IMMEDIATE_TIMEOUT = int(os.getenv("MCP_REQUEST_IMMEDIATE_TIMEOUT", "2"))


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
        에이전트에게 메시지를 보내고, 정해진 시간(IMMEDIATE_RESPONSE_TIMEOUT)을 기다립니다.
        - 시간 내에 응답이 오면, 최종 결과를 즉시 반환합니다.
        - 시간 내에 응답이 오지 않으면, 'pending' 상태를 반환하고 작업은 백그라운드에서 계속됩니다.
        """
        agent_info = self.agent_manager.get_agent(agent_url)
        if not agent_info:
            raise ValueError(f"Agent not registered: {agent_url}")

        gateway_task_id = str(uuid.uuid4())

        # 1. 'pending' 상태의 태스크를 미리 생성하고 저장합니다.
        #    타임아웃이 발생하면 이 객체의 정보가 반환됩니다.
        pending_task = StoredTask(
            task_id=gateway_task_id,
            agent_url=agent_url,
            agent_name=agent_info.card.name,
            request_message=message_text,
            status="pending",
            result={
                "message": f"The Request isn't end in {MCP_REQUEST_IMMEDIATE_TIMEOUT} second. Task is being processed in background..."
            },
        )
        self.tasks[gateway_task_id] = pending_task

        # 2. 실제 통신 및 상태 업데이트를 처리할 코루틴을 정의합니다.
        async def _send_and_update_task():
            try:
                # 이 함수는 항상 self.tasks에 있는 StoredTask를 업데이트합니다.
                timeout_config = httpx.Timeout(MCP_REQUEST_TIMEOUT, connect=5.0)
                async with httpx.AsyncClient(timeout=timeout_config) as http_client:
                    client = A2AClient(
                        httpx_client=http_client, agent_card=agent_info.card
                    )
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
                    response = await client.send_message(request)
                    # 상태 업데이트 후 최종 StoredTask 객체를 self.tasks에 저장
                    updated_task = await self._process_agent_response(
                        response,
                        gateway_task_id,
                        agent_url,
                        agent_info,
                        message_text,
                    )
                    self.tasks[gateway_task_id] = updated_task
            except Exception as e:
                logger.error(
                    f"Background task {gateway_task_id} failed: {e}", exc_info=True
                )
                # self.tasks에 있는 태스크를 직접 찾아 에러 상태로 업데이트합니다.
                if task := self.tasks.get(gateway_task_id):
                    task.update_status("error", {"message": str(e)})

        # 3. 백그라운드 작업을 생성합니다.
        background_task = asyncio.create_task(_send_and_update_task())

        try:
            # 4. 정해진 시간 동안만 백그라운드 작업이 끝나기를 기다립니다.
            # asyncio.shield()는 타임아웃 시에도 background_task가 취소되지 않도록 보호합니다.
            await asyncio.wait_for(
                asyncio.shield(background_task), timeout=MCP_REQUEST_IMMEDIATE_TIMEOUT
            )

            # 5. [성공] 시간 내에 작업이 완료된 경우
            logger.info(
                f"Task {gateway_task_id} completed within timeout. Returning final result."
            )
            # self.tasks에서 최종 업데이트된 태스크 정보를 가져와 반환합니다.
            return self.tasks[gateway_task_id].model_dump(mode="json")

        except asyncio.TimeoutError:
            # 6. [타임아웃] 시간이 초과된 경우
            logger.info(
                f"Task {gateway_task_id} timed out. Returning pending status while it runs in background."
            )
            # 작업은 백그라운드에서 계속 실행되며, 우리는 미리 만들어둔 'pending' 상태를 반환합니다.
            return pending_task.model_dump(mode="json")

    async def get_task_result(self, task_id: str) -> Dict[str, Any]:
        """게이트웨이 task_id를 사용하여 태스크 결과를 폴링합니다."""
        stored_task = self.get_task(task_id)
        if not stored_task:
            return {"status": "error", "message": f"Task ID not found: {task_id}"}

        return stored_task.model_dump(mode="json")

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
