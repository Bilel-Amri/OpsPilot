"""Basic validation 2/3 — RBAC static security.

The Role must grant exactly the read-only verbs needed by the four MVP MCP tools
(spec §9.2) and NEVER touch secrets or any mutating verb (SEC-02/SEC-03/SEC-08).
These are STATIC guarantees; runtime refusals are verified with `kubectl auth
can-i` in scripts/create-cluster.ps1 (S1-01) and re-run in S2 before any LLM
integration (gate G2).
"""
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ALLOWED_VERBS = {"get", "list"}


def _yaml(path: Path):
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _role():
    return _yaml(REPO_ROOT / "k8s" / "rbac" / "role.yaml")


def test_role_resource_and_verb_map_matches_mcp_tools():
    rules = {tuple(r["resources"]): set(r["verbs"]) for r in _role()["rules"]}
    # Minimum permissions for the four MVP tools (spec §9.2)
    assert rules[("pods",)] >= {"get", "list"}
    assert rules[("pods/log",)] == {"get"}
    assert rules[("events",)] >= {"get", "list"}


def test_role_contains_no_write_verb_and_no_sensitive_resources():
    forbidden_resources = {"secrets", "configmaps", "pods/exec", "pods/attach", "pods/portforward"}
    forbidden_verbs = {
        "create", "update", "patch", "delete", "deletecollection",
        "watch", "proxy", "escalate", "bind", "impersonate",
    }
    for rule in _role()["rules"]:
        for res in rule["resources"]:
            assert res not in forbidden_resources, f"role unexpectedly grants {res}"
        for verb in rule["verbs"]:
            assert verb not in forbidden_verbs, f"role grants {verb} on {rule['resources']}"
        assert set(rule["verbs"]) <= ALLOWED_VERBS


def test_rolebinding_binds_dedicated_serviceaccount_inside_lab_namespace():
    role = _role()
    rb = _yaml(REPO_ROOT / "k8s" / "rbac" / "rolebinding.yaml")
    assert rb["metadata"]["namespace"] == "opspilot-lab"  # no cluster-wide binding
    subject = rb["subjects"][0]
    assert subject == {"kind": "ServiceAccount", "name": "opspilot-mcp", "namespace": "opspilot-lab"}
    assert rb["roleRef"]["name"] == role["metadata"]["name"]


def test_serviceaccount_lives_in_lab_namespace():
    sa = _yaml(REPO_ROOT / "k8s" / "rbac" / "serviceaccount.yaml")
    assert sa["metadata"]["name"] == "opspilot-mcp"
    assert sa["metadata"]["namespace"] == "opspilot-lab"
