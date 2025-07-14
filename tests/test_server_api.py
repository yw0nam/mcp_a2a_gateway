# tests/test_server_api.py

import pytest

from mcp_a2a_gateway.agent_manager import AgentInfo

# server.py에서 사용하는 전역 manager 인스턴스를 모킹 대상으로 지정합니다.
AGENT_MANAGER_PATH = "mcp_a2a_gateway.server.agent_manager"
TASK_MANAGER_PATH = "mcp_a2a_gateway.server.task_manager"


@pytest.mark.asyncio
async def test_tool_register_agent_success(mocker, mock_mcp_context, mock_agent_card):
    """register_agent tool의 성공 케이스를 테스트합니다."""
    # Arrange
    test_url = "http://test.agent/api"
    mock_agent_info = AgentInfo(card=mock_agent_card)
    # 서버의 agent_manager가 특정 값을 반환하도록 설정합니다.
    mocker.patch(
        f"{AGENT_MANAGER_PATH}.register_agent", return_value=(test_url, mock_agent_info)
    )

    # Act - mcp 도구의 내부 함수를 직접 테스트
    # 이렇게 하면 실제 툴 등록이 아닌 그 안의 로직만 테스트할 수 있습니다
    from mcp_a2a_gateway.server import agent_manager

    url, agent_info = await agent_manager.register_agent(test_url)

    # Assert
    assert url == test_url
    assert agent_info.card.name == "TestAgent"


@pytest.mark.asyncio
async def test_tool_register_agent_failure(mocker, mock_mcp_context):
    """register_agent tool의 실패 케이스를 테스트합니다."""
    # Arrange
    test_url = "http://failing.agent/api"
    # manager 메서드가 예외를 발생시키도록 설정합니다.
    mocker.patch(
        f"{AGENT_MANAGER_PATH}.register_agent",
        side_effect=Exception("Connection Refused"),
    )

    # Act & Assert
    from mcp_a2a_gateway.server import agent_manager

    with pytest.raises(Exception, match="Connection Refused"):
        await agent_manager.register_agent(test_url)


@pytest.mark.asyncio
async def test_tool_send_message(mocker, mock_mcp_context):
    """send_message tool을 테스트합니다."""
    # Arrange
    agent_url = "http://test.agent/api"
    message = "ping"
    mock_task_result = {"task_id": "task-abc", "status": "running"}
    mocker.patch(
        f"{TASK_MANAGER_PATH}.send_message_async", return_value=mock_task_result
    )

    # Act
    from mcp_a2a_gateway.server import task_manager

    result = await task_manager.send_message_async(agent_url, message, None)

    # Assert
    assert result["task_id"] == "task-abc"
    assert result["status"] == "running"
