"""Load and validate a scenario contract YAML file."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ALLOWED_CRITICALITY = {"critical", "expected"}
ALLOWED_SOURCE_TYPES = {"pod_status", "pod_spec", "pod_logs", "events", "manifest"}


class ScenarioContractError(ValueError):
    """Raised when a scenario YAML contract is missing required structure."""


def validate_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(scenario, dict):
        raise ScenarioContractError("Scenario root must be a YAML object.")
    for key in ("scenario_id", "title", "family", "required_observations"):
        if key not in scenario:
            raise ScenarioContractError(f"Scenario is missing required key: {key}")
    rules = scenario["required_observations"]
    if not isinstance(rules, list) or not rules:
        raise ScenarioContractError("required_observations must be a non-empty list.")

    seen: set[str] = set()
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise ScenarioContractError(f"Observation rule #{index + 1} must be an object.")
        for key in ("field", "source_type", "criticality"):
            if key not in rule:
                raise ScenarioContractError(f"Rule #{index + 1} is missing '{key}'.")
        field = rule["field"]
        source_type = rule["source_type"]
        criticality = rule["criticality"]
        if not isinstance(field, str) or not field.strip():
            raise ScenarioContractError(f"Rule #{index + 1} has an invalid field name.")
        if field in seen:
            raise ScenarioContractError(f"Duplicate observation field in scenario: {field}")
        seen.add(field)
        if source_type not in ALLOWED_SOURCE_TYPES:
            raise ScenarioContractError(
                f"Rule '{field}' uses unsupported source_type '{source_type}'."
            )
        if criticality not in ALLOWED_CRITICALITY:
            raise ScenarioContractError(
                f"Rule '{field}' criticality must be 'critical' or 'expected'."
            )
        if rule.get("absence_policy", "required") not in {"required", "allowed"}:
            raise ScenarioContractError(
                f"Rule '{field}' absence_policy must be 'required' or 'allowed'."
            )
    return scenario


def load_scenario(path: str | Path) -> dict[str, Any]:
    scenario_path = Path(path)
    if not scenario_path.is_file():
        raise FileNotFoundError(f"Scenario file not found: {scenario_path}")
    with scenario_path.open("r", encoding="utf-8-sig") as file:
        data = yaml.safe_load(file)
    return validate_scenario(data)
