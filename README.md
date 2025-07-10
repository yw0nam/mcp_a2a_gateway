# MCP-A2A-Gateway

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
![](https://badge.mcpx.dev?type=server 'MCP Server')

A gateway server that bridges the Model Context Protocol (MCP) with the Agent-to-Agent (A2A) protocol, enabling MCP-compatible AI assistants (like Claude) to seamlessly interact with A2A agents.

## Overview

This project serves as an integration layer between two cutting-edge AI agent protocols:

- **Model Context Protocol (MCP)**: Developed by Anthropic, MCP allows AI assistants to connect to external tools and data sources. It standardizes how AI applications and large language models connect to external resources in a secure, composable way.

- **Agent-to-Agent Protocol (A2A)**: Developed by Google, A2A enables communication and interoperability between different AI agents through a standardized JSON-RPC interface.

By bridging these protocols, this server allows MCP clients (like Claude) to discover, register, communicate with, and manage tasks on A2A agents through a unified interface.

## Quick Start

🎉 **The package is now available on PyPI!**

### No Installation Required
```bash
# Run with default settings (stdio transport)
uvx mcp-a2a-gateway

# Run with HTTP transport for web clients
MCP_TRANSPORT=streamable-http MCP_PORT=10000 uvx mcp-a2a-gateway

# Run with custom data directory
MCP_DATA_DIR="/Users/your-username/Desktop/a2a_data" uvx mcp-a2a-gateway

# Run with specific version
uvx mcp-a2a-gateway==0.1.6

# Run with multiple environment variables
MCP_TRANSPORT=stdio MCP_DATA_DIR="/custom/path" LOG_LEVEL=DEBUG uvx mcp-a2a-gateway
```

### For Development (Local)
```bash
# Clone and run locally
git clone https://github.com/yw0nam/MCP-A2A-Gateway.git
cd MCP-A2A-Gateway

# Run with uv
uv run mcp-a2a-gateway

# Run with uvx from local directory
uvx --from . mcp-a2a-gateway

# Run with custom environment for development
MCP_TRANSPORT=streamable-http MCP_PORT=8080 uvx --from . mcp-a2a-gateway
```

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

### Option 1: Direct Run with uvx (Recommended)

Run directly without installation using `uvx`:

```bash
uvx mcp-a2a-gateway
```

This will automatically download and run the latest version from PyPI.

### Option 2: Local Development

1. Clone the repository:

```bash
git clone https://github.com/yw0nam/MCP-A2A-Gateway.git
cd MCP-A2A-Gateway
```

2. Run using uv:

```bash
uv run mcp-a2a-gateway
```

3. Or use uvx with local path:

```bash
uvx --from . mcp-a2a-gateway
```

### Option 3: HTTP (For Web Clients)

**Start the server with HTTP transport:**
```bash
# Using uvx
MCP_TRANSPORT=streamable-http MCP_HOST=0.0.0.0 MCP_PORT=10000 uvx mcp-a2a-gateway
```
### Option 4:  (Server-Sent Events)

**Start the server with SSE transport:**
```bash
# Using uvx
MCP_TRANSPORT=sse MCP_HOST=0.0.0.0 MCP_PORT=10000 uvx mcp-a2a-gateway
```

## Configuration

### Environment Variables

The server can be configured using the following environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_TRANSPORT` | `stdio` | Transport type: `stdio`, `streamable-http`, or `sse` |
| `MCP_HOST` | `0.0.0.0` | Host for HTTP/SSE transports |
| `MCP_PORT` | `8000` | Port for HTTP/SSE transports |
| `MCP_PATH` | `/mcp` | HTTP endpoint path |
| `MCP_DATA_DIR` | `data` | Directory for persistent data storage |
| `MCP_REQUEST_TIMEOUT` | `30` | Request timeout in seconds |
| `MCP_REQUEST_IMMEDIATE_TIMEOUT` | `2` | Immediate response timeout in seconds |
| `LOG_LEVEL` | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

**Example .env file:**
```bash
# Transport configuration
MCP_TRANSPORT=stdio
MCP_HOST=0.0.0.0
MCP_PORT=10000
MCP_PATH=/mcp

# Data storage
MCP_DATA_DIR=/Users/your-username/Desktop/data/a2a_gateway

# Timeouts
MCP_REQUEST_TIMEOUT=30
MCP_REQUEST_IMMEDIATE_TIMEOUT=2

# Logging
LOG_LEVEL=INFO
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



## TO connect github copilot

### For HTTP/SSE Transport
Add below to VS Code settings.json for sse or http:
```json
"mcpServers": {
  "mcp_a2a_gateway": {
    "url": "http://0.0.0.0:10000/mcp"
  }
}
```

### For STDIO Transport

**Using uvx (Published Package):**
```json
"mcpServers": {
  "mcp_a2a_gateway": {
    "type": "stdio",
    "command": "uvx",
    "args": ["mcp-a2a-gateway"],
    "env": {
      "MCP_TRANSPORT": "stdio",
      "MCP_DATA_DIR": "/Users/your-username/Desktop/data/Copilot/a2a_gateway/"
    }
  }
}
```

**Using uvx (Local Development):**
```json
"mcpServers": {
  "mcp_a2a_gateway": {
    "type": "stdio",
    "command": "uvx",
    "args": ["--from", "/path/to/MCP-A2A-Gateway", "mcp-a2a-gateway"],
    "env": {
      "MCP_TRANSPORT": "stdio",
      "MCP_DATA_DIR": "/Users/your-username/Desktop/data/Copilot/a2a_gateway/"
    }
  }
}
```

**Using uv (Local Development):**
```json
"mcpServers": {
  "mcp_a2a_gateway": {
    "type": "stdio",
    "command": "uv",
    "args": [
      "--directory",
      "/path/to/MCP-A2A-Gateway",
      "run",
      "mcp-a2a-gateway"
    ],
    "env": {
      "MCP_TRANSPORT": "stdio",
      "MCP_DATA_DIR": "/Users/your-username/Desktop/data/Copilot/a2a_gateway/"
    }
  }
}
```

## To Connect claude desktop

### Transport: STDIO (Recommended)

**Using uvx (Published Package):**
Add this to claude_config.json

```json
"mcpServers": {
  "mcp_a2a_gateway": {
    "command": "uvx",
    "args": ["mcp-a2a-gateway"],
    "env": {
      "MCP_TRANSPORT": "stdio",
      "MCP_DATA_DIR": "/Users/your-username/Desktop/data/Claude/a2a_gateway/"
    }
  }
}
```

**Using uvx (Local Development):**
Add this to claude_config.json

```json
"mcpServers": {
  "mcp_a2a_gateway": {
    "command": "uvx",
    "args": ["--from", "/path/to/MCP-A2A-Gateway", "mcp-a2a-gateway"],
    "env": {
      "MCP_TRANSPORT": "stdio",
      "MCP_DATA_DIR": "/Users/your-username/Desktop/data/Claude/a2a_gateway/"
    }
  }
}
```

**Using uv (Local Development):**
Add this to claude_config.json

```json
"mcpServers": {
  "mcp_a2a_gateway": {
    "command": "uv",
    "args": ["--directory", "/path/to/MCP-A2A-Gateway", "run", "mcp-a2a-gateway"],
    "env": {
      "MCP_TRANSPORT": "stdio",
      "MCP_DATA_DIR": "/Users/your-username/Desktop/data/Claude/a2a_gateway/"
    }
  }
}
```


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


## Roadmap & How to Contribute

We are actively developing and improving the gateway! We welcome contributions of all kinds. Here is our current development roadmap, focusing on creating a rock-solid foundation first.

### Core Stability & Developer Experience (Help Wanted! 👍)

This is our current focus. Our goal is to make the gateway as stable and easy to use as possible.

-   [ ] **Implement Streaming Responses**: Full support for streaming responses from A2A agents.
-   [ ] **Enhance Error Handling**: Provide clearer error messages and proper HTTP status codes for all scenarios.
-   [ ] **Input Validation**: Sanitize and validate agent URLs during registration for better security.
-   [ ] **Add Health Check Endpoint**: A simple `/health` endpoint to monitor the server's status.
-   [ ] **Configuration Validation**: Check for necessary environment variables at startup.
-   [ ] **Comprehensive Integration Tests**: Increase test coverage to ensure reliability.
-   [ ] **Cancel Task**: Implement task cancellation
-   [ ] **Implement Streaming Update**: Implement streaming task update. So that user check the progress.


### Community & Distribution

-   [x] **Easy Installation**: Add support for `uvx`
-   [ ] **Docker Support**: Provide a Docker Compose setup for easy deployment.
-   [ ] **Better Documentation**: Create a dedicated documentation site or expand the Wiki.

---
**Want to contribute?** Check out the issues tab or feel free to open a new one to discuss your ideas!

## License

This project is licensed under the Apache License, Version 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Anthropic for the [Model Context Protocol](https://modelcontextprotocol.io/)
- Google for the [Agent-to-Agent Protocol](https://github.com/google/A2A)
- Contributors to the FastMCP library
- Contributors of [A2A-MCP-Server](https://github.com/GongRzhe/A2A-MCP-Server) (This project highly inspired from this repo.)