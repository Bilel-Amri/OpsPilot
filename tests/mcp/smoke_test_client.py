
"""Manual MCP integration test for all four OpsPilot tools."""

import asyncio
import json

from mcp import Client

MCP_URL = "http://127.0.0.1:8001/mcp"


async def main():
    async with Client(MCP_URL) as client:

        # 1. Discover all registered tools.
        tools_result = await client.list_tools()
        tool_names = {tool.name for tool in tools_result.tools}

        expected_tools = {
            "list_pods",
            "get_pod_status",
            "get_pod_logs",
            "get_recent_events",
        }

        print("Available tools:", sorted(tool_names))

        missing = expected_tools - tool_names

        if missing:
            raise RuntimeError(f"Missing MCP tools: {missing}")

        # 2. Discover a real Pod.
        pods_result = await client.call_tool("list_pods", {})
        if pods_result.is_error:
            raise RuntimeError("list_pods failed")

        pods = pods_result.structured_content
        if not pods or not pods["pods"]:
            raise RuntimeError("No Pods found")

        pod = pods["pods"][0]
        pod_name = pod["name"]

        print("\nlist_pods: SUCCESS")
        print("Pod:", pod_name)

        # 3. Get detailed status.
        status_result = await client.call_tool(
            "get_pod_status",
            {"pod_name": pod_name},
        )

        if status_result.is_error:
            raise RuntimeError("get_pod_status failed")

        status = status_result.structured_content

        container_name = status["containers"][0]["name"]

        print("\nget_pod_status: SUCCESS")
        print("Phase:", status["phase"])
        print("Container:", container_name)

        # 4. Read current logs.
        logs_result = await client.call_tool(
            "get_pod_logs",
            {
                "pod_name": pod_name,
                "container_name": container_name,
                "previous": False,
                "tail_lines": 50,
                "timestamps": True,
            },
        )

        if logs_result.is_error:
            raise RuntimeError("get_pod_logs failed")

        logs = logs_result.structured_content

        if logs["collection_status"] != "success":
            raise RuntimeError("Current log collection was unsuccessful")

        print("\nget_pod_logs: SUCCESS")
        print("Lines:", logs["log_line_count"])

        # 5. Collect recent Events for the selected Pod.
        events_result = await client.call_tool(
            "get_recent_events",
            {
                "pod_name": pod_name,
                "since_seconds": 86400,
                "limit": 50,
            },
        )

        if events_result.is_error:
            raise RuntimeError("get_recent_events failed")

        events = events_result.structured_content

        print("\nget_recent_events: SUCCESS")
        print("Events returned:", events["events_returned"])
        print("Unknown timestamps:", events["events_with_unknown_timestamp"])

        print("\nALL FOUR MCP TOOLS PASSED")

        print("\nEvent response example:")
        print(json.dumps(events, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
