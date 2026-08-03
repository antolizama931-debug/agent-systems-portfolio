"""Manual live check for the mounted MCP Streamable HTTP endpoint."""

import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main() -> None:
    async with streamable_http_client("http://127.0.0.1:8010/mcp/") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            print([tool.name for tool in result.tools])


if __name__ == "__main__":
    asyncio.run(main())
