"""End-to-end scenario evaluation tests using synthetic SC-01 evidence."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from eqg.engine import evaluate_snapshot
from eqg.freshness import FreshnessPolicy
from eqg.hashing import calculate_payload_hash


ROOT = Path(__file__).resolve().parents[2]
SCENARIO_PATH = ROOT / "scenarios" / "sc-01-crashloopbackoff" / "scenario.yaml"
SNAPSHOT_PATH = (
    ROOT
    / "examples"
    / "scenarios"
    / "sc-01-crashloopbackoff"
    / "snapshot.json"
)
POD_UID = "pod-uid-sc01-demo-001"

FRESHNESS_POLICY = FreshnessPolicy(
    max_age_seconds_by_source={
        "pod_status": 180,
        "pod_spec": 900,
        "pod_logs": 900,
        "events": 600,
    },
    expected_pod_uid=POD_UID,
)


@pytest.fixture
def base_snapshot():
    """Load a fresh copy of the valid synthetic snapshot for every test."""
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def evaluate(snapshot):
    """Run the actual EQG engine against the SC-01 contract."""
    report = evaluate_snapshot(
        snapshot=snapshot,
        scenario=SCENARIO_PATH,
        freshness_policy=FRESHNESS_POLICY,
    )
    return report.to_dict()


def find_item(snapshot, evidence_id):
    return next(
        item
        for item in snapshot["evidence_items"]
        if item["evidence_id"] == evidence_id
    )


def test_complete_evidence_returns_sufficient(base_snapshot):
    result = evaluate(base_snapshot)

    assert result["decision"] == "SUFFICIENT"
    assert result["issues"] == []
    for dimension in ("provenance", "completeness", "freshness", "consistency"):
        assert result["dimensions"][dimension]["status"] == "pass"


def test_modified_payload_hash_returns_invalid_provenance(base_snapshot):
    item = base_snapshot["evidence_items"][0]
    original_hash = item["payload_hash"]
    item["payload_hash"] = ("0" if original_hash[0] != "0" else "1") + original_hash[1:]

    result = evaluate(base_snapshot)

    assert result["decision"] == "INVALID_PROVENANCE"
    assert any(
        issue["code"] == "PAYLOAD_HASH_MISMATCH"
        for issue in result["issues"]
    )


def test_missing_previous_logs_returns_partial(base_snapshot):
    missing_id = "E-SC01-005"
    base_snapshot["evidence_items"] = [
        item
        for item in base_snapshot["evidence_items"]
        if item["evidence_id"] != missing_id
    ]
    # Keep the source manifest aligned with the evidence actually present.
    for entry in base_snapshot["source_manifest"]:
        if entry["tool_name"] == "get_pod_logs":
            entry["evidence_ids"] = [
                eid for eid in entry["evidence_ids"] if eid != missing_id
            ]

    result = evaluate(base_snapshot)

    assert result["decision"] == "PARTIAL"
    assert any(
        issue["code"] == "EXPECTED_OBSERVATION_MISSING"
        and issue["field"] == "logs_previous"
        for issue in result["issues"]
    )


def test_old_previous_logs_returns_stale(base_snapshot):
    item = find_item(base_snapshot, "E-SC01-005")
    item["collected_at"] = "2026-11-14T11:40:00Z"

    result = evaluate(base_snapshot)

    assert result["decision"] == "STALE"
    assert any(
        issue["code"] == "EVIDENCE_TOO_OLD"
        for issue in result["issues"]
    )


def test_near_simultaneous_conflicting_reasons_return_conflicted(base_snapshot):
    original = find_item(base_snapshot, "E-SC01-002")
    conflicting = copy.deepcopy(original)
    conflicting["evidence_id"] = "E-SC01-007"
    conflicting["collected_at"] = "2026-11-14T12:02:31Z"
    conflicting["resource_version"] = "opaque-E-SC01-007"
    conflicting["payload"]["containers"][0]["state"]["waiting"][
        "reason"
    ] = "ImagePullBackOff"
    # Recalculate the hash: this test targets consistency, not hash integrity.
    conflicting["payload_hash"] = calculate_payload_hash(conflicting["payload"])
    base_snapshot["evidence_items"].append(conflicting)

    status_manifest = next(
        entry
        for entry in base_snapshot["source_manifest"]
        if entry["tool_name"] == "get_pod_status"
    )
    status_manifest["evidence_ids"].append("E-SC01-007")
    status_manifest["evidence_ids"].sort()
    base_snapshot["captured_at"] = "2026-11-14T12:02:31Z"

    result = evaluate(base_snapshot)

    assert result["decision"] == "CONFLICTED"
    assert any(
        issue["code"] == "CONTRADICTORY_OBSERVATIONS"
        and issue["field"] == "container_state_waiting_reason"
        for issue in result["issues"]
    )
