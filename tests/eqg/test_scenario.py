import pytest

from eqg.scenario import ScenarioContractError, validate_scenario
from tests.eqg.helpers import small_scenario


def test_valid_scenario_contract_is_accepted():
    assert validate_scenario(small_scenario())["scenario_id"] == "SC-TEST"


def test_unknown_source_type_is_rejected():
    scenario = small_scenario()
    scenario["required_observations"][0]["source_type"] = "random_source"
    with pytest.raises(ScenarioContractError):
        validate_scenario(scenario)


def test_invalid_absence_policy_is_rejected():
    scenario = small_scenario()
    scenario["required_observations"][0]["absence_policy"] = "ignore-all"
    with pytest.raises(ScenarioContractError):
        validate_scenario(scenario)
from pathlib import Path


def test_all_three_ops_pilot_example_scenarios_load():
    root = Path(__file__).parents[2] / "examples" / "scenarios"
    paths = [
        root / "sc-01-crashloopbackoff" / "scenario.yaml",
        root / "sc-02-imagepullbackoff" / "scenario.yaml",
        root / "sc-04-oomkilled" / "scenario.yaml",
    ]
    for path in paths:
        assert validate_scenario(__import__("yaml").safe_load(path.read_text(encoding="utf-8")))
