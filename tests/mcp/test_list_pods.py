"""Unit tests for the Kubernetes list_pods collector."""

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from kubernetes.client.exceptions import ApiException


# Import the local MCP server module.
MCP_DIR = Path(__file__).resolve().parents[2] / "mcp"
sys.path.insert(0, str(MCP_DIR))

import server


def make_pod():
    """Create a fake Kubernetes Pod response."""

    now = datetime(2026, 11, 14, 22, 30, tzinfo=timezone.utc)

    return SimpleNamespace(
        metadata=SimpleNamespace(
            name="demo-api",
            namespace="opspilot-lab",
            uid="test-pod-uid",
            resource_version="12345",
            creation_timestamp=now,
            labels={"app": "opspilot-demo"},
        ),
        spec=SimpleNamespace(
            node_name="opspilot-control-plane",
            containers=[
                SimpleNamespace(
                    name="demo-app",
                    image="opspilot-demo:0.1.0",
                )
            ],
        ),
        status=SimpleNamespace(
            pod_ip="10.244.0.5",
            phase="Running",
            start_time=now,
        ),
    )


def test_list_pods_returns_realistic_pod_metadata(monkeypatch):
    """The collector must preserve the important Pod identity fields."""

    fake_api = SimpleNamespace(
        list_namespaced_pod=lambda namespace: SimpleNamespace(
            items=[make_pod()]
        )
    )

    monkeypatch.setattr(
        server,
        "get_core_v1_api",
        lambda: fake_api,
    )

    result = server.list_pods()

    assert result["namespace"] == "opspilot-lab"
    assert result["pod_count"] == 1
    assert result["pods"][0]["name"] == "demo-api"
    assert result["pods"][0]["uid"] == "test-pod-uid"
    assert result["pods"][0]["phase"] == "Running"
    assert result["pods"][0]["resource_version"] == "12345"
    assert result["pods"][0]["containers"][0]["name"] == "demo-app"
    assert result["pods"][0]["labels"]["app"] == "opspilot-demo"
    assert result["collected_at"].endswith("Z")


def test_list_pods_handles_empty_namespace(monkeypatch):
    """An empty namespace must return an empty collection, not an error."""

    fake_api = SimpleNamespace(
        list_namespaced_pod=lambda namespace: SimpleNamespace(items=[])
    )

    monkeypatch.setattr(
        server,
        "get_core_v1_api",
        lambda: fake_api,
    )

    result = server.list_pods()

    assert result["pod_count"] == 0
    assert result["pods"] == []


def test_list_pods_reports_kubernetes_api_error(monkeypatch):
    """Forbidden or unavailable API requests must not look like empty results."""

    def fail_request(namespace):
        raise ApiException(status=403, reason="Forbidden")

    fake_api = SimpleNamespace(
        list_namespaced_pod=fail_request
    )

    monkeypatch.setattr(
        server,
        "get_core_v1_api",
        lambda: fake_api,
    )

    with pytest.raises(RuntimeError, match="HTTP 403, Forbidden"):
        server.list_pods()