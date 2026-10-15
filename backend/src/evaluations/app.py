"""Evaluation job API and deterministic pinned evaluation engine."""
from __future__ import annotations

import hashlib
import json
import os

from botocore.exceptions import BotoCoreError, ClientError

from common.auth import AuthorizationError, authorize, configured_scope
from common.contracts import is_local
from common.dynamodb import dynamodb_resource
from common.evaluation_jobs import JobError, get_job, list_jobs, new_job, resolve_pinned_intent
from common.http import error, parse_body, query_params, response, utc_now
from common.manifest import ATTRIBUTE_TYPES
from common.attribute_rules import attribute_outcome
from common.topology import evaluate_topology


TARGET_TYPES = {
    "S3_BLOCK_PUBLIC_ACCESS": "AWS::S3::Bucket",
    "EC2_NO_PUBLIC_IP": "AWS::EC2::Instance",
    "RDS_NOT_PUBLICLY_ACCESSIBLE": "AWS::RDS::DBInstance",
    "SECURITY_GROUP_NO_OPEN_SSH": "AWS::EC2::SecurityGroup",
}
ATTRIBUTE_CATEGORIES = {
    "S3_BLOCK_PUBLIC_ACCESS": "PUBLIC_EXPOSURE",
    "EC2_NO_PUBLIC_IP": "NETWORK_EXPOSURE",
    "RDS_NOT_PUBLICLY_ACCESSIBLE": "PUBLIC_EXPOSURE",
    "SECURITY_GROUP_NO_OPEN_SSH": "NETWORK_PATH",
}


