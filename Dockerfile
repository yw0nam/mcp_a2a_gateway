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
COPY mcp_a2a_gateway/ ./mcp_a2a_gateway/

# Expose the port the app runs on
EXPOSE 8000

# Run the application
CMD ["uv", "run", "mcp-a2a-gateway"]
