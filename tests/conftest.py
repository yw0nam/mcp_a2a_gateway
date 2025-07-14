# tests/conftest.py

from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from a2a.types import AgentCard

from mcp_a2a_gateway.agent_manager import AgentManager
from mcp_a2a_gateway.task_manager import TaskManager


@pytest.fixture
def agent_manager():
    """매 테스트마다 새로운 AgentManager 인스턴스를 제공하는 fixture입니다."""
    return AgentManager()


@pytest.fixture
def task_manager(agent_manager):
    """
    AgentManager fixture를 주입받아 TaskManager 인스턴스를 생성합니다.
    이렇게 하면 TaskManager가 항상 최신 상태의 AgentManager를 참조하게 됩니다.
    """
    return TaskManager(agent_manager)


@pytest.fixture
def mock_agent_card():
    """테스트에서 반복적으로 사용될 모의 AgentCard 객체를 생성합니다."""
    return AgentCard(
        name="TestAgent",
        version="1.0",
        description="A mock agent for testing purposes.",
        url="http://test.agent/api",
        capabilities={
            "textGeneration": True,
            "imageGeneration": False,
            "fileProcessing": False,
            "webSearch": False,
            "codeExecution": False,
        },
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        skills=[],
    )


@pytest_asyncio.fixture
async def mock_mcp_context():
    """FastMCP의 Context 객체를 모의(Mock)합니다. info, error 등의 메서드를 가집니다."""
    # MagicMock을 사용하면 어떤 메서드 호출이든 에러 없이 수신합니다.
    # 비동기 메서드를 모킹하기 위해 AsyncMock을 사용할 수도 있습니다.
    mock = MagicMock()

    async def info(msg):
        print(f"[MOCK INFO] {msg}")

    async def error(msg):
        print(f"[MOCK ERROR] {msg}")

    mock.info = info
    mock.error = error
    return mock
