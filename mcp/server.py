"""OpsPilot Kubernetes MCP server."""

import os
from datetime import datetime, timedelta, timezone
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




def _collect_pod_logs(
    pod_name: str,
    container_name: str,
    previous: bool = False,
    tail_lines: int = 100,
    timestamps: bool = True,
    limit_bytes: int = 262144,
) -> dict[str, Any]:
    """Collect logs from a selected container in the OpsPilot namespace."""

    if not pod_name or not pod_name.strip():
        raise ValueError("pod_name must not be empty")

    if not container_name or not container_name.strip():
        raise ValueError("container_name must not be empty")

    if isinstance(tail_lines, bool) or not isinstance(tail_lines, int):
        raise ValueError("tail_lines must be an integer")

    if not 1 <= tail_lines <= 500:
        raise ValueError("tail_lines must be between 1 and 500")

    if isinstance(limit_bytes, bool) or not isinstance(limit_bytes, int):
        raise ValueError("limit_bytes must be an integer")

    if not 1 <= limit_bytes <= 1_048_576:
        raise ValueError("limit_bytes must be between 1 and 1048576")

    if not isinstance(previous, bool):
        raise ValueError("previous must be a boolean")

    if not isinstance(timestamps, bool):
        raise ValueError("timestamps must be a boolean")

    try:
        api = get_core_v1_api()

        # Read the Pod first: we need its UID and container information.
        pod = api.read_namespaced_pod(
            name=pod_name,
            namespace=OPS_NAMESPACE,
        )

        # Support regular containers and init containers.
        regular_containers = list(pod.spec.containers or [])
        init_containers = list(pod.spec.init_containers or [])

        selected_spec = next(
            (
                item
                for item in regular_containers + init_containers
                if item.name == container_name
            ),
            None,
        )

        if selected_spec is None:
            available = [
                item.name
                for item in regular_containers + init_containers
            ]
            raise ValueError(
                f"Container '{container_name}' not found in Pod "
                f"'{pod_name}'. Available containers: {available}"
            )

        # Find the runtime status belonging to the selected container.
        statuses = list(pod.status.container_statuses or [])
        statuses += list(pod.status.init_container_statuses or [])

        container_status = next(
            (item for item in statuses if item.name == container_name),
            None,
        )

        # Previous logs exist only when Kubernetes reports a previous
        # terminated container instance.
        if previous:
            has_previous_termination = (
                container_status is not None
                and container_status.last_state is not None
                and container_status.last_state.terminated is not None
            )

            if not has_previous_termination:
                return {
                    "collection_status": "unavailable",
                    "availability_reason": "no_previous_terminated_instance",
                    "pod_name": pod.metadata.name,
                    "namespace": OPS_NAMESPACE,
                    "pod_uid": pod.metadata.uid,
                    "container_name": container_name,
                    "previous": True,
                    "collected_at": _format_timestamp(
                        datetime.now(timezone.utc)
                    ),
                    "logs": None,
                    "log_line_count": 0,
                    "logs_available": False,
                }

        # Ask Kubernetes for logs. follow=False is intentional:
        # this is a bounded evidence snapshot, not an endless stream.
        raw_logs = api.read_namespaced_pod_log(
            name=pod_name,
            namespace=OPS_NAMESPACE,
            container=container_name,
            follow=False,
            previous=previous,
            tail_lines=tail_lines,
            timestamps=timestamps,
            limit_bytes=limit_bytes,
        )

    except ApiException as exc:
        raise RuntimeError(
            f"Kubernetes API request failed: "
            f"HTTP {exc.status}, {exc.reason}"
        ) from exc

    logs = raw_logs or ""

    return {
        "collection_status": "success",
        "pod_name": pod.metadata.name,
        "namespace": OPS_NAMESPACE,
        "pod_uid": pod.metadata.uid,
        "pod_resource_version": pod.metadata.resource_version,
        "container_name": container_name,
        "container_id": (
            container_status.container_id
            if container_status else None
        ),
        "previous": previous,
        "timestamps": timestamps,
        "tail_lines": tail_lines,
        "limit_bytes": limit_bytes,
        "collected_at": _format_timestamp(
            datetime.now(timezone.utc)
        ),
        "logs_available": True,
        "log_line_count": len(logs.splitlines()),
        "log_bytes": len(logs.encode("utf-8")),
        "logs": logs,
    }


