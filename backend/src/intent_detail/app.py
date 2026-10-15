import os
from common.dynamodb import dynamodb_resource
from common.auth import AuthorizationError, authorize, configured_scope
from botocore.exceptions import BotoCoreError, ClientError
from common.http import response, error


def lambda_handler(event, context):
    intent_id = (event.get("pathParameters") or {}).get("intentId")
    if not intent_id:
        return error(400, "MISSING_INTENT_ID", "intentId is required.")
    try:
        authorize(event, required="viewer")
        scope = configured_scope()
    except AuthorizationError as exc:
        return error(exc.status, exc.code, str(exc))
    try:
        table = dynamodb_resource().Table(os.environ["INTENTS_TABLE"])
    except (ClientError, BotoCoreError) as exc:
        return error(502, "DYNAMODB_CONFIGURATION_FAILED", "Could not initialize DynamoDB.", str(exc)[:250])
    try:
        result = table.get_item(Key={"intentId": intent_id}, ConsistentRead=True)
    except (ClientError, BotoCoreError) as exc:
        return error(502, "INTENT_READ_FAILED", "Could not retrieve the intent.", str(exc)[:250])
    item = result.get("Item")
    if not item:
        return error(404, "INTENT_NOT_FOUND", "No intent exists with that ID.")
    if not item.get("scopeKey"):
        return error(409, "INTENT_MIGRATION_REQUIRED", "Backfill the configured scope before reading this legacy intent.")
    if item["scopeKey"] != scope:
        return error(404, "INTENT_NOT_FOUND", "No intent exists with that ID.")
    return response(200, {"item": item})
