import base64
import json
import os
import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import BotoCoreError, ClientError
from common.http import response, error, query_params


def lambda_handler(event, context):
    table = boto3.resource("dynamodb").Table(os.environ["FINDINGS_TABLE"])
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
    if params.get("status"):
        scan_kwargs["FilterExpression"] = Attr("status").eq(params["status"].upper())
    try:
        result = table.scan(**scan_kwargs)
    except (ClientError, BotoCoreError) as exc:
        return error(502, "FINDINGS_READ_FAILED", "Could not read findings.", str(exc)[:250])
    key = result.get("LastEvaluatedKey")
    next_token = base64.urlsafe_b64encode(json.dumps(key, default=str).encode("utf-8")).decode("utf-8").rstrip("=") if key else None
    items = result.get("Items", [])
    priority = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
    items.sort(key=lambda x: x.get("lastSeenAt", ""), reverse=True)
    items.sort(key=lambda x: priority.get(x.get("severity", "INFO"), 5))
    return response(200, {"items": items, "nextToken": next_token, "count": len(items), "limit": limit})
