# Test Suite Documentation

This directory contains the comprehensive test suite for the MCP-A2A Gateway project. The tests validate the functionality of bridging Model Context Protocol (MCP) with Agent-to-Agent (A2A) protocol.

## 📋 Test Overview

The test suite includes **19 test cases** covering all major components:

- **Agent Management**: Agent registration, retrieval, and listing
- **Task Management**: Message sending, task tracking, and status filtering  
- **Server API**: MCP tool functionality and error handling
- **Basic Infrastructure**: Configuration, data persistence, and imports

## 🏗️ Test Structure

### Test Files

| File | Purpose | Test Count |
|------|---------|------------|
| `test_agent_manager.py` | Agent registration and management | 4 tests |
| `test_task_manager.py` | Task creation and message handling | 5 tests |
| `test_server_api.py` | MCP server tools and API endpoints | 3 tests |
| `test_basic.py` | Basic functionality and infrastructure | 5 tests |
| `conftest.py` | Shared fixtures and test configuration | - |
| `pytest.ini` | pytest configuration settings | - |

### Fixtures (conftest.py)

#### Core Fixtures
- **`agent_manager`**: Fresh AgentManager instance for each test
- **`task_manager`**: TaskManager instance with injected AgentManager
- **`mock_agent_card`**: Mock AgentCard with required A2A fields
- **`mock_mcp_context`**: Mock FastMCP Context for logging

#### Mock AgentCard Structure
```python
AgentCard(
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
```

## 🧪 Test Categories

### 1. Agent Manager Tests (`test_agent_manager.py`)

Tests the core agent registration and management functionality:

#### `test_register_agent_success`
- **Purpose**: Validates successful agent registration
- **Mocks**: A2ACardResolver.get_agent_card
- **Assertions**: 
  - Agent URL and info returned correctly
  - Agent stored in registered_agents dict
  - Mock called once with correct parameters

#### `test_register_agent_failure_on_fetch`
- **Purpose**: Tests error handling when agent card fetch fails
- **Mocks**: A2ACardResolver.get_agent_card (raises Exception)
- **Assertions**: Exception propagated, agent not registered

#### `test_get_agent_info`
- **Purpose**: Tests agent retrieval by URL
- **Setup**: Registers agent first
- **Assertions**: 
  - Existing agent returned correctly
  - Non-existent agent returns None

#### `test_list_agents_with_url`
- **Purpose**: Tests listing all registered agents
- **Setup**: Registers multiple agents
- **Assertions**: 
  - Correct count of agents
  - Agent data structure integrity

### 2. Task Manager Tests (`test_task_manager.py`)

Tests asynchronous message sending and task management:

#### `test_send_message_async_success`
- **Purpose**: Validates successful message sending to agent
- **Mocks**: 
  - A2ACardResolver.get_agent_card
  - A2AClient.send_message
- **Setup**: Creates mock Task and SendMessageSuccessResponse
- **Assertions**:
  - Task ID is valid UUID (36 characters)
  - Task stored in task manager
  - A2AClient.send_message called once

#### `test_send_message_async_agent_not_found`
- **Purpose**: Tests error when sending to unregistered agent
- **Assertions**: ValueError raised with "Agent not registered" message

#### `test_get_task_list_with_filter` (Parameterized)
- **Purpose**: Tests task filtering by status
- **Parameters**: 
  - `("all", 3)` - All tasks
  - `("working", 1)` - Only working tasks
  - `("completed", 1)` - Only completed tasks
  - `("failed", 1)` - Only failed tasks
  - `("canceled", 0)` - No canceled tasks
- **Setup**: Creates mock tasks with different statuses and timestamps
- **Assertions**: Correct count returned for each filter

### 3. Server API Tests (`test_server_api.py`)

Tests the MCP server tools and their integration:

#### `test_tool_register_agent_success`
- **Purpose**: Tests register_agent MCP tool
- **Mocks**: server.agent_manager.register_agent
- **Approach**: Tests underlying manager function directly
- **Assertions**: Agent registered successfully with correct data

