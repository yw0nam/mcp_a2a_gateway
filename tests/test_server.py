import asyncio
import httpx
import pytest
import uvicorn
from unittest.mock import patch, AsyncMock, MagicMock

# --- Test Setup ---

# 실제 uvicorn 서버를 테스트 중에 실행하기 위한 설정
# 프로젝트의 main.py에서 app 객체를 가져옵니다.
from mcp_a2a_gateway.server import mcp as app


class TestServer(uvicorn.Server):
    """Uvicorn 서버를 백그라운드에서 실행하기 위한 커스텀 클래스"""

    def install_signal_handlers(self):
        pass

    async def run(self, sockets=None):
        self.config.setup_event_loop()
        await self.serve(sockets=sockets)


@pytest.fixture
async def test_server():
    """Pytest Fixture: 테스트용 서버를 실행하고 테스트가 끝나면 종료합니다."""
    # 테스트를 위해 http 전송 방식, 임의의 포트를 사용하도록 설정
    config = uvicorn.Config(app, host="127.0.0.1", port=51234, log_level="info")
    server = TestServer(config)

    # 서버를 백그라운드 스레드에서 실행
    server_task = asyncio.create_task(server.run())

    # 서버가 시작될 시간을 잠시 기다림
    await asyncio.sleep(1)

    yield "http://127.0.0.1:51234"  # 테스트 함수에 서버 주소를 전달

    # 테스트 종료 후 서버를 정지
    await server.shutdown()
    server_task.cancel()


# --- Mocking Setup ---


# a2a.types.AgentCard가 실제로는 없으므로 가짜 클래스를 만들어줍니다.
class FakeAgentCard:
    def __init__(self, name="TestAgent"):
        self.name = name

    def model_dump(self, mode="json"):
        return {"name": self.name}


mock_agent_info = MagicMock()
mock_agent_info.card = FakeAgentCard()


# --- Integration Tests ---


@pytest.mark.asyncio
# @patch를 사용하여 실제 네트워크 호출을 하는 부분을 모킹(Mocking)합니다.
@patch("mcp_a2a_gateway.server.agent_manager", new_callable=MagicMock)
async def test_list_agents_integration(mock_agent_manager, test_server):
    """list_agents 도구를 통합 테스트합니다."""
    # 모킹된 agent_manager가 반환할 값을 설정합니다.
    mock_agent_manager.list_agents_with_url.return_value = [
        ("http://test.agent", mock_agent_info)
    ]

    async with httpx.AsyncClient() as client:
        # FastMCP는 JSON-RPC 2.0 형식을 따릅니다.
        response = await client.post(
            f"{test_server}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "list_agents",
                "params": {},
                "id": 1,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert "error" not in data
    result = data["result"]
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["url"] == "http://test.agent"
    assert result[0]["card"]["name"] == "TestAgent"


@pytest.mark.asyncio
@patch("mcp_a2a_gateway.server.agent_manager", new_callable=MagicMock)
async def test_register_agent_integration(mock_agent_manager, test_server):
    """register_agent 도구를 통합 테스트합니다."""
    mock_agent_manager.register_agent = AsyncMock(
        return_value=("http://new.agent", mock_agent_info)
    )

    agent_url_to_register = "http://new.agent"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{test_server}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "register_agent",
                "params": {"url": agent_url_to_register},
                "id": 2,
            },
        )

    # agent_manager의 register_agent 함수가 올바른 인자와 함께 호출되었는지 확인
    mock_agent_manager.register_agent.assert_called_once_with(agent_url_to_register)

    assert response.status_code == 200
    data = response.json()
    assert data["result"]["status"] == "success"
    assert data["result"]["agent"]["url"] == agent_url_to_register


@pytest.mark.asyncio
@patch("mcp_a2a_gateway.server.task_manager", new_callable=MagicMock)
@patch("mcp_a2a_gateway.server.agent_manager", new_callable=MagicMock)
async def test_send_message_integration(
    mock_agent_manager, mock_task_manager, test_server
):
    """send_message 도구를 통합 테스트합니다."""
    # send_message를 호출하기 전에 에이전트가 등록되어 있어야 합니다.
    mock_agent_manager.get_agent.return_value = mock_agent_info
    mock_task_manager.send_message = AsyncMock(
        return_value={"task_id": "task-123", "status": "success"}
    )

    agent_url = "http://test.agent"
    message = "Hello, agent!"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{test_server}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "send_message",
                "params": {"agent_url": agent_url, "message": message},
                "id": 3,
            },
        )

    mock_agent_manager.get_agent.assert_called_once_with(agent_url)
    mock_task_manager.send_message.assert_called_once_with(agent_url, message, None)

    assert response.status_code == 200
    data = response.json()
    assert data["result"]["task_id"] == "task-123"