def _finding_id(intent_id: str, constraint_id: str, resource_id: str) -> str:
    raw = f"{intent_id}|{constraint_id}|{resource_id}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def run_pinned_evaluation(intent: dict, inventory: dict, evaluation_id: str) -> tuple[dict, list[dict]]:
    """Evaluate only the provided immutable intent and observations; perform no I/O."""
    started_at = utc_now()
    topology_results = []
    attribute_results = []
    findings: list[dict] = []
    checked: set[str] = set()
    violated: set[str] = set()
    unknown: set[str] = set()
    not_applicable: set[str] = set()
    passed_bindings: set[tuple[str, str]] = set()

    if int(intent.get("schemaVersion", 1)) == 2:
        if os.environ.get("TOPOLOGY_ENABLED", "true").lower() != "true":
            raise JobError(409, "TOPOLOGY_NOT_ENABLED", "Topology evaluation is disabled.")
        topology_results = evaluate_topology(intent, inventory)

    for constraint in intent.get("constraints", []):
        if not constraint.get("enabled", True) or constraint.get("type") not in ATTRIBUTE_TYPES:
            continue
        target_type = TARGET_TYPES[constraint["type"]]
        bindings = []
        for resource in inventory.get("items", []):
            if resource.get("resourceType") != target_type:
                continue
            checked.add(constraint["id"])
            outcome, observed, explanation = attribute_outcome(constraint, resource)
            if outcome != "NOT_APPLICABLE":
                bindings.append({"resourceId": resource["resourceId"], "outcome": outcome})
            if outcome == "UNKNOWN":
                unknown.add(constraint["id"])
            elif outcome == "PASS":
                passed_bindings.add((constraint["id"], resource["resourceId"]))
            elif outcome == "VIOLATION":
                violated.add(constraint["id"])
                now = utc_now()
                findings.append({
                    "findingId": _finding_id(intent["intentId"], constraint["id"], resource["resourceId"]),
                    "title": f"{constraint.get('description') or constraint['id']} - {resource.get('name') or resource['resourceId']}",
                    "description": constraint.get("description") or explanation,
                    "explanation": explanation, "severity": constraint.get("severity", "MEDIUM"),
                    "category": ATTRIBUTE_CATEGORIES[constraint["type"]], "status": "OPEN",
                    "resourceId": resource["resourceId"], "resourceName": resource.get("name", resource["resourceId"]),
                    "resourceType": resource["resourceType"], "region": resource.get("region"),
                    "accountId": inventory.get("meta", {}).get("accountId"),
                    "simulated": inventory.get("meta", {}).get("simulated", False),
                    "intentId": intent["intentId"], "intentName": intent.get("name"),
                    "intentVersion": int(intent.get("version", 1)), "constraintId": constraint["id"],
                    "ruleId": constraint["type"],
                    "expected": {"description": constraint.get("description"), "constraintType": constraint["type"]},
                    "observed": observed,
                    "evidence": [{"source": resource.get("source"), "resourceId": resource["resourceId"],
                                  "observedAt": resource.get("lastObservedAt"), "details": observed}],
                    "firstSeenAt": now, "lastSeenAt": now, "updatedAt": now,
                    "evaluationId": evaluation_id,
                })
        if not bindings:
            coverage = inventory.get("meta", {}).get("coverage", {}).get("resourceTypes", {}).get(target_type)
            if coverage != "COMPLETE":
                checked.add(constraint["id"])
                unknown.add(constraint["id"])
            else:
                not_applicable.add(constraint["id"])
        state = ("VIOLATION" if constraint["id"] in violated else "UNKNOWN" if constraint["id"] in unknown
                 else "NOT_APPLICABLE" if constraint["id"] in not_applicable else "PASS")
        attribute_results.append({"ruleId": constraint["id"], "type": constraint["type"],
                                  "outcome": state, "bindings": bindings})

    resources = {row["resourceId"]: row for row in inventory.get("items", []) if row.get("resourceId")}
    for result in topology_results:
        rule_id = result["ruleId"]
        if result["outcome"] == "NOT_APPLICABLE":
            not_applicable.add(rule_id)
        else:
            checked.add(rule_id)
        if result["outcome"] == "UNKNOWN":
            unknown.add(rule_id)
        if result["outcome"] != "VIOLATION":
            continue
        violated.add(rule_id)
        for witness in result.get("witnesses", []):
            rid = witness.get("resourceId") or witness.get("targetId") or witness.get("sourceId")
            if not rid:
                continue
            resource = resources.get(rid, {"resourceId": rid, "resourceType": "Intent::Component", "name": rid})
            fingerprint = rid + "|" + str(witness.get("sourceId", "")) + "|" + str(witness.get("targetId", ""))
            fid = _finding_id(intent["intentId"], rule_id, fingerprint)
            if any(row["findingId"] == fid for row in findings):
                continue
            now = utc_now()
            observed = {key: value for key, value in witness.items() if key != "resource"}
            evidence = [{"source": row.get("source", "Topology observations"), "resourceId": row.get("resourceId", rid),
                         "observedAt": row.get("observedAt", inventory.get("meta", {}).get("collectedAt", now)),
                         "details": row.get("details", row)} for row in result.get("evidence", [])]
            if not evidence:
                evidence = [{"source": resource.get("source", "Topology observations"), "resourceId": rid,
                             "observedAt": inventory.get("meta", {}).get("collectedAt", now), "details": observed}]
            findings.append({
                "findingId": fid, "title": result.get("explanation", rule_id) + " - " + resource.get("name", rid),
                "description": result.get("explanation", rule_id), "explanation": result.get("explanation", rule_id),
                "severity": result.get("severity", "HIGH"), "category": "NETWORK_PATH", "status": "OPEN",
                "resourceId": rid, "resourceName": resource.get("name", rid), "resourceType": resource["resourceType"],
                "region": inventory.get("meta", {}).get("region"), "accountId": inventory.get("meta", {}).get("accountId"),
                "intentId": intent["intentId"], "intentName": intent.get("name"),
                "intentVersion": int(intent.get("version", 1)), "constraintId": rule_id, "ruleId": result["type"],
                "expected": {"constraintType": result["type"], "description": result.get("explanation")},
                "observed": observed, "evidence": evidence, "firstSeenAt": now, "lastSeenAt": now,
                "updatedAt": now, "evaluationId": evaluation_id,
                "simulated": inventory.get("meta", {}).get("simulated", False),
            })

    if inventory.get("meta", {}).get("partial"):
        # A positive, well-evidenced violation is retained, while absence checks stay unknown.
        for row in attribute_results:
            if row["outcome"] == "PASS" and not row.get("bindings"):
                row["outcome"] = "UNKNOWN"
                unknown.add(row["ruleId"])

    total, failing = len(checked), len(violated)
    passing = len(checked - violated - unknown)
    status = "PARTIAL" if inventory.get("meta", {}).get("partial") or unknown else "SUCCEEDED"
    meta = inventory.get("meta", {})
    evaluation = {
        "evaluationId": evaluation_id, "status": status, "intentId": intent["intentId"],
        "intentName": intent.get("name"), "intentVersion": int(intent.get("version", 1)),
        "intentHash": intent.get("contentHash"), "accountId": meta.get("accountId"), "region": meta.get("region"),
        "startedAt": started_at, "finishedAt": utc_now(),
        "conformance": {"percent": round(passing / total * 100) if total and status == "SUCCEEDED" else None,
                        "totalRules": total, "passingRules": passing, "failingRules": failing,
                        "unknownRules": len(unknown), "notApplicableRules": len(not_applicable),
                        "definition": "Enabled applicable policy rules; unknown evidence prevents full conformance."},
        "summary": {"resourceCount": meta.get("totalResources", len(inventory.get("items", []))),
                    "violationsFound": len(findings), "resolvedFindings": 0,
                    "inventoryPartial": bool(meta.get("partial") or unknown)},
        "ruleResults": attribute_results + [
            {key: row[key] for key in ("ruleId", "type", "outcome", "severity", "explanation") if key in row}
            for row in topology_results],
        "simulated": meta.get("simulated", False), "warnings": meta.get("warnings", []),
    }
    return evaluation, findings


