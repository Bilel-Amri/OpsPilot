"""Basic validation 1/3 — YAML validity and static demo-app sanity.

Runs WITHOUT any cluster and without network access (spec §16.4: no implicit
network calls in unit tests). See tests/README.md for suite coverage.
Run: python -m pytest tests/ -v
"""
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_k8s_yaml(path: Path):
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_kind_config_is_valid_and_pins_a_node_image():
    cfg = _load_k8s_yaml(REPO_ROOT / "k8s" / "kind-config.yaml")
    assert cfg["apiVersion"] == "kind.x-k8s.io/v1alpha4"
    assert cfg["kind"] == "Cluster"
    # Node version must be pinned (spec §4.4). The candidate pin is verified at G0.
    nodes = cfg["nodes"]
    assert nodes, "kind config must declare at least one node"
    for node in nodes:
        assert node.get("image"), "every node must pin a node image"


def test_all_k8s_yaml_files_parse():
    yaml_files = (
        sorted(REPO_ROOT.glob("*.yaml"))
        + sorted((REPO_ROOT / "k8s").rglob("*.yaml"))
        + sorted((REPO_ROOT / "scenarios").rglob("*.yaml"))
    )
    assert len(yaml_files) >= 10, f"expected a full config tree, found {len(yaml_files)} files"
    for path in yaml_files:
        doc = _load_k8s_yaml(path)
        assert isinstance(doc, dict), f"{path} did not parse to a mapping"


def test_demo_app_is_not_the_backend():
    """The demo app is a lab component; it must not pretend to be the project
    backend, and no backend skeleton exists yet (no placeholder modules)."""
    demo = (REPO_ROOT / "demo-app" / "app.py").read_text(encoding="utf-8")
    assert "not the project backend" in demo
    assert not (REPO_ROOT / "backend").exists(), "backend/ must not be created before S5"


def test_demo_app_supports_the_three_scenarios():
    demo = (REPO_ROOT / "demo-app" / "app.py").read_text(encoding="utf-8")
    for behavior in ("healthy", "crashloop", "oom"):
        assert behavior in demo, f"demo app must support the '{behavior}' behavior"
