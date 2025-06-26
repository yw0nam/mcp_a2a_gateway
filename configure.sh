# Transport type: stdio, streamable-http, or sse
export MCP_TRANSPORT="streamable-http"

# Host for the MCP server
export MCP_HOST="0.0.0.0"

# Port for the MCP server (when using HTTP transports)
export MCP_PORT="10000"

# Path for the MCP server endpoint (when using HTTP transports)
export MCP_PATH="/mcp"

# Path for SSE endpoint (when using SSE transport)
export MCP_SSE_PATH="/sse"

# Enable debug logging
export MCP_DEBUG="true"
