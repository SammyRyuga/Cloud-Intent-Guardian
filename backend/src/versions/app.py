"""Version history and explicit intent activation endpoints."""
from __future__ import annotations

import json
import os
from decimal import Decimal
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from common.auth import AuthorizationError, authorize
from common.auth import configured_scope
from common.audit import request_id
from common.dynamodb import dynamodb_resource
from common.http import _json_default, error, parse_body, query_params, response
from common.pagination import encode_cursor, page_options
from common.versions import (
    VersionError,
    approve_version,
    content_from,
    create_version,
    list_versions,
    rollback,
    semantic_diff,
)


def _json(result: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(result, default=_json_default))


def _request_id(event: dict[str, Any], context: Any) -> str | None:
    return request_id(event) or getattr(context, "aws_request_id", None)


def _version_number(value: Any) -> int:
    try:
        if isinstance(value, bool):
            raise ValueError
        number = int(value)
        if number < 1 or str(number) != str(value):
            raise ValueError
        return number
    except (TypeError, ValueError):
        raise VersionError(400, "INVALID_VERSION", "Version must be a positive integer.")


def _expected_revision(value: Any) -> int:
    if (isinstance(value, bool) or not isinstance(value, (int, Decimal))
            or isinstance(value, Decimal) and (not value.is_finite() or value != value.to_integral_value())
            or int(value) < 0):
        raise VersionError(400, "INVALID_REVISION", "expectedRevision must be a non-negative integer.")
    return int(value)


def _effective(snapshot: dict[str, Any], active_version: Any) -> dict[str, Any]:
    result = dict(snapshot)
    if snapshot.get("status") == "APPROVED" and int(snapshot.get("version", 0)) != int(active_version or 0):
        result["effectiveStatus"] = "SUPERSEDED"
    else:
        result["effectiveStatus"] = snapshot.get("status")
    return result


def _get_intent(table: Any, intent_id: str) -> dict[str, Any]:
    item = table.get_item(Key={"intentId": intent_id}, ConsistentRead=True).get("Item")
    if not item:
        raise VersionError(404, "INTENT_NOT_FOUND", "No intent exists with that ID.")
    scope_key = item.get("scopeKey")
    if not scope_key:
        raise VersionError(409, "INTENT_MIGRATION_REQUIRED", "Backfill the configured scope before using this legacy intent.")
    if scope_key != configured_scope():
        raise VersionError(404, "INTENT_NOT_FOUND", "No intent exists with that ID.")
    return item


