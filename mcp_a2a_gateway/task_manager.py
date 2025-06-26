# a2a_mcp_server/task_manager.py (최종 수정 버전)
import uuid
from typing import Dict, Any, Optional, AsyncGenerator
import logging
import httpx

from a2a.client import A2AClient
from a2a.types import (
    Message,
    TextPart,
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
    if task.status.message and task.status.message.parts:
        response["message"] = " ".join(
            part.text
            for part in task.status.message.parts
            if isinstance(part, TextPart)
        )
    if task.artifacts:
        response["artifacts"] = [a.model_dump(mode="json") for a in task.artifacts]
    return response


class TaskManager:
    def __init__(self, agent_manager: AgentManager):
        self.task_agent_mapping: Dict[str, str] = {}
        self.agent_manager = agent_manager

    def get_agent_url_for_task(self, task_id: str) -> Optional[str]:
        return self.task_agent_mapping.get(task_id)

    def remove_tasks_for_agent(self, url: str) -> int:
        tasks_to_remove = [
            task_id
            for task_id, agent_url in self.task_agent_mapping.items()
            if agent_url == url
        ]
        for task_id in tasks_to_remove:
            del self.task_agent_mapping[task_id]
        logger.info(f"Removed {len(tasks_to_remove)} tasks for agent {url}.")
        return len(tasks_to_remove)

    # --- 올바른 A2A 통신 로직 (응답 객체 처리 포함) ---

    async def send_message(
        self, agent_url: str, message_text: str, session_id: Optional[str]
    ) -> Dict[str, Any]:
        agent_info = self.agent_manager.get_agent(agent_url)
        if not agent_info:
            raise ValueError(f"Agent not registered: {agent_url}")

        task_id = str(uuid.uuid4())
        self.task_agent_mapping[task_id] = agent_url

        try:
            async with httpx.AsyncClient() as http_client:
                client = A2AClient(httpx_client=http_client, agent_card=agent_info.card)

                params = MessageSendParams(
                    message=Message(
                        role="user",
                        parts=[TextPart(text=message_text)],
                        messageId=str(uuid.uuid4()),
                    )
                )
                request = SendMessageRequest(id=task_id, params=params)

                response: SendMessageResponse = await client.send_message(request)

                # --- 응답 객체 처리 로직 추가 ---
                if isinstance(response.root, SendMessageSuccessResponse):
                    result = response.root.result
                    if isinstance(result, Task):
                        return format_task_response(result)
                    elif isinstance(result, Message):
                        return {
                            "status": "success",
                            "message": " ".join(
                                p.text for p in result.parts if isinstance(p, TextPart)
                            ),
                        }
                elif isinstance(response.root, JSONRPCErrorResponse):
                    error = response.root.error
                    return {
                        "status": "error",
                        "message": f"Agent Error: {error.message} (Code: {error.code})",
                    }

                raise TypeError(f"Unexpected response type: {type(response.root)}")

        except Exception as e:
            logger.error(f"Error sending message to {agent_url}: {e}")
            raise

    async def get_task_result(
        self, task_id: str, history_length: Optional[int]
    ) -> Dict[str, Any]:
        agent_url = self.get_agent_url_for_task(task_id)
        if not agent_url:
            raise ValueError(f"Task ID not found: {task_id}")
        agent_info = self.agent_manager.get_agent(agent_url)
        if not agent_info:
            raise ValueError(f"Agent for task {task_id} not found.")

        try:
            async with httpx.AsyncClient() as http_client:
                client = A2AClient(httpx_client=http_client, agent_card=agent_info.card)

                params = TaskQueryParams(id=task_id, historyLength=history_length)
                request = GetTaskRequest(id=task_id, params=params, method="tasks/get")

                response: GetTaskResponse = await client.get_task(request)

                if isinstance(response.root, GetTaskSuccessResponse):
                    return format_task_response(response.root.result)
                elif isinstance(response.root, JSONRPCErrorResponse):
                    error = response.root.error
                    return {
                        "status": "error",
                        "message": f"Agent Error: {error.message} (Code: {error.code})",
                    }

                raise TypeError(f"Unexpected response type: {type(response.root)}")
        except Exception as e:
            logger.error(f"Error retrieving task {task_id}: {e}")
            raise

    async def cancel_task(self, task_id: str) -> Dict[str, Any]:
        agent_url = self.get_agent_url_for_task(task_id)
        if not agent_url:
            raise ValueError(f"Task ID not found: {task_id}")
        agent_info = self.agent_manager.get_agent(agent_url)
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
                    return format_task_response(response.root.result)
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
        agent_info = self.agent_manager.get_agent(agent_url)
        if not agent_info:
            yield {"status": "error", "message": f"Agent not registered: {agent_url}"}
            return

        task_id = str(uuid.uuid4())
        self.task_agent_mapping[task_id] = agent_url

        # 스트리밍에서는 httpx.AsyncClient를 with 블록 밖에서 선언할 필요가 없습니다.
        # A2AClient가 내부적으로 스트리밍 연결을 관리합니다.
        try:
            # 스트리밍에서는 httpx.AsyncClient를 직접 관리하지 않아도 됩니다.
            # A2AClient가 내부적으로 처리합니다.
            async with httpx.AsyncClient() as http_client:
                client = A2AClient(httpx_client=http_client, agent_card=agent_info.card)

                params = MessageSendParams(
                    message=Message(
                        role="user",
                        parts=[TextPart(text=message_text)],
                        messageId=str(uuid.uuid4()),
                    )
                )
                request = SendStreamingMessageRequest(id=task_id, params=params)

                async for event in client.send_message_streaming(request):
                    yield event.model_dump(mode="json")
        except Exception as e:
            logger.error(f"Error streaming message to {agent_url}: {e}")
            yield {"status": "error", "message": str(e), "task_id": task_id}

    def load_tasks_from_data(self, data: Dict[str, str]):
        self.task_agent_mapping = data
        logger.info(f"Loaded {len(self.task_agent_mapping)} task mappings.")
