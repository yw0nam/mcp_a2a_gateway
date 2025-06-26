# a2a_mcp_server/data_manager.py
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def save_to_json(data: Dict[str, Any], file_path: str):
    """Saves a dictionary to a JSON file."""
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except IOError as e:
        logger.error(f"Error saving data to {file_path}: {e}")


def load_from_json(file_path: str) -> Dict[str, Any]:
    """Loads a dictionary from a JSON file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"File not found: {file_path}. Returning empty dictionary.")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {file_path}: {e}")
        return {}
