FROM python:3.12-slim

# Install uv
RUN pip install uv

# Set the working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock ./
COPY README.md ./

# Install dependencies
RUN uv pip install --system --no-cache .

# Copy the application code
COPY . .
# Transport type: stdio, streamable-http, or sse
ENV MCP_TRANSPORT="streamable-http"
# Host for the MCP server
ENV MCP_HOST="0.0.0.0"
# Port for the MCP server (when using HTTP transports)
ENV MCP_PORT="10000"
# Path for the MCP server endpoint (when using HTTP transports)
ENV MCP_PATH="/mcp"
# Path for SSE endpoint (when using SSE transport)
ENV MCP_SSE_PATH="/sse"
# Enable debug logging
ENV MCP_DEBUG="true"
# Request timeout in seconds
ENV MCP_REQUEST_TIMEOUT=30
ENV MCP_REQUEST_IMMEDIATE_TIMEOUT=2
ENV MCP_DATA_DIR="data"
# Expose the port the app runs on
EXPOSE 10000

# Run the application
CMD ["uv", "run", "mcp-a2a-gateway"]
