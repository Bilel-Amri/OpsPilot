
"""Automated tests for the Kubernetes get_recent_events collector."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from kubernetes.client.exceptions import ApiException


MCP_DIR = Path(__file__).resolve().parents[2] / "mcp"
sys.path.insert(0, str(MCP_DIR))

import server


NOW = datetime.now(timezone.utc)


def make_event(
    name="demo-event",
    event_type="Warning",
    when=NOW,
    series=None,
    pod_name="demo-api",
):
    return SimpleNamespace(
        metadata=SimpleNamespace(
            name=name,
            namespace="opspilot-lab",
            uid=f"uid-{name}",
            resource_version="12345",
            creation_timestamp=NOW,
        ),
        type=event_type,
        reason="Failed",
        message="Demo event message",
        action="Pull",
        count=3,
        event_time=when,
        first_timestamp=when,
        last_timestamp=when,
        series=series,
        involved_object=SimpleNamespace(
            api_version="v1",
            kind="Pod",
            name=pod_name,
            namespace="opspilot-lab",
            uid="test-pod-uid",
            resource_version="123",
            field_path="spec.containers{api}",
        ),
        related=None,
        source=SimpleNamespace(
            component="kubelet",
            host="opspilot-control-plane",
        ),
        reporting_component="kubelet",
        reporting_instance="kubelet-node",
    )


def make_page(items, continue_token=None):
    return SimpleNamespace(
        items=items,
        metadata=SimpleNamespace(
            _continue=continue_token,
        ),
    )


def install_fake_api(monkeypatch, pages):
    calls = []

    def list_events(**kwargs):
        calls.append(kwargs)
        return pages[len(calls) - 1]

    fake_api = SimpleNamespace(
        list_namespaced_event=list_events,
    )

    monkeypatch.setattr(
        server,
        "get_core_v1_api",
        lambda: fake_api,
    )

    return calls


def test_event_metadata_and_timestamps_are_preserved(monkeypatch):
    series = SimpleNamespace(
        count=5,
        last_observed_time=NOW,
    )

    event = make_event(
        when=NOW - timedelta(minutes=10),
        series=series,
    )

    install_fake_api(
        monkeypatch,
        [make_page([event])],
    )

    result = server.get_recent_events(
        pod_name="demo-api",
        since_seconds=3600,
    )

    assert result["namespace"] == "opspilot-lab"
    assert result["events_returned"] == 1

    item = result["events"][0]

    assert item["event_uid"] == "uid-demo-event"
    assert item["reason"] == "Failed"
    assert item["type"] == "Warning"
    assert item["involved_object"]["uid"] == "test-pod-uid"

    # For an Event series, last_observed_time is preferred.
    assert item["event_timestamp_source"] == (
        "series.last_observed_time"
    )
    assert item["series_count"] == 5
    assert item["within_requested_window"] is True


def test_pod_and_event_type_filters_are_sent_to_kubernetes(monkeypatch):
    event = make_event(event_type="Warning")

    calls = install_fake_api(
        monkeypatch,
        [make_page([event])],
    )

    result = server.get_recent_events(
        pod_name="demo-api",
        event_type="warning",
    )

    assert result["event_type_filter"] == "Warning"

    selector = calls[0]["field_selector"]

    assert "involvedObject.name=demo-api" in selector
    assert "involvedObject.kind=Pod" in selector
    assert "type=Warning" in selector


def test_old_events_are_excluded_from_requested_window(monkeypatch):
    old_event = make_event(
        name="old-event",
        when=NOW - timedelta(hours=3),
    )

    recent_event = make_event(
        name="recent-event",
        when=NOW,
    )

    install_fake_api(
        monkeypatch,
        [make_page([old_event, recent_event])],
    )

    result = server.get_recent_events(since_seconds=3600)

    assert result["events_scanned"] == 2
    assert result["events_returned"] == 1
    assert result["events"][0]["event_name"] == "recent-event"


def test_unknown_event_timestamp_is_preserved(monkeypatch):
    event = make_event(when=None)

    install_fake_api(
        monkeypatch,
        [make_page([event])],
    )

    result = server.get_recent_events()

    item = result["events"][0]

    assert item["event_timestamp"] is None
    assert item["within_requested_window"] is None
    assert result["events_with_unknown_timestamp"] == 1


def test_event_pagination_collects_multiple_pages(monkeypatch):
    first_event = make_event(name="first")
    second_event = make_event(name="second")

    calls = install_fake_api(
        monkeypatch,
        [
            make_page([first_event], continue_token="next-page"),
            make_page([second_event]),
        ],
    )

    result = server.get_recent_events()

    assert len(calls) == 2
    assert calls[0]["limit"] == 500
    assert calls[1]["_continue"] == "next-page"
    assert result["pages_scanned"] == 2
    assert result["events_scanned"] == 2
    assert result["collection_truncated"] is False


def test_empty_namespace_returns_empty_events(monkeypatch):
    install_fake_api(
        monkeypatch,
        [make_page([])],
    )

    result = server.get_recent_events()

    assert result["events_returned"] == 0
    assert result["events"] == []


def test_api_permission_error_is_reported(monkeypatch):
    def forbidden(**kwargs):
        raise ApiException(status=403, reason="Forbidden")

    monkeypatch.setattr(
        server,
        "get_core_v1_api",
        lambda: SimpleNamespace(list_namespaced_event=forbidden),
    )

    with pytest.raises(RuntimeError, match="HTTP 403, Forbidden"):
        server.get_recent_events()


def test_invalid_event_filters_are_rejected(monkeypatch):
    with pytest.raises(ValueError, match="event_type"):
        server.get_recent_events(event_type="Delete")

    with pytest.raises(ValueError, match="since_seconds"):
        server.get_recent_events(since_seconds=0)

    with pytest.raises(ValueError, match="limit"):
        server.get_recent_events(limit=501)
