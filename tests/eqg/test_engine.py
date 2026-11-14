from copy import deepcopy

from eqg import FreshnessPolicy, evaluate_snapshot
from eqg.hashing import calculate_payload_hash
from tests.eqg.helpers import crashloop_payload, make_item, make_snapshot, small_scenario


def base_items():
    status = make_item("E-001", "pod_status", "get_pod_status", crashloop_payload())
    logs = make_item("E-002", "pod_logs", "get_pod_logs", {"previous": True, "available": True, "logs": "startup failed"})
    return [status, logs]


def test_complete_evidence_returns_sufficient():
    items = base_items()
    result = evaluate_snapshot(make_snapshot(items), small_scenario(), freshness_policy=FreshnessPolicy(max_age_seconds_by_source={"pod_status": 600, "pod_logs": 600}))
    assert result.decision == "SUFFICIENT"
    assert result.permission.startswith("confirmed_diagnosis_allowed")


def test_missing_critical_observation_returns_partial_not_invalid_provenance():
    scenario = small_scenario()
    items = [make_item("E-001", "pod_status", "get_pod_status", {"pod": {"name": "demo-api", "uid": "pod-uid-1", "namespace": "opspilot-lab", "phase": "Running"}})]
    result = evaluate_snapshot(make_snapshot(items), scenario)
    assert result.decision == "PARTIAL"
    assert any(issue.code == "CRITICAL_OBSERVATION_MISSING" for issue in result.issues)


def test_optional_absence_does_not_make_evidence_partial():
    scenario = small_scenario()
    scenario["required_observations"][-1]["absence_policy"] = "allowed"
    items = [make_item("E-001", "pod_status", "get_pod_status", crashloop_payload())]
    result = evaluate_snapshot(make_snapshot(items), scenario, freshness_policy=FreshnessPolicy(max_age_seconds_by_source={"pod_status": 600}))
    assert result.decision == "SUFFICIENT"


def test_expected_absence_passes_when_absent():
    scenario = {
        "scenario_id": "SC-02-TEST", "title": "Image pull", "family": "imagepullbackoff",
        "required_observations": [
            {"field": "logs_current", "source_type": "pod_logs", "criticality": "expected", "expected_absence": True, "absence_policy": "allowed"}
        ],
    }
    items = [make_item("E-001", "pod_status", "get_pod_status", {"pod": {"name": "demo-api", "uid": "pod-uid-1", "namespace": "opspilot-lab", "phase": "Pending"}})]
    result = evaluate_snapshot(make_snapshot(items), scenario, freshness_policy=FreshnessPolicy(max_age_seconds_by_source={"pod_status": 600}))
    assert result.decision == "SUFFICIENT"


def test_unexpected_logs_when_absence_is_expected_returns_conflicted():
    scenario = {
        "scenario_id": "SC-02-TEST", "title": "Image pull", "family": "imagepullbackoff",
        "required_observations": [
            {"field": "logs_current", "source_type": "pod_logs", "criticality": "expected", "expected_absence": True, "absence_policy": "allowed"}
        ],
    }
    items = [
        make_item("E-001", "pod_status", "get_pod_status", {"pod": {"name": "demo-api", "uid": "pod-uid-1", "namespace": "opspilot-lab", "phase": "Pending"}}),
        make_item("E-002", "pod_logs", "get_pod_logs", {"previous": False, "available": True, "logs": "application started"}),
    ]
    result = evaluate_snapshot(make_snapshot(items), scenario)
    assert result.decision == "CONFLICTED"
    assert any(issue.code == "UNEXPECTED_EVIDENCE_PRESENT" for issue in result.issues)


def test_hash_mismatch_returns_invalid_provenance():
    items = base_items()
    items[0]["payload"]["pod"]["phase"] = "Failed"  # Do not recompute the hash.
    result = evaluate_snapshot(make_snapshot(items), small_scenario())
    assert result.decision == "INVALID_PROVENANCE"
    assert any(issue.code == "PAYLOAD_HASH_MISMATCH" for issue in result.issues)


def test_incident_mismatch_returns_invalid_provenance():
    items = base_items()
    items[0]["incident_id"] = "INC-OTHER"
    result = evaluate_snapshot(make_snapshot(items), small_scenario())
    assert result.decision == "INVALID_PROVENANCE"
    assert any(issue.code == "INCIDENT_ID_MISMATCH" for issue in result.issues)


def test_old_evidence_with_configured_max_age_returns_stale():
    items = [make_item("E-001", "pod_status", "get_pod_status", crashloop_payload(), collected_at="2026-11-12T23:00:00Z")]
    result = evaluate_snapshot(make_snapshot(items), small_scenario(), freshness_policy=FreshnessPolicy(max_age_seconds_by_source={"pod_status": 300}))
    assert result.decision == "STALE"
    assert any(issue.code == "EVIDENCE_TOO_OLD" for issue in result.issues)


def test_wrong_pod_uid_returns_stale():
    items = base_items()
    result = evaluate_snapshot(make_snapshot(items), small_scenario(), freshness_policy=FreshnessPolicy(expected_pod_uid="a-different-uid"))
    assert result.decision == "STALE"
    assert any(issue.code == "POD_UID_NOT_CURRENT" for issue in result.issues)


def test_two_different_pod_uids_for_same_pod_name_returns_stale():
    first = make_item("E-001", "pod_status", "get_pod_status", crashloop_payload())
    second_payload = crashloop_payload()
    second_payload["pod"]["uid"] = "pod-uid-2"
    second = make_item("E-002", "pod_status", "get_pod_status", second_payload, pod_uid="pod-uid-2", collected_at="2026-11-13T00:00:01Z")
    result = evaluate_snapshot(make_snapshot([first, second]), small_scenario())
    assert result.decision == "STALE"
    assert any(issue.code == "MULTIPLE_POD_UIDS_FOR_NAME" for issue in result.issues)


def test_same_time_conflicting_container_wait_reason_returns_conflicted():
    first = make_item("E-001", "pod_status", "get_pod_status", crashloop_payload())
    second_payload = crashloop_payload()
    second_payload["containers"][0]["state"]["waiting"]["reason"] = "ImagePullBackOff"
    second = make_item("E-002", "pod_status", "get_pod_status", second_payload, collected_at="2026-11-13T00:00:01Z")
    result = evaluate_snapshot(make_snapshot([first, second]), small_scenario())
    assert result.decision == "CONFLICTED"
    assert any(issue.code == "CONTRADICTORY_OBSERVATIONS" for issue in result.issues)


def test_running_pod_with_waiting_crashloop_is_not_a_conflict():
    items = [make_item("E-001", "pod_status", "get_pod_status", crashloop_payload())]
    result = evaluate_snapshot(make_snapshot(items), small_scenario())
    assert result.decision == "PARTIAL"  # previous logs are missing, not a consistency failure
    assert result.dimensions["consistency"].status == "pass"


def test_resource_version_is_not_used_as_a_clock():
    items = base_items()
    items[0]["resource_version"] = "999999999999"
    items[1]["resource_version"] = "1"
    result = evaluate_snapshot(make_snapshot(items), small_scenario(), freshness_policy=FreshnessPolicy(max_age_seconds_by_source={"pod_status": 600, "pod_logs": 600}))
    assert result.decision == "SUFFICIENT"


def test_naive_collected_at_is_invalid_provenance():
    items = base_items()
    items[0]["collected_at"] = "2026-11-13T00:00:00"
    result = evaluate_snapshot(make_snapshot(items), small_scenario())
    assert result.decision == "INVALID_PROVENANCE"
    assert any(issue.code == "COLLECTED_AT_INVALID" for issue in result.issues)


def test_source_tool_mismatch_is_invalid_provenance():
    items = base_items()
    items[1]["tool_name"] = "get_pod_status"
    items[1]["payload_hash"] = calculate_payload_hash(items[1]["payload"])
    snapshot = make_snapshot(items)
    result = evaluate_snapshot(snapshot, small_scenario())
    assert result.decision == "INVALID_PROVENANCE"
    assert any(issue.code == "TOOL_SOURCE_MISMATCH" for issue in result.issues)


def test_restart_count_time_window_requires_multiple_timestamped_observations():
    scenario = small_scenario()
    scenario["required_observations"] = [
        {"field": "restart_count", "source_type": "pod_status", "expected_condition": ">= 3 within ~3 minutes", "criticality": "critical"}
    ]
    one = make_item("E-001", "pod_status", "get_pod_status", crashloop_payload(3))
    result = evaluate_snapshot(make_snapshot([one]), scenario)
    assert result.decision == "PARTIAL"
    assert any(issue.code == "TEMPORAL_CONDITION_UNVERIFIABLE" for issue in result.issues)


def test_restart_count_threshold_crossing_within_window_is_sufficient():
    scenario = small_scenario()
    scenario["required_observations"] = [
        {"field": "restart_count", "source_type": "pod_status", "expected_condition": ">= 3 within ~3 minutes", "criticality": "critical"}
    ]
    first = make_item("E-001", "pod_status", "get_pod_status", crashloop_payload(2), collected_at="2026-11-13T00:00:00Z")
    second = make_item("E-002", "pod_status", "get_pod_status", crashloop_payload(3), collected_at="2026-11-13T00:02:00Z")
    result = evaluate_snapshot(make_snapshot([first, second]), scenario, freshness_policy=FreshnessPolicy(max_age_seconds_by_source={"pod_status": 600}))
    assert result.decision == "SUFFICIENT"


def test_event_without_matching_involved_object_uid_is_not_linked_to_pod():
    scenario = {
        "scenario_id": "SC-EVENT", "title": "Event linkage", "family": "imagepullbackoff",
        "required_observations": [
            {"field": "linked_events", "source_type": "events", "criticality": "critical", "expected_value": "ErrImagePull"}
        ],
    }
    item = make_item("E-001", "events", "get_recent_events", {
        "events": [{"reason": "ErrImagePull", "message": "pull failed", "involvedObject": {"kind": "Pod", "name": "demo-api"}}]
    })
    result = evaluate_snapshot(make_snapshot([item]), scenario)
    assert result.decision == "PARTIAL"
    assert any(issue.code == "CRITICAL_OBSERVATION_MISSING" for issue in result.issues)


def test_event_with_matching_involved_object_uid_is_linked():
    scenario = {
        "scenario_id": "SC-EVENT", "title": "Event linkage", "family": "imagepullbackoff",
        "required_observations": [
            {"field": "linked_events", "source_type": "events", "criticality": "critical", "expected_value": "ErrImagePull"}
        ],
    }
    item = make_item("E-001", "events", "get_recent_events", {
        "events": [{"reason": "ErrImagePull", "message": "pull failed", "involvedObject": {"kind": "Pod", "name": "demo-api", "uid": "pod-uid-1"}}]
    })
    result = evaluate_snapshot(make_snapshot([item]), scenario, freshness_policy=FreshnessPolicy(max_age_seconds_by_source={"events": 600}))
    assert result.decision == "SUFFICIENT"


def test_missing_source_specific_freshness_policy_blocks_sufficient_decision():
    items = base_items()
    result = evaluate_snapshot(make_snapshot(items), small_scenario(), freshness_policy=FreshnessPolicy(max_age_seconds_by_source={"pod_status": 600}))
    assert result.decision == "PARTIAL"
    assert any(issue.code == "FRESHNESS_POLICY_MISSING" for issue in result.issues)