#### `test_tool_register_agent_failure`
- **Purpose**: Tests error handling in register_agent tool
- **Mocks**: server.agent_manager.register_agent (raises Exception)
- **Assertions**: Exception propagated correctly

#### `test_tool_send_message`
- **Purpose**: Tests send_message MCP tool
- **Mocks**: server.task_manager.send_message_async
- **Assertions**: Task created with correct ID and status

### 4. Basic Infrastructure Tests (`test_basic.py`)

Tests fundamental components and configuration:

#### `test_agent_manager_creation`
- **Purpose**: Validates AgentManager can be instantiated
- **Assertions**: Instance created successfully

#### `test_task_manager_creation`
- **Purpose**: Validates TaskManager can be instantiated with dependencies
- **Assertions**: Instance created with AgentManager dependency

#### `test_config_values`
- **Purpose**: Tests configuration loading and validation
- **Assertions**:
  - Required config attributes exist
  - MCP_PORT is integer type
  - Logger is available

#### `test_data_manager_functions`
- **Purpose**: Tests JSON data persistence functions
- **Setup**: Creates temporary file
- **Assertions**: Data saved and loaded correctly

#### `test_mcp_server_creation`
- **Purpose**: Tests MCP server instantiation
- **Assertions**: Server has required FastMCP attributes

## 🛠️ Testing Technologies

### Dependencies
- **pytest**: Test framework
- **pytest-asyncio**: Async test support
- **pytest-mock**: Enhanced mocking capabilities
- **pytest-cov**: Coverage reporting (optional)
- **unittest.mock**: Python standard mocking

### Mocking Strategy
- **A2A SDK Components**: Mock A2AClient, A2ACardResolver
- **External Dependencies**: Mock HTTP clients, file operations
- **Internal Components**: Mock manager interactions for isolation

## 🚀 Running Tests

### Prerequisites
```bash
# Install test dependencies (if not already installed)
uv sync --extra test

# Or install individually
uv add pytest pytest-asyncio pytest-mock pytest-cov
```

### Run All Tests
```bash
uv run pytest tests/ -v
```

### Run Specific Test Files
```bash
# Agent manager tests only
uv run pytest tests/test_agent_manager.py -v

# Task manager tests only  
uv run pytest tests/test_task_manager.py -v

# Server API tests only
uv run pytest tests/test_server_api.py -v

# Basic infrastructure tests only
uv run pytest tests/test_basic.py -v
```

### Run Specific Test Cases
```bash
# Run single test
uv run pytest tests/test_agent_manager.py::test_register_agent_success -v

# Run parameterized test with specific parameter
uv run pytest tests/test_task_manager.py::test_get_task_list_with_filter[working-1] -v
```

### Generate Coverage Report
```bash
# Prerequisites: Ensure pytest-cov is installed
uv sync --extra test

# Generate coverage report (pytest-cov now included in dependencies)
uv run pytest tests/ --cov=mcp_a2a_gateway --cov-report=html

# Alternative: Simple coverage percentage
uv run pytest tests/ --cov=mcp_a2a_gateway

# Terminal report with missing lines
uv run pytest tests/ --cov=mcp_a2a_gateway --cov-report=term-missing

# View HTML report (opens in browser)
open htmlcov/index.html
```

**Note**: If you encounter "unrecognized arguments: --cov" error with pytest>=8.4.1, ensure `pytest-cov>=6.0.0` is installed via `uv sync --extra test`.

## 📊 Test Configuration

### pytest.ini Settings
```ini
[tool.pytest.ini_options]
testpaths = tests
python_files = test_*.py *_test.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short --strict-config --strict-markers
filterwarnings = 
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
```

### Key Configuration Options
- **Verbose output**: `-v` flag shows detailed test names
- **Short tracebacks**: `--tb=short` for concise error information
- **Strict mode**: Ensures clean test configuration
- **Warning filters**: Suppresses known deprecation warnings

## 🔍 Test Patterns and Best Practices