@mcp.tool(
    title="Get Kubernetes Pod logs",
    annotations=ToolAnnotations(
        read_only_hint=True,
        open_world_hint=False,
    ),
)
def get_pod_logs(
    pod_name: str,
    container_name: str,
    previous: bool = False,
    tail_lines: int = 100,
    timestamps: bool = True,
    limit_bytes: int = 262144,
) -> dict[str, Any]:
    """
    Collect current or previous logs from a selected Pod container.

    Previous logs are returned only when Kubernetes reports a previous
    terminated container instance. This tool never modifies Kubernetes.
    """
    return _collect_pod_logs(
        pod_name=pod_name,
        container_name=container_name,
        previous=previous,
        tail_lines=tail_lines,
        timestamps=timestamps,
        limit_bytes=limit_bytes,
    )

MAX_EVENT_PAGES = 5
EVENT_PAGE_SIZE = 500
MAX_EVENT_WINDOW_SECONDS = 7 * 24 * 60 * 60


def _event_timestamp(event) -> tuple[datetime | None, str | None]:
    """
    Return the best available occurrence timestamp and its source.

    Prefer the latest observation of an event series, then legacy
    last_timestamp, event_time and first_timestamp.
    """

    series = getattr(event, "series", None)

    candidates = [
        (
            "series.last_observed_time",
            getattr(series, "last_observed_time", None)
            if series else None,
        ),
        ("last_timestamp", getattr(event, "last_timestamp", None)),
        ("event_time", getattr(event, "event_time", None)),
        ("first_timestamp", getattr(event, "first_timestamp", None)),
    ]

    for source, value in candidates:
        if value is not None:
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)

            return value.astimezone(timezone.utc), source

    return None, None


def _serialize_event(
    event,
    cutoff: datetime,
) -> dict[str, Any]:
    """Convert one Kubernetes Event into a JSON-compatible dictionary."""

    metadata = event.metadata
    involved = getattr(event, "involved_object", None)
    related = getattr(event, "related", None)
    series = getattr(event, "series", None)
    source = getattr(event, "source", None)

    occurrence_time, timestamp_source = _event_timestamp(event)

    if occurrence_time is None:
        within_window = None
    else:
        within_window = occurrence_time >= cutoff

    return {
        "event_uid": metadata.uid,
        "event_name": metadata.name,
        "namespace": metadata.namespace,
        "resource_version": metadata.resource_version,
        "metadata_creation_timestamp": _format_timestamp(
            metadata.creation_timestamp
        ),

        "type": event.type,
        "reason": event.reason,
        "message": event.message,
        "action": getattr(event, "action", None),

        "count": getattr(event, "count", None),
        "series_count": (
            getattr(series, "count", None)
            if series else None
        ),

        "event_time": _format_timestamp(
            getattr(event, "event_time", None)
        ),
        "first_timestamp": _format_timestamp(
            getattr(event, "first_timestamp", None)
        ),
        "last_timestamp": _format_timestamp(
            getattr(event, "last_timestamp", None)
        ),
        "series_last_observed_time": _format_timestamp(
            getattr(series, "last_observed_time", None)
            if series else None
        ),

        "event_timestamp": _format_timestamp(occurrence_time),
        "event_timestamp_source": timestamp_source,
        "within_requested_window": within_window,

        "involved_object": {
            "api_version": getattr(involved, "api_version", None),
            "kind": getattr(involved, "kind", None),
            "name": getattr(involved, "name", None),
            "namespace": getattr(involved, "namespace", None),
            "uid": getattr(involved, "uid", None),
            "resource_version": getattr(
                involved, "resource_version", None
            ),
            "field_path": getattr(involved, "field_path", None),
        } if involved else None,

        "related_object": {
            "kind": getattr(related, "kind", None),
            "name": getattr(related, "name", None),
            "namespace": getattr(related, "namespace", None),
            "uid": getattr(related, "uid", None),
        } if related else None,

        "source_component": (
            getattr(source, "component", None)
            if source else None
        ),
        "source_host": (
            getattr(source, "host", None)
            if source else None
        ),
        "reporting_component": getattr(
            event, "reporting_component", None
        ),
        "reporting_instance": getattr(
            event, "reporting_instance", None
        ),
    }


