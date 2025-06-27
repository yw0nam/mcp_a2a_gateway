import asyncio
import atexit
from typing import Any, Dict, List, Optional, Literal
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
    """
    Registers an Agent-to-Agent (A2A) agent with the bridge server.

    This tool fetches the agent's information (AgentCard) from the given URL
    and stores it in the server's list of registered agents, making it available
    for communication.

    Args:
        url (str): The base URL of the A2A agent to register.
                   This URL should point to where the agent's card can be resolved.
        ctx (Context): The MCP context, used for logging information back to the client.

    Returns:
        Dict[str, Any]: A dictionary containing the registration status.
                        On success, it includes the status and the registered agent's details.
                        On error, it includes the status and an error message.
    """
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
async def list_agents(dummy: str = "") -> List[Dict[str, Any]]:
    """
    Lists all A2A agents currently registered with the bridge server.

    This resource returns a list of all agents, including their URL and
    AgentCard information.

    Args:
        dummy (str): A dummy parameter to satisfy the MCP tool signature. Just for compatibility. Just pass the empty string.
    Returns:
        List[Dict[str, Any]]: A list of dictionaries, each containing the URL and
                              AgentCard information of a registered agent.
                              Each dictionary has the keys "url" and "card".
    """
    agent_list = []
    for url, agent_info in agent_manager.list_agents_with_url():
        agent_list.append({"url": url, "card": agent_info.card.model_dump(mode="json")})
    if not agent_list:
        agent_list.append({"url": "", "card": {}})
    return agent_list


@mcp.tool()
async def unregister_agent(url: str, ctx: Context) -> Dict[str, Any]:
    """
    Unregisters an A2A agent from the bridge server.

    This also removes any tasks associated with the unregistered agent.

    Args:
        url (str): The URL of the agent to unregister.
        ctx (Context): The MCP context for logging.

    Returns:
        Dict[str, Any]: A dictionary confirming the action, including the
                        name of the unregistered agent and the number of
                        tasks that were removed. Returns an error if the
                        agent was not found.
    """
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
    """
    Sends a message to a registered A2A agent and creates a task.

    This function initiates a conversation or sends a command to an agent.
    It returns a task ID that can be used later to retrieve the result.

    Args:
        agent_url (str): The URL of the registered A2A agent to send the message to.
        message (str): The text content of the message to send.
        session_id (Optional[str]): An optional identifier to group related messages
                                     into a single conversation context.
        ctx (Context): The MCP context for logging.

    Returns:
        Dict[str, Any]: A dictionary containing the result of the message sending
                        operation, including a `task_id` for future reference.
    """
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
    """
    Retrieves the result or status of a previously created task.

    Using the task_id returned by `send_message`, this tool fetches the
    current state and any results from the corresponding A2A agent.

    Args:
        task_id (str): The unique identifier of the task to retrieve.
        history_length (Optional[int]): If provided, retrieves the last N
                                         messages in the task's history.
        ctx (Context): The MCP context for logging.

    Returns:
        Dict[str, Any]: A dictionary containing the task's current status,
                        result message, and any associated data or an error
                        if the task ID is not found.
    """
    try:
        if ctx:
            await ctx.info(f"Retrieving result for task: {task_id}")
        return await task_manager.get_task_result(task_id, history_length)
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
async def cancel_task(task_id: str, ctx: Context) -> Dict[str, Any]:
    """
    Cancels a running task on an A2A agent.

    Args:
        task_id (str): The identifier of the task to be cancelled.
        ctx (Context): The MCP context for logging.

    Returns:
        Dict[str, Any]: A dictionary containing the final status of the
                        cancelled task.
    """
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
    """
    Sends a message to an agent and streams the response back in real-time.

    This is useful for long-running tasks or conversations where intermediate
    updates are desired.

    Args:
        agent_url (str): The URL of the agent to send the message to.
        message (str): The text content of the message.
        session_id (Optional[str]): An optional session identifier.
        ctx (Context): The MCP context, which will receive the streaming events.

    Returns:
        Dict[str, Any]: A dictionary representing the final event of the stream,
                        or a success message if the stream completes without a
                        specific final event.
    """
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


@mcp.tool()
async def get_task_list(
    status: Literal[
        "all", "completed", "running", "error", "pending", "streaming", "cancelled"
    ] = "all",
    sort: Literal["Descending", "Ascending"] = "Descending",
    number: int = 10,
    ctx: Context = None,
) -> List[Dict[str, Any]]:
    """
    Retrieves a list of tasks being managed by the server.

    Args:
        status (Literal["all", "completed", "running", "error", "pending", "streaming", "cancelled"]):
            Filters tasks by their status. Defaults to "all".
        sort (Literal["Descending", "Ascending"]):
            Sorts tasks by their last update time. Defaults to "Descending".
        number (int): The maximum number of tasks to return. Defaults to 10.
        ctx (Context): The MCP context for logging.

    Returns:
        List[Dict[str, Any]]: A list of tasks, each represented as a dictionary.
    """
    try:
        if ctx:
            await ctx.info(
                f"Retrieving task list with status='{status}', sort='{sort}', number={number}"
            )

        tasks = task_manager.get_task_list(status=status, sort=sort, number=number)
        task_list = [task.model_dump(mode="json") for task in tasks]

        return task_list
    except Exception as e:
        if ctx:
            await ctx.error(f"Failed to get task list: {e}")
        # To maintain consistency, return a dictionary with error info
        # The tool is expected to return a list, but in case of a top-level
        # exception, a descriptive error object is more informative.
        # However, to avoid schema mismatches on the client, we wrap it
        # in a way that can be handled. Returning a list with a single error object.
        return [{"status": "error", "message": str(e)}]
