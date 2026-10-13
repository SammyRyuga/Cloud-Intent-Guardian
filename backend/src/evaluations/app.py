import hashlib
import os
import uuid
from common.dynamodb import dynamodb_resource
from botocore.exceptions import BotoCoreError, ClientError
from common.http import response, error, parse_body, utc_now
from common.inventory import collect_inventory
from common.contracts import is_local, scan_all

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}


def _violates(constraint, resource):
    ctype = constraint["type"]
    attrs = resource.get("attributes") or {}
    if ctype == "S3_BLOCK_PUBLIC_ACCESS" and resource["resourceType"] == "AWS::S3::Bucket":
        value = attrs.get("publicAccessBlockEnabled")
        return value is False, {"publicAccessBlockEnabled": value, "bucketPolicyPublic": attrs.get("bucketPolicyPublic")}, "All four S3 Block Public Access settings must be enabled."
    if ctype == "EC2_NO_PUBLIC_IP" and resource["resourceType"] == "AWS::EC2::Instance":
        value = attrs.get("publicIpAddress")
        return bool(value), {"publicIpAddress": value}, "The EC2 instance has a public IPv4 address."
    if ctype == "RDS_NOT_PUBLICLY_ACCESSIBLE" and resource["resourceType"] == "AWS::RDS::DBInstance":
        value = attrs.get("publiclyAccessible")
        return value is True, {"publiclyAccessible": value}, "The RDS instance is configured as publicly accessible."
    if ctype == "SECURITY_GROUP_NO_OPEN_SSH" and resource["resourceType"] == "AWS::EC2::SecurityGroup":
        matching = []
        for rule in attrs.get("ingressRules", []):
            protocol = str(rule.get("protocol", ""))
            first, last, cidr = rule.get("fromPort"), rule.get("toPort"), str(rule.get("cidr", ""))
            port_covers_ssh = protocol == "-1" or (protocol in {'tcp', '6'} and first is not None and last is not None and first <= 22 <= last)
            public_source = cidr in {"0.0.0.0/0", "::/0"}
            if port_covers_ssh and public_source:
                matching.append(rule)
        return bool(matching), {"matchingIngressRules": matching}, "The security group permits SSH (TCP/22) from the public internet."
    return False, {}, "Constraint does not apply to this resource type."


