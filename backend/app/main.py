from fastapi import FastAPI, HTTPException

from app.services.mcp_client import call_mcp_tool

app = FastAPI(
    title="OpsPilot API",
    description="API de supervision Kubernetes via MCP",
    version="1.0.0",
)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "opspilot-api"}


@app.get("/api/pods")
async def list_pods():
    try:
        return await call_mcp_tool("list_pods")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/api/pods/{pod_name}")
async def get_pod_status(pod_name: str):
    try:
        return await call_mcp_tool(
            "get_pod_status",
            {"pod_name": pod_name},
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/api/pods/{pod_name}/logs")
async def get_pod_logs(pod_name: str, tail_lines: int = 100):
    try:
        return await call_mcp_tool(
            "get_pod_logs",
            {
                "pod_name": pod_name,
                "tail_lines": tail_lines,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/api/events")
async def get_events():
    try:
        return await call_mcp_tool("get_recent_events")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/api/issues")
async def detect_issues():
    try:
        return await call_mcp_tool("detect_pod_issues")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
