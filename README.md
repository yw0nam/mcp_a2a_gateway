# MCP-A2A-Gateway

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
![](https://badge.mcpx.dev?type=server 'MCP Server')

A gateway server that bridges the Model Context Protocol (MCP) with the Agent-to-Agent (A2A) protocol, enabling MCP-compatible AI assistants (like Claude) to seamlessly interact with A2A agents.

## Overview

This project serves as an integration layer between two cutting-edge AI agent protocols:

- **Model Context Protocol (MCP)**: Developed by Anthropic, MCP allows AI assistants to connect to external tools and data sources. It standardizes how AI applications and large language models connect to external resources in a secure, composable way.

- **Agent-to-Agent Protocol (A2A)**: Developed by Google, A2A enables communication and interoperability between different AI agents through a standardized JSON-RPC interface.

By bridging these protocols, this server allows MCP clients (like Claude) to discover, register, communicate with, and manage tasks on A2A agents through a unified interface.

### Demo

#### 1, Run The hello world Agent in A2A Sample

![agent](public/agent.png)

`also support cloud deployed Agent`

![cloudAgent](https://github.com/user-attachments/assets/481cbf01-95a0-4b0a-9ac5-898aef66a944)

#### 2, Use Claude or github copilot to register the agent.

![register_claude](public/register_claude.png)
![register_copilot](public/register_copilot.png)

#### 3, Use Claude to Send a task to the hello Agent and get the result.

![send_message](public/send_message.png)

#### 4, Use Claude to retrieve the task result.

![retrieve_result](public/retrieve_result.png)

## Features

- **Agent Management**
  - Register A2A agents with the bridge server
  - List all registered agents
  - Unregister agents when no longer needed

- **Communication**
  - Send messages to A2A agents and receive responses
  - Asynchronous message sending for immediate server response.
  - Stream responses from A2A agents in real-time

- **Task Management**
  - Track which A2A agent handles which task
  - Retrieve task results using task IDs
  - Get a list of all tasks and their statuses.
  - Cancel running tasks

- **Transport Support**
  - Multiple transport types: stdio, streamable-http, SSE
  - Configure transport type using MCP_TRANSPORT environment variable

## Prerequisites

Before you begin, ensure you have the following installed:

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (for local development)

## Installation

### Option 1: Local Installation

1. Clone the repository:

```bash
git clone https://github.com/yw0nam/MCP-A2A-Gateway.git
cd MCP-A2A-Gateway
```

2. Run using uv. (Note, you need uv for this.)

```bash
uv run mcp-a2a-gateway
```

## Configuration

### Environment Variables

Create a `.env` file in the root of the project and add the following environment variables:

```
MCP_TRANSPORT=streamable-http
```

### Transport Types

The A2A MCP Server supports multiple transport types:

1. **stdio** (default): Uses standard input/output for communication
   - Ideal for command-line usage and testing
   - No HTTP server is started
   - Required for Claude Desktop

2. **streamable-http** (recommended for web clients): HTTP transport with streaming support
   - Recommended for production deployments
   - Starts an HTTP server to handle MCP requests
   - Enables streaming of large responses

3. **sse**: Server-Sent Events transport
   - Provides real-time event streaming
   - Useful for real-time updates

## Available MCP Tools

The server exposes the following MCP tools for integration with LLMs like Claude:

### Agent Management

-   **register_agent**: Register an A2A agent with the bridge server

    ```json
    {
      "name": "register_agent",
      "arguments": {
        "url": "http://localhost:41242"
      }
    }
    ```

-   **list_agents**: Get a list of all registered agents

    ```json
    {
      "name": "list_agents",
      "arguments": {"dummy": "" }
    }
    ```

-   **unregister_agent**: Remove an A2A agent from the bridge server

    ```json
    {
      "name": "unregister_agent",
      "arguments": {
        "url": "http://localhost:41242"
      }
    }
    ```

### Message Processing

-   **send_message**: Send a message to an agent and get a task_id for the response

    ```json
    {
      "name": "send_message",
      "arguments": {
        "agent_url": "http://localhost:41242",
        "message": "What's the exchange rate from USD to EUR?",
        "session_id": "optional-session-id"
      }
    }
    ```

### Task Management

-   **get_task_result**: Retrieve a task's result using its ID

    ```json
    {
      "name": "get_task_result",
      "arguments": {
        "task_id": "b30f3297-e7ab-4dd9-8ff1-877bd7cfb6b1",
      }
    }
    ```

-   **get_task_list**: Get a list of all tasks and their statuses.

    ```json
    {
        "name": "get_task_list",
        "arguments": {}
    }
    ```

## Development

To set up a development environment, follow these steps:

1. Clone the repository:

```bash
git clone https://github.com/yw0nam/MCP-A2A-Gateway.git
cd MCP-A2A-Gateway
```

2. Run using:
```bash
uv run mcp-a2a-gateway
```

## Contributing

Contributions are welcome! Please open an issue or submit a pull request if you have any improvements or suggestions.

## TODO

### Installation & Distribution
- [ ] Add smithery install and npx support
- [ ] Add Docker Compose setup for easy deployment
- [ ] Create pre-built Docker images for different architectures

### Data Persistence & Storage
- [ ] Connect DB or Redis to store the task data
- [ ] Implement persistent agent registry (survive server restarts)
- [ ] Add task history and analytics
- [ ] Implement data backup and recovery mechanisms

### Authentication & Security
- [ ] Validate and sanitize A2A agent URLs during registration

### Monitoring & Observability
- [ ] Add comprehensive logging with structured format
- [ ] Implement health check endpoints
- [ ] Add metrics collection (Prometheus/OpenTelemetry)
- [ ] Create dashboard for monitoring agents and tasks

### Error Handling & Resilience
- [ ] Implement retry logic for failed A2A agent communications
- [ ] Add circuit breaker pattern for unreliable agents
- [ ] Better error messages and status codes
- [ ] Graceful degradation when agents are unavailable

### Features & Functionality
- [ ] Add support for streaming responses from agents
- [ ] Implement task scheduling and delayed execution

### Testing & Quality
- [ ] Add comprehensive integration tests
- [ ] Implement end-to-end testing with real A2A agents
- [ ] Add performance benchmarking
- [ ] Create test coverage reporting

### Documentation & Examples
- [ ] Add API documentation (OpenAPI/Swagger)
- [ ] Add troubleshooting guide

### Developer Experience
- [ ] Implement configuration validation

## License

This project is licensed under the Apache License, Version 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Anthropic for the [Model Context Protocol](https://modelcontextprotocol.io/)
- Google for the [Agent-to-Agent Protocol](https://github.com/google/A2A)
- Contributors to the FastMCP library
- Contributors of [A2A-MCP-Server](https://github.com/GongRzhe/A2A-MCP-Server) (This project highly inspired from this repo.)