### AAA Pattern (Arrange-Act-Assert)
All tests follow the AAA pattern:
```python
def test_example():
    # Arrange - Set up test data and mocks
    test_data = "example"
    
    # Act - Execute the function under test
    result = function_under_test(test_data)
    
    # Assert - Verify the results
    assert result == expected_value
```

### Async Testing
```python
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result is not None
```

### Parameterized Testing
```python
@pytest.mark.parametrize("input,expected", [
    ("input1", "output1"),
    ("input2", "output2"),
])
def test_multiple_cases(input, expected):
    assert function(input) == expected
```

### Mock Validation
```python
# Verify mock was called
mock_function.assert_called_once()

# Verify mock was called with specific arguments
mock_function.assert_called_once_with(expected_arg)

# Verify mock was called specific number of times
mock_function.assert_called()
```

## 🐛 Common Testing Issues and Solutions

### Issue: Coverage Command Not Working
**Problem**: `pytest: error: unrecognized arguments: --cov=mcp_a2a_gateway --cov-report=html`
**Root Cause**: The `pytest-cov` plugin is not installed in the environment
**Solution**: 
1. **Recommended**: Install test dependencies: `uv sync --extra test` 
2. **Alternative**: Install individually: `uv add pytest-cov>=6.0.0`
3. **Verify Installation**: Check that `pytest-cov` appears in `uv list` output
4. **Test Installation**: Run `uv run pytest --version` and verify "cov-" appears in plugins list

**Note**: The `pytest-cov>=6.0.0` dependency is already defined in `pyproject.toml` under `[project.optional-dependencies].test`, but optional dependencies must be explicitly installed.

### Issue: Import Errors
**Problem**: Module not found errors
**Solution**: Ensure all dependencies installed via `uv add`

### Issue: Async Test Failures
**Problem**: Tests hanging or failing on async operations
**Solution**: Use `@pytest.mark.asyncio` decorator and proper async/await

### Issue: Mock Not Working
**Problem**: Mock not intercepting calls
**Solution**: Verify mock target path and import order

### Issue: Fixture Not Found
**Problem**: Test can't find fixture
**Solution**: Check `conftest.py` is in correct location and fixture is properly defined

## 📈 Test Metrics

### Current Status
- **Total Tests**: 19
- **Pass Rate**: 100% ✅
- **Overall Coverage**: 40%
- **Async Tests**: 8 tests
- **Parameterized Tests**: 1 test with 5 parameter sets

### Module Coverage Breakdown
- **agent_manager.py**: 73% (45 statements, 12 missed)
- **config.py**: 84% (19 statements, 3 missed)
- **data_manager.py**: 60% (20 statements, 8 missed)
- **server.py**: 30% (91 statements, 64 missed)
- **task_manager.py**: 37% (231 statements, 146 missed)
- **main.py**: 0% (19 statements, 19 missed - not tested)
- **__main__.py**: 0% (3 statements, 3 missed - not tested)

### Performance
- **Average Runtime**: ~0.35 seconds for full suite
- **Fastest Tests**: Basic infrastructure tests
- **Slowest Tests**: Async message sending tests

## 🔮 Future Test Enhancements

### Immediate Priorities (Based on Coverage Analysis)
1. **Server API Tests**: Increase coverage from 30% - test more MCP tools and error handling
2. **Task Manager Tests**: Increase coverage from 37% - test more task lifecycle scenarios
3. **Main Module Tests**: Add tests for CLI entry points (currently 0% coverage)
4. **Data Manager Tests**: Increase coverage from 60% - test edge cases and error handling

### Additional Test Types
1. **Integration Tests**: End-to-end workflow testing
2. **Performance Tests**: Load testing for concurrent operations  
3. **Error Recovery Tests**: Network failure scenarios
4. **Security Tests**: Authentication and authorization
5. **Compatibility Tests**: Multiple A2A SDK versions

### Test Maintenance
- Regular review of mock assumptions
- Update tests when A2A SDK changes
- Monitor for flaky tests in CI/CD
- Expand edge case coverage
- Target 80%+ overall coverage
