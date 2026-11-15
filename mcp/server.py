"""OpsPilot Kubernetes MCP server."""

import os
from datetime import datetime, timezone
from typing import Any

from kubernetes.client.exceptions import ApiException
from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from kubernetes_client import get_core_v1_api


# OpsPilot only collects evidence from this namespace.
OPS_NAMESPACE = "opspilot-lab"

MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("MCP_PORT", "8001"))


mcp = MCPServer(
    "OpsPilot Kubernetes MCP",
    instructions=(
        "Read-only Kubernetes evidence collection for OpsPilot. "
        "All tools collect observations from the opspilot-lab namespace. "
        "Tools must never modify Kubernetes resources."
    ),
)


def _format_timestamp(value: datetime | None) -> str | None:
    """Convert a Kubernetes datetime to an RFC3339 UTC string."""

    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _collect_pods() -> dict[str, Any]:
    """Collect Pod metadata from the OpsPilot laboratory namespace."""

    try:
        api = get_core_v1_api()

        response = api.list_namespaced_pod(
            namespace=OPS_NAMESPACE
        )

    except ApiException as exc:
        raise RuntimeError(
            f"Kubernetes API request failed: "
            f"HTTP {exc.status}, {exc.reason}"
        ) from exc

    pods = []

    for pod in response.items:
        metadata = pod.metadata
        spec = pod.spec
        status = pod.status

        containers = [
            {
                "name": container.name,
                "image": container.image,
            }
            for container in (spec.containers or [])
        ] if spec else []

        pods.append({
            "name": metadata.name,
            "namespace": metadata.namespace or OPS_NAMESPACE,
            "uid": metadata.uid,
            "resource_version": metadata.resource_version,
            "creation_timestamp": _format_timestamp(
                metadata.creation_timestamp
            ),
            "labels": dict(metadata.labels or {}),
            "node_name": spec.node_name if spec else None,
            "pod_ip": status.pod_ip if status else None,
            "phase": status.phase if status else None,
            "start_time": _format_timestamp(
                status.start_time if status else None
            ),
            "containers": containers,
        })

    return {
        "namespace": OPS_NAMESPACE,
        "collected_at": _format_timestamp(
            datetime.now(timezone.utc)
        ),
        "pod_count": len(pods),
        "pods": pods,
    }


@mcp.tool(
    title="List Kubernetes Pods",
    annotations=ToolAnnotations(
        read_only_hint=True,
        open_world_hint=False,
    ),
)
def list_pods() -> dict[str, Any]:
    """
    List Pods in the OpsPilot laboratory namespace.

    Returns Pod identity, labels, timestamps, node, phase,
    and container names and images.
    """
    return _collect_pods()


def _serialize_container_state(state) -> dict[str, Any] | None:
    """Convert a Kubernetes ContainerState into a readable dictionary."""

    if state is None:
        return None

    if state.waiting is not None:
        return {
            "type": "waiting",
            "reason": state.waiting.reason,
            "message": state.waiting.message,
        }

    if state.running is not None:
        return {
            "type": "running",
            "started_at": _format_timestamp(
                state.running.started_at
            ),
        }

    if state.terminated is not None:
        terminated = state.terminated

        return {
            "type": "terminated",
            "reason": terminated.reason,
            "message": terminated.message,
            "exit_code": terminated.exit_code,
            "signal": terminated.signal,
            "started_at": _format_timestamp(
                terminated.started_at
            ),
            "finished_at": _format_timestamp(
                terminated.finished_at
            ),
        }

    return None


def _collect_pod_status(pod_name: str) -> dict[str, Any]:
    """Collect detailed Pod and container status."""

    try:
        api = get_core_v1_api()

        pod = api.read_namespaced_pod(
            name=pod_name,
            namespace=OPS_NAMESPACE,
        )

    except ApiException as exc:
        raise RuntimeError(
            f"Kubernetes API request failed: "
            f"HTTP {exc.status}, {exc.reason}"
        ) from exc

    metadata = pod.metadata
    spec = pod.spec
    status = pod.status

    # Match runtime container status with its specification.
    status_by_name = {
        container.name: container
        for container in (status.container_statuses or [])
    }

    containers = []

    for container_spec in (spec.containers or []):
        container_status = status_by_name.get(container_spec.name)
        resources = container_spec.resources

        containers.append({
            "name": container_spec.name,
            "image": container_spec.image,
            "image_pull_policy": container_spec.image_pull_policy,

            "resources": {
                "requests": dict(resources.requests or {})
                if resources else {},
                "limits": dict(resources.limits or {})
                if resources else {},
            },

            "container_id": (
                container_status.container_id
                if container_status else None
            ),
            "runtime_image": (
                container_status.image
                if container_status else None
            ),
            "image_id": (
                container_status.image_id
                if container_status else None
            ),
            "ready": (
                container_status.ready
                if container_status else None
            ),
            "started": (
                container_status.started
                if container_status else None
            ),
            "restart_count": (
                container_status.restart_count
                if container_status else None
            ),
            "state": (
                _serialize_container_state(container_status.state)
                if container_status else None
            ),
            "last_state": (
                _serialize_container_state(container_status.last_state)
                if container_status else None
            ),
        })

    conditions = [
        {
            "type": condition.type,
            "status": condition.status,
            "reason": condition.reason,
            "message": condition.message,
            "last_probe_time": _format_timestamp(
                condition.last_probe_time
            ),
            "last_transition_time": _format_timestamp(
                condition.last_transition_time
            ),
        }
        for condition in (status.conditions or [])
    ]

    return {
        "pod_name": metadata.name,
        "namespace": metadata.namespace or OPS_NAMESPACE,
        "pod_uid": metadata.uid,
        "resource_version": metadata.resource_version,
        "creation_timestamp": _format_timestamp(
            metadata.creation_timestamp
        ),
        "collected_at": _format_timestamp(
            datetime.now(timezone.utc)
        ),
        "phase": status.phase,
        "reason": status.reason,
        "message": status.message,
        "node_name": spec.node_name,
        "pod_ip": status.pod_ip,
        "host_ip": status.host_ip,
        "start_time": _format_timestamp(status.start_time),
        "conditions": conditions,
        "containers": containers,
    }


@mcp.tool(
    title="Get Kubernetes Pod status",
    annotations=ToolAnnotations(
        read_only_hint=True,
        open_world_hint=False,
    ),
)
def get_pod_status(pod_name: str) -> dict[str, Any]:
    """
    Get detailed Pod and container status.

    Includes current state, previous termination state,
    restart count, image and resource requests/limits.
    """
    return _collect_pod_status(pod_name)



if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host=MCP_HOST,
        port=MCP_PORT,
        streamable_http_path="/mcp",
    )