# tests/test_agent_manager.py

import pytest
from mcp_a2a_gateway.agent_manager import AgentInfo
from a2a.client import A2ACardResolver


@pytest.mark.asyncio
async def test_register_agent_success(agent_manager, mocker, mock_agent_card):
    """에이전트 등록 성공 케이스를 테스트합니다."""
    # Arrange (준비)
    test_url = "http://mock.agent/api"
    # A2ACardResolver의 get_agent_card 비동기 메서드를 모킹합니다.
    mocker.patch.object(A2ACardResolver, "get_agent_card", return_value=mock_agent_card)

    # Act (실행)
    url, agent_info = await agent_manager.register_agent(test_url)

    # Assert (검증)
    assert url == test_url
    assert isinstance(agent_info, AgentInfo)
    assert agent_info.card == mock_agent_card
    assert test_url in agent_manager.registered_agents
    assert agent_manager.registered_agents[test_url] == agent_info
    # 모킹된 메서드가 올바른 인자와 함께 한 번 호출되었는지 확인합니다.
    A2ACardResolver.get_agent_card.assert_called_once()


@pytest.mark.asyncio
async def test_register_agent_failure_on_fetch(agent_manager, mocker):
    """에이전트 정보 조회 실패 시 예외가 발생하는지 테스트합니다."""
    # Arrange
    test_url = "http://failing.agent/api"
    # get_agent_card 메서드가 호출되면 Exception을 발생시키도록 설정합니다.
    mocker.patch.object(
        A2ACardResolver, "get_agent_card", side_effect=Exception("Fetch failed")
    )

    # Act & Assert
    with pytest.raises(Exception, match="Fetch failed"):
        await agent_manager.register_agent(test_url)

    assert test_url not in agent_manager.registered_agents


@pytest.mark.asyncio
async def test_get_agent_info(agent_manager, mocker, mock_agent_card):
    """에이전트 정보 조회 및 실패 케이스를 테스트합니다."""
    # Arrange
    test_url = "http://existing.agent/api"
    mocker.patch.object(A2ACardResolver, "get_agent_card", return_value=mock_agent_card)
    await agent_manager.register_agent(test_url)

    # Act & Assert (Success)
    info = agent_manager.get_agent(test_url)
    assert info is not None
    assert info.card.name == "TestAgent"

    # Act & Assert (Failure)
    info_fail = agent_manager.get_agent("http://non.existing/api")
    assert info_fail is None


@pytest.mark.asyncio
async def test_list_agents_with_url(agent_manager, mocker, mock_agent_card):
    """등록된 에이전트 목록 조회를 테스트합니다."""
    # Arrange
    assert agent_manager.list_agents_with_url() == []  # 초기에 비어있는지 확인

    url1 = "http://agent1/api"
    url2 = "http://agent2/api"
    mocker.patch.object(A2ACardResolver, "get_agent_card", return_value=mock_agent_card)
    await agent_manager.register_agent(url1)
    await agent_manager.register_agent(url2)

    # Act
    agent_list = agent_manager.list_agents_with_url()

    # Assert
    assert len(agent_list) == 2
    assert agent_list[0][0] == url1
    assert agent_list[0][1].card == mock_agent_card
