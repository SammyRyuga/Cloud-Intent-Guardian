import base64
import json
import os
import uuid
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from common.http import response, error, parse_body, utc_now, query_params

ALLOWED_TYPES = {"S3_BLOCK_PUBLIC_ACCESS", "EC2_NO_PUBLIC_IP", "RDS_NOT_PUBLICLY_ACCESSIBLE", "SECURITY_GROUP_NO_OPEN_SSH"}
ALLOWED_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}


def lambda_handler(event, context):
    table = boto3.resource("dynamodb").Table(os.environ["INTENTS_TABLE"])
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
    name = str(body.get("name", "")).strip()
    description = str(body.get("description", "")).strip()
    constraints = body.get("constraints")
    if not name or len(name) > 120:
        return error(400, "INVALID_NAME", "name is required and must be at most 120 characters.")
    if not isinstance(constraints, list) or not constraints or len(constraints) > 50:
        return error(400, "INVALID_CONSTRAINTS", "constraints must be a list containing 1 to 50 constraints.")
    normalised = []
    seen = set()
    for index, item in enumerate(constraints):
        if not isinstance(item, dict):
            return error(400, "INVALID_CONSTRAINT", f"constraints[{index}] must be an object.")
        ctype = str(item.get("type", "")).upper()
        cid = str(item.get("id", "")).strip() or f"constraint-{index + 1}"
        severity = str(item.get("severity", "MEDIUM")).upper()
        if ctype not in ALLOWED_TYPES:
            return error(400, "UNSUPPORTED_CONSTRAINT_TYPE", f"Unsupported constraint type: {ctype}.", {"allowedTypes": sorted(ALLOWED_TYPES)})
        if severity not in ALLOWED_SEVERITIES:
            return error(400, "INVALID_SEVERITY", f"Unsupported severity: {severity}.", {"allowedSeverities": sorted(ALLOWED_SEVERITIES)})
        if cid in seen:
            return error(400, "DUPLICATE_CONSTRAINT_ID", f"Constraint ID must be unique: {cid}.")
        seen.add(cid)
        normalised.append({"id": cid, "type": ctype, "severity": severity, "description": str(item.get("description", cid))[:500], "enabled": item.get("enabled", True) is not False})
    now = utc_now()
    record = {
        "intentId": str(uuid.uuid4()),
        "name": name,
        "description": description[:1000],
        "version": 1,
        "status": "DRAFT",
        "constraints": normalised,
        "createdAt": now,
        "updatedAt": now,
        "approvedAt": None,
        "createdBy": (event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {}).get("email") or "authenticated-user"),
        "sourceType": "JSON_CONSTRAINT_MANIFEST",
    }
    try:
        table.put_item(Item=record, ConditionExpression="attribute_not_exists(intentId)")
    except (ClientError, BotoCoreError) as exc:
        return error(502, "INTENT_WRITE_FAILED", "Could not save the intent.", str(exc)[:250])
    return response(201, {"item": record})
