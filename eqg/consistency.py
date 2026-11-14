"""Identity and same-time contradiction checks."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .extractors import collect_field_values
from .models import Issue
from .time_utils import parse_timestamp

FACT_FIELDS = (
    ("pod_status", "pod_phase"),
    ("pod_status", "container_state_waiting_reason"),
    ("pod_status", "container_last_state_terminated_reason"),
    ("pod_status", "exit_code"),
)


def evaluate_consistency(evidence_items: list[dict[str, Any]], same_time_window_seconds: int = 2) -> tuple[list[Issue], list[dict[str, Any]]]:
    issues: list[Issue] = []
    checks: list[dict[str, Any]] = []

    # A Pod name can be reused. Different UIDs mean different Pod instances.
    uids_by_pod: dict[tuple[str, str], set[str]] = defaultdict(set)
    ids_by_pod: dict[tuple[str, str], list[str]] = defaultdict(list)
    for item in evidence_items:
        if item.get("source_type") not in {"pod_status", "pod_spec", "pod_logs", "events"}:
            continue
        key = (str(item.get("namespace", "")), str(item.get("pod_name", "")))
        uid = item.get("pod_uid")
        if uid:
            uids_by_pod[key].add(str(uid))
        if item.get("evidence_id"):
            ids_by_pod[key].append(str(item["evidence_id"]))
    for key, uids in uids_by_pod.items():
        if len(uids) > 1:
            issues.append(Issue("MULTIPLE_POD_UIDS_FOR_NAME", "freshness", "stale",
                                f"Evidence for Pod {key[1]!r} in namespace {key[0]!r} refers to multiple Pod UIDs; it may mix Pod instances.", ids_by_pod[key]))

    # Compare semantically identical facts only when identity and collection
    # times are almost the same. A restart at a later time is not a conflict.
    for source_type, field in FACT_FIELDS:
        values = collect_field_values(field, source_type, evidence_items)
        for index, (left_value, left_item) in enumerate(values):
            left_time = parse_timestamp(left_item.get("collected_at"))
            for right_value, right_item in values[index + 1:]:
                if left_item.get("pod_uid") != right_item.get("pod_uid"):
                    continue
                if left_item.get("container_name") != right_item.get("container_name"):
                    continue
                right_time = parse_timestamp(right_item.get("collected_at"))
                if not left_time or not right_time:
                    continue
                if abs(left_time.timestamp() - right_time.timestamp()) > same_time_window_seconds:
                    continue
                if left_value != right_value:
                    ids = [str(left_item.get("evidence_id", "")), str(right_item.get("evidence_id", ""))]
                    issues.append(Issue("CONTRADICTORY_OBSERVATIONS", "consistency", "conflict",
                                        f"Two near-simultaneous observations disagree on '{field}' for the same Pod/container identity.",
                                        [x for x in ids if x], field))

    # Different Pod phase and container state are intentionally not compared:
    # Running Pod + Waiting container is a valid Kubernetes state.
    checks.append({"code": "pod_identity", "passed": not any(i.code == "MULTIPLE_POD_UIDS_FOR_NAME" for i in issues)})
    checks.append({"code": "same_time_facts", "passed": not any(i.code == "CONTRADICTORY_OBSERVATIONS" for i in issues), "window_seconds": same_time_window_seconds})
    return issues, checks
