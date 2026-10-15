import os
import json
from common.dynamodb import dynamodb_resource
from common.manifest import validate_manifest, ManifestValidationError
from botocore.exceptions import BotoCoreError, ClientError
from common.http import response, error, utc_now, _json_default
from boto3.dynamodb.conditions import Attr


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
        try:
            fields = {'name', 'description', 'constraints', 'schemaVersion', 'components', 'relationships', 'trustBoundaries', 'criticality'}
            manifest = {key: value for key, value in found.items() if key in fields}
            validate_manifest(json.loads(json.dumps(manifest, default=_json_default)))
        except ManifestValidationError as exc:
            return error(409, "INTENT_NOT_VALID", exc.message, exc.details)
        if found.get("status") == "APPROVED":
            return response(200, {"item": found, "message": "Intent was already approved."})
        if found.get('status') != 'DRAFT':
            return error(409, 'INTENT_STATE_CONFLICT', 'Only a draft intent can be approved.')
        now = utc_now()
        updated = table.update_item(
            Key={"intentId": intent_id},
            UpdateExpression="SET #s = :approved, approvedAt = :now, updatedAt = :now",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":approved": "APPROVED", ":now": now},
            ReturnValues="ALL_NEW",
            ConditionExpression=Attr('status').eq('DRAFT'),
        ).get("Attributes", {})
        return response(200, {"item": updated})
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return error(409, 'INTENT_STATE_CONFLICT', 'The intent changed during approval. Refresh before trying again.')
    except (ClientError, BotoCoreError) as exc:
        return error(502, "INTENT_APPROVAL_FAILED", "Could not approve the intent.", str(exc)[:250])
