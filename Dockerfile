FROM ghcr.io/astral-sh/uv:latest AS uv
FROM python:3.12-slim AS builder

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Development Dependancies
ENV UV_NO_DEV=1

# Disable Python Downloads so we can use the system interpretor across both images
ENV UV_PYTHON_DOWNLOADS=1

# SetUp Our Workspace Directory
WORKDIR /app

# Install uv binary
COPY --from=uv /uv /uv/bin/uv
ENV PATH="/uv/bin:$PATH"

# Setup our lock file and install dependancies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# Copy project files
COPY pyproject.toml uv.lock README.md ./
COPY mcp_a2a_gateway/ ./mcp_a2a_gateway/

# Now we install the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# We now setup our final light weight image
FROM python:3.12-slim

# Setup our working directory
WORKDIR /app

# Install curl for healthchecks and remove the install sources list afterwards
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy uv binary
COPY --from=uv /uv /uv/bin/uv
ENV PATH="/uv/bin:$PATH"

# Copy the virtual environment from the builder
COPY --from=builder /app/.venv /app/.venv
# Copy project files needed for uv run to recognize the project
COPY pyproject.toml README.md ./
COPY mcp_a2a_gateway/ ./mcp_a2a_gateway/

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV MCP_DATA_DIR=/app/data
ENV UV_CACHE_DIR=/app/.cache/uv

# Create a non-root user and directories
RUN groupadd -r mcpuser && useradd -r -g mcpuser -m mcpuser \
    && mkdir -p /app/data /app/.cache/uv \
    && chown -R mcpuser:mcpuser /app

USER mcpuser

# Expose the port the app runs on
EXPOSE 8888

# Run the application using uv run --no-sync and the script name defined in pyproject.toml
CMD ["uv", "run", "--no-sync", "mcp-a2a-gateway"]
