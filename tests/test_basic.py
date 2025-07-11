"""Basic tests for MCP-A2A-Gateway"""

import pytest


def test_imports():
    """Test that all main modules can be imported."""
    try:
        import mcp_a2a_gateway
        from mcp_a2a_gateway.agent_manager import AgentManager
        from mcp_a2a_gateway.config import logger
        from mcp_a2a_gateway.data_manager import load_from_json, save_to_json
        from mcp_a2a_gateway.main import main, main_async
        from mcp_a2a_gateway.server import mcp
        from mcp_a2a_gateway.task_manager import TaskManager
    except ImportError as e:
        pytest.fail(f"Failed to import modules: {e}")


def test_agent_manager_creation():
    """Test that AgentManager can be created."""
    from mcp_a2a_gateway.agent_manager import AgentManager

    agent_manager = AgentManager()
    assert agent_manager is not None


def test_task_manager_creation():
    """Test that TaskManager can be created."""
    from mcp_a2a_gateway.agent_manager import AgentManager
    from mcp_a2a_gateway.task_manager import TaskManager

    agent_manager = AgentManager()
    task_manager = TaskManager(agent_manager)
    assert task_manager is not None


def test_config_values():
    """Test that config values are loaded properly."""
    from mcp_a2a_gateway import config

    # Test that basic config values exist and have reasonable defaults
    assert hasattr(config, "MCP_TRANSPORT")
    assert hasattr(config, "MCP_HOST")
    assert hasattr(config, "MCP_PORT")
    assert hasattr(config, "DATA_DIR")
    assert hasattr(config, "logger")

    # Test that MCP_PORT is an integer
    assert isinstance(config.MCP_PORT, int)


def test_data_manager_functions():
    """Test that data manager functions work with basic data."""
    import os
    import tempfile

    from mcp_a2a_gateway.data_manager import load_from_json, save_to_json

    # Test data
    test_data = {"test_key": "test_value", "number": 42}

    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_file = f.name

    try:
        # Test saving
        save_to_json(test_data, temp_file)
        assert os.path.exists(temp_file)

        # Test loading
        loaded_data = load_from_json(temp_file)
        assert loaded_data == test_data

    finally:
        # Clean up
        if os.path.exists(temp_file):
            os.unlink(temp_file)


def test_mcp_server_creation():
    """Test that MCP server can be created without starting."""
    from mcp_a2a_gateway.server import mcp

    # Just test that the server object exists and has expected attributes
    assert mcp is not None
    assert hasattr(mcp, "tool")  # FastMCP should have tool decorator
