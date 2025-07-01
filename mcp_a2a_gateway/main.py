# mcp_a2a_gateway/main.py
import asyncio

from mcp_a2a_gateway import config
from mcp_a2a_gateway.server import mcp, load_all_data, periodic_save


async def main_async():
    """Main async function to start the MCP server."""
    load_all_data()
    asyncio.create_task(periodic_save())

    config.logger.info(f"Starting MCP server with {config.MCP_TRANSPORT} transport...")
    if config.MCP_TRANSPORT == "stdio":
        # For stdio transport, we use the run_stdio_async method
        await mcp.run_stdio_async()
    else:
        await mcp.run_async(
            transport=config.MCP_TRANSPORT,
            host=config.MCP_HOST,
            port=config.MCP_PORT,
            path=config.MCP_PATH,
        )


def main():
    """Main entry point."""
    config.logger.info("A2A-MCP Bridge Server (Modularized) is starting...")
    config.logger.info(
        f"Configuration: Transport={config.MCP_TRANSPORT}, Host={config.MCP_HOST}, Port={config.MCP_PORT}"
    )
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        config.logger.info("Server is shutting down.")


if __name__ == "__main__":
    main()
