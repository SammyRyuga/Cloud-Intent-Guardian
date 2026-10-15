"""Immutable intent-version records and optimistic lifecycle transactions."""
from __future__ import annotations

import hashlib
import json
import os
from decimal import Decimal
from typing import Any

from boto3.dynamodb.conditions import Key

from common.audit import audit_event, audit_put, transaction_write
from common.auth import configured_scope
from common.http import utc_now, _json_default
from common.manifest import ManifestValidationError, validate_manifest


CONTENT_FIELDS = (
    "name", "description", "constraints", "schemaVersion", "components",
    "relationships", "trustBoundaries", "criticality",
)
VERSION_TABLE_ENV = "INTENT_VERSIONS_TABLE"
AUDIT_TABLE_ENV = "AUDIT_TABLE"


class VersionError(ValueError):
    def __init__(self, status: int, code: str, message: str, details: Any = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def content_from(item: dict[str, Any]) -> dict[str, Any]:
    return {key: item[key] for key in CONTENT_FIELDS if key in item}


def content_hash(content: dict[str, Any]) -> str:
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=_json_default)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _table_names() -> tuple[str, str]:
    versions_name = os.environ.get(VERSION_TABLE_ENV)
    audit_name = os.environ.get(AUDIT_TABLE_ENV)
    if not versions_name or not audit_name:
        raise VersionError(409, "VERSIONING_NOT_CONFIGURED", "Intent versioning and audit storage are not configured.")
    return versions_name, audit_name


def _revision(item: dict[str, Any]) -> int:
    value = item.get("revision", 0)
    if (isinstance(value, bool) or not isinstance(value, (int, Decimal))
            or isinstance(value, Decimal) and (not value.is_finite() or value != value.to_integral_value())
            or int(value) < 0):
        raise VersionError(409, "INTENT_REVISION_INVALID", "The stored intent revision is invalid.")
    return int(value)


def _condition(expected_revision: int) -> tuple[str, dict[str, str], dict[str, Any]]:
    names = {"#revision": "revision"}
    values = {":expectedRevision": expected_revision}
    if expected_revision == 0:
        return "(attribute_not_exists(#revision) OR #revision = :expectedRevision)", names, values
    return "#revision = :expectedRevision", names, values


def _version_row(intent_id: str, version: int, content: dict[str, Any], now: str, *,
                 status: str = "DRAFT", author: dict[str, Any] | None = None,
                 parent_version: int | None = None, source: dict[str, Any] | None = None) -> dict[str, Any]:
    row = {
        "intentId": intent_id,
        "version": version,
        **content,
        "status": status,
        "contentHash": content_hash(content),
        "createdAt": now,
        "updatedAt": now,
        "createdBy": (author or {}).get("sub", "unknown"),
        "author": {"sub": (author or {}).get("sub", "unknown"),
                   "displayName": (author or {}).get("displayName", (author or {}).get("sub", "unknown"))},
    }
    if parent_version is not None:
        row["parentVersion"] = parent_version
    if source:
        for field in ("sourceType", "schemaVersion"):
            if field in source and field not in row:
                row[field] = source[field]
        if "scopeKey" in source:
            row["scopeKey"] = source["scopeKey"]
    return row


def _put_op(table_name: str, item: dict[str, Any], condition: str = "attribute_not_exists(intentId)") -> dict[str, Any]:
    return {"Put": {"TableName": table_name, "Item": item, "ConditionExpression": condition}}


