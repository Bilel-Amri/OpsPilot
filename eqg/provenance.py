"""Provenance and payload-integrity checks for an EvidenceSnapshot."""

from __future__ import annotations

import re
from typing import Any

from .hashing import verify_payload_hash
from .models import Issue
from .time_utils import parse_timestamp

ALLOWED_TOOLS = {
    "pod_status": {"get_pod_status", "list_pods"},
    "pod_spec": {"get_pod_status", "list_pods"},
    "pod_logs": {"get_pod_logs"},
    "events": {"get_recent_events"},
}
KUBERNETES_SOURCES = {"pod_status", "pod_spec", "pod_logs", "events"}
SHA256_RE = re.compile(r"^(?:sha256:)?[0-9a-fA-F]{64}$")


def validate_provenance(
    snapshot: dict[str, Any], evidence_items: list[dict[str, Any]]
) -> tuple[list[Issue], list[dict[str, Any]]]:
    issues: list[Issue] = []
    checks: list[dict[str, Any]] = []

    snapshot_id = snapshot.get("snapshot_id")
    incident_id = snapshot.get("incident_id")
    captured_at = snapshot.get("captured_at")
    captured_dt = parse_timestamp(captured_at)
    if not snapshot_id or not incident_id or captured_dt is None:
        issues.append(Issue(
            code="SNAPSHOT_METADATA_INVALID", dimension="provenance", severity="invalid",
            message="Snapshot must contain snapshot_id, incident_id and a timezone-aware captured_at timestamp.",
        ))
    checks.append({"code": "snapshot_metadata", "passed": not any(i.code == "SNAPSHOT_METADATA_INVALID" for i in issues)})

    if not isinstance(evidence_items, list):
        evidence_items = []
        issues.append(Issue("EVIDENCE_ITEMS_INVALID", "provenance", "invalid", "Evidence items must be a list."))

    seen_ids: set[str] = set()
    manifest_entries = snapshot.get("source_manifest")
    manifest_index: dict[str, set[str]] = {}
    if not isinstance(manifest_entries, list):
        issues.append(Issue("SOURCE_MANIFEST_INVALID", "provenance", "invalid", "Snapshot source_manifest must be a list."))
        manifest_entries = []
    elif evidence_items and not manifest_entries:
        issues.append(Issue("SOURCE_MANIFEST_EMPTY", "provenance", "invalid", "Snapshot contains evidence but source_manifest is empty."))
    if isinstance(manifest_entries, list):
        for entry in manifest_entries:
            if not isinstance(entry, dict):
                continue
            tool = entry.get("tool_name") or entry.get("tool")
            ids = entry.get("evidence_ids")
            if isinstance(tool, str) and isinstance(ids, list):
                manifest_index.setdefault(tool, set()).update(str(x) for x in ids)

    for item in evidence_items:
        if not isinstance(item, dict):
            issues.append(Issue("EVIDENCE_ITEM_NOT_OBJECT", "provenance", "invalid", "An evidence item is not an object."))
            continue
        evidence_id = item.get("evidence_id")
        eid = str(evidence_id) if evidence_id is not None else ""
        source = item.get("source_type")
        tool = item.get("tool_name")

        if not eid:
            issues.append(Issue("EVIDENCE_ID_MISSING", "provenance", "invalid", "Evidence item has no evidence_id."))
        elif eid in seen_ids:
            issues.append(Issue("DUPLICATE_EVIDENCE_ID", "provenance", "invalid", f"Duplicate evidence_id '{eid}'.", [eid]))
        else:
            seen_ids.add(eid)

        if item.get("snapshot_id") != snapshot_id:
            issues.append(Issue("SNAPSHOT_ID_MISMATCH", "provenance", "invalid", "Evidence belongs to a different snapshot.", [eid] if eid else []))
        if item.get("incident_id") != incident_id:
            issues.append(Issue("INCIDENT_ID_MISMATCH", "provenance", "invalid", "Evidence belongs to a different incident.", [eid] if eid else []))

        if source not in KUBERNETES_SOURCES | {"manifest"}:
            issues.append(Issue("SOURCE_TYPE_INVALID", "provenance", "invalid", f"Unsupported source_type: {source!r}.", [eid] if eid else []))
        if not isinstance(tool, str) or not tool.strip():
            issues.append(Issue("TOOL_NAME_MISSING", "provenance", "invalid", "Evidence has no tool_name.", [eid] if eid else []))
        elif source in ALLOWED_TOOLS and tool not in ALLOWED_TOOLS[source]:
            issues.append(Issue("TOOL_SOURCE_MISMATCH", "provenance", "invalid", f"Tool '{tool}' is not allowed for source_type '{source}'.", [eid] if eid else []))

        for key in ("namespace", "pod_name"):
            if source in KUBERNETES_SOURCES and not (isinstance(item.get(key), str) and item[key].strip()):
                issues.append(Issue(f"{key.upper()}_MISSING", "provenance", "invalid", f"Kubernetes evidence is missing {key}.", [eid] if eid else []))
        if source in KUBERNETES_SOURCES and not (isinstance(item.get("pod_uid"), str) and item["pod_uid"].strip()):
            issues.append(Issue("POD_UID_MISSING", "provenance", "invalid", "Kubernetes evidence is missing the Pod UID.", [eid] if eid else []))

        collected_dt = parse_timestamp(item.get("collected_at"))
        if collected_dt is None:
            issues.append(Issue("COLLECTED_AT_INVALID", "provenance", "invalid", "collected_at must be a timezone-aware ISO-8601 timestamp.", [eid] if eid else []))
        elif captured_dt and collected_dt.timestamp() > captured_dt.timestamp() + 120:
            issues.append(Issue("COLLECTED_AFTER_SNAPSHOT", "provenance", "invalid", "Evidence was collected more than 120 seconds after the snapshot capture time.", [eid] if eid else []))

        payload = item.get("payload")
        payload_hash = item.get("payload_hash")
        if not isinstance(payload, dict):
            issues.append(Issue("PAYLOAD_INVALID", "provenance", "invalid", "Evidence payload must be a JSON object.", [eid] if eid else []))
        if not isinstance(payload_hash, str) or not SHA256_RE.fullmatch(payload_hash):
            issues.append(Issue("PAYLOAD_HASH_INVALID", "provenance", "invalid", "payload_hash must be a 64-character SHA-256 hex digest.", [eid] if eid else []))
        elif isinstance(payload, dict) and not verify_payload_hash(payload, payload_hash):
            issues.append(Issue("PAYLOAD_HASH_MISMATCH", "provenance", "invalid", "The payload does not match its SHA-256 hash.", [eid] if eid else []))

        # The snapshot manifest is authoritative when it records evidence IDs.
        if manifest_index and eid:
            if tool not in manifest_index or eid not in manifest_index.get(tool, set()):
                issues.append(Issue("SOURCE_MANIFEST_MISMATCH", "provenance", "invalid", "Evidence ID/tool is not recorded in the snapshot source_manifest.", [eid]))

    checks.append({"code": "evidence_provenance", "passed": len(issues) == 0, "items_checked": len(evidence_items)})
    return issues, checks
