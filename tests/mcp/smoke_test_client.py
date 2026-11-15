
"""Manual MCP integration test for OpsPilot collection tools."""

import asyncio
import json

from mcp import Client

MCP_URL = "http://127.0.0.1:8001/mcp"


async def main():
    async with Client(MCP_URL) as client:

        # 1. Discover available tools.
        tools_result = await client.list_tools()
        tool_names = [tool.name for tool in tools_result.tools]

        print("Available tools:", tool_names)

        expected = {"list_pods", "get_pod_status"}
        if not expected.issubset(set(tool_names)):
            raise RuntimeError(
                f"Missing tools: {expected - set(tool_names)}"
            )

        # 2. Call list_pods.
        pods_result = await client.call_tool("list_pods", {})

        if pods_result.is_error:
            raise RuntimeError("list_pods failed")

        pods = pods_result.structured_content

        if not pods or not pods["pods"]:
            raise RuntimeError("No Pods returned")

        pod_name = pods["pods"][0]["name"]

        print("\nlist_pods: SUCCESS")
        print("Pod:", pod_name)

        # 3. Call get_pod_status using the discovered Pod name.
        status_result = await client.call_tool(
            "get_pod_status",
            {"pod_name": pod_name},
        )

        if status_result.is_error:
            raise RuntimeError("get_pod_status failed")

        status = status_result.structured_content

        if status["pod_name"] != pod_name:
            raise RuntimeError("Unexpected Pod returned")

        print("\nget_pod_status: SUCCESS")
        print(json.dumps(status, indent=2))

        print("\nALL MCP INTEGRATION CHECKS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
