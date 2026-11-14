"""Configurable freshness and incident-instance checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .models import Issue
from .time_utils import parse_timestamp


@dataclass
class FreshnessPolicy:
    """No universal TTL is imposed; configure limits per source/scenario."""
    max_age_seconds_by_source: Mapping[str, int] = field(default_factory=dict)
    expected_pod_uid: str | None = None
    expected_container_id: str | None = None
    incident_window_start: str | None = None
    incident_window_end: str | None = None
    allowed_clock_skew_seconds: int = 120


def evaluate_freshness(snapshot: dict[str, Any], evidence_items: list[dict[str, Any]], policy: FreshnessPolicy | None = None) -> tuple[list[Issue], list[dict[str, Any]], str]:
    policy = policy or FreshnessPolicy()
    issues: list[Issue] = []
    checks: list[dict[str, Any]] = []
    captured = parse_timestamp(snapshot.get("captured_at"))
    window_start = parse_timestamp(policy.incident_window_start)
    window_end = parse_timestamp(policy.incident_window_end)

    configured_sources = set(policy.max_age_seconds_by_source)
    observed_sources = {
        item.get("source_type") for item in evidence_items
        if isinstance(item.get("source_type"), str) and item.get("source_type")
    }
    missing_policy_sources = sorted(observed_sources - configured_sources)
    for source in missing_policy_sources:
        source_items = [
            str(item.get("evidence_id")) for item in evidence_items
            if item.get("source_type") == source and item.get("evidence_id")
        ]
        issues.append(Issue(
            "FRESHNESS_POLICY_MISSING", "freshness", "warning",
            f"No maximum evidence age is configured for source '{source}'. "
            "Configure a scenario/source-specific threshold before treating freshness as verified.",
            source_items,
        ))

    for item in evidence_items:
        eid = str(item.get("evidence_id", ""))
        source = item.get("source_type")
        collected = parse_timestamp(item.get("collected_at"))
        if collected is None or captured is None:
            continue  # Provenance dimension reports invalid timestamps.
        age = captured.timestamp() - collected.timestamp()
        max_age = policy.max_age_seconds_by_source.get(source)
        if max_age is not None and age > max_age:
            issues.append(Issue("EVIDENCE_TOO_OLD", "freshness", "stale",
                                f"Evidence age ({int(age)}s) exceeds the configured {max_age}s limit for '{source}'.", [eid] if eid else []))
        if policy.expected_pod_uid and source in {"pod_status", "pod_spec", "pod_logs", "events"}:
            if item.get("pod_uid") != policy.expected_pod_uid:
                issues.append(Issue("POD_UID_NOT_CURRENT", "freshness", "stale",
                                    "Evidence belongs to a different Pod UID than the incident's expected Pod instance.", [eid] if eid else []))
        if policy.expected_container_id and source == "pod_logs":
            actual_container_id = item.get("container_id")
            if actual_container_id and actual_container_id != policy.expected_container_id:
                issues.append(Issue("CONTAINER_ID_NOT_CURRENT", "freshness", "stale",
                                    "Logs belong to a different container instance.", [eid] if eid else []))
        # Previous-container logs are not rejected merely because their content
        # predates the current container. Their collection time is what matters.
        if window_start and source != "pod_logs":
            observed = parse_timestamp(item.get("observed_at"))
            if observed and observed < window_start:
                issues.append(Issue("OBSERVATION_BEFORE_INCIDENT", "freshness", "stale",
                                    "Observation timestamp is before the configured incident window.", [eid] if eid else []))
        if window_end:
            observed = parse_timestamp(item.get("observed_at"))
            if observed and observed > window_end:
                issues.append(Issue("OBSERVATION_AFTER_INCIDENT", "freshness", "stale",
                                    "Observation timestamp is after the configured incident window.", [eid] if eid else []))
        if age < -policy.allowed_clock_skew_seconds:
            issues.append(Issue("COLLECTION_AFTER_SNAPSHOT", "freshness", "stale",
                                "Evidence collection time is later than snapshot capture time.", [eid] if eid else []))

    evaluated = bool(policy.max_age_seconds_by_source or policy.expected_pod_uid or policy.expected_container_id or window_start or window_end or missing_policy_sources)
    checks.append({
        "code": "freshness_policy",
        "passed": not issues,
        "evaluated": evaluated,
        "configured_max_age_seconds_by_source": dict(policy.max_age_seconds_by_source),
        "sources_missing_age_policy": missing_policy_sources,
        "expected_pod_uid_configured": bool(policy.expected_pod_uid),
        "incident_window_configured": bool(window_start or window_end),
    })
    has_stale_issue = any(issue.severity == "stale" for issue in issues)
    status = "fail" if has_stale_issue else ("warning" if issues else ("pass" if evaluated else "not_evaluated"))
    if missing_policy_sources:
        note = "Freshness is only partially configured: every observed source needs an explicit age threshold or a documented source-specific freshness rule."
    else:
        note = "Freshness was checked using configured policy." if evaluated else "Timestamp format was checked under provenance, but no age/window/expected-UID policy was supplied; age-based freshness is not evaluated."
    return issues, checks, note
