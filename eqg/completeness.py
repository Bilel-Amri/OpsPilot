"""Scenario-driven completeness checks."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from .extractors import collect_field_values
from .models import Issue
from .time_utils import parse_timestamp

THRESHOLD_RE = re.compile(r"(>=|>|<=|<|==)\s*(\d+)")
WINDOW_RE = re.compile(r"(\d+)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)", re.IGNORECASE)


def _matches_expected(actual: Any, expected: Any) -> bool:
    if isinstance(actual, list):
        return any(_matches_expected(value, expected) for value in actual)
    if isinstance(actual, dict):
        # Event rule: expected value may match event reason or message.
        for key in ("reason", "message", "type"):
            if key in actual and _matches_expected(actual[key], expected):
                return True
        return False
    if isinstance(actual, str) and isinstance(expected, str):
        return actual.strip().lower() == expected.strip().lower()
    return actual == expected


def _condition_passes(value: Any, condition: Any) -> bool | None:
    if isinstance(condition, dict):
        operator = condition.get("operator")
        threshold = condition.get("value")
    elif isinstance(condition, str):
        match = THRESHOLD_RE.search(condition)
        if not match:
            return None
        operator, threshold = match.group(1), int(match.group(2))
    else:
        return None
    try:
        number = float(value)
        threshold_number = float(threshold)
    except (TypeError, ValueError):
        return False
    return {
        ">=": number >= threshold_number,
        ">": number > threshold_number,
        "<=": number <= threshold_number,
        "<": number < threshold_number,
        "==": number == threshold_number,
    }.get(operator)


def _window_seconds(condition: Any) -> int | None:
    if not isinstance(condition, str):
        return None
    match = WINDOW_RE.search(condition)
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2).lower()
    if unit.startswith(("sec", "s")):
        return amount
    if unit.startswith(("min", "m")):
        return amount * 60
    return amount * 3600


def _temporal_condition_proven(rule: dict[str, Any], evidence_items: list[dict[str, Any]], values: list[tuple[Any, dict[str, Any]]]) -> bool | None:
    """Prove a threshold was crossed within a window using repeated observations.

    One restartCount value cannot prove when those restarts happened. We require
    two timestamped observations showing the threshold crossing within the window.
    """
    window = _window_seconds(rule.get("expected_condition"))
    if window is None:
        return True
    observations: list[tuple[Any, float, str | None]] = []
    for value, item in values:
        collected = parse_timestamp(item.get("collected_at"))
        if collected is None:
            continue
        observations.append((value, collected.timestamp(), item.get("pod_uid")))
    observations.sort(key=lambda x: x[1])
    threshold_match = THRESHOLD_RE.search(str(rule.get("expected_condition", "")))
    threshold = int(threshold_match.group(2)) if threshold_match else None
    if threshold is None:
        return None
    for index, (first_value, first_time, first_uid) in enumerate(observations):
        try:
            first_number = int(first_value)
        except (TypeError, ValueError):
            continue
        for second_value, second_time, second_uid in observations[index + 1:]:
            if first_uid != second_uid:
                continue
            try:
                second_number = int(second_value)
            except (TypeError, ValueError):
                continue
            elapsed = second_time - first_time
            if first_number < threshold <= second_number and 0 <= elapsed <= window:
                return True
    return None


def evaluate_completeness(scenario: dict[str, Any], evidence_items: list[dict[str, Any]]) -> tuple[list[Issue], list[dict[str, Any]]]:
    issues: list[Issue] = []
    checks: list[dict[str, Any]] = []
    for rule in scenario["required_observations"]:
        field = rule["field"]
        source_type = rule["source_type"]
        criticality = rule["criticality"]
        matches = collect_field_values(field, source_type, evidence_items)
        values = [value for value, _ in matches]
        evidence_ids = [str(item.get("evidence_id")) for _, item in matches if item.get("evidence_id")]
        present = bool(matches)

        if rule.get("expected_absence") is True:
            passed = not present
            checks.append({"field": field, "source_type": source_type, "passed": passed, "expected_absence": True, "evidence_ids": evidence_ids})
            if present:
                issues.append(Issue(
                    "UNEXPECTED_EVIDENCE_PRESENT", "consistency", "conflict",
                    f"Scenario '{scenario['scenario_id']}' expects '{field}' to be absent, but evidence was collected.",
                    evidence_ids, field,
                ))
            continue

        if not present:
            allowed = rule.get("absence_policy") == "allowed" or rule.get("presence") == "optional"
            checks.append({"field": field, "source_type": source_type, "passed": allowed, "present": False, "evidence_ids": []})
            if not allowed:
                severity = "block" if criticality == "critical" else "warning"
                issues.append(Issue(
                    "CRITICAL_OBSERVATION_MISSING" if criticality == "critical" else "EXPECTED_OBSERVATION_MISSING",
                    "completeness", severity,
                    f"Required observation '{field}' from '{source_type}' is missing.", [], field,
                ))
            continue

        expected_value = rule.get("expected_value")
        if "expected_value" in rule and not any(_matches_expected(value, expected_value) for value in values):
            severity = "block" if criticality == "critical" else "warning"
            issues.append(Issue("EXPECTED_VALUE_MISMATCH", "completeness", severity,
                                f"Observation '{field}' does not match expected value {expected_value!r}.", evidence_ids, field))
            checks.append({"field": field, "source_type": source_type, "passed": False, "evidence_ids": evidence_ids})
            continue

        if "expected_condition" in rule:
            condition_results = [_condition_passes(value, rule["expected_condition"]) for value in values]
            if not any(result is True for result in condition_results):
                severity = "block" if criticality == "critical" else "warning"
                issues.append(Issue("EXPECTED_CONDITION_NOT_MET", "completeness", severity,
                                    f"Observation '{field}' does not satisfy {rule['expected_condition']!r}.", evidence_ids, field))
                checks.append({"field": field, "source_type": source_type, "passed": False, "evidence_ids": evidence_ids})
                continue
            temporal = _temporal_condition_proven(rule, evidence_items, matches)
            if temporal is None:
                issues.append(Issue("TEMPORAL_CONDITION_UNVERIFIABLE", "completeness", "warning",
                                    f"'{field}' meets the numeric threshold, but a single snapshot cannot prove the requested time window. Collect repeated timestamped observations.", evidence_ids, field))
                checks.append({"field": field, "source_type": source_type, "passed": False, "temporal_proof": "unavailable", "evidence_ids": evidence_ids})
                continue

        checks.append({"field": field, "source_type": source_type, "passed": True, "evidence_ids": evidence_ids})
    return issues, checks
