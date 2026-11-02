"""Basic validation 3/3 — scenario contracts and deployment manifests.

Each scenario.yaml is the contract for observers/EQG (S3) and records which
absence is critical per the spec §10.6 matrix. The deployments must follow the
reproducibility decisions documented in their headers (SC-02 must stay
offline-reproducible via imagePullPolicy: Never).
"""
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = REPO_ROOT / "scenarios"

MANDATORY_SCENARIOS = {
    "sc-01-crashloopbackoff": {"scenario_id": "SC-01", "family": "crashloopbackoff"},
    "sc-02-imagepullbackoff": {"scenario_id": "SC-02", "family": "imagepullbackoff"},
    "sc-04-oomkilled": {"scenario_id": "SC-04", "family": "oomkilled"},
}


def _yaml(path: Path):
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_all_three_mandatory_scenarios_exist_with_contract_and_deployment():
    for dirname in MANDATORY_SCENARIOS:
        d = SCENARIOS / dirname
        assert (d / "deployment.yaml").is_file(), f"missing deployment for {dirname}"
        assert (d / "scenario.yaml").is_file(), f"missing contract for {dirname}"


def test_sc_contracts_match_mandatory_families():
    for dirname, ids in MANDATORY_SCENARIOS.items():
        contract = _yaml(SCENARIOS / dirname / "scenario.yaml")
        assert contract["scenario_id"] == ids["scenario_id"]
        assert contract["family"] == ids["family"]
        assert contract["required_observations"], "contract must declare required observations"


def test_sc02_contract_contains_no_app_log_expectation_without_note():
    """For SC-02 the container never starts: no application logs are expected, and
    the contract must say so instead of instructing collectors to expect some
    (spec §10.6 row 2)."""
    contract = _yaml(SCENARIOS / "sc-02-imagepullbackoff" / "scenario.yaml")
    log_fields = [o for o in contract["required_observations"] if o["field"].startswith("logs_")]
    assert log_fields, "contract should discuss log absence explicitly"
    for field in log_fields:
        assert field.get("note"), f"logs field {field['field']} must carry an absence note for SC-02"
        assert "never start" in field["note"] or "not expected" in field["note"].lower() or "absence" in field["note"].lower()


def test_sc04_contract_states_exit_code_must_be_observed():
    """SC-04: exit code 137 must be OBSERVED, never presumed (spec §10.6 row 3)."""
    contract = _yaml(SCENARIOS / "sc-04-oomkilled" / "scenario.yaml")
    exit_fields = [o for o in contract["required_observations"] if o["field"] == "exit_code"]
    assert exit_fields, "SC-04 contract must declare the exit_code field"
    note = " ".join(str(o.get("note", "")) for o in exit_fields).lower()
    assert "never" in note or "not presumed" in note, "exit code note must forbid presuming 137"


def test_deployment_images_follow_the_reproducibility_decisions():
    d01 = _yaml(SCENARIOS / "sc-01-crashloopbackoff" / "deployment.yaml")
    c01 = d01["spec"]["template"]["spec"]["containers"][0]
    assert c01["image"] == "opspilot/demo-app:s1"
    assert c01["imagePullPolicy"] == "IfNotPresent"
    assert c01["env"][0] == {"name": "SCENARIO", "value": "crashloop"}

    d02 = _yaml(SCENARIOS / "sc-02-imagepullbackoff" / "deployment.yaml")
    c02 = d02["spec"]["template"]["spec"]["containers"][0]
    assert c02["imagePullPolicy"] == "Never"
    assert "never-built" in c02["image"]

    d04 = _yaml(SCENARIOS / "sc-04-oomkilled" / "deployment.yaml")
    c04 = d04["spec"]["template"]["spec"]["containers"][0]
    assert c04["env"][0] == {"name": "SCENARIO", "value": "oom"}
    # SC-04 must have a memory limit: the OOM kill depends on it (spec §10.6 row 3)
    assert "memory" in c04["resources"]["limits"]


def test_all_scenario_workloads_live_in_the_lab_namespace():
    for path in SCENARIOS.rglob("deployment.yaml"):
        doc = _yaml(path)
        assert doc["metadata"]["namespace"] == "opspilot-lab", f"{path.name} must target opspilot-lab"
