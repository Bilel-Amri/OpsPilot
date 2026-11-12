import json
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


MCP_SERVER_URL = os.getenv(
    "MCP_SERVER_URL",
    "http://127.0.0.1:18001/mcp"
)


async def call_mcp_tool(tool_name: str, arguments: dict | None = None):
    """Appelle un outil du serveur MCP Kubernetes."""

    try:
        async with streamablehttp_client(MCP_SERVER_URL) as (
            read,
            write,
            _
        ):
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.call_tool(
                    tool_name,
                    arguments or {}
                )

                if result.isError:
                    raise RuntimeError(
                        f"Erreur MCP lors de l'appel à {tool_name}"
                    )

                output = []

                for item in result.content:
                    if hasattr(item, "text"):
                        try:
                            output.append(json.loads(item.text))
                        except json.JSONDecodeError:
                            output.append(item.text)

                return output

    except Exception as exc:
        raise RuntimeError(
            f"Impossible de communiquer avec MCP : {exc}"
        ) from exc
