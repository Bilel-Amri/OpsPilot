import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT_DIR = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT_DIR / "contracts" / "v1" / "evidence-item.schema.json"

with SCHEMA_PATH.open(encoding="utf-8") as file:
    EVIDENCE_ITEM_SCHEMA = json.load(file)

VALID_EVIDENCE_ITEM = {
    "evidence_id": "E-0001",
    "snapshot_id": "SNAP-INC-001",
    "incident_id": "INC-001",
    "source_type": "pod_status",
    "tool_name": "get_pod_status",
    "namespace": "opspilot-lab",
    "pod_name": "demo-api",
    "pod_uid": "pod-uid-123",
    "container_name": "api",
    "container_id": None,
    "collected_at": "2026-11-12T10:30:00Z",
    "observed_at": None,
    "resource_version": "12345",
    "payload_hash": "a" * 64,
    "payload": {
        "phase": "Running",
        "container_state": "Waiting",
        "waiting_reason": "CrashLoopBackOff",
        "restart_count": 5
    }
}

def get_validator():
    return Draft202012Validator(
        EVIDENCE_ITEM_SCHEMA,
        format_checker=FormatChecker()
    )

def get_errors(data):
    return list(get_validator().iter_errors(data))

def test_schema_definition_is_valid():
    Draft202012Validator.check_schema(EVIDENCE_ITEM_SCHEMA)

def test_valid_evidence_item_is_accepted():
    errors = get_errors(VALID_EVIDENCE_ITEM)
    assert errors == [], [error.message for error in errors]

def test_unknown_pod_uid_can_be_null():
    item = copy.deepcopy(VALID_EVIDENCE_ITEM)
    item["pod_uid"] = None
    assert get_errors(item) == []

def test_invalid_source_tool_combination_is_rejected():
    item = copy.deepcopy(VALID_EVIDENCE_ITEM)
    item["source_type"] = "pod_logs"
    item["tool_name"] = "list_pods"
    assert get_errors(item)

def test_invalid_payload_hash_is_rejected():
    item = copy.deepcopy(VALID_EVIDENCE_ITEM)
    item["payload_hash"] = "invalid-hash"
    assert get_errors(item)

def test_missing_required_field_is_rejected():
    item = copy.deepcopy(VALID_EVIDENCE_ITEM)
    del item["evidence_id"]
    assert get_errors(item)

def test_unknown_field_is_rejected():
    item = copy.deepcopy(VALID_EVIDENCE_ITEM)
    item["unexpected_field"] = "unexpected"
    assert get_errors(item)

def test_invalid_collection_timestamp_is_rejected():
    item = copy.deepcopy(VALID_EVIDENCE_ITEM)
    item["collected_at"] = "yesterday"
    assert get_errors(item)
