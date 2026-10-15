import base64
import json
import os
import uuid
from common.dynamodb import dynamodb_resource
from common.manifest import validate_manifest, ManifestValidationError
from botocore.exceptions import BotoCoreError, ClientError
from common.http import response, error, parse_body, utc_now, query_params


def lambda_handler(event, context):
    print(json.dumps({"event": "intent_handler_started", "requestId": getattr(context, "aws_request_id", None)}), flush=True)
    try:
        table = dynamodb_resource().Table(os.environ["INTENTS_TABLE"])
    except (ClientError, BotoCoreError) as exc:
        return error(502, "DYNAMODB_CONFIGURATION_FAILED", "Could not initialize DynamoDB.", str(exc)[:250])
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET").upper()
    if method == "GET":
        params = query_params(event)
        try:
            limit = max(1, min(int(params.get("limit", "25")), 100))
        except ValueError:
            return error(400, "INVALID_LIMIT", "The limit query parameter must be an integer between 1 and 100.")
        scan_kwargs = {"Limit": limit}
        token = params.get("nextToken")
        if token:
            try:
                decoded = base64.urlsafe_b64decode(token.encode("utf-8") + b"=" * (-len(token) % 4))
                scan_kwargs["ExclusiveStartKey"] = json.loads(decoded.decode("utf-8"))
            except Exception:
                return error(400, "INVALID_CURSOR", "The nextToken cursor is invalid.")
        try:
            result = table.scan(**scan_kwargs)
            items = result.get("Items", [])
            items.sort(key=lambda x: x.get("updatedAt", ""), reverse=True)
            key = result.get("LastEvaluatedKey")
            next_token = base64.urlsafe_b64encode(json.dumps(key, default=str).encode("utf-8")).decode("utf-8").rstrip("=") if key else None
            return response(200, {"items": items, "count": len(items), "nextToken": next_token, "limit": limit})
        except (ClientError, BotoCoreError) as exc:
            return error(502, "INTENTS_READ_FAILED", "Could not read intents.", str(exc)[:250])
    if method != "POST":
        return error(405, "METHOD_NOT_ALLOWED", "Method not allowed.")
    try:
        body = parse_body(event)
    except (ValueError, json.JSONDecodeError) as exc:
        return error(400, "INVALID_JSON", "Request body must be a valid JSON object.", str(exc))
    try:
        manifest = validate_manifest(body)
    except ManifestValidationError as exc:
        return error(400, exc.code, exc.message, exc.details)
    now = utc_now()
    record = {
        "intentId": str(uuid.uuid4()),
        **manifest,
        "version": 1,
        "status": "DRAFT",
        "createdAt": now,
        "updatedAt": now,
        "approvedAt": None,
        "createdBy": (event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {}).get("email") or "authenticated-user"),
        "sourceType": "JSON_CONSTRAINT_MANIFEST",
    }
    try:
        print(json.dumps({"event": "intent_put_started", "table": table.name, "intentId": record["intentId"]}), flush=True)
        table.put_item(Item=record, ConditionExpression="attribute_not_exists(intentId)")
    except (ClientError, BotoCoreError) as exc:
        return error(502, "INTENT_WRITE_FAILED", "Could not save the intent.", str(exc)[:250])
    print(json.dumps({"event": "intent_put_succeeded", "intentId": record["intentId"]}), flush=True)
    return response(201, {"item": record})
