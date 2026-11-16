
"""Automated tests for the Kubernetes get_pod_logs collector."""

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from kubernetes.client.exceptions import ApiException


MCP_DIR = Path(__file__).resolve().parents[2] / "mcp"
sys.path.insert(0, str(MCP_DIR))

import server


NOW = datetime.now(timezone.utc)


def make_pod(previous_terminated=False):
    terminated = None

    if previous_terminated:
        terminated = SimpleNamespace(
            reason="Error",
            exit_code=1,
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
            containers=[
                SimpleNamespace(name="api", image="demo-api:0.1")
            ],
            init_containers=[],
        ),
        status=SimpleNamespace(
            container_statuses=[
                SimpleNamespace(
                    name="api",
                    container_id="containerd://current-id",
                    restart_count=1 if previous_terminated else 0,
                    last_state=SimpleNamespace(
                        terminated=terminated
                    ),
                )
            ],
            init_container_statuses=[],
        ),
    )


def install_fake_api(monkeypatch, pod, log_text="line 1\nline 2\n"):
    calls = []

    def read_pod(name, namespace):
        assert name == "demo-api"
        assert namespace == "opspilot-lab"
        return pod

    def read_logs(**kwargs):
        calls.append(kwargs)
        return log_text

    fake_api = SimpleNamespace(
        read_namespaced_pod=read_pod,
        read_namespaced_pod_log=read_logs,
    )

    monkeypatch.setattr(
        server,
        "get_core_v1_api",
        lambda: fake_api,
    )

    return calls


def test_current_logs_are_collected_with_limits(monkeypatch):
    calls = install_fake_api(monkeypatch, make_pod())

    result = server.get_pod_logs(
        "demo-api",
        "api",
        tail_lines=50,
        timestamps=True,
        limit_bytes=8192,
    )

    assert result["collection_status"] == "success"
    assert result["logs_available"] is True
    assert result["logs"] == "line 1\nline 2\n"
    assert result["log_line_count"] == 2
    assert result["pod_uid"] == "test-pod-uid"

    assert calls[0]["previous"] is False
    assert calls[0]["container"] == "api"
    assert calls[0]["tail_lines"] == 50
    assert calls[0]["timestamps"] is True
    assert calls[0]["limit_bytes"] == 8192
    assert calls[0]["follow"] is False


def test_previous_logs_are_collected_after_termination(monkeypatch):
    calls = install_fake_api(
        monkeypatch,
        make_pod(previous_terminated=True),
        "previous failure\n",
    )

    result = server.get_pod_logs(
        "demo-api",
        "api",
        previous=True,
    )

    assert result["collection_status"] == "success"
    assert result["previous"] is True
    assert result["logs"] == "previous failure\n"
    assert calls[0]["previous"] is True


def test_previous_logs_without_previous_instance_are_unavailable(
    monkeypatch,
):
    calls = install_fake_api(monkeypatch, make_pod())

    result = server.get_pod_logs(
        "demo-api",
        "api",
        previous=True,
    )

    assert result["collection_status"] == "unavailable"
    assert result["logs_available"] is False
    assert result["logs"] is None
    assert result["availability_reason"] == (
        "no_previous_terminated_instance"
    )

    # Kubernetes log endpoint must not be called.
    assert calls == []


def test_successful_empty_log_is_not_collection_failure(monkeypatch):
    install_fake_api(
        monkeypatch,
        make_pod(),
        log_text="",
    )

    result = server.get_pod_logs("demo-api", "api")

    assert result["collection_status"] == "success"
    assert result["logs_available"] is True
    assert result["logs"] == ""
    assert result["log_line_count"] == 0


def test_unknown_container_is_rejected(monkeypatch):
    install_fake_api(monkeypatch, make_pod())

    with pytest.raises(ValueError, match="not found"):
        server.get_pod_logs("demo-api", "unknown-container")


def test_invalid_tail_limit_is_rejected(monkeypatch):
    install_fake_api(monkeypatch, make_pod())

    with pytest.raises(ValueError, match="between 1 and 500"):
        server.get_pod_logs(
            "demo-api",
            "api",
            tail_lines=501,
        )


def test_api_permission_error_is_reported(monkeypatch):
    pod = make_pod()

    fake_api = SimpleNamespace(
        read_namespaced_pod=lambda name, namespace: pod,
        read_namespaced_pod_log=lambda **kwargs: (
            _raise_forbidden()
        ),
    )

    monkeypatch.setattr(
        server,
        "get_core_v1_api",
        lambda: fake_api,
    )

    with pytest.raises(RuntimeError, match="HTTP 403, Forbidden"):
        server.get_pod_logs("demo-api", "api")


def _raise_forbidden():
    raise ApiException(status=403, reason="Forbidden")
