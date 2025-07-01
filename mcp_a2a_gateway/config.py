# a2a_mcp_server/config.py
import os
import logging
from dotenv import load_dotenv

load_dotenv()
# --- General Configuration ---
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
DATA_DIR = os.environ.get("MCP_DATA_DIR", "data")

# --- FastMCP Server Configuration ---
MCP_TRANSPORT = os.environ.get("MCP_TRANSPORT", "stdio").lower()
MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("MCP_PORT", 8000))
MCP_PATH = os.environ.get("MCP_PATH", "/mcp")
# --- File Paths for Persistence ---
REGISTERED_AGENTS_FILE = os.path.join(DATA_DIR, "registered_agents.json")
TASK_AGENT_MAPPING_FILE = os.path.join(DATA_DIR, "task_agent_mapping.json")

# --- Logging Setup ---
logging.basicConfig(
    level=LOG_LEVEL, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- Environment Variable for FastMCP ---
os.environ.setdefault("FASTMCP_LOG_LEVEL", LOG_LEVEL)


def ensure_data_dir_exists():
    """Ensures the data directory exists."""
    if not os.path.exists(DATA_DIR):
        logger.info(f"Creating data directory at: {DATA_DIR}")
        os.makedirs(DATA_DIR)