def _update_facade_op(intent_table: str, intent: dict[str, Any], values: dict[str, Any], expected_revision: int,
                      remove_fields: list[str] | None = None) -> dict[str, Any]:
    condition, names, expression_values = _condition(expected_revision)
    set_parts = []
    for index, (name, value) in enumerate(values.items()):
        name_key, value_key = f"#field{index}", f":field{index}"
        names[name_key] = name
        expression_values[value_key] = value
        set_parts.append(f"{name_key} = {value_key}")
    expression = "SET " + ", ".join(set_parts)
    remove_parts = []
    for index, name in enumerate(remove_fields or []):
        name_key = f"#remove{index}"
        names[name_key] = name
        remove_parts.append(name_key)
    if remove_parts:
        expression += " REMOVE " + ", ".join(remove_parts)
    return {"Update": {
        "TableName": intent_table,
        "Key": {"intentId": intent["intentId"]},
        "UpdateExpression": expression,
        "ConditionExpression": condition,
        "ExpressionAttributeNames": names,
        "ExpressionAttributeValues": expression_values,
    }}


def _audit(actor: dict[str, Any], action: str, target: str, request_id: str | None,
           metadata: dict[str, Any], scope: Any = None) -> dict[str, Any]:
    return audit_event(actor, action, {"type": "INTENT", "id": target},
                       requestId=request_id, metadata=metadata, scope=scope)


