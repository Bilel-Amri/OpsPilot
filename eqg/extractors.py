"""Read named observations from normalized OpsPilot evidence payloads."""

from __future__ import annotations

from typing import Any

MISSING = object()


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first(*values: Any) -> Any:
    for value in values:
        if value is not MISSING and value is not None:
            return value
    return MISSING


def _containers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [
        payload.get("containers"),
        _dict(payload.get("pod")).get("containers"),
        _dict(_dict(payload.get("spec")).get("template")).get("containers"),
        _dict(_dict(_dict(payload.get("spec")).get("template")).get("spec")).get("containers"),
        _dict(payload.get("spec")).get("containers"),
    ]
    for candidate in candidates:
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
    return []


def _select_container(payload: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    containers = _containers(payload)
    wanted = item.get("container_name")
    if wanted:
        for container in containers:
            if container.get("name") == wanted:
                return container
    return containers[0] if len(containers) == 1 else {}


def _pod(payload: dict[str, Any]) -> dict[str, Any]:
    pod = payload.get("pod")
    return pod if isinstance(pod, dict) else payload


def _terminated(container: dict[str, Any]) -> dict[str, Any]:
    last_state = _dict(container.get("last_state") or container.get("lastState"))
    terminated = last_state.get("terminated")
    if isinstance(terminated, dict):
        return terminated
    status = _dict(container.get("status"))
    last_state = _dict(status.get("last_state") or status.get("lastState"))
    terminated = last_state.get("terminated")
    return terminated if isinstance(terminated, dict) else {}


def _waiting(container: dict[str, Any]) -> dict[str, Any]:
    state = _dict(container.get("state"))
    waiting = state.get("waiting")
    if isinstance(waiting, dict):
        return waiting
    status = _dict(container.get("status"))
    state = _dict(status.get("state"))
    waiting = state.get("waiting")
    return waiting if isinstance(waiting, dict) else {}


def _resources(container: dict[str, Any]) -> dict[str, Any]:
    spec = _dict(container.get("spec"))
    resources = container.get("resources") or spec.get("resources")
    return resources if isinstance(resources, dict) else {}


def _events(payload: dict[str, Any], item: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("events")
    candidates = raw if isinstance(raw, list) else [payload]
    expected_uid = item.get("pod_uid") or _dict(payload.get("pod")).get("uid")
    result: list[dict[str, Any]] = []
    for event in candidates:
        if not isinstance(event, dict):
            continue
        involved = event.get("involvedObject") or event.get("involved_object") or {}
        involved_uid = involved.get("uid") if isinstance(involved, dict) else None
        if involved_uid is None:
            involved_uid = event.get("involved_object_uid")
        # Event association must be demonstrated by the event object itself.
        # An item-level Pod UID alone does not prove that a given Event concerns it.
        if expected_uid and involved_uid != expected_uid:
            continue
        if not expected_uid or not involved_uid:
            continue
        result.append(event)
    return result


def extract_field(field: str, item: dict[str, Any]) -> Any:
    """Return a field value or MISSING. No missing value is fabricated."""
    payload = _dict(item.get("payload"))
    pod = _pod(payload)
    container = _select_container(payload, item)
    waiting = _waiting(container)
    terminated = _terminated(container)
    resources = _resources(container)

    if field == "pod_uid":
        return _first(item.get("pod_uid"), pod.get("uid"), payload.get("uid"))
    if field == "pod_phase":
        return _first(pod.get("phase"), payload.get("phase"))
    if field == "container_state_waiting_reason":
        return _first(waiting.get("reason"), _dict(payload.get("container_state_waiting")).get("reason"), payload.get("waiting_reason"))
    if field == "restart_count":
        return _first(container.get("restart_count"), container.get("restartCount"), _dict(container.get("status")).get("restart_count"), _dict(container.get("status")).get("restartCount"), payload.get("restart_count"))
    if field == "last_state_terminated":
        return terminated if terminated else MISSING
    if field == "container_last_state_terminated_reason":
        return _first(terminated.get("reason"))
    if field == "exit_code":
        return _first(terminated.get("exit_code"), terminated.get("exitCode"))
    if field == "container_image":
        return _first(container.get("image"), _dict(container.get("spec")).get("image"), payload.get("image"))
    if field in {"resource_requests", "resource_limits", "resource_requests_limits"}:
        requests = resources.get("requests")
        limits = resources.get("limits")
        if field == "resource_requests":
            return requests if isinstance(requests, dict) and requests else MISSING
        if field == "resource_limits":
            return limits if isinstance(limits, dict) and limits else MISSING
        combined = {}
        if isinstance(requests, dict) and requests:
            combined["requests"] = requests
        if isinstance(limits, dict) and limits:
            combined["limits"] = limits
        return combined if combined else MISSING
    if field in {"logs_current", "logs_previous", "logs_current_or_previous"}:
        previous = payload.get("previous")
        available = payload.get("available")
        logs = _first(payload.get("logs"), payload.get("text"), payload.get("content"))
        if available is False or logs is MISSING:
            return MISSING
        if field == "logs_current" and previous is not False:
            return MISSING
        if field == "logs_previous" and previous is not True:
            return MISSING
        if field == "logs_current_or_previous" and not isinstance(previous, bool):
            return MISSING
        return logs
    if field in {"linked_events", "event_timestamps"}:
        events = _events(payload, item)
        if field == "linked_events":
            return events if events else MISSING
        timestamps: list[dict[str, Any]] = []
        timestamp_keys = ("eventTime", "firstTimestamp", "lastTimestamp", "first_timestamp", "last_timestamp", "lastObservedTime")
        for event in events:
            values = {key: event[key] for key in timestamp_keys if event.get(key) is not None}
            series = _dict(event.get("series"))
            if series.get("lastObservedTime") is not None:
                values["series.lastObservedTime"] = series["lastObservedTime"]
            if values:
                timestamps.append(values)
        return timestamps if timestamps else MISSING
    if field == "no_errimageneverpull":
        pull_policy = _first(
            container.get("imagePullPolicy"),
            _dict(container.get("spec")).get("imagePullPolicy"),
            payload.get("imagePullPolicy"),
        )
        # Kubernetes defaults an omitted pull policy to IfNotPresent.
        if pull_policy is MISSING:
            return True
        return str(pull_policy).lower() != "never"
    if field == "manifest_image_pull_policy":
        return _first(container.get("imagePullPolicy"), _dict(container.get("spec")).get("imagePullPolicy"), payload.get("imagePullPolicy"))

    # Last-resort direct lookup supports additional fields added to scenario YAML.
    value = payload.get(field, MISSING)
    return value


def collect_field_values(field: str, source_type: str, evidence_items: list[dict[str, Any]]) -> list[tuple[Any, dict[str, Any]]]:
    values: list[tuple[Any, dict[str, Any]]] = []
    for item in evidence_items:
        if item.get("source_type") != source_type:
            continue
        value = extract_field(field, item)
        if value is not MISSING and value is not None:
            values.append((value, item))
    return values