def _collect_recent_events(
    pod_name: str | None = None,
    since_seconds: int = 3600,
    event_type: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Collect recent Kubernetes Events from the OpsPilot namespace."""

    if isinstance(since_seconds, bool) or not isinstance(since_seconds, int):
        raise ValueError("since_seconds must be an integer")

    if not 1 <= since_seconds <= MAX_EVENT_WINDOW_SECONDS:
        raise ValueError("since_seconds must be between 1 and 604800")

    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError("limit must be an integer")

    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")

    if pod_name is not None:
        if not isinstance(pod_name, str) or not pod_name.strip():
            raise ValueError("pod_name must be a non-empty string")

        if any(ch.isspace() or ch in ",=" for ch in pod_name):
            raise ValueError("pod_name contains invalid field-selector characters")

    if event_type is not None:
        if not isinstance(event_type, str):
            raise ValueError("event_type must be Normal, Warning or None")

        event_type = event_type.strip().capitalize()

        if event_type not in {"Normal", "Warning"}:
            raise ValueError("event_type must be Normal, Warning or None")

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=since_seconds)

    # Kubernetes field selectors allow server-side filtering.
    selectors = []

    if pod_name:
        selectors.append(f"involvedObject.name={pod_name}")
        selectors.append("involvedObject.kind=Pod")

    if event_type:
        selectors.append(f"type={event_type}")

    field_selector = ",".join(selectors) if selectors else None

    try:
        api = get_core_v1_api()

        scanned_events = []
        continue_token = None
        pages_scanned = 0

        # Read bounded pages so that a busy namespace does not result
        # in an unlimited event collection.
        for _ in range(MAX_EVENT_PAGES):
            kwargs = {
                "namespace": OPS_NAMESPACE,
                "limit": EVENT_PAGE_SIZE,
                "timeout_seconds": 15,
            }

            if field_selector:
                kwargs["field_selector"] = field_selector

            if continue_token:
                kwargs["_continue"] = continue_token

            page = api.list_namespaced_event(**kwargs)

            scanned_events.extend(page.items or [])
            pages_scanned += 1

            continue_token = getattr(
                page.metadata,
                "_continue",
                None,
            )

            if not continue_token:
                break

    except ApiException as exc:
        raise RuntimeError(
            f"Kubernetes API request failed: "
            f"HTTP {exc.status}, {exc.reason}"
        ) from exc

    serialized_events = [
        _serialize_event(event, cutoff)
        for event in scanned_events
    ]

    unknown_timestamp_count = sum(
        event["event_timestamp"] is None
        for event in serialized_events
    )

    # Keep events within the requested time window.
    # Events without timestamps are retained, but explicitly marked
    # as unknown. We do not invent a timestamp for them.
    matching_events = [
        event
        for event in serialized_events
        if event["within_requested_window"] is not False
    ]

    # Sort events from newest to oldest. Unknown timestamps come last.
    matching_events.sort(
        key=lambda event: (
            event["event_timestamp"] is not None,
            event["event_timestamp"] or "",
        ),
        reverse=True,
    )

    result_truncated = len(matching_events) > limit

    returned_events = matching_events[:limit]

    return {
        "namespace": OPS_NAMESPACE,
        "pod_name_filter": pod_name,
        "event_type_filter": event_type,
        "since_seconds": since_seconds,
        "collected_at": _format_timestamp(now),

        "pages_scanned": pages_scanned,
        "events_scanned": len(scanned_events),
        "events_returned": len(returned_events),

        "events_with_unknown_timestamp": unknown_timestamp_count,
        "result_truncated": result_truncated,
        "collection_truncated": bool(continue_token),

        "events": returned_events,
    }


@mcp.tool(
    title="Get recent Kubernetes Events",
    annotations=ToolAnnotations(
        read_only_hint=True,
        open_world_hint=False,
    ),
)
def get_recent_events(
    pod_name: str | None = None,
    since_seconds: int = 3600,
    event_type: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """
    Collect recent Kubernetes Events from opspilot-lab.

    Events may be filtered by Pod name and Normal/Warning type.
    Unknown event timestamps are preserved and explicitly marked.
    """
    return _collect_recent_events(
        pod_name=pod_name,
        since_seconds=since_seconds,
        event_type=event_type,
        limit=limit,
    )




if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host=MCP_HOST,
        port=MCP_PORT,
        streamable_http_path="/mcp",
    )