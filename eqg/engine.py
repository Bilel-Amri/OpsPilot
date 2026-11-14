"""Main deterministic Evidence Quality Gate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .completeness import evaluate_completeness
from .consistency import evaluate_consistency
from .freshness import FreshnessPolicy, evaluate_freshness
from .models import DimensionResult, EQGReport, Issue
from .provenance import validate_provenance
from .scenario import load_scenario, validate_scenario

DECISION_PRIORITY = (
    "INVALID_PROVENANCE",
    "CONFLICTED",
    "STALE",
    "PARTIAL",
    "SUFFICIENT",
)
PERMISSIONS = {
    "SUFFICIENT": "confirmed_diagnosis_allowed_subject_to_claim_validation",
    "PARTIAL": "tentative_hypotheses_only",
    "STALE": "request_new_evidence_collection",
    "CONFLICTED": "abstain_on_disputed_cause",
    "INVALID_PROVENANCE": "reject_invalid_evidence_and_block_confirmation",
}
EXPLANATIONS = {
    "SUFFICIENT": "All critical scenario observations passed the configured provenance, completeness, freshness and consistency checks.",
    "PARTIAL": "Some expected or critical scenario observations are missing, unavailable or not fully verifiable. Only cautious hypotheses are allowed.",
    "STALE": "Evidence cannot be reliably linked to the current incident window or Pod/container instance. Collect fresh evidence before confirming a diagnosis.",
    "CONFLICTED": "Critical observations disagree for the same resource identity and time window. Abstain on the disputed cause until the conflict is resolved.",
    "INVALID_PROVENANCE": "At least one evidence item has missing or invalid source, identity, timestamp, snapshot linkage or payload-integrity metadata. Invalid evidence must not support a confirmed diagnosis.",
}


def _normalize_snapshot(snapshot: dict[str, Any], evidence_items: list[dict[str, Any]] | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(snapshot, dict):
        raise TypeError("snapshot must be a dictionary")
    items = evidence_items
    if items is None:
        items = snapshot.get("evidence_items")
    if items is None:
        items = snapshot.get("evidence")
    if items is None:
        items = []
    if not isinstance(items, list):
        raise TypeError("evidence_items must be a list")
    return snapshot, items


def evaluate_snapshot(
    snapshot: dict[str, Any],
    scenario: dict[str, Any] | str | Path,
    evidence_items: list[dict[str, Any]] | None = None,
    freshness_policy: FreshnessPolicy | None = None,
) -> EQGReport:
    """Evaluate one frozen incident snapshot against one scenario contract.

    `scenario` may be a loaded YAML dictionary or a path to a scenario YAML file.
    Evidence can be supplied separately or inside snapshot['evidence_items'].
    """
    scenario_data = load_scenario(scenario) if isinstance(scenario, (str, Path)) else validate_scenario(scenario)
    snapshot_data, items = _normalize_snapshot(snapshot, evidence_items)

    provenance_issues, provenance_checks = validate_provenance(snapshot_data, items)
    completeness_issues, completeness_checks = evaluate_completeness(scenario_data, items)
    freshness_issues, freshness_checks, freshness_note = evaluate_freshness(snapshot_data, items, freshness_policy)
    consistency_issues, consistency_checks = evaluate_consistency(items)

    dimensions = {
        "provenance": DimensionResult("fail" if provenance_issues else "pass", provenance_checks, provenance_issues),
        "completeness": DimensionResult("fail" if any(i.severity in {"block", "conflict"} for i in completeness_issues) else ("warning" if completeness_issues else "pass"), completeness_checks, completeness_issues),
        "freshness": DimensionResult(
            "fail" if any(issue.severity == "stale" for issue in freshness_issues)
            else ("warning" if freshness_issues else (
                "pass" if freshness_policy and (
                    freshness_policy.max_age_seconds_by_source or freshness_policy.expected_pod_uid
                    or freshness_policy.expected_container_id or freshness_policy.incident_window_start
                    or freshness_policy.incident_window_end
                ) else "not_evaluated"
            )),
            freshness_checks, freshness_issues,
        ),
        "consistency": DimensionResult("fail" if consistency_issues else "pass", consistency_checks, consistency_issues),
    }

    all_issues = provenance_issues + completeness_issues + freshness_issues + consistency_issues
    if any(issue.severity == "invalid" for issue in provenance_issues):
        decision = "INVALID_PROVENANCE"
    elif any(issue.severity == "conflict" for issue in all_issues):
        decision = "CONFLICTED"
    elif any(issue.severity == "stale" for issue in all_issues):
        decision = "STALE"
    elif completeness_issues or any(issue.severity == "warning" for issue in all_issues):
        decision = "PARTIAL"
    else:
        decision = "SUFFICIENT"

    next_steps: list[str] = []
    if decision == "INVALID_PROVENANCE":
        next_steps.append("Reject or recollect evidence with valid source, identity, timestamps and SHA-256 payload hashes.")
    if decision == "CONFLICTED":
        next_steps.append("Show the conflicting observations and recollect status/events for the same Pod UID and container instance.")
    if decision == "STALE":
        next_steps.append("Collect a new read-only snapshot and bind every observation to the current Pod UID and incident window.")
    if decision == "PARTIAL":
        next_steps.append("Collect the missing observations where possible; otherwise state the limitation and keep conclusions tentative.")
    if decision == "SUFFICIENT":
        next_steps.append("Continue to version-filtered RAG and LLM report generation, then run deterministic claim/citation validation.")
    if not freshness_checks[0]["evaluated"]:
        next_steps.append("Configure scenario/source-specific freshness thresholds before using age-based freshness as an acceptance criterion.")

    explanation = EXPLANATIONS[decision]
    if freshness_note:
        explanation += " " + freshness_note

    return EQGReport(
        scenario_id=str(scenario_data["scenario_id"]),
        snapshot_id=str(snapshot_data.get("snapshot_id", "")),
        incident_id=str(snapshot_data.get("incident_id", "")),
        decision=decision,
        permission=PERMISSIONS[decision],
        explanation=explanation,
        dimensions=dimensions,
        issues=all_issues,
        recommended_next_steps=next_steps,
    )
