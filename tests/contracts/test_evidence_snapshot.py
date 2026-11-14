import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT_DIR = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT_DIR / "contracts" / "v1" / "evidence-snapshot.schema.json"

with SCHEMA_PATH.open(encoding="utf-8") as file:
    EVIDENCE_SNAPSHOT_SCHEMA = json.load(file)

VALID_SNAPSHOT = {
    "snapshot_id": "SNAP-INC-001",
    "incident_id": "INC-001",
    "captured_at": "2026-11-12T10:35:00Z",
    "cluster_version": "v1.37.0",
    "source_manifest": [
        {
            "tool_name": "list_pods",
            "status": "success",
            "evidence_ids": ["E-0001"]
        },
        {
            "tool_name": "get_pod_status",
            "status": "success",
            "evidence_ids": ["E-0002"]
        },
        {
            "tool_name": "get_pod_logs",
            "status": "failed",
            "evidence_ids": []
        },
        {
            "tool_name": "get_recent_events",
            "status": "success",
            "evidence_ids": ["E-0003"]
        }
    ]
}

def get_validator():
    return Draft202012Validator(
        EVIDENCE_SNAPSHOT_SCHEMA,
        format_checker=FormatChecker()
    )

def get_errors(data):
    return list(get_validator().iter_errors(data))

def test_snapshot_schema_definition_is_valid():
    Draft202012Validator.check_schema(EVIDENCE_SNAPSHOT_SCHEMA)

def test_valid_snapshot_is_accepted():
    errors = get_errors(VALID_SNAPSHOT)
    assert errors == [], [error.message for error in errors]

def test_unknown_cluster_version_can_be_null():
    snapshot = copy.deepcopy(VALID_SNAPSHOT)
    snapshot["cluster_version"] = None
    assert get_errors(snapshot) == []

def test_invalid_tool_name_is_rejected():
    snapshot = copy.deepcopy(VALID_SNAPSHOT)
    snapshot["source_manifest"][0]["tool_name"] = "delete_pod"
    assert get_errors(snapshot)

def test_invalid_collection_status_is_rejected():
    snapshot = copy.deepcopy(VALID_SNAPSHOT)
    snapshot["source_manifest"][0]["status"] = "unknown_status"
    assert get_errors(snapshot)

def test_invalid_evidence_id_is_rejected():
    snapshot = copy.deepcopy(VALID_SNAPSHOT)
    snapshot["source_manifest"][0]["evidence_ids"] = ["INVALID-ID"]
    assert get_errors(snapshot)

def test_duplicate_evidence_ids_are_rejected():
    snapshot = copy.deepcopy(VALID_SNAPSHOT)
    snapshot["source_manifest"][0]["evidence_ids"] = ["E-0001", "E-0001"]
    assert get_errors(snapshot)

def test_invalid_capture_timestamp_is_rejected():
    snapshot = copy.deepcopy(VALID_SNAPSHOT)
    snapshot["captured_at"] = "not-a-date"
    assert get_errors(snapshot)

def test_missing_source_manifest_is_rejected():
    snapshot = copy.deepcopy(VALID_SNAPSHOT)
    del snapshot["source_manifest"]
    assert get_errors(snapshot)

def test_unknown_snapshot_field_is_rejected():
    snapshot = copy.deepcopy(VALID_SNAPSHOT)
    snapshot["unexpected_field"] = "unexpected"
    assert get_errors(snapshot)
