from __future__ import annotations

from copy import deepcopy
from typing import Any

from eqg.hashing import calculate_payload_hash


def make_item(
    evidence_id: str,
    source_type: str,
    tool_name: str,
    payload: dict[str, Any],
    *,
    collected_at: str = "2026-11-13T00:00:00Z",
    pod_uid: str | None = "pod-uid-1",
    namespace: str | None = "opspilot-lab",
    pod_name: str | None = "demo-api",
    container_name: str | None = "api",
    incident_id: str = "INC-001",
    snapshot_id: str = "SNAP-001",
) -> dict[str, Any]:
    item = {
        "evidence_id": evidence_id,
        "snapshot_id": snapshot_id,
        "incident_id": incident_id,
        "source_type": source_type,
        "tool_name": tool_name,
        "namespace": namespace,
        "pod_name": pod_name,
        "pod_uid": pod_uid,
        "container_name": container_name,
        "container_id": "containerd://abc123" if source_type == "pod_logs" else None,
        "collected_at": collected_at,
        "observed_at": None,
        "resource_version": "opaque-rv-100",
        "payload": deepcopy(payload),
    }
    item["payload_hash"] = calculate_payload_hash(item["payload"])
    return item


def make_snapshot(items: list[dict[str, Any]]) -> dict[str, Any]:
    manifest: dict[str, set[str]] = {}
    for item in items:
        manifest.setdefault(item["tool_name"], set()).add(item["evidence_id"])
    source_manifest = [
        {"tool_name": tool, "status": "success", "evidence_ids": sorted(ids)}
        for tool, ids in sorted(manifest.items())
    ]
    return {
        "snapshot_id": "SNAP-001",
        "incident_id": "INC-001",
        "captured_at": "2026-11-13T00:00:00Z",
        "cluster_version": "1.36",
        "source_manifest": source_manifest,
        "evidence_items": items,
    }


def crashloop_payload(restart_count: int = 3) -> dict[str, Any]:
    return {
        "pod": {"name": "demo-api", "uid": "pod-uid-1", "namespace": "opspilot-lab", "phase": "Running"},
        "containers": [{
            "name": "api",
            "state": {"waiting": {"reason": "CrashLoopBackOff"}},
            "last_state": {"terminated": {"reason": "Error", "exit_code": 1}},
            "restart_count": restart_count,
            "spec": {"image": "opspilot-demo:dev", "resources": {"requests": {"memory": "64Mi"}, "limits": {"memory": "128Mi"}}},
        }],
    }


def small_scenario() -> dict[str, Any]:
    return {
        "scenario_id": "SC-TEST",
        "title": "Test CrashLoopBackOff",
        "family": "crashloopbackoff",
        "required_observations": [
            {"field": "pod_uid", "source_type": "pod_status", "criticality": "critical"},
            {"field": "pod_phase", "source_type": "pod_status", "criticality": "critical"},
            {"field": "container_state_waiting_reason", "source_type": "pod_status", "expected_value": "CrashLoopBackOff", "criticality": "critical"},
            {"field": "restart_count", "source_type": "pod_status", "expected_condition": ">= 3", "criticality": "critical"},
            {"field": "logs_previous", "source_type": "pod_logs", "criticality": "expected"},
        ],
    }
