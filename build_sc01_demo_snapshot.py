"""Build a synthetic SC-01 EvidenceSnapshot for local EQG testing.

This creates simulated evidence only. It does not contact Kubernetes or MCP.
Run from the OpsPilot repository root:
    python build_sc01_demo_snapshot.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eqg.hashing import calculate_payload_hash


SNAPSHOT_ID = "SNAP-SC01-DEMO-001"
INCIDENT_ID = "INC-SC01-DEMO-001"
POD_UID = "pod-uid-sc01-demo-001"
POD_NAME = "demo-api"
NAMESPACE = "opspilot-lab"
CONTAINER_NAME = "api"
CAPTURED_AT = "2026-11-14T12:02:30Z"


def make_item(
    evidence_id: str,
    source_type: str,
    tool_name: str,
    collected_at: str,
    payload: dict[str, Any],
    container_id: str | None = None,
) -> dict[str, Any]:
    """Create an EvidenceItem with the metadata and hash EQG expects."""
    item = {
        "evidence_id": evidence_id,
        "snapshot_id": SNAPSHOT_ID,
        "incident_id": INCIDENT_ID,
        "source_type": source_type,
        "tool_name": tool_name,
        "namespace": NAMESPACE,
        "pod_name": POD_NAME,
        "pod_uid": POD_UID,
        "container_name": CONTAINER_NAME,
        "container_id": container_id,
        "collected_at": collected_at,
        "observed_at": None,
        "resource_version": f"opaque-{evidence_id}",
        "payload": payload,
    }
    item["payload_hash"] = calculate_payload_hash(payload)
    return item


def make_status_payload(restart_count: int) -> dict[str, Any]:
    """Represent Pod phase separately from the container waiting state."""
    return {
        "pod": {
            "name": POD_NAME,
            "uid": POD_UID,
            "namespace": NAMESPACE,
            "phase": "Running",
        },
        "containers": [
            {
                "name": CONTAINER_NAME,
                "state": {"waiting": {"reason": "CrashLoopBackOff"}},
                "last_state": {
                    "terminated": {"reason": "Error", "exit_code": 1}
                },
                "restart_count": restart_count,
            }
        ],
    }


def build_snapshot() -> dict[str, Any]:
    items: list[dict[str, Any]] = []

    # Two observations prove the restart count crossed 3 within 3 minutes:
    # 2 -> 3 restarts in 150 seconds for the same Pod UID.
    items.append(
        make_item(
            "E-SC01-001", "pod_status", "get_pod_status",
            "2026-11-14T12:00:00Z", make_status_payload(2),
        )
    )
    items.append(
        make_item(
            "E-SC01-002", "pod_status", "get_pod_status",
            "2026-11-14T12:02:30Z", make_status_payload(3),
        )
    )

    # Pod specification: image and resource requests/limits.
    spec_payload = {
        "pod": {"name": POD_NAME, "uid": POD_UID, "namespace": NAMESPACE},
        "containers": [
            {
                "name": CONTAINER_NAME,
                "image": "opspilot-demo:dev",
                "spec": {
                    "resources": {
                        "requests": {"cpu": "100m", "memory": "64Mi"},
                        "limits": {"cpu": "500m", "memory": "128Mi"},
                    }
                },
            }
        ],
    }
    items.append(
        make_item(
            "E-SC01-003", "pod_spec", "get_pod_status",
            "2026-11-14T12:02:00Z", spec_payload,
        )
    )

    # Current logs from the current container instance.
    items.append(
        make_item(
            "E-SC01-004", "pod_logs", "get_pod_logs",
            "2026-11-14T12:02:10Z",
            {
                "previous": False,
                "available": True,
                "logs": (
                    "Starting OpsPilot demo application.\n"
                    "Initializing application.\n"
                    "Simulated application failure."
                ),
            },
            container_id="containerd://sc01-current-001",
        )
    )

    # Previous logs are a separate observation. Their collection time is fresh;
    # their content describes the previous container execution.
    items.append(
        make_item(
            "E-SC01-005", "pod_logs", "get_pod_logs",
            "2026-11-14T12:02:10Z",
            {
                "previous": True,
                "available": True,
                "logs": (
                    "Previous container started.\n"
                    "Application initialization failed.\n"
                    "Process exited with code 1."
                ),
            },
            container_id="containerd://sc01-previous-001",
        )
    )

    # Event association is proven by involvedObject.uid matching the Pod UID.
    event_payload = {
        "events": [
            {
                "type": "Warning",
                "reason": "BackOff",
                "message": "Back-off restarting failed container api in pod demo-api",
                "involvedObject": {
                    "kind": "Pod",
                    "namespace": NAMESPACE,
                    "name": POD_NAME,
                    "uid": POD_UID,
                },
                "eventTime": "2026-11-14T12:02:15Z",
                "firstTimestamp": "2026-11-14T12:00:00Z",
                "lastTimestamp": "2026-11-14T12:02:15Z",
                "count": 3,
            }
        ]
    }
    items.append(
        make_item(
            "E-SC01-006", "events", "get_recent_events",
            "2026-11-14T12:02:15Z", event_payload,
        )
    )

    # Build the source manifest from the evidence actually included.
    ids_by_tool: dict[str, list[str]] = {}
    for item in items:
        ids_by_tool.setdefault(item["tool_name"], []).append(item["evidence_id"])

    source_manifest = [
        {
            "tool_name": tool,
            "status": "success",
            "evidence_ids": sorted(evidence_ids),
        }
        for tool, evidence_ids in sorted(ids_by_tool.items())
    ]

    return {
        "snapshot_id": SNAPSHOT_ID,
        "incident_id": INCIDENT_ID,
        "captured_at": CAPTURED_AT,
        "cluster_version": "1.36",
        "source_manifest": source_manifest,
        "evidence_items": items,
    }


def main() -> None:
    output_path = (
        Path(__file__).resolve().parent
        / "examples"
        / "scenarios"
        / "sc-01-crashloopbackoff"
        / "snapshot.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot()
    output_path.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print("SC-01 synthetic snapshot created successfully.")
    print(f"Output: {output_path}")
    print(f"Evidence items: {len(snapshot['evidence_items'])}")
    print(f"Snapshot ID: {SNAPSHOT_ID}")
    print(f"Pod UID: {POD_UID}")


if __name__ == "__main__":
    main()
