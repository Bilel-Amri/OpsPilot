
"""Automated tests for the get_pod_status collector."""

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from kubernetes.client.exceptions import ApiException


MCP_DIR = Path(__file__).resolve().parents[2] / "mcp"
sys.path.insert(0, str(MCP_DIR))

import server


NOW = datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc)


def make_state(waiting=None, running=None, terminated=None):
    return SimpleNamespace(
        waiting=waiting,
        running=running,
        terminated=terminated,
    )


def make_terminated(reason="Error", exit_code=1):
    return SimpleNamespace(
        reason=reason,
        message="Container terminated",
        exit_code=exit_code,
        signal=None,
        started_at=NOW,
        finished_at=NOW,
    )


def make_pod(
    current_state=None,
    last_state=None,
    restart_count=0,
    ready=True,
    include_container_status=True,
):
    container_spec = SimpleNamespace(
        name="demo-app",
        image="opspilot-demo:0.1.0",
        image_pull_policy="IfNotPresent",
        resources=SimpleNamespace(
            requests={"cpu": "50m", "memory": "64Mi"},
            limits={"cpu": "250m", "memory": "128Mi"},
        ),
    )

    container_statuses = []

    if include_container_status:
        container_statuses.append(
            SimpleNamespace(
                name="demo-app",
                container_id="containerd://test-container",
                image="docker.io/library/opspilot-demo:0.1.0",
                image_id="sha256:test-image",
                ready=ready,
                started=True,
                restart_count=restart_count,
                state=current_state or make_state(),
                last_state=last_state or make_state(),
            )
        )

    return SimpleNamespace(
        metadata=SimpleNamespace(
            name="demo-api",
            namespace="opspilot-lab",
            uid="test-pod-uid",
            resource_version="12345",
            creation_timestamp=NOW,
        ),
        spec=SimpleNamespace(
            node_name="opspilot-control-plane",
            containers=[container_spec],
        ),
        status=SimpleNamespace(
            phase="Running",
            reason=None,
            message=None,
            pod_ip="10.244.0.5",
            host_ip="172.23.0.2",
            start_time=NOW,
            conditions=[],
            container_statuses=container_statuses,
        ),
    )


def install_fake_pod(monkeypatch, pod):
    """Replace Kubernetes API access with a controlled Pod response."""

    def read_pod(name, namespace):
        assert name == "demo-api"
        assert namespace == "opspilot-lab"
        return pod

    fake_api = SimpleNamespace(
        read_namespaced_pod=read_pod
    )

    monkeypatch.setattr(
        server,
        "get_core_v1_api",
        lambda: fake_api,
    )


def test_running_container(monkeypatch):
    pod = make_pod(
        current_state=make_state(
            running=SimpleNamespace(started_at=NOW)
        )
    )

    install_fake_pod(monkeypatch, pod)

    result = server.get_pod_status("demo-api")
    container = result["containers"][0]

    assert result["phase"] == "Running"
    assert result["pod_uid"] == "test-pod-uid"
    assert container["ready"] is True
    assert container["restart_count"] == 0
    assert container["state"]["type"] == "running"
    assert container["last_state"] is None


def test_crashloop_waiting_with_previous_termination(monkeypatch):
    pod = make_pod(
        current_state=make_state(
            waiting=SimpleNamespace(
                reason="CrashLoopBackOff",
                message="Back-off restarting failed container",
            )
        ),
        last_state=make_state(
            terminated=make_terminated("Error", 1)
        ),
        restart_count=5,
        ready=False,
    )

    install_fake_pod(monkeypatch, pod)

    result = server.get_pod_status("demo-api")
    container = result["containers"][0]

    assert container["state"]["type"] == "waiting"
    assert container["state"]["reason"] == "CrashLoopBackOff"
    assert container["last_state"]["type"] == "terminated"
    assert container["last_state"]["reason"] == "Error"
    assert container["last_state"]["exit_code"] == 1
    assert container["restart_count"] == 5


def test_image_pull_backoff(monkeypatch):
    pod = make_pod(
        current_state=make_state(
            waiting=SimpleNamespace(
                reason="ImagePullBackOff",
                message="Back-off pulling image",
            )
        ),
        restart_count=0,
        ready=False,
    )

    install_fake_pod(monkeypatch, pod)

    result = server.get_pod_status("demo-api")
    container = result["containers"][0]

    assert container["state"]["reason"] == "ImagePullBackOff"
    assert container["image"] == "opspilot-demo:0.1.0"
    assert container["last_state"] is None


def test_oomkilled_termination(monkeypatch):
    # 137 is a fixture value representing what Kubernetes reported.
    # The collector must preserve the API value, never invent it.
    pod = make_pod(
        current_state=make_state(
            terminated=make_terminated("OOMKilled", 137)
        ),
        ready=False,
    )

    install_fake_pod(monkeypatch, pod)

    result = server.get_pod_status("demo-api")
    container = result["containers"][0]

    assert container["state"]["type"] == "terminated"
    assert container["state"]["reason"] == "OOMKilled"
    assert container["state"]["exit_code"] == 137
    assert container["resources"]["limits"]["memory"] == "128Mi"


def test_missing_runtime_container_status(monkeypatch):
    pod = make_pod(include_container_status=False)

    install_fake_pod(monkeypatch, pod)

    result = server.get_pod_status("demo-api")
    container = result["containers"][0]

    assert container["name"] == "demo-app"
    assert container["container_id"] is None
    assert container["ready"] is None
    assert container["restart_count"] is None
    assert container["state"] is None
    assert container["last_state"] is None


def test_forbidden_api_request_is_reported(monkeypatch):
    def forbidden(name, namespace):
        raise ApiException(status=403, reason="Forbidden")

    fake_api = SimpleNamespace(
        read_namespaced_pod=forbidden
    )

    monkeypatch.setattr(
        server,
        "get_core_v1_api",
        lambda: fake_api,
    )

    with pytest.raises(RuntimeError, match="HTTP 403, Forbidden"):
        server.get_pod_status("demo-api")