def _finding_id(intent_id, constraint_id, resource_id):
    raw = f"{intent_id}|{constraint_id}|{resource_id}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def lambda_handler(event, context):
    if is_local():
        return error(409, 'AWS_DISCOVERY_DISABLED_LOCAL', 'Live AWS evaluation is disabled in local API mode. Intent persistence is available.')
    try:
        body = parse_body(event)
    except Exception as exc:
        return error(400, "INVALID_JSON", "Request body must be a valid JSON object.", str(exc))

    try:
        dynamodb = dynamodb_resource()
        intents_table = dynamodb.Table(os.environ["INTENTS_TABLE"])
        findings_table = dynamodb.Table(os.environ["FINDINGS_TABLE"])
        evaluations_table = dynamodb.Table(os.environ["EVALUATIONS_TABLE"])
    except (ClientError, BotoCoreError) as exc:
        return error(502, "DYNAMODB_CONFIGURATION_FAILED", "Could not initialize DynamoDB.", str(exc)[:250])
    intent_id = body.get("intentId")
    try:
        if intent_id:
            intent = intents_table.get_item(Key={"intentId": intent_id}, ConsistentRead=True).get("Item")
            if not intent:
                return error(404, "INTENT_NOT_FOUND", "The requested intent does not exist.")
            candidates = [intent]
        else:
            candidates, truncated = scan_all(intents_table)
            if truncated:
                return error(409, 'INTENT_SELECTION_INCOMPLETE', 'Specify an approved intentId; default selection exceeded its scan bound.')
            candidates = [item for item in candidates if item.get("status") == "APPROVED"]
            candidates.sort(key=lambda item: item.get("updatedAt", ""), reverse=True)
            candidates = candidates[:1]
    except (ClientError, BotoCoreError) as exc:
        return error(502, "INTENT_READ_FAILED", "Could not load the approved intent.", str(exc)[:250])

    if not candidates:
        return error(409, "NO_APPROVED_INTENT", "Create an intent and approve it before running an evaluation.")
    intent = candidates[0]
    if intent.get("status") != "APPROVED":
        return error(409, "INTENT_NOT_APPROVED", "Only an approved intent can be evaluated.")

    evaluation_id = str(uuid.uuid4())
    started_at = utc_now()
    try:
        inventory = collect_inventory(os.environ.get("AWS_REGION"))
    except (ClientError, BotoCoreError) as exc:
        return error(502, "INVENTORY_FAILED", "Could not collect live AWS inventory.", str(exc)[:250])
    if not inventory["meta"].get("accountId"):
        return error(502, "AWS_IDENTITY_UNAVAILABLE", "AWS identity could not be confirmed; evaluation was not saved.")

    try:
        new_or_updated = []
        checked_constraints = set()
        violated_constraints = set()
        target_types = {'S3_BLOCK_PUBLIC_ACCESS': 'AWS::S3::Bucket', 'EC2_NO_PUBLIC_IP': 'AWS::EC2::Instance',
                        'RDS_NOT_PUBLICLY_ACCESSIBLE': 'AWS::RDS::DBInstance', 'SECURITY_GROUP_NO_OPEN_SSH': 'AWS::EC2::SecurityGroup'}
        current_ids = set()
        for constraint in intent.get("constraints", []):
            if not constraint.get("enabled", True):
                continue
            for resource in inventory["items"]:
                if resource['resourceType'] == target_types.get(constraint['type']):
                    checked_constraints.add(constraint['id'])
                violated, observed, explanation = _violates(constraint, resource)
                if not violated:
                    continue
                violated_constraints.add(constraint['id'])
                finding_id = _finding_id(intent["intentId"], constraint["id"], resource["resourceId"])
                current_ids.add(finding_id)
                existing = findings_table.get_item(Key={"findingId": finding_id}).get("Item")
                now = utc_now()
                finding = {
                    "findingId": finding_id,
                    "title": f"{constraint.get('description') or constraint['id']} — {resource.get('name') or resource['resourceId']}",
                    "description": constraint.get("description") or explanation,
                    "explanation": explanation,
                    "severity": constraint.get("severity", "MEDIUM"),
                    "category": {"S3_BLOCK_PUBLIC_ACCESS": "PUBLIC_EXPOSURE", "EC2_NO_PUBLIC_IP": "NETWORK_EXPOSURE", "RDS_NOT_PUBLICLY_ACCESSIBLE": "PUBLIC_EXPOSURE", "SECURITY_GROUP_NO_OPEN_SSH": "NETWORK_PATH"}.get(constraint["type"], "CONFIGURATION_DRIFT"),
                    "status": "OPEN" if not existing or existing.get("status") == "RESOLVED" else existing.get("status", "OPEN"),
                    "resourceId": resource["resourceId"],
                    "resourceName": resource.get("name", resource["resourceId"]),
                    "resourceType": resource["resourceType"],
                    "region": resource.get("region"),
                    "intentId": intent["intentId"],
                    "intentName": intent.get("name"),
                    "intentVersion": intent.get("version", 1),
                    "constraintId": constraint["id"],
                    "ruleId": constraint["type"],
                    "expected": {"description": constraint.get("description"), "constraintType": constraint["type"]},
                    "observed": observed,
                    "evidence": [{"source": resource.get("source"), "resourceId": resource["resourceId"], "observedAt": resource.get("lastObservedAt"), "details": observed}],
                    "firstSeenAt": existing.get("firstSeenAt", now) if existing else now,
                    "lastSeenAt": now,
                    "updatedAt": now,
                    "evaluationId": evaluation_id,
                }
                findings_table.put_item(Item=finding)
                new_or_updated.append(finding)

    except (ClientError, BotoCoreError) as exc:
        return error(502, "FINDING_WRITE_FAILED", "Evaluation could not persist all findings; no success is reported.", type(exc).__name__)

    # Only resolve old findings after a complete inventory. Partial collection must never clear findings.
    resolved_count = 0
    if not inventory["meta"].get("partial"):
        try:
            previous, truncated = scan_all(findings_table)
            if truncated:
                inventory['meta']['partial'] = True
                inventory['meta']['warnings'].append({'source': 'findings', 'message': 'Resolution skipped because the findings scan was incomplete.'})
            for prior in previous if not truncated else []:
                if prior.get("intentId") != intent["intentId"] or prior.get("status") == "RESOLVED":
                    continue
                if prior.get("findingId") not in current_ids:
                    findings_table.update_item(
                        Key={"findingId": prior["findingId"]},
                        UpdateExpression="SET #s = :resolved, updatedAt = :now, resolvedAt = :now",
                        ExpressionAttributeNames={"#s": "status"},
                        ExpressionAttributeValues={":resolved": "RESOLVED", ":now": utc_now()},
                    )
                    resolved_count += 1
        except (ClientError, BotoCoreError) as exc:
            inventory['meta']['partial'] = True
            inventory['meta']['warnings'].append({'source': 'findings', 'message': f'Resolution failed: {type(exc).__name__}'})

    finished_at = utc_now()
    status = "PARTIAL" if inventory["meta"].get("partial") else "SUCCEEDED"
    total = len(checked_constraints)
    failing = len(violated_constraints)
    passing = total - failing
    evaluation = {
        "evaluationId": evaluation_id,
        "status": status,
        "intentId": intent["intentId"],
        "intentName": intent.get("name"),
        "intentVersion": intent.get("version", 1),
        "accountId": inventory["meta"].get("accountId"),
        "region": inventory["meta"].get("region"),
        "startedAt": started_at,
        "finishedAt": finished_at,
        "conformance": {"percent": round(passing / total * 100) if total and status == 'SUCCEEDED' else None,
                        "totalRules": total, "passingRules": passing, "failingRules": failing},
        "summary": {"resourceCount": inventory["meta"]["totalResources"], "violationsFound": len(new_or_updated), "resolvedFindings": resolved_count, "inventoryPartial": inventory["meta"].get("partial", False)},
        "warnings": inventory["meta"].get("warnings", []),
    }
    try:
        evaluations_table.put_item(Item=evaluation)
    except (ClientError, BotoCoreError) as exc:
        return error(502, "EVALUATION_SAVE_FAILED", "Evaluation ran but the result record could not be saved.", str(exc)[:250])
    new_or_updated.sort(key=lambda item: SEVERITY_ORDER.get(item.get("severity", "INFO"), 5))
    return response(200, {"evaluation": evaluation, "findings": new_or_updated[:100], "inventory": inventory["meta"]})