def _response_error(exc: JobError):
    return error(exc.status, exc.code, exc.message, exc.details)


def _job_summary(item: dict) -> dict:
    fields = ("evaluationId", "status", "intentId", "intentName", "intentVersion", "scopeKey",
              "createdAt", "createdOrder", "startedAt", "finishedAt", "progressStage",
              "summary", "conformance", "warnings", "error", "simulated", "accountId", "region", "ruleResults")
    return {key: item[key] for key in fields if key in item}


def lambda_handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method") or event.get("httpMethod", "POST")
    method = str(method).upper()
    path_params = event.get("pathParameters") or {}
    evaluation_id = path_params.get("evaluationId") or path_params.get("id")
    try:
        actor = authorize(event, "admin" if method == "POST" else "viewer")
        scope = configured_scope()
    except AuthorizationError as exc:
        return error(exc.status, exc.code, str(exc))

    local = is_local()
    provider = os.environ.get("INVENTORY_PROVIDER", "aws")
    if method == "POST" and local and provider != "fixture":
        return error(409, "AWS_DISCOVERY_DISABLED_LOCAL", "Live AWS evaluation is disabled in local API mode.")
    if method == "POST" and not local and provider != "aws":
        return error(409, "FIXTURE_PROVIDER_LOCAL_ONLY", "Fixture evaluations are available only in explicit local mode.")

    try:
        db = dynamodb_resource()
        table = db.Table(os.environ["EVALUATIONS_TABLE"])
    except (KeyError, ClientError, BotoCoreError) as exc:
        return error(502, "DYNAMODB_CONFIGURATION_FAILED", "Could not initialize evaluation storage.", str(exc)[:250])

    if method == "POST":
        if not local and os.environ.get("ASYNC_WORKER_ENABLED", "false").lower() != "true":
            return error(409, "ASYNC_EVALUATION_NOT_ENABLED", "Evaluation work cannot be accepted until the async worker is enabled.")
        try:
            body = parse_body(event)
        except Exception as exc:
            return error(400, "INVALID_JSON", "Request body must be a valid JSON object.", str(exc))
        if set(body) - {"intentId", "intentVersion", "reason"}:
            return error(400, "INVALID_REQUEST", "Only intentId, intentVersion, and reason are accepted.")
        if body.get("intentId") is not None and (not isinstance(body["intentId"], str) or not body["intentId"] or len(body["intentId"]) > 200):
            return error(400, "INVALID_REQUEST", "intentId must be a non-empty string of at most 200 characters.")
        if body.get("reason") is not None and (not isinstance(body["reason"], str) or len(body["reason"]) > 500):
            return error(400, "INVALID_REQUEST", "reason must be a string of at most 500 characters.")
        try:
            intent, _ = resolve_pinned_intent(db, db.Table(os.environ["INTENTS_TABLE"]), body.get("intentId"), body.get("intentVersion"), scope)
            job = new_job(db, actor, intent, scope, event.get("requestContext", {}).get("requestId"), body.get("reason"))
            return response(202, {"evaluation": {key: job.get(key) for key in ("evaluationId", "status", "intentId", "intentVersion", "createdAt")},
                                  "statusUrl": f"/v1/evaluations/{job['evaluationId']}"})
        except JobError as exc:
            return _response_error(exc)
        except (ClientError, BotoCoreError, KeyError) as exc:
            return error(502, "EVALUATION_QUEUE_FAILED", "Could not durably queue the evaluation.", str(exc)[:250])

    if method != "GET":
        return error(405, "METHOD_NOT_ALLOWED", "Use POST to queue an evaluation or GET to read evaluation history.")
    try:
        if evaluation_id:
            item = get_job(table, evaluation_id, scope)
            if not item:
                return error(404, "EVALUATION_NOT_FOUND", "The requested evaluation does not exist.")
            return response(200, {"item": _job_summary(item)})
        result = list_jobs(table, query_params(event), scope)
        result["items"] = [_job_summary(item) for item in result["items"]]
        return response(200, result)
    except JobError as exc:
        return _response_error(exc)
    except (ClientError, BotoCoreError) as exc:
        return error(502, "EVALUATION_READ_FAILED", "Could not read evaluation history.", str(exc)[:250])
