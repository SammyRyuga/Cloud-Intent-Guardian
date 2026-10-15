"""Backward-compatible initial intent approval backed by version transactions."""
import os

from botocore.exceptions import BotoCoreError, ClientError

from common.audit import request_id
from common.auth import AuthorizationError, authorize, configured_scope
from common.dynamodb import dynamodb_resource
from common.http import error, response
from common.versions import VersionError, approve_initial


def lambda_handler(event, context):
    intent_id = (event.get("pathParameters") or {}).get("intentId")
    if not intent_id:
        return error(400, "MISSING_INTENT_ID", "intentId is required.")
    try:
        actor = authorize(event, required="approver")
        scope = configured_scope()
    except AuthorizationError as exc:
        return error(exc.status, exc.code, str(exc))
    try:
        db = dynamodb_resource()
        table = db.Table(os.environ["INTENTS_TABLE"])
        found = table.get_item(Key={"intentId": intent_id}, ConsistentRead=True).get("Item")
        if not found:
            return error(404, "INTENT_NOT_FOUND", "No intent exists with that ID.")
        if not found.get("scopeKey"):
            return error(409, "INTENT_MIGRATION_REQUIRED", "Backfill the configured scope before changing this legacy intent.")
        if found["scopeKey"] != scope:
            return error(404, "INTENT_NOT_FOUND", "No intent exists with that ID.")
        updated = approve_initial(db, found, actor, request_id(event))
        message = "Intent was already approved." if found.get("status") == "APPROVED" else None
        payload = {"item": updated}
        if message:
            payload["message"] = message
        return response(200, payload)
    except VersionError as exc:
        return error(exc.status, exc.code, exc.message, exc.details)
    except (ClientError, BotoCoreError) as exc:
        if getattr(exc, "response", {}).get("Error", {}).get("Code") in {"TransactionCanceledException", "ConditionalCheckFailedException"}:
            return error(409, "INTENT_STATE_CONFLICT", "The intent changed during approval. Refresh before trying again.")
        return error(502, "INTENT_APPROVAL_FAILED", "Could not approve the intent.", str(exc)[:250])
