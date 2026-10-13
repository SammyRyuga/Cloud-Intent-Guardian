import os
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from common.http import response, error


def lambda_handler(event, context):
    intent_id = (event.get("pathParameters") or {}).get("intentId")
    if not intent_id:
        return error(400, "MISSING_INTENT_ID", "intentId is required.")
    table = boto3.resource("dynamodb").Table(os.environ["INTENTS_TABLE"])
    try:
        result = table.get_item(Key={"intentId": intent_id}, ConsistentRead=True)
    except (ClientError, BotoCoreError) as exc:
        return error(502, "INTENT_READ_FAILED", "Could not retrieve the intent.", str(exc)[:250])
    item = result.get("Item")
    if not item:
        return error(404, "INTENT_NOT_FOUND", "No intent exists with that ID.")
    return response(200, {"item": item})
