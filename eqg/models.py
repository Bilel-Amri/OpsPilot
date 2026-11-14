"""Small result models used by all EQG dimensions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Issue:
    code: str
    dimension: str
    severity: str
    message: str
    evidence_ids: list[str] = field(default_factory=list)
    field: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DimensionResult:
    status: str
    checks: list[dict[str, Any]] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "checks": self.checks,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass
class EQGReport:
    scenario_id: str
    snapshot_id: str
    incident_id: str
    decision: str
    permission: str
    explanation: str
    dimensions: dict[str, DimensionResult]
    issues: list[Issue]
    recommended_next_steps: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "snapshot_id": self.snapshot_id,
            "incident_id": self.incident_id,
            "decision": self.decision,
            "permission": self.permission,
            "explanation": self.explanation,
            "dimensions": {
                name: result.to_dict() for name, result in self.dimensions.items()
            },
            "issues": [issue.to_dict() for issue in self.issues],
            "recommended_next_steps": self.recommended_next_steps,
        }
