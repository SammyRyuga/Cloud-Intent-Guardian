"""Durable evaluation job records, scope-bound reads, and artifact helpers."""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from boto3.dynamodb.conditions import Key, Attr

from common.audit import audit_event, audit_put, transaction_write
from common.auth import configured_scope
from common.contracts import scan_all
from common.http import utc_now, _json_default
from common.pagination import encode_cursor, page_options
from common.versions import content_from, content_hash


INDEX_NAME = "scope-created"
ARTIFACT_CHUNK_BYTES = 240 * 1024
JOB_TERMINAL = {"SUCCEEDED", "PARTIAL", "FAILED"}


class JobError(ValueError):
    def __init__(self, status: int, code: str, message: str, details: Any = None):
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details


def _integer(value: Any, default: int, low: int, high: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, parsed))


def _content_hash(row: dict[str, Any]) -> str:
    fields = content_from(row)
    calculated = content_hash(fields)
    supplied = row.get("contentHash")
    if supplied and supplied != calculated:
        raise JobError(409, "INTENT_VERSION_HASH_MISMATCH", "The approved version snapshot failed its content hash check.")
    return calculated


def resolve_pinned_intent(db: Any, intents_table: Any, intent_id: str | None,
                          requested_version: Any = None, scope: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the approved immutable version and a minimal root facade."""
    if intent_id:
        facade = intents_table.get_item(Key={"intentId": intent_id}, ConsistentRead=True).get("Item")
        if not facade:
            raise JobError(404, "INTENT_NOT_FOUND", "The requested intent does not exist.")
    else:
        rows, truncated = scan_all(intents_table, max_pages=20)
        if truncated:
            raise JobError(409, "INTENT_SELECTION_INCOMPLETE", "Specify an approved intentId; default selection exceeded its scan bound.")
        candidates = [row for row in rows if row.get("status") == "APPROVED" and row.get("scopeKey") == (scope or configured_scope())]
        if not candidates and any(row.get("status") == "APPROVED" and not row.get("scopeKey") for row in rows):
            raise JobError(409, "VERSION_MIGRATION_REQUIRED", "Legacy intents must be assigned to the configured scope before evaluation.")
        candidates.sort(key=lambda row: row.get("updatedAt", ""), reverse=True)
        facade = candidates[0] if candidates else None
        if not facade:
            raise JobError(409, "NO_APPROVED_INTENT", "Create and approve an intent before running an evaluation.")
    if not facade.get("scopeKey"):
        raise JobError(409, "VERSION_MIGRATION_REQUIRED", "The intent has no configured scope assignment; backfill it before evaluation.")
    if facade.get("scopeKey") != (scope or configured_scope()):
        raise JobError(404, "INTENT_NOT_FOUND", "The requested intent does not exist in the configured scope.")
    if facade.get("status") != "APPROVED":
        raise JobError(409, "INTENT_NOT_APPROVED", "Only an approved intent can be evaluated.")
    active = facade.get("activeVersion", facade.get("version", 1))
    try:
        active = int(active)
        version = active if requested_version is None else int(requested_version)
        if isinstance(requested_version, bool) or version < 1 or (requested_version is not None and str(version) != str(requested_version)):
            raise ValueError()
    except (TypeError, ValueError):
        raise JobError(400, "INVALID_VERSION", "intentVersion must be a positive integer.")
    if requested_version is not None and version != active:
        # Historic approved versions are valid, but must come from immutable storage.
        pass
    table_name = os.environ.get("INTENT_VERSIONS_TABLE")
    if not table_name:
        raise JobError(409, "VERSIONING_NOT_CONFIGURED", "Intent version storage is not configured.")
    versions = db.Table(table_name)
    snapshot = versions.get_item(Key={"intentId": facade["intentId"], "version": version}, ConsistentRead=True).get("Item")
    if not snapshot:
        raise JobError(409, "VERSION_MIGRATION_REQUIRED", "The requested approved intent version has no immutable snapshot.",
                       {"intentId": facade["intentId"], "version": version, "remediation": "Backfill the legacy intent version before evaluating it."})
    if snapshot.get("status") != "APPROVED":
        raise JobError(409, "INTENT_VERSION_NOT_APPROVED", "Only an approved immutable intent version can be evaluated.")
    if snapshot.get("intentId") != facade["intentId"] or int(snapshot.get("version", -1)) != version:
        raise JobError(409, "INTENT_VERSION_INVALID", "The stored intent version does not match the requested identity.")
    if snapshot.get("scopeKey") and snapshot.get("scopeKey") != facade["scopeKey"]:
        raise JobError(409, "INTENT_VERSION_SCOPE_MISMATCH", "The immutable version scope does not match its intent.")
    digest = _content_hash(snapshot)
    intent = {**content_from(snapshot), "intentId": facade["intentId"], "version": version,
              "activeVersion": active, "contentHash": digest, "status": "APPROVED"}
    return intent, facade


def new_job(db: Any, actor: dict[str, Any], intent: dict[str, Any], scope: str,
            request_id: str | None = None, reason: str | None = None) -> dict[str, Any]:
    table_name, audit_name = os.environ.get("EVALUATIONS_TABLE"), os.environ.get("AUDIT_TABLE")
    if not table_name or not audit_name:
        raise JobError(409, "EVALUATION_STORAGE_NOT_CONFIGURED", "Evaluation and audit storage are not configured.")
    now = utc_now()
    evaluation_id = str(uuid.uuid4())
    created_order = f"{now}#{evaluation_id}"
    budget = _integer(os.environ.get("EVALUATION_DEADLINE_SECONDS"), 900, 60, 3600)
    deadline = (datetime.now(timezone.utc) + timedelta(seconds=budget)).isoformat().replace("+00:00", "Z")
    item = {
        "evaluationId": evaluation_id, "status": "QUEUED", "intentId": intent["intentId"],
        "intentName": intent.get("name"), "intentVersion": int(intent["version"]),
        "intentHash": intent["contentHash"], "intentSnapshot": intent,
        "scopeKey": scope, "createdAt": now, "createdOrder": created_order,
        "startedAt": None, "finishedAt": None, "progressStage": "QUEUED",
        "leaseExpiresAt": None, "attemptCount": 0, "deadlineAt": deadline,
        "summary": None, "conformance": None, "warnings": [],
        "reason": (reason or "")[:500], "createdBy": actor["sub"],
    }
    event = audit_event(actor, "EVALUATION_QUEUED", {"type": "EVALUATION", "id": evaluation_id}, requestId=request_id,
                        metadata={"intentId": intent["intentId"], "intentVersion": int(intent["version"]),
                                  "intentHash": intent["contentHash"]}, scope=scope)
    transaction_write(db, [
        {"Put": {"TableName": table_name, "Item": item, "ConditionExpression": "attribute_not_exists(evaluationId)"}},
        audit_put(event),
    ])
    return item


def list_jobs(table: Any, params: dict[str, str], scope: str) -> dict[str, Any]:
    filters = {key: params[key] for key in ("intentId", "status") if params.get(key)}
    if "status" in filters and filters["status"] not in {"QUEUED", "RUNNING", "SUCCEEDED", "PARTIAL", "FAILED"}:
        raise JobError(400, "INVALID_STATUS_FILTER", "status must be QUEUED, RUNNING, SUCCEEDED, PARTIAL, or FAILED.")
    try:
        options = page_options(params, scope, "evaluations", filters)
    except ValueError as exc:
        raise JobError(400, "INVALID_PAGINATION", str(exc)) from exc
    # A GSI omits legacy items that lack either key. Check the base table with a
    # bounded scan so an existing index cannot make history look complete while
    # silently hiding rows that still need the explicit backfill.
    _require_migrated_history(table, scope)
    query = {"IndexName": INDEX_NAME, "KeyConditionExpression": Key("scopeKey").eq(scope),
             "ScanIndexForward": False, **options}
    if filters:
        query["FilterExpression"] = Attr("intentId").eq(filters["intentId"]) if "intentId" in filters else Attr("status").eq(filters["status"])
        if len(filters) == 2:
            query["FilterExpression"] = Attr("intentId").eq(filters["intentId"]) & Attr("status").eq(filters["status"])
    try:
        page = table.query(**query)
    except Exception as exc:
        if getattr(exc, "response", {}).get("Error", {}).get("Code") == "ValidationException":
            raise JobError(409, "EVALUATION_HISTORY_INDEX_NOT_READY", "Evaluation history index is missing or still requires migration.",
                           {"requiredIndex": INDEX_NAME, "remediation": "Add the scope-created index and backfill legacy createdOrder/scopeKey fields."}) from exc
        raise
    items = page.get("Items", [])
    next_token = encode_cursor(page.get("LastEvaluatedKey"), scope, "evaluations", filters)
    return {"items": items, "count": len(items), "nextToken": next_token, "limit": options["Limit"]}


def _require_migrated_history(table: Any, scope: str) -> None:
    names = {"#id": "evaluationId", "#scope": "scopeKey", "#order": "createdOrder",
             "#account": "accountId", "#region": "region"}
    rows, truncated = scan_all(
        table, max_pages=20, ConsistentRead=True,
        ProjectionExpression="#id, #scope, #order, #account, #region",
        ExpressionAttributeNames=names,
    )
    parts = scope.split("#")
    account, region = (parts[0], parts[1]) if len(parts) >= 2 else (None, None)
    unmigrated = False
    for row in rows:
        row_scope = row.get("scopeKey")
        if row_scope == scope and not row.get("createdOrder"):
            unmigrated = True
            break
        if row_scope:
            continue
        row_account, row_region = row.get("accountId"), row.get("region")
        # Rows with no legacy scope clues are ambiguous and must be migrated
        # explicitly before any tenant can claim a complete history view.
        if not row_account or not row_region or (row_account == account and row_region == region):
            unmigrated = True
            break
    if unmigrated or truncated:
        raise JobError(
            409, "EVALUATION_HISTORY_MIGRATION_REQUIRED",
            "Evaluation history is incomplete until legacy rows are assigned scope and ordering keys.",
            {"requiredIndex": INDEX_NAME,
             "remediation": "Run the explicit, resumable evaluation history backfill; do not recreate the table."},
        )


def get_job(table: Any, evaluation_id: str, scope: str) -> dict[str, Any] | None:
    item = table.get_item(Key={"evaluationId": evaluation_id}, ConsistentRead=True).get("Item")
    if item and item.get("scopeKey") != scope:
        return None
    return item


def chunk_artifacts(evaluation_id: str, artifacts: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Split canonical JSON artifacts into bounded, independently hashed chunks."""
    chunks: list[dict[str, Any]] = []
    # ensure_ascii keeps UTF-8 boundaries safe when chunks are byte-sliced.
    content = json.dumps(artifacts, sort_keys=True, separators=(",", ":"), default=_json_default,
                         ensure_ascii=True).encode("utf-8")
    for offset in range(0, len(content), ARTIFACT_CHUNK_BYTES):
        data = content[offset:offset + ARTIFACT_CHUNK_BYTES]
        chunks.append({"evaluationId": evaluation_id, "artifactKey": f"chunk#{len(chunks):06d}",
                       "encoding": "json-utf8", "data": data.decode("utf-8"),
                       "sha256": hashlib.sha256(data).hexdigest(), "byteLength": len(data)})
    if not chunks:
        data = b"[]"
        chunks.append({"evaluationId": evaluation_id, "artifactKey": "chunk#000000", "encoding": "json-utf8",
                       "data": "[]", "sha256": hashlib.sha256(data).hexdigest(), "byteLength": 2})
    manifest = {"evaluationId": evaluation_id, "artifactKey": "manifest", "chunkCount": len(chunks),
                "totalBytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
                "complete": True, "createdAt": utc_now()}
    return chunks, manifest


def artifact_limit_check(item: dict[str, Any]) -> None:
    payload = json.dumps(item, separators=(",", ":"), default=_json_default).encode("utf-8")
    if len(payload) > 300 * 1024:
        raise JobError(413, "EVALUATION_ARTIFACT_TOO_LARGE", "One evaluation artifact exceeds the 300 KiB safety limit.")
