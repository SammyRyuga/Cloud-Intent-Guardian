import hashlib
import os
import uuid
from common.dynamodb import dynamodb_resource
from botocore.exceptions import BotoCoreError, ClientError
from common.http import response, error, parse_body, utc_now
from common.inventory import collect_inventory
from common.contracts import is_local, scan_all
from common.manifest import ATTRIBUTE_TYPES
from common.attribute_rules import _violates, attribute_outcome
from common.observations import observations, ObservationUnavailable
from common.topology import evaluate_topology

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}


def _finding_id(intent_id, constraint_id, resource_id):
    raw = f"{intent_id}|{constraint_id}|{resource_id}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def lambda_handler(event, context):
    if is_local() and os.environ.get("INVENTORY_PROVIDER") != "fixture":
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
        inventory = observations(collect_inventory, os.environ.get("AWS_REGION"))
    except ObservationUnavailable as exc:
        return error(409, "AWS_DISCOVERY_DISABLED_LOCAL", str(exc))
    except (ClientError, BotoCoreError) as exc:
        return error(502, "INVENTORY_FAILED", "Could not collect live AWS inventory.", str(exc)[:250])
    if not inventory["meta"].get("accountId"):
        return error(502, "AWS_IDENTITY_UNAVAILABLE", "AWS identity could not be confirmed; evaluation was not saved.")

    try:
        new_or_updated = []
        checked_constraints = set()
        violated_constraints = set()
        unknown_constraints = set()
        passed_bindings = set()
        topology_results = []
        attribute_results = []
        not_applicable_constraints = set()
        if int(intent.get('schemaVersion', 1)) == 2:
            if os.environ.get('TOPOLOGY_ENABLED', 'true').lower() != 'true':
                return error(409, 'TOPOLOGY_NOT_ENABLED', 'Topology evaluation is disabled.')
            topology_results = evaluate_topology(intent, inventory)
        target_types = {'S3_BLOCK_PUBLIC_ACCESS': 'AWS::S3::Bucket', 'EC2_NO_PUBLIC_IP': 'AWS::EC2::Instance',
                        'RDS_NOT_PUBLICLY_ACCESSIBLE': 'AWS::RDS::DBInstance', 'SECURITY_GROUP_NO_OPEN_SSH': 'AWS::EC2::SecurityGroup'}
        current_ids = set()
        for constraint in intent.get("constraints", []):
            if not constraint.get("enabled", True) or constraint["type"] not in ATTRIBUTE_TYPES:
                continue
            bindings = []
            for resource in inventory["items"]:
                if resource['resourceType'] == target_types.get(constraint['type']):
                    checked_constraints.add(constraint['id'])
                outcome, observed, explanation = attribute_outcome(constraint, resource)
                if outcome != 'NOT_APPLICABLE':
                    bindings.append({'resourceId': resource['resourceId'], 'outcome': outcome})
                if outcome == 'UNKNOWN':
                    unknown_constraints.add(constraint['id'])
                if outcome == 'PASS':
                    passed_bindings.add((constraint['id'], resource['resourceId']))
                if outcome != 'VIOLATION':
                    continue
                violated_constraints.add(constraint['id'])
                finding_id = _finding_id(intent["intentId"], constraint["id"], resource["resourceId"])
                current_ids.add(finding_id)
                existing = findings_table.get_item(Key={"findingId": finding_id}).get("Item")
                now = utc_now()
                finding = {
                    **(existing or {}),
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
                    "accountId": inventory["meta"].get("accountId"),
                    "simulated": inventory["meta"].get("simulated", False),
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

            if not bindings:
                coverage = inventory['meta'].get('coverage', {}).get('resourceTypes', {}).get(target_types[constraint['type']])
                if coverage != 'COMPLETE':
                    checked_constraints.add(constraint['id'])
                    unknown_constraints.add(constraint['id'])
                else:
                    not_applicable_constraints.add(constraint['id'])
            result_state = ('VIOLATION' if constraint['id'] in violated_constraints else
                            'UNKNOWN' if constraint['id'] in unknown_constraints else
                            'NOT_APPLICABLE' if constraint['id'] in not_applicable_constraints else 'PASS')
            attribute_results.append({'ruleId': constraint['id'], 'type': constraint['type'],
                                      'outcome': result_state, 'bindings': bindings})

        resources = {row['resourceId']: row for row in inventory['items']}
        for result in topology_results:
            rule_id = result['ruleId']
            if result['outcome'] != 'NOT_APPLICABLE':
                checked_constraints.add(rule_id)
            else:
                not_applicable_constraints.add(rule_id)
            if result['outcome'] == 'UNKNOWN':
                unknown_constraints.add(rule_id)
            if result['outcome'] != 'VIOLATION':
                continue
            violated_constraints.add(rule_id)
            for witness in result.get('witnesses', []):
                rid = witness.get('resourceId') or witness.get('targetId') or witness.get('sourceId')
                if not rid:
                    continue
                resource = resources.get(rid, {'resourceId': rid, 'resourceType': 'Intent::Component', 'name': rid})
                fingerprint = rid + '|' + str(witness.get('sourceId', '')) + '|' + str(witness.get('targetId', ''))
                fid = _finding_id(intent['intentId'], rule_id, fingerprint)
                if fid in current_ids:
                    continue
                current_ids.add(fid)
                existing = findings_table.get_item(Key={'findingId': fid}, ConsistentRead=True).get('Item') or {}
                now = utc_now()
                observed = {key: value for key, value in witness.items() if key != 'resource'}
                evidence = result.get('evidence') or []
                evidence = [{'source': row.get('source', 'Topology observations'), 'resourceId': row.get('resourceId', rid),
                             'observedAt': row.get('observedAt', inventory['meta'].get('collectedAt', now)),
                             'details': row.get('details', row)} for row in evidence]
                if not evidence:
                    evidence = [{'source': resource.get('source', 'Topology observations'), 'resourceId': rid,
                                 'observedAt': inventory['meta'].get('collectedAt', now), 'details': observed}]
                finding = {**existing, 'findingId': fid,
                    'title': result.get('explanation', rule_id) + ' - ' + resource.get('name', rid),
                    'description': result.get('explanation', rule_id), 'explanation': result.get('explanation', rule_id),
                    'severity': result.get('severity', 'HIGH'), 'category': 'NETWORK_PATH',
                    'status': 'OPEN' if existing.get('status') in {None, 'RESOLVED'} else existing['status'],
                    'resourceId': rid, 'resourceName': resource.get('name', rid), 'resourceType': resource['resourceType'],
                    'region': inventory['meta']['region'], 'accountId': inventory['meta']['accountId'],
                    'intentId': intent['intentId'], 'intentName': intent.get('name'), 'intentVersion': intent.get('version', 1),
                    'constraintId': rule_id, 'ruleId': result['type'],
                    'expected': {'constraintType': result['type'], 'description': result.get('explanation')},
                    'observed': observed, 'evidence': evidence, 'firstSeenAt': existing.get('firstSeenAt', now),
                    'lastSeenAt': now, 'updatedAt': now, 'evaluationId': evaluation_id,
                    'simulated': inventory['meta'].get('simulated', False)}
                findings_table.put_item(Item=finding)
                new_or_updated.append(finding)

    except (ClientError, BotoCoreError) as exc:
        return error(502, "FINDING_WRITE_FAILED", "Evaluation could not persist all findings; no success is reported.", type(exc).__name__)

    # Only resolve old findings after a complete inventory. Partial collection must never clear findings.
    resolved_count = 0
    if not inventory["meta"].get("partial") and not unknown_constraints:
        try:
            previous, truncated = scan_all(findings_table)
            if truncated:
                inventory['meta']['partial'] = True
                inventory['meta']['warnings'].append({'source': 'findings', 'message': 'Resolution skipped because the findings scan was incomplete.'})
            for prior in previous if not truncated else []:
                topology_pass = any(row['ruleId'] == prior.get('constraintId') and row['outcome'] == 'PASS' for row in topology_results)
                binding_pass = (prior.get('constraintId'), prior.get('resourceId')) in passed_bindings
                if (prior.get("intentId") != intent["intentId"] or prior.get("status") == "RESOLVED"
                        or prior.get('accountId') != inventory['meta'].get('accountId')
                        or prior.get('region') != inventory['meta'].get('region')
                        or not (topology_pass or binding_pass)):
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
    status = "PARTIAL" if inventory["meta"].get("partial") or unknown_constraints else "SUCCEEDED"
    total = len(checked_constraints)
    failing = len(violated_constraints)
    passing = len(checked_constraints - violated_constraints - unknown_constraints)
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
                        "totalRules": total, "passingRules": passing, "failingRules": failing,
                        "unknownRules": len(unknown_constraints),
                        "notApplicableRules": len(not_applicable_constraints),
                        "definition": "Enabled applicable policy rules; unknown evidence prevents full conformance."},
        "summary": {"resourceCount": inventory["meta"]["totalResources"], "violationsFound": len(new_or_updated), "resolvedFindings": resolved_count, "inventoryPartial": inventory["meta"].get("partial", False) or bool(unknown_constraints)},
        "ruleResults": attribute_results + [
            {key: row[key] for key in ('ruleId', 'type', 'outcome', 'severity', 'explanation') if key in row}
            for row in topology_results],
        "simulated": inventory['meta'].get('simulated', False),
        "warnings": inventory["meta"].get("warnings", []),
    }
    try:
        evaluations_table.put_item(Item=evaluation)
    except (ClientError, BotoCoreError) as exc:
        return error(502, "EVALUATION_SAVE_FAILED", "Evaluation ran but the result record could not be saved.", str(exc)[:250])
    new_or_updated.sort(key=lambda item: SEVERITY_ORDER.get(item.get("severity", "INFO"), 5))
    return response(200, {"evaluation": evaluation, "findings": new_or_updated[:100], "inventory": inventory["meta"]})
