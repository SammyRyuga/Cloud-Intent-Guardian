"""Idempotent evaluation stream worker and fixture-only local runner target."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from boto3.dynamodb.types import TypeDeserializer
from boto3.dynamodb.conditions import Key
from botocore.exceptions import BotoCoreError, ClientError

from common.audit import audit_event, audit_put, transaction_write
from common.auth import configured_scope
from common.escalation import escalate
from common.drift import stage as stage_drift
from common.contracts import scan_all
from common.dynamodb import dynamodb_resource
from common.evaluation_jobs import (JobError, artifact_limit_check,
                                    chunk_artifacts, resolve_pinned_intent)
from common.http import utc_now, _json_default
from common.inventory import collect_inventory
from common.network_evidence import enrich_network_evidence
from common.observations import ObservationUnavailable, observations
from common.versions import content_from, content_hash
from evaluations.app import run_pinned_evaluation


DESERIALIZER = TypeDeserializer()
STAGE_ORDER = {"QUEUED": -1, "CLAIMED": 0, "WAITING_FOR_PUBLICATION_LOCK": 0,
               "COLLECTING": 1, "EVALUATING": 2, "WRITING_ARTIFACTS": 3,
               "PUBLISHING": 4, "SUCCEEDED": 5, "PARTIAL": 5, "FAILED": 5}


def _seconds(name: str, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(os.environ.get(name, default))))
    except (ValueError, TypeError):
        return default


def _to_native(value: Any) -> Any:
    if isinstance(value, dict):
        if len(value) == 1 and next(iter(value)) in {"S", "N", "BOOL", "NULL", "M", "L", "SS", "NS", "BS", "B"}:
            return DESERIALIZER.deserialize(value)
        return {key: _to_native(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_native(item) for item in value]
    return value


def _job_id_from_record(record: dict) -> str | None:
    if record.get("eventName") != "INSERT":
        return None
    image = record.get("dynamodb", {}).get("NewImage") or {}
    row = _to_native(image)
    if isinstance(row, dict) and row.get("status") == "QUEUED":
        return row.get("evaluationId")
    return None


def _state_audit(db, job_table_name, audit_table_name, item, actor, action, stage, extra=None):
    current = db.Table(job_table_name).get_item(Key={"evaluationId": item["evaluationId"]}, ConsistentRead=True).get("Item") or {}
    if (current.get("status") == "RUNNING" and
            STAGE_ORDER.get(current.get("progressStage"), -1) > STAGE_ORDER.get(stage, -1)):
        return
    now = utc_now()
    updated = {"TableName": job_table_name, "Key": {"evaluationId": item["evaluationId"]},
               "UpdateExpression": "SET progressStage = :stage, updatedAt = :now",
               "ConditionExpression": "#status = :running AND leaseOwner = :owner",
               "ExpressionAttributeNames": {"#status": "status"},
               "ExpressionAttributeValues": {":stage": stage, ":now": now, ":running": "RUNNING",
                                              ":owner": item["evaluationId"]}}
    event = audit_event(actor, action, {"type": "EVALUATION", "id": item["evaluationId"]}, requestId=f"{item['evaluationId']}:{action}:{stage}",
                        metadata={"stage": stage, **(extra or {})}, scope=item["scopeKey"])
    try:
        transaction_write(db, [{"Update": updated}, audit_put(event)])
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") not in {"ConditionalCheckFailedException", "TransactionCanceledException"}:
            raise
        current = db.Table(job_table_name).get_item(Key={"evaluationId": item["evaluationId"]}, ConsistentRead=True).get("Item") or {}
        prior_event = db.Table(audit_table_name).get_item(Key={"auditId": event["auditId"]}, ConsistentRead=True).get("Item")
        if not prior_event or current.get("status") != "RUNNING" or current.get("progressStage") != stage:
            raise


def _claim_job(table, evaluation_id: str, max_attempts: int, lease_seconds: int) -> dict | None:
    before = table.get_item(Key={"evaluationId": evaluation_id}, ConsistentRead=True).get("Item")
    if not before:
        return None
    prior_stage = before.get("progressStage", "QUEUED")
    next_stage = ("CLAIMED" if before.get("status") == "QUEUED" and prior_stage in {"QUEUED", "WAITING_FOR_PUBLICATION_LOCK"}
                  else prior_stage)
    now = utc_now()
    expiry = (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)).isoformat().replace("+00:00", "Z")
    try:
        result = table.update_item(
            Key={"evaluationId": evaluation_id},
            UpdateExpression="SET #s = :running, startedAt = if_not_exists(startedAt, :now), leaseOwner = :owner, leaseExpiresAt = :expiry, progressStage = :stage, updatedAt = :now ADD attemptCount :one",
            ConditionExpression="(attribute_exists(evaluationId)) AND (attribute_not_exists(#s) OR #s = :queued OR (#s = :running AND leaseExpiresAt < :now)) AND attemptCount < :max AND deadlineAt > :now",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":running": "RUNNING", ":queued": "QUEUED", ":now": now,
                                      ":owner": evaluation_id, ":expiry": expiry, ":stage": next_stage,
                                      ":one": 1, ":max": max_attempts},
            ReturnValues="ALL_NEW")
        return result.get("Attributes")
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return None
        raise


def _acquire_publication_lock(intent_table, intent_id, evaluation_id, created_order, lease_seconds):
    now = utc_now()
    expiry = (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)).isoformat().replace("+00:00", "Z")
    try:
        intent_table.update_item(
            Key={"intentId": intent_id},
            UpdateExpression="SET publicationLeaseOwner = :owner, publicationLeaseExpiresAt = :expiry",
            ConditionExpression="attribute_exists(intentId) AND (attribute_not_exists(latestEvaluationOrder) OR latestEvaluationOrder < :order) AND (attribute_not_exists(publicationLeaseOwner) OR publicationLeaseOwner = :owner OR publicationLeaseExpiresAt < :now)",
            ExpressionAttributeValues={":owner": evaluation_id, ":expiry": expiry, ":now": now, ":order": created_order})
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        raise


def _release_publication_lock(intent_table, intent_id, evaluation_id):
    try:
        intent_table.update_item(Key={"intentId": intent_id},
                                 UpdateExpression="REMOVE publicationLeaseOwner, publicationLeaseExpiresAt",
                                 ConditionExpression="publicationLeaseOwner = :owner",
                                 ExpressionAttributeValues={":owner": evaluation_id})
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise


def _persist_artifacts(db, table_name, job_id, intent, evaluation, inventory, findings):
    artifact_rows = [
        {"kind": "intent", "value": intent},
        {"kind": "snapshot", "inventory": inventory},
        {"kind": "evaluation", "value": evaluation},
        {"kind": "findingEvidence", "items": findings},
    ]
    chunks, manifest = chunk_artifacts(job_id, artifact_rows)
    table = db.Table(table_name)
    for item in chunks:
        artifact_limit_check(item)
        table.put_item(Item=item)
    # A manifest is the readiness marker and is always written last.
    existing = table.get_item(Key={"evaluationId": job_id, "artifactKey": "manifest"}, ConsistentRead=True).get("Item")
    if existing:
        if (not existing.get("complete") or existing.get("sha256") != manifest["sha256"]
                or existing.get("chunkCount") != manifest["chunkCount"]):
            raise JobError(409, "ARTIFACT_MANIFEST_CONFLICT", "A prior attempt wrote a different or incomplete artifact manifest.")
    else:
        table.put_item(Item=manifest, ConditionExpression="attribute_not_exists(artifactKey)")
    return manifest


def _load_complete_artifacts(db, table_name, job_id):
    table = db.Table(table_name)
    manifest = table.get_item(Key={"evaluationId": job_id, "artifactKey": "manifest"}, ConsistentRead=True).get("Item")
    if not manifest:
        return None
    if not manifest.get("complete"):
        raise JobError(409, "ARTIFACT_MANIFEST_INCOMPLETE", "A staged artifact manifest is incomplete.")
    chunks = []
    options = {"KeyConditionExpression": Key("evaluationId").eq(job_id)}
    for _ in range(100):
        page = table.query(**options)
        chunks.extend(row for row in page.get("Items", []) if row.get("artifactKey", "").startswith("chunk#"))
        next_key = page.get("LastEvaluatedKey")
        if not next_key:
            break
        options["ExclusiveStartKey"] = next_key
    else:
        raise JobError(413, "ARTIFACT_CHUNK_SCAN_LIMIT", "The evaluation artifact exceeds its bounded recovery limit.")
    chunks.sort(key=lambda row: row["artifactKey"])
    if len(chunks) != manifest.get("chunkCount"):
        raise JobError(409, "ARTIFACT_CHUNKS_MISSING", "The completed artifact manifest references missing chunks.")
    data = bytearray()
    import hashlib
    for index, row in enumerate(chunks):
        if row.get("artifactKey") != f"chunk#{index:06d}":
            raise JobError(409, "ARTIFACT_CHUNK_ORDER_INVALID", "An artifact chunk is missing or out of order.")
        chunk = row.get("data", "").encode("utf-8")
        if hashlib.sha256(chunk).hexdigest() != row.get("sha256"):
            raise JobError(409, "ARTIFACT_CHUNK_HASH_MISMATCH", "An evaluation artifact chunk failed its hash check.")
        data.extend(chunk)
    if hashlib.sha256(data).hexdigest() != manifest.get("sha256"):
        raise JobError(409, "ARTIFACT_HASH_MISMATCH", "The evaluation artifacts failed their manifest hash check.")
    if len(data) != manifest.get("totalBytes"):
        raise JobError(409, "ARTIFACT_LENGTH_MISMATCH", "The evaluation artifact length does not match its manifest.")
    try:
        rows = json.loads(data.decode("utf-8"))
        by_kind = {row["kind"]: row for row in rows}
        return (by_kind["evaluation"]["value"], by_kind["snapshot"]["inventory"],
                by_kind["findingEvidence"]["items"])
    except (UnicodeError, ValueError, KeyError, TypeError) as exc:
        raise JobError(409, "ARTIFACT_CONTENT_INVALID", "The completed evaluation artifacts could not be decoded.") from exc


def _finding_write(db, finding_table, audit_table, job, finding, actor):
    order = job["createdOrder"]
    existing = finding_table.get_item(Key={"findingId": finding["findingId"]}, ConsistentRead=True).get("Item") or {}
    if existing and (existing.get("scopeKey") != job["scopeKey"]
                     or existing.get("intentId") != job["intentId"]):
        raise JobError(
            409, "FINDING_OWNERSHIP_MISMATCH",
            "An existing finding with this identifier is not owned by the evaluation scope and intent.",
        )
    if existing.get("lastEvaluationOrder", "") > order:
        return False
    now = utc_now()
    finding = {**existing, **finding, "scopeKey": job["scopeKey"],
               "scopeIntentKey": f"{job['scopeKey']}#{job['intentId']}",
               "lastEvaluationOrder": order, "lastSeenAt": now, "updatedAt": now}
    if existing.get("status") == "RESOLVED":
        finding["status"] = "OPEN"
    elif existing.get("status"):
        finding["status"] = existing["status"]
    finding.setdefault("revision", 0)
    event = audit_event(actor, "FINDING_DETECTED", {"type": "FINDING", "id": finding["findingId"]},
                        requestId=f"{job['evaluationId']}:finding:{finding['findingId']}",
                        metadata={"evaluationId": job["evaluationId"], "intentId": job["intentId"],
                                  "intentVersion": job["intentVersion"], "status": finding["status"]},
                        scope=job["scopeKey"])
    item_op = {"Put": {"TableName": finding_table.name, "Item": finding,
                        "ConditionExpression": "(attribute_not_exists(lastEvaluationOrder) OR lastEvaluationOrder <= :order) AND (attribute_not_exists(revision) OR revision = :revision) AND (attribute_not_exists(#status) OR #status = :status)",
                        "ExpressionAttributeNames": {"#status": "status"},
                        "ExpressionAttributeValues": {":order": order, ":revision": existing.get("revision", 0),
                                                       ":status": existing.get("status", "OPEN")}}}
    try:
        transaction_write(db, [item_op, audit_put(event)])
        return True
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in {"ConditionalCheckFailedException", "TransactionCanceledException"}:
            latest = finding_table.get_item(Key={"findingId": finding["findingId"]}, ConsistentRead=True).get("Item") or {}
            prior_event = db.Table(audit_table).get_item(Key={"auditId": event["auditId"]}, ConsistentRead=True).get("Item")
            if latest.get("lastEvaluationOrder", "") > order:
                return False
            if latest.get("lastEvaluationOrder") == order and latest.get("evaluationId") == job["evaluationId"] and prior_event:
                return False
            raise
        raise


def _resolution_plan(db, job, evaluation, findings, actor, only_ids=None):
    """Stage scoped resolution updates for one atomic terminal transaction."""
    if evaluation.get("status") != "SUCCEEDED" or evaluation.get("summary", {}).get("inventoryPartial"):
        return [], []
    present_ids = {row["findingId"] for row in findings}
    rules = evaluation.get("ruleResults", [])
    topology_pass = {row.get("ruleId") for row in rules if row.get("outcome") == "PASS" and "bindings" not in row}
    binding_pass = {(row.get("ruleId"), binding.get("resourceId"))
                    for row in rules for binding in row.get("bindings", []) if binding.get("outcome") == "PASS"}
    finding_table = db.Table(os.environ["FINDINGS_TABLE"])
    prior, truncated = scan_all(finding_table)
    if truncated:
        return [], []
    resolved_ids = []
    operations = []
    now = utc_now()
    for finding in prior:
        if (finding.get("scopeKey") != job["scopeKey"] or finding.get("intentId") != job["intentId"]
                or finding.get("status") == "RESOLVED" or finding.get("findingId") in present_ids
                or finding.get("lastEvaluationOrder", "") >= job["createdOrder"]):
            continue
        if only_ids is not None and finding.get("findingId") not in only_ids:
            continue
        if (finding.get("constraintId") not in topology_pass and
                (finding.get("constraintId"), finding.get("resourceId")) not in binding_pass):
            continue
        revision = int(finding.get("revision", 0))
        updated = {**finding, "status": "RESOLVED", "resolvedAt": now, "updatedAt": now,
                   "revision": revision + 1, "lastEvaluationOrder": job["createdOrder"],
                   "evaluationId": job["evaluationId"]}
        event = audit_event(actor, "FINDING_RESOLVED", {"type": "FINDING", "id": finding["findingId"]},
                            requestId=f"{job['evaluationId']}:resolved:{finding['findingId']}",
                            metadata={"intentId": job["intentId"], "intentVersion": job["intentVersion"],
                                      "previousStatus": finding.get("status")}, scope=job["scopeKey"])
        operation = {"Put": {"TableName": finding_table.name, "Item": updated,
                              "ConditionExpression": "#status = :status AND (attribute_not_exists(revision) OR revision = :revision) AND (attribute_not_exists(lastEvaluationOrder) OR lastEvaluationOrder < :order)",
                              "ExpressionAttributeNames": {"#status": "status"},
                              "ExpressionAttributeValues": {":status": finding["status"], ":revision": revision,
                                                             ":order": job["createdOrder"]}}}
        operations.extend([operation, audit_put(event)])
        resolved_ids.append(finding["findingId"])
    # Keep the complete finding transition set atomic with terminal publication.
    # DynamoDB transactions allow at most 100 actions; reserve room for job,
    # intent pointer and terminal audit writes.
    if len(operations) > 96:
        return [], []
    return operations, resolved_ids


def _load_publication(db, job_id):
    row = db.Table(os.environ["EVALUATION_ARTIFACTS_TABLE"]).get_item(
        Key={"evaluationId": job_id, "artifactKey": "publication"}, ConsistentRead=True).get("Item")
    if not row:
        return None
    value = row.get("value")
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), default=_json_default).encode("utf-8")
    import hashlib
    if hashlib.sha256(data).hexdigest() != row.get("sha256"):
        raise JobError(409, "PUBLICATION_ARTIFACT_HASH_MISMATCH", "The evaluation publication artifact failed its hash check.")
    return value


def _write_publication(db, job_id, evaluation, resolved_ids):
    value = {"status": evaluation["status"], "summary": evaluation.get("summary"),
             "conformance": evaluation.get("conformance"), "warnings": evaluation.get("warnings", []),
             "resolvedFindingIds": sorted(resolved_ids)}
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), default=_json_default).encode("utf-8")
    import hashlib
    item = {"evaluationId": job_id, "artifactKey": "publication", "value": value,
            "byteLength": len(data), "sha256": hashlib.sha256(data).hexdigest(), "complete": True}
    artifact_limit_check(item)
    table = db.Table(os.environ["EVALUATION_ARTIFACTS_TABLE"])
    existing = table.get_item(Key={"evaluationId": job_id, "artifactKey": "publication"}, ConsistentRead=True).get("Item")
    if existing:
        if existing.get("sha256") != item["sha256"]:
            raise JobError(409, "PUBLICATION_ARTIFACT_CONFLICT", "A retry produced a conflicting publication result.")
        return existing["value"]
    table.put_item(Item=item, ConditionExpression="attribute_not_exists(artifactKey)")
    return value


def _publish_terminal(db, job_table, audit_table, job, evaluation, status, actor, error_payload=None,
                      resolution_operations=None, drift_baseline=None):
    now = utc_now()
    summary = evaluation.get("summary") if evaluation else job.get("summary")
    conformance = evaluation.get("conformance") if evaluation else job.get("conformance")
    warnings = evaluation.get("warnings", []) if evaluation else job.get("warnings", [])
    values = {":status": status, ":now": now, ":stage": status, ":owner": job["evaluationId"], ":running": "RUNNING",
              ":summary": summary, ":conformance": conformance, ":warnings": warnings,
              ":simulated": bool(evaluation.get("simulated")) if evaluation else False,
              ":account": evaluation.get("accountId") if evaluation else job.get("accountId"),
              ":region": evaluation.get("region") if evaluation else job.get("region"),
              ":rules": [{key: rule[key] for key in ("ruleId", "type", "outcome", "severity", "explanation") if key in rule}
                         for rule in evaluation.get("ruleResults", [])] if evaluation else job.get("ruleResults", [])}
    expression = "SET #s = :status, finishedAt = :now, updatedAt = :now, progressStage = :stage, summary = :summary, conformance = :conformance, warnings = :warnings, simulated = :simulated, ruleResults = :rules"
    if values[":account"] is not None:
        expression += ", accountId = :account"
    if values[":region"] is not None:
        expression += ", #region = :region"
    if error_payload:
        expression += ", #error = :error"
        values[":error"] = error_payload
    expression += " REMOVE leaseOwner, leaseExpiresAt"
    if not error_payload:
        expression += ", #error"
    names = {"#s": "status", "#error": "error"}
    if values[":region"] is not None:
        names["#region"] = "region"
    update = {"TableName": job_table.name, "Key": {"evaluationId": job["evaluationId"]},
              "UpdateExpression": expression, "ConditionExpression": "#s = :running AND leaseOwner = :owner",
              "ExpressionAttributeNames": names, "ExpressionAttributeValues": values}
    event = audit_event(actor, f"EVALUATION_{status}", {"type": "EVALUATION", "id": job["evaluationId"]},
                        requestId=f"{job['evaluationId']}:terminal:{status}",
                        metadata={"intentId": job["intentId"], "intentVersion": job["intentVersion"],
                                  "errorCode": (error_payload or {}).get("code")}, scope=job["scopeKey"])
    operations = [{"Update": update}]
    operations.extend(resolution_operations or [])
    if status in {"SUCCEEDED", "PARTIAL"}:
        intent_update = {"TableName": os.environ["INTENTS_TABLE"], "Key": {"intentId": job["intentId"]},
                         "UpdateExpression": "SET latestEvaluationOrder = :order, latestEvaluationId = :evaluation REMOVE publicationLeaseOwner, publicationLeaseExpiresAt",
                         "ConditionExpression": "publicationLeaseOwner = :owner AND (attribute_not_exists(latestEvaluationOrder) OR latestEvaluationOrder < :order)",
                         "ExpressionAttributeValues": {":order": job["createdOrder"], ":evaluation": job["evaluationId"],
                                                        ":owner": job["evaluationId"]}}
        if drift_baseline:
            intent_update["UpdateExpression"] = intent_update["UpdateExpression"].replace(" REMOVE", ", driftBaseline = :baseline REMOVE")
            intent_update["ExpressionAttributeValues"][":baseline"] = drift_baseline
        operations.append({"Update": intent_update})
    if drift_baseline:
        drift_audit = audit_event(actor, "DRIFT_SNAPSHOT_PUBLISHED", {"type": "EVALUATION", "id": job["evaluationId"]},
            requestId=f"{job['evaluationId']}:drift", metadata={"intentId": job["intentId"], "intentVersion": job["intentVersion"],
            "eventCount": (summary or {}).get("driftEventCount", 0)}, scope=job["scopeKey"])
        operations.append(audit_put(drift_audit))
    operations.append(audit_put(event))
    transaction_write(db, operations)


def _retry_or_fail(db, job_table, audit_table, job, actor, exc, max_attempts):
    if int(job.get("attemptCount", 0)) >= max_attempts:
        payload = {"code": "EVALUATION_ATTEMPTS_EXHAUSTED", "message": f"Evaluation failed after its bounded retry count ({type(exc).__name__})."}
        _publish_terminal(db, job_table, audit_table, job, None, "FAILED", actor, payload)
        return "FAILED"
    event = audit_event(actor, "EVALUATION_RETRY_SCHEDULED", {"type": "EVALUATION", "id": job["evaluationId"]},
                        requestId=f"{job['evaluationId']}:retry:{job.get('attemptCount', 1)}",
                        metadata={"attemptCount": int(job.get("attemptCount", 1)), "errorType": type(exc).__name__},
                        scope=job["scopeKey"])
    update = {"TableName": job_table.name, "Key": {"evaluationId": job["evaluationId"]},
              "UpdateExpression": "SET #s = :queued, updatedAt = :now REMOVE leaseOwner, leaseExpiresAt",
              "ConditionExpression": "#s = :running AND leaseOwner = :owner",
              "ExpressionAttributeNames": {"#s": "status"},
              "ExpressionAttributeValues": {":queued": "QUEUED", ":running": "RUNNING",
                                             ":now": utc_now(), ":owner": job["evaluationId"]}}
    transaction_write(db, [{"Update": update}, audit_put(event)])
    return "QUEUED"


def _process(db, evaluation_id: str) -> dict:
    job_table_name = os.environ["EVALUATIONS_TABLE"]
    findings_name = os.environ["FINDINGS_TABLE"]
    artifact_name = os.environ["EVALUATION_ARTIFACTS_TABLE"]
    job_table = db.Table(job_table_name)
    actor = {"sub": "evaluation-worker", "displayName": "Evaluation worker", "role": "system"}
    max_attempts = _seconds("EVALUATION_MAX_ATTEMPTS", 3, 1, 10)
    lease_seconds = _seconds("EVALUATION_LEASE_SECONDS", 300, 30, 3600)
    job = _claim_job(job_table, evaluation_id, max_attempts, lease_seconds)
    if not job:
        reconcile_expired(db, evaluation_id)
        return {"evaluationId": evaluation_id, "result": "SKIPPED"}
    audit_table = os.environ["AUDIT_TABLE"]
    intent_table = db.Table(os.environ["INTENTS_TABLE"])
    locked = False
    try:
        _state_audit(db, job_table_name, audit_table, job, actor, "EVALUATION_STAGE_CHANGED", "CLAIMED")
        if job.get("scopeKey") != configured_scope():
            raise JobError(409, "SCOPE_MISMATCH", "The queued job scope does not match this worker's configured scope.")
        if not _acquire_publication_lock(intent_table, job["intentId"], evaluation_id, job["createdOrder"], lease_seconds):
            current_intent = intent_table.get_item(Key={"intentId": job["intentId"]}, ConsistentRead=True).get("Item") or {}
            if current_intent.get("latestEvaluationOrder", "") >= job["createdOrder"]:
                raise JobError(409, "EVALUATION_SUPERSEDED", "A newer evaluation has already published for this intent.")
            if int(job.get("attemptCount", 0)) >= max_attempts:
                payload = {"code": "PUBLICATION_LOCK_CONTENTION", "message": "The evaluation could not acquire its publication lock within the configured retry bound."}
                _publish_terminal(db, job_table, audit_table, job, None, "FAILED", actor, payload)
                return {"evaluationId": evaluation_id, "result": "FAILED", "error": payload}
            event = audit_event(actor, "EVALUATION_DEFERRED", {"type": "EVALUATION", "id": evaluation_id},
                                requestId=f"{evaluation_id}:deferred:{utc_now()}",
                                metadata={"reason": "PUBLICATION_LOCK_BUSY"}, scope=job["scopeKey"])
            update = {"TableName": job_table_name, "Key": {"evaluationId": evaluation_id},
                      "UpdateExpression": "SET #s = :queued, progressStage = :waiting, updatedAt = :now REMOVE leaseOwner, leaseExpiresAt",
                      "ConditionExpression": "#s = :running AND leaseOwner = :owner",
                      "ExpressionAttributeNames": {"#s": "status"},
                      "ExpressionAttributeValues": {":queued": "QUEUED", ":running": "RUNNING",
                                                     ":waiting": "WAITING_FOR_PUBLICATION_LOCK", ":owner": evaluation_id,
                                                     ":now": utc_now()}}
            transaction_write(db, [{"Update": update}, audit_put(event)])
            # The original DynamoDB stream INSERT is retried by Lambda after this
            # exception. A local runner can safely invoke the same ID again.
            raise RuntimeError("Evaluation publication lock is busy; retry the stream record.")
        locked = True
        _state_audit(db, job_table_name, audit_table, job, actor, "EVALUATION_STAGE_CHANGED", "COLLECTING")
        snapshot = job.get("intentSnapshot")
        if not isinstance(snapshot, dict):
            snapshot, _ = resolve_pinned_intent(db, intent_table, job["intentId"], job["intentVersion"])
        if (snapshot.get("contentHash") != job.get("intentHash")
                or content_hash(content_from(snapshot)) != job.get("intentHash")):
            raise JobError(409, "PINNED_INTENT_HASH_MISMATCH", "The pinned intent no longer matches its recorded content hash.")
        complete_artifacts = _load_complete_artifacts(db, artifact_name, evaluation_id)
        if complete_artifacts:
            evaluation, inventory, findings = complete_artifacts
            manifest = db.Table(artifact_name).get_item(Key={"evaluationId": evaluation_id, "artifactKey": "manifest"}, ConsistentRead=True).get("Item")
        else:
            if os.environ.get("INVENTORY_PROVIDER", "aws") == "fixture":
                from common.contracts import is_local
                if not is_local():
                    raise JobError(409, "FIXTURE_PROVIDER_LOCAL_ONLY", "Fixture observations are available only in explicit local mode.")
            inventory = observations(collect_inventory, os.environ.get("AWS_REGION"))
            inventory = enrich_network_evidence(snapshot, inventory)
            _state_audit(db, job_table_name, audit_table, job, actor, "EVALUATION_STAGE_CHANGED", "EVALUATING")
            evaluation, findings = run_pinned_evaluation(snapshot, inventory, evaluation_id)
            from common.candidate_history import prepare_history
            history = prepare_history(db, job, evaluation, inventory, _load_complete_artifacts)
            evaluation, findings = escalate(snapshot, inventory, evaluation, findings, history=history)
            evaluation["startedAt"] = job.get("startedAt") or evaluation["startedAt"]
            evaluation["finishedAt"] = utc_now()
            _state_audit(db, job_table_name, audit_table, job, actor, "EVALUATION_STAGE_CHANGED", "WRITING_ARTIFACTS")
            manifest = _persist_artifacts(db, artifact_name, evaluation_id, snapshot, evaluation, inventory, findings)
        for finding in findings:
            _finding_write(db, db.Table(findings_name), audit_table, job, finding, actor)
        drift_baseline = stage_drift(db, job, evaluation, inventory, _load_complete_artifacts)
        publication = _load_publication(db, evaluation_id)
        if publication:
            evaluation.update({key: publication[key] for key in ("summary", "conformance", "warnings", "status") if key in publication})
            resolved_ids = publication.get("resolvedFindingIds", [])
        else:
            _, resolved_ids = _resolution_plan(db, job, evaluation, findings, actor)
            evaluation.setdefault("summary", {})["resolvedFindings"] = len(resolved_ids)
            publication = _write_publication(db, evaluation_id, evaluation, resolved_ids)
            evaluation.update({key: publication[key] for key in ("summary", "conformance", "warnings", "status") if key in publication})
        resolution_operations, _ = _resolution_plan(db, job, evaluation, findings, actor, set(resolved_ids)) if resolved_ids else ([], [])
        # A manifest written with complete=true is required before any terminal success.
        if not manifest.get("complete"):
            raise JobError(500, "ARTIFACTS_INCOMPLETE", "Evaluation artifacts were not marked complete.")
        _state_audit(db, job_table_name, audit_table, job, actor, "EVALUATION_STAGE_CHANGED", "PUBLISHING")
        _publish_terminal(db, job_table, audit_table, job, evaluation, evaluation["status"], actor,
                          resolution_operations=resolution_operations, drift_baseline=drift_baseline)
        return {"evaluationId": evaluation_id, "result": evaluation["status"]}
    except ObservationUnavailable as exc:
        payload = {"code": "OBSERVATIONS_UNAVAILABLE", "message": str(exc)[:250]}
        _publish_terminal(db, job_table, audit_table, job, None, "FAILED", actor, payload)
        return {"evaluationId": evaluation_id, "result": "FAILED", "error": payload}
    except JobError as exc:
        payload = {"code": exc.code, "message": exc.message[:250]}
        _publish_terminal(db, job_table, audit_table, job, None, "FAILED", actor, payload)
        return {"evaluationId": evaluation_id, "result": "FAILED", "error": payload}
    except Exception as exc:
        # Reset the claim so the original INSERT record can be retried. Complete
        # artifacts are immutable and are resumed without recollecting inputs.
        disposition = _retry_or_fail(db, job_table, audit_table, job, actor, exc, max_attempts)
        if disposition == "FAILED":
            return {"evaluationId": evaluation_id, "result": "FAILED"}
        raise
    finally:
        if locked:
            _release_publication_lock(intent_table, job["intentId"], evaluation_id)


def reconcile_expired(db=None, evaluation_id: str | None = None) -> list[dict]:
    """Fail only expired, exhausted jobs; partial runs never resolve findings."""
    db = db or dynamodb_resource()
    table = db.Table(os.environ["EVALUATIONS_TABLE"])
    if evaluation_id:
        rows = [table.get_item(Key={"evaluationId": evaluation_id}, ConsistentRead=True).get("Item")]
        rows = [row for row in rows if row]
    else:
        rows, _ = scan_all(table)
    now = utc_now()
    results = []
    actor = {"sub": "evaluation-reconciler", "displayName": "Evaluation reconciler", "role": "system"}
    for item in rows:
        if item.get("status") not in {"QUEUED", "RUNNING"}:
            continue
        lease_expired = item.get("status") == "RUNNING" and item.get("leaseExpiresAt", "") < now
        deadline_expired = item.get("deadlineAt", "") < now
        exhausted = int(item.get("attemptCount", 0)) >= _seconds("EVALUATION_MAX_ATTEMPTS", 3, 1, 10)
        if not deadline_expired and not (lease_expired and exhausted):
            continue
        code = "EVALUATION_DEADLINE_EXCEEDED" if deadline_expired else "EVALUATION_ATTEMPTS_EXHAUSTED"
        error_payload = {"code": code, "message": "The evaluation did not complete before its configured execution bounds."}
        expected_status = item["status"]
        names = {"#s": "status", "#error": "error"}
        values = {":failed": "FAILED", ":now": now, ":expected": expected_status, ":stage": "FAILED",
                  ":error": error_payload}
        condition = "#s = :expected"
        if expected_status == "QUEUED":
            condition += " AND (deadlineAt <= :now OR attemptCount >= :max)"
            values[":max"] = _seconds("EVALUATION_MAX_ATTEMPTS", 3, 1, 10)
        else:
            condition += " AND leaseExpiresAt <= :now AND (deadlineAt <= :now OR attemptCount >= :max)"
            values[":max"] = _seconds("EVALUATION_MAX_ATTEMPTS", 3, 1, 10)
        update = {"TableName": table.name, "Key": {"evaluationId": item["evaluationId"]},
                  "UpdateExpression": "SET #s = :failed, finishedAt = :now, updatedAt = :now, progressStage = :stage, #error = :error REMOVE leaseOwner, leaseExpiresAt",
                  "ConditionExpression": condition, "ExpressionAttributeNames": names,
                  "ExpressionAttributeValues": values}
        audit = audit_event(actor, "EVALUATION_FAILED", {"type": "EVALUATION", "id": item["evaluationId"]},
                            requestId=f"{item['evaluationId']}:reconcile:{code}",
                            metadata={"intentId": item["intentId"], "intentVersion": item["intentVersion"], "errorCode": code},
                            scope=item["scopeKey"])
        try:
            transaction_write(db, [{"Update": update}, audit_put(audit)])
            results.append({"evaluationId": item["evaluationId"], "result": "FAILED"})
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise
    return results


def lambda_handler(event, context):
    if isinstance(event, dict) and event.get('diagnostic') == 'BEDROCK_SYNTHETIC':
        from common.runtime_verification import verify_bedrock_runtime
        return verify_bedrock_runtime(event)
    local = os.environ.get("CIG_LOCAL", "").lower() == "true" or os.environ.get("AWS_SAM_LOCAL", "").lower() == "true"
    if local and os.environ.get("INVENTORY_PROVIDER") != "fixture":
        raise RuntimeError("Local evaluation worker requires INVENTORY_PROVIDER=fixture.")
    if not local and os.environ.get("INVENTORY_PROVIDER", "aws") != "aws":
        raise RuntimeError("Fixture observations are restricted to explicit local mode.")
    if not local and os.environ.get("ASYNC_WORKER_ENABLED", "false").lower() != "true":
        raise RuntimeError("Async evaluation worker is disabled.")
    db = dynamodb_resource()
    ids = set()
    direct = event.get("evaluationId") or event.get("jobId")
    if direct:
        ids.add(str(direct))
    for record in event.get("Records", []):
        ident = _job_id_from_record(record)
        if ident:
            ids.add(ident)
    return {"results": [_process(db, ident) for ident in sorted(ids)]}
