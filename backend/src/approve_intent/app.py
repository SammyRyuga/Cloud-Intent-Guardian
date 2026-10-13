import os
from common.dynamodb import dynamodb_resource
from botocore.exceptions import BotoCoreError, ClientError
from common.http import response, error, utc_now


def lambda_handler(event, context):
    intent_id = (event.get("pathParameters") or {}).get("intentId")
    if not intent_id:
        return error(400, "MISSING_INTENT_ID", "intentId is required.")
    try:
        table = dynamodb_resource().Table(os.environ["INTENTS_TABLE"])
    except (ClientError, BotoCoreError) as exc:
        return error(502, "DYNAMODB_CONFIGURATION_FAILED", "Could not initialize DynamoDB.", str(exc)[:250])
    try:
        found = table.get_item(Key={"intentId": intent_id}, ConsistentRead=True).get("Item")
        if not found:
            return error(404, "INTENT_NOT_FOUND", "No intent exists with that ID.")
        if not found.get("constraints"):
            return error(409, "INTENT_NOT_VALID", "An intent with no constraints cannot be approved.")
        if found.get("status") == "APPROVED":
            return response(200, {"item": found, "message": "Intent was already approved."})
        now = utc_now()
        updated = table.update_item(
            Key={"intentId": intent_id},
            UpdateExpression="SET #s = :approved, approvedAt = :now, updatedAt = :now",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":approved": "APPROVED", ":now": now},
            ReturnValues="ALL_NEW",
        ).get("Attributes", {})
        return response(200, {"item": updated})
    except (ClientError, BotoCoreError) as exc:
        return error(502, "INTENT_APPROVAL_FAILED", "Could not approve the intent.", str(exc)[:250])