def _get_version(table: Any, intent_id: str, version: int) -> dict[str, Any]:
    item = table.get_item(Key={"intentId": intent_id, "version": version}, ConsistentRead=True).get("Item")
    if not item:
        raise VersionError(404, "INTENT_VERSION_NOT_FOUND", "The requested intent version does not exist.")
    if not item.get("scopeKey"):
        raise VersionError(409, "INTENT_MIGRATION_REQUIRED", "Backfill the configured scope before using this legacy intent version.")
    if item["scopeKey"] != configured_scope():
        raise VersionError(404, "INTENT_VERSION_NOT_FOUND", "The requested intent version does not exist.")
    return item


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    path = event.get("rawPath", "") or event.get("path", "")
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET").upper()
    params = query_params(event)
    path_params = event.get("pathParameters") or {}
    intent_id = path_params.get("intentId")
    version_value = path_params.get("version")

    try:
        if method == "POST" and path.endswith("/rollback"):
            actor = authorize(event, required="approver")
        elif method == "POST" and path.endswith("/approve"):
            actor = authorize(event, required="approver")
        elif method == "POST":
            actor = authorize(event, required="admin")
        else:
            actor = authorize(event, required="viewer")
    except AuthorizationError as exc:
        return error(exc.status, exc.code, str(exc))

    if not intent_id:
        return error(400, "MISSING_INTENT_ID", "intentId is required.")

    try:
        db = dynamodb_resource()
        intent_table = db.Table(os.environ["INTENTS_TABLE"])
        versions_table = db.Table(os.environ["INTENT_VERSIONS_TABLE"])

        if method == "POST" and path.endswith("/rollback"):
            body = parse_body(event)
            intent = _get_intent(intent_table, intent_id)
            target_version = _version_number(body.get("targetVersion"))
            snapshot = _get_version(versions_table, intent_id, target_version)
            expected_revision = _expected_revision(body.get("expectedRevision"))
            result = rollback(db, intent, snapshot, expected_revision, body.get("reason", ""),
                              actor, _request_id(event, context))
            return response(200, {"item": _json(result)})

        if method == "POST" and version_value and path.endswith("/approve"):
            body = parse_body(event)
            intent = _get_intent(intent_table, intent_id)
            snapshot = _get_version(versions_table, intent_id, _version_number(version_value))
            expected_revision = _expected_revision(body.get("expectedRevision"))
            result = approve_version(db, intent, snapshot, expected_revision,
                                    actor, _request_id(event, context), body.get("comment"))
            return response(200, {"item": _json(result)})

        if method == "POST" and path.endswith("/versions"):
            body = parse_body(event)
            intent = _get_intent(intent_table, intent_id)
            manifest = body.get("manifest")
            if not isinstance(manifest, dict):
                raise VersionError(400, "INVALID_MANIFEST", "manifest must be an object.")
            expected_revision = _expected_revision(body.get("expectedRevision"))
            result = create_version(db, intent, manifest, expected_revision, actor, _request_id(event, context))
            return response(201, {"item": _json(result)})

        if method == "GET" and path.endswith("/diff"):
            _get_intent(intent_table, intent_id)
            from_version = _version_number(params.get("fromVersion"))
            to_version = _version_number(params.get("toVersion"))
            left = _get_version(versions_table, intent_id, from_version)
            right = _get_version(versions_table, intent_id, to_version)
            item = {"intentId": intent_id, "fromVersion": from_version, "toVersion": to_version,
                    **semantic_diff(left, right)}
            return response(200, {"item": item})

        if method == "GET" and version_value:
            intent = _get_intent(intent_table, intent_id)
            snapshot = _get_version(versions_table, intent_id, _version_number(version_value))
            return response(200, {"item": _json(_effective(snapshot, intent.get("activeVersion")))})

        if method == "GET" and path.endswith("/versions"):
            intent = _get_intent(intent_table, intent_id)
            try:
                limit = int(params.get("limit", "25"))
            except (TypeError, ValueError):
                return error(400, "INVALID_LIMIT", "limit must be an integer from 1 to 100.")
            if not 1 <= limit <= 100:
                return error(400, "INVALID_LIMIT", "limit must be an integer from 1 to 100.")
            scope = configured_scope()
            filters = {"intentId": intent_id}
            options = page_options(params, scope, "intent-versions", filters)
            page = list_versions(versions_table, intent_id, options["Limit"], options.get("ExclusiveStartKey"))
            items = [_json(_effective(row, intent.get("activeVersion"))) for row in page["items"]]
            return response(200, {"items": items, "count": len(items),
                                  "nextToken": encode_cursor(page.get("lastEvaluatedKey"), scope, "intent-versions", filters), "limit": options["Limit"]})

        return error(405 if method not in {"GET", "POST"} else 404,
                     "METHOD_NOT_ALLOWED" if method not in {"GET", "POST"} else "ROUTE_NOT_FOUND",
                     "Method or version route is not supported.")
    except VersionError as exc:
        return error(exc.status, exc.code, exc.message, exc.details)
    except AuthorizationError as exc:
        return error(exc.status, exc.code, str(exc))
    except (ClientError, BotoCoreError) as exc:
        if getattr(exc, "response", {}).get("Error", {}).get("Code") in {"TransactionCanceledException", "ConditionalCheckFailedException"}:
            return error(409, "STALE_INTENT_REVISION", "The intent changed; refresh before retrying.")
        return error(502, "INTENT_VERSION_OPERATION_FAILED", "Could not complete the intent version operation.", type(exc).__name__)
    except (ValueError, TypeError) as exc:
        return error(400, "INVALID_REQUEST", str(exc))
