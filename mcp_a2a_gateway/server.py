# mcp_a2a_gateway/server.py (수정됨)
import asyncio
import atexit
from typing import Any, Dict, List, Optional
from fastmcp import Context, FastMCP

from mcp_a2a_gateway import config
from mcp_a2a_gateway.data_manager import save_to_json, load_from_json
from mcp_a2a_gateway.agent_manager import AgentManager
from mcp_a2a_gateway.task_manager import TaskManager

# --- Initialization ---
mcp = FastMCP("A2A Bridge Server (Clarified)")
agent_manager = AgentManager()
task_manager = TaskManager(agent_manager)


# --- Data Persistence ---
def save_all_data():
    """Saves all application data to files."""
    config.logger.info("Saving data before exit...")
    save_to_json(
        agent_manager.get_agents_data_for_saving(), config.REGISTERED_AGENTS_FILE
    )
    # 수정된 TaskManager의 저장 함수를 사용합니다.
    save_to_json(task_manager.get_tasks_for_saving(), config.TASK_AGENT_MAPPING_FILE)
    config.logger.info("Data saved successfully.")


def load_all_data():
    """Loads all application data from files."""
    config.ensure_data_dir_exists()
    config.logger.info("Loading saved data...")
    agent_data = load_from_json(config.REGISTERED_AGENTS_FILE)
    if agent_data:
        agent_manager.load_agents_from_data(agent_data)

    task_data = load_from_json(config.TASK_AGENT_MAPPING_FILE)
    if task_data:
        # 수정된 TaskManager의 불러오기 함수를 사용합니다.
        task_manager.load_tasks_from_data(task_data)


atexit.register(save_all_data)


async def periodic_save():
    """Periodically saves data."""
    while True:
        await asyncio.sleep(300)  # 5분마다 저장
        save_all_data()


# --- MCP Tool Definitions ---
@mcp.tool()
async def register_agent(url: str, ctx: Context) -> Dict[str, Any]:
    """Register an A2A agent with the bridge server."""
    try:
        registered_url, agent_info = await agent_manager.register_agent(url)
        await ctx.info(
            f"Agent '{agent_info.card.name}' registered from {registered_url}"
        )
        response_agent = {
            "url": registered_url,
            "card": agent_info.card.model_dump(mode="json"),
        }
        return {"status": "success", "agent": response_agent}
    except Exception as e:
        await ctx.error(f"Failed to register agent: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool()
async def list_agents() -> List[Dict[str, Any]]:
    """List all registered A2A agents."""
    agent_list = []
    for url, agent_info in agent_manager.list_agents_with_url():
        agent_list.append({"url": url, "card": agent_info.card.model_dump(mode="json")})
    return agent_list


@mcp.tool()
async def unregister_agent(url: str, ctx: Context) -> Dict[str, Any]:
    """Unregister an A2A agent from the bridge server."""
    agent_info = agent_manager.unregister_agent(url)
    if not agent_info:
        return {"status": "error", "message": f"Agent not registered: {url}"}

    removed_count = task_manager.remove_tasks_for_agent(url)
    await ctx.info(
        f"Unregistered '{agent_info.card.name}', removed {removed_count} tasks."
    )
    return {
        "status": "success",
        "unregistered_agent": agent_info.card.name,
        "removed_tasks": removed_count,
    }


@mcp.tool()
async def send_message(
    agent_url: str, message: str, session_id: Optional[str] = None, ctx: Context = None
) -> Dict[str, Any]:
    """Send a message to an A2A agent."""
    if not agent_manager.get_agent(agent_url):
        return {"status": "error", "message": f"Agent not registered: {agent_url}"}
    try:
        if ctx:
            await ctx.info(f"Sending message to: {agent_url}")
        return await task_manager.send_message(agent_url, message, session_id)
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
async def get_task_result(
    task_id: str, history_length: Optional[int] = None, ctx: Context = None
) -> Dict[str, Any]:
    """Retrieve the result of a task from an A2A agent."""
    try:
        if ctx:
            await ctx.info(f"Retrieving result for task: {task_id}")
        return await task_manager.get_task_result(task_id, history_length)
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
async def cancel_task(task_id: str, ctx: Context) -> Dict[str, Any]:
    """Cancel a running task on an A2A agent."""
    try:
        if ctx:
            await ctx.info(f"Cancelling task: {task_id}")
        return await task_manager.cancel_task(task_id)
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
async def send_message_stream(
    agent_url: str, message: str, session_id: Optional[str] = None, ctx: Context = None
) -> Dict[str, Any]:
    """Send a message to an A2A agent and stream the response."""
    if not agent_manager.get_agent(agent_url):
        return {"status": "error", "message": f"Agent not registered: {agent_url}"}
    try:
        if ctx:
            await ctx.info(f"Streaming message to: {agent_url}")

        final_response = {}
        async for event in task_manager.send_message_stream(
            agent_url, message, session_id
        ):
            if ctx:
                await ctx.info(str(event))
            if event.get("kind") == "status-update":
                final_response = event

        return final_response or {"status": "success", "message": "Stream completed."}
    except Exception as e:
        return {"status": "error", "message": str(e)}