def create_initial(db: Any, intent_table: Any, record: dict[str, Any], actor: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    """Atomically create the legacy facade, v1 draft snapshot, and audit row."""
    versions_name, _audit_name = _table_names()
    now = record.get("createdAt") or utc_now()
    record = {**record, "version": 1, "latestVersion": 1, "revision": 0}
    content = content_from(record)
    snapshot = _version_row(record["intentId"], 1, content, now, author=actor, source=record)
    event = _audit(actor, "INTENT_CREATED", record["intentId"], request_id,
                   {"version": 1, "contentHash": snapshot["contentHash"]})
    transaction_write(db, [
        _put_op(intent_table.name, record),
        _put_op(versions_name, snapshot),
        audit_put(event),
    ])
    return record


def migrate_legacy(db: Any, intent: dict[str, Any], actor: dict[str, Any],
                   request_id: str | None = None) -> dict[str, Any]:
    """Explicitly backfill one legacy root into its v1 snapshot and scope.

    This is intended for an operator-controlled migration command. Request
    handlers must never call it as an implicit read or approval fallback.
    """
    if intent.get("scopeKey") and intent.get("latestVersion") and intent.get("revision") is not None:
        return intent
    if intent.get("status") not in {"DRAFT", "APPROVED"}:
        raise VersionError(409, "INTENT_MIGRATION_CONFLICT", "Only a legacy draft or approved intent can be backfilled.")
    if int(intent.get("version", 1)) != 1:
        raise VersionError(409, "INTENT_MIGRATION_CONFLICT", "Legacy version backfill only supports version 1.")
    content = content_from(intent)
    try:
        validate_manifest(content)
    except ManifestValidationError as exc:
        raise VersionError(409, "INTENT_NOT_VALID", exc.message, exc.details) from exc
    versions_name, _audit_name = _table_names()
    if db.Table(versions_name).get_item(
            Key={"intentId": intent["intentId"], "version": 1}, ConsistentRead=True).get("Item"):
        raise VersionError(409, "INTENT_MIGRATION_CONFLICT", "A version snapshot already exists; reconcile the migration state before retrying.")
    now = utc_now()
    historical_actor = intent.get("createdBy") or "unknown"
    author = {"sub": str(historical_actor), "displayName": str(historical_actor)}
    snapshot = _version_row(intent["intentId"], 1, content, intent.get("createdAt", now),
                            status=intent["status"], author=author,
                            source={"scopeKey": configured_scope(), **{k: intent[k] for k in ("sourceType", "schemaVersion") if k in intent}})
    snapshot["updatedAt"] = intent.get("updatedAt", snapshot["createdAt"])
    if intent["status"] == "APPROVED":
        snapshot["approvedAt"] = intent.get("approvedAt", snapshot["updatedAt"])
    revision = _revision(intent)
    values = {"version": 1, "latestVersion": 1, "revision": revision + 1, "scopeKey": configured_scope()}
    if intent["status"] == "APPROVED":
        values["activeVersion"] = 1
    event = _audit(actor, "INTENT_VERSION_BACKFILLED", intent["intentId"], request_id,
                   {"version": 1, "contentHash": snapshot["contentHash"], "historicalActorKnown": bool(intent.get("createdBy"))})
    transaction_write(db, [
        _put_op(versions_name, snapshot, "attribute_not_exists(version)"),
        _update_facade_op(os.environ["INTENTS_TABLE"], intent, values, revision,
                          [field for field in CONTENT_FIELDS if field not in content]
                          + ([] if intent["status"] == "APPROVED" else ["activeVersion"])),
        audit_put(event),
    ])
    return {**intent, **values}


def approve_initial(db: Any, intent: dict[str, Any], actor: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    """Seal and activate the initial draft; repeated approval is idempotent."""
    if intent.get("status") == "APPROVED" and int(intent.get("activeVersion", intent.get("version", 1))) == 1:
        return intent
    if intent.get("status") != "DRAFT":
        raise VersionError(409, "INTENT_STATE_CONFLICT", "Only a draft intent can be approved.")
    try:
        content = validate_manifest(content_from(intent))
    except ManifestValidationError as exc:
        raise VersionError(409, "INTENT_NOT_VALID", exc.message, exc.details) from exc
    versions_name, _audit_name = _table_names()
    intent_table = os.environ["INTENTS_TABLE"]
    version = int(intent.get("version", 1))
    if version != 1:
        raise VersionError(409, "INITIAL_VERSION_INVALID", "Initial approval must target version 1.")
    old_revision = _revision(intent)
    now = utc_now()
    snapshot = _version_row(intent["intentId"], 1, content, intent.get("createdAt", now), author=actor, source=intent)
    snapshot.update({"status": "APPROVED", "approvedAt": now, "updatedAt": now})
    event = _audit(actor, "INTENT_VERSION_APPROVED", intent["intentId"], request_id,
                   {"version": 1, "contentHash": snapshot["contentHash"]})
    values = {**content, "version": 1, "activeVersion": 1, "latestVersion": max(1, int(intent.get("latestVersion", 1))),
              "status": "APPROVED", "approvedAt": now, "updatedAt": now, "revision": old_revision + 1}
    existing_version = db.Table(versions_name).get_item(
        Key={"intentId": intent["intentId"], "version": 1}, ConsistentRead=True
    ).get("Item")
    if not existing_version:
        raise VersionError(409, "VERSION_MIGRATION_REQUIRED", "This legacy intent has no version snapshot. Complete the explicit version backfill before approval.")
    if existing_version.get("status") != "DRAFT":
        raise VersionError(409, "VERSION_STATE_CONFLICT", "Initial version is not a draft.")
    snapshot["createdAt"] = existing_version.get("createdAt", snapshot["createdAt"])
    snapshot["createdBy"] = existing_version.get("createdBy", snapshot["createdBy"])
    version_op = {"Put": {"TableName": versions_name, "Item": snapshot,
                          "ConditionExpression": "#status = :draft",
                          "ExpressionAttributeNames": {"#status": "status"},
                          "ExpressionAttributeValues": {":draft": "DRAFT"}}}
    operations = [
        version_op,
        _update_facade_op(intent_table, intent, values, old_revision,
                          [field for field in CONTENT_FIELDS if field not in content]),
        audit_put(event),
    ]
    transaction_write(db, operations)
    return {**intent, **values}


def create_version(db: Any, intent: dict[str, Any], manifest: dict[str, Any], expected_revision: int,
                   actor: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    try:
        content = validate_manifest(manifest)
    except ManifestValidationError as exc:
        raise VersionError(400, exc.code, exc.message, exc.details) from exc
    if intent.get("status") != "APPROVED" or not intent.get("activeVersion"):
        raise VersionError(409, "VERSION_MIGRATION_REQUIRED", "This legacy intent has no active version snapshot. Complete the approved version backfill before creating a new version.")
    actual_revision = _revision(intent)
    if expected_revision != actual_revision:
        raise VersionError(409, "STALE_INTENT_REVISION", "The intent changed; refresh before creating a version.", {"expectedRevision": actual_revision})
    versions_name, _audit_name = _table_names()
    version = int(intent.get("latestVersion", intent.get("activeVersion", 1))) + 1
    now = utc_now()
    snapshot = _version_row(intent["intentId"], version, content, now, author=actor,
                            parent_version=int(intent["activeVersion"]), source=intent)
    event = _audit(actor, "INTENT_VERSION_CREATED", intent["intentId"], request_id,
                   {"version": version, "parentVersion": snapshot["parentVersion"], "contentHash": snapshot["contentHash"]})
    root_op = _update_facade_op(os.environ["INTENTS_TABLE"], intent,
                                {"latestVersion": version, "updatedAt": now, "revision": actual_revision + 1},
                                actual_revision)
    transaction_write(db, [
        _put_op(versions_name, snapshot, "attribute_not_exists(version)"),
        root_op,
        audit_put(event),
    ])
    return snapshot


def _activate(db: Any, intent: dict[str, Any], snapshot: dict[str, Any], actor: dict[str, Any],
              action: str, request_id: str | None = None, reason: str | None = None,
              comment: str | None = None, approve: bool = False,
              expected_revision: int | None = None) -> dict[str, Any]:
    versions_name, _audit_name = _table_names()
    intent_table = os.environ["INTENTS_TABLE"]
    revision = _revision(intent)
    if expected_revision is not None and expected_revision != revision:
        raise VersionError(409, "STALE_INTENT_REVISION", "The intent changed; refresh before activating a version.", {"expectedRevision": revision})
    version = int(snapshot["version"])
    if approve and snapshot.get("status") != "DRAFT":
        if snapshot.get("status") == "APPROVED" and int(intent.get("activeVersion", 0)) == version:
            return {**intent, **content_from(snapshot), "version": version, "activeVersion": version}
        raise VersionError(409, "VERSION_STATE_CONFLICT", "Only a draft version can be approved.")
    if not approve and snapshot.get("status") != "APPROVED":
        raise VersionError(409, "ROLLBACK_VERSION_NOT_APPROVED", "Rollback target must be a previously approved version.")
    content = content_from(snapshot)
    now = utc_now()
    new_revision = revision + 1
    values = {**content, "version": version, "activeVersion": version, "status": "APPROVED",
              "approvedAt": snapshot.get("approvedAt", now), "updatedAt": now, "revision": new_revision,
              "latestVersion": max(int(intent.get("latestVersion", version)), version)}
    if approve:
        snapshot_update = {**snapshot, "status": "APPROVED", "approvedAt": now, "updatedAt": now}
        if comment:
            snapshot_update["approvalComment"] = comment
        version_op = {"Put": {"TableName": versions_name, "Item": snapshot_update,
                              "ConditionExpression": "#status = :draft",
                              "ExpressionAttributeNames": {"#status": "status"},
                              "ExpressionAttributeValues": {":draft": "DRAFT"}}}
    else:
        version_op = None
    metadata = {"version": version, "contentHash": snapshot.get("contentHash")}
    if reason:
        metadata["reason"] = reason
    if comment:
        metadata["comment"] = comment
    event = _audit(actor, action, intent["intentId"], request_id, metadata)
    ops = []
    if version_op:
        ops.append(version_op)
    ops.extend([_update_facade_op(intent_table, intent, values, revision,
                                  [field for field in CONTENT_FIELDS if field not in content]), audit_put(event)])
    transaction_write(db, ops)
    return {**intent, **values}


def approve_version(db: Any, intent: dict[str, Any], snapshot: dict[str, Any], expected_revision: int,
                    actor: dict[str, Any], request_id: str | None = None,
                    comment: str | None = None) -> dict[str, Any]:
    if snapshot.get("intentId") != intent.get("intentId"):
        raise VersionError(404, "INTENT_VERSION_NOT_FOUND", "The requested intent version does not exist.")
    if expected_revision != _revision(intent):
        raise VersionError(409, "STALE_INTENT_REVISION", "The intent changed; refresh before approving this version.",
                           {"expectedRevision": _revision(intent)})
    if snapshot.get("status") != "DRAFT":
        if snapshot.get("status") == "APPROVED" and int(intent.get("activeVersion", 0)) == int(snapshot["version"]):
            return {**intent, **content_from(snapshot), "version": int(snapshot["version"]), "activeVersion": int(snapshot["version"])}
        raise VersionError(409, "VERSION_STATE_CONFLICT", "Only a draft version can be approved.")
    try:
        normalized = validate_manifest(content_from(snapshot))
    except ManifestValidationError as exc:
        raise VersionError(409, "INTENT_NOT_VALID", exc.message, exc.details) from exc
    if comment is not None and (not isinstance(comment, str) or len(comment.strip()) > 500):
        raise VersionError(400, "INVALID_APPROVAL_COMMENT", "comment must be a string of at most 500 characters.")
    snapshot = {**snapshot, **normalized, "contentHash": content_hash(normalized)}
    return _activate(db, intent, snapshot, actor, "INTENT_VERSION_APPROVED", request_id,
                     comment=comment.strip() if isinstance(comment, str) else None,
                     approve=True, expected_revision=expected_revision)


def rollback(db: Any, intent: dict[str, Any], snapshot: dict[str, Any], expected_revision: int,
             reason: str, actor: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    if not reason or not reason.strip():
        raise VersionError(400, "ROLLBACK_REASON_REQUIRED", "A non-empty rollback reason is required.")
    if snapshot.get("intentId") != intent.get("intentId"):
        raise VersionError(404, "INTENT_VERSION_NOT_FOUND", "The requested intent version does not exist.")
    return _activate(db, intent, snapshot, actor, "INTENT_ROLLED_BACK", request_id,
                     reason=reason.strip()[:500], expected_revision=expected_revision)


def list_versions(table: Any, intent_id: str, limit: int = 25, next_key: dict[str, Any] | None = None) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"KeyConditionExpression": Key("intentId").eq(intent_id), "Limit": limit, "ScanIndexForward": False}
    if next_key:
        kwargs["ExclusiveStartKey"] = next_key
    result = table.query(**kwargs)
    return {"items": result.get("Items", []), "count": len(result.get("Items", [])),
            "lastEvaluatedKey": result.get("LastEvaluatedKey")}


def semantic_diff(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    sections: dict[str, Any] = {}
    id_fields = {"components": "id", "relationships": "id", "trustBoundaries": "id", "constraints": "id"}
    for section, key in id_fields.items():
        old = {str(row[key]): row for row in left.get(section, []) or []}
        new = {str(row[key]): row for row in right.get(section, []) or []}
        added = [{"id": ident, "value": new[ident]} for ident in sorted(new.keys() - old.keys())]
        removed = [{"id": ident, "value": old[ident]} for ident in sorted(old.keys() - new.keys())]
        changed = [{"id": ident, "before": old[ident], "after": new[ident]}
                   for ident in sorted(old.keys() & new.keys()) if old[ident] != new[ident]]
        sections[section] = {"added": added, "removed": removed, "changed": changed}
    old_crit, new_crit = left.get("criticality", {}) or {}, right.get("criticality", {}) or {}
    crit_ids = set(old_crit) | set(new_crit)
    sections["criticality"] = {
        "added": [{"id": ident, "value": new_crit[ident]} for ident in sorted(new_crit.keys() - old_crit.keys())],
        "removed": [{"id": ident, "value": old_crit[ident]} for ident in sorted(old_crit.keys() - new_crit.keys())],
        "changed": [{"id": ident, "before": old_crit[ident], "after": new_crit[ident]}
                    for ident in sorted(old_crit.keys() & new_crit.keys()) if old_crit[ident] != new_crit[ident]],
    }
    return sections
