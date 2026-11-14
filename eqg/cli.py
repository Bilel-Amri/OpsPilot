"""Run EQG from JSON snapshot + scenario YAML files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import evaluate_snapshot
from .freshness import FreshnessPolicy


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate one OpsPilot EvidenceSnapshot.")
    parser.add_argument("--scenario", required=True, help="Path to scenario YAML contract")
    parser.add_argument("--snapshot", required=True, help="Path to JSON snapshot including evidence_items")
    parser.add_argument("--pod-uid", help="Expected Pod UID for this incident")
    parser.add_argument("--max-age-pod-status", type=int)
    parser.add_argument("--max-age-pod-spec", type=int)
    parser.add_argument("--max-age-pod-logs", type=int)
    parser.add_argument("--max-age-events", type=int)
    args = parser.parse_args()

    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    max_ages = {}
    for source, value in (
        ("pod_status", args.max_age_pod_status),
        ("pod_spec", args.max_age_pod_spec),
        ("pod_logs", args.max_age_pod_logs),
        ("events", args.max_age_events),
    ):
        if value is not None:
            max_ages[source] = value
    policy = FreshnessPolicy(max_age_seconds_by_source=max_ages, expected_pod_uid=args.pod_uid)
    result = evaluate_snapshot(snapshot, args.scenario, freshness_policy=policy)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
