"""Evaluation API and worker contracts use Moto only; no cloud services are contacted."""
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import boto3
from moto import mock_aws
from boto3.dynamodb.conditions import Key
from common.evaluation_jobs import new_job
from common.versions import content_hash


def decoded(result):
    return json.loads(result["body"])


class EvaluationJobsTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "AWS_REGION": "ap-south-1", "AWS_DEFAULT_REGION": "ap-south-1",
            "AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test",
            "CIG_LOCAL": "false", "CIG_ACCOUNT_ID": "123456789012", "STAGE_NAME": "dev",
            "INTENTS_TABLE": "jobs-intents", "INTENT_VERSIONS_TABLE": "jobs-versions",
            "FINDINGS_TABLE": "jobs-findings", "EVALUATIONS_TABLE": "jobs-evaluations",
            "EVALUATION_ARTIFACTS_TABLE": "jobs-artifacts", "AUDIT_TABLE": "jobs-audit",
            "ASYNC_WORKER_ENABLED": "true", "INVENTORY_PROVIDER": "aws",
            "EVALUATION_MAX_ATTEMPTS": "3", "EVALUATION_LEASE_SECONDS": "300",
        }, clear=True)
        self.env.start()
        self.aws = mock_aws()
        self.aws.start()
        self.db = boto3.resource("dynamodb", region_name="ap-south-1")
        self.db.create_table(TableName="jobs-intents", KeySchema=[{"AttributeName": "intentId", "KeyType": "HASH"}],
                             AttributeDefinitions=[{"AttributeName": "intentId", "AttributeType": "S"}], BillingMode="PAY_PER_REQUEST")
        self.db.create_table(TableName="jobs-versions", KeySchema=[{"AttributeName": "intentId", "KeyType": "HASH"},
                             {"AttributeName": "version", "KeyType": "RANGE"}], AttributeDefinitions=[
                                 {"AttributeName": "intentId", "AttributeType": "S"}, {"AttributeName": "version", "AttributeType": "N"}],
                             BillingMode="PAY_PER_REQUEST")
        self.db.create_table(TableName="jobs-evaluations", KeySchema=[{"AttributeName": "evaluationId", "KeyType": "HASH"}],
                             AttributeDefinitions=[{"AttributeName": "evaluationId", "AttributeType": "S"},
                                                   {"AttributeName": "scopeKey", "AttributeType": "S"},
                                                   {"AttributeName": "createdOrder", "AttributeType": "S"}],
                             GlobalSecondaryIndexes=[{"IndexName": "scope-created", "KeySchema": [
                                 {"AttributeName": "scopeKey", "KeyType": "HASH"},
                                 {"AttributeName": "createdOrder", "KeyType": "RANGE"}],
                                 "Projection": {"ProjectionType": "ALL"}}], BillingMode="PAY_PER_REQUEST")
        self.db.create_table(TableName="jobs-findings", KeySchema=[{"AttributeName": "findingId", "KeyType": "HASH"}],
                             AttributeDefinitions=[{"AttributeName": "findingId", "AttributeType": "S"}], BillingMode="PAY_PER_REQUEST")
        self.db.create_table(TableName="jobs-artifacts", KeySchema=[{"AttributeName": "evaluationId", "KeyType": "HASH"},
                             {"AttributeName": "artifactKey", "KeyType": "RANGE"}], AttributeDefinitions=[
                                 {"AttributeName": "evaluationId", "AttributeType": "S"}, {"AttributeName": "artifactKey", "AttributeType": "S"}],
                             BillingMode="PAY_PER_REQUEST")
        self.db.create_table(TableName="jobs-audit", KeySchema=[{"AttributeName": "auditId", "KeyType": "HASH"}],
                             AttributeDefinitions=[{"AttributeName": "auditId", "AttributeType": "S"}], BillingMode="PAY_PER_REQUEST")
        self.intent_id = "intent-1"
        content = {"name": "test baseline", "description": "fixture", "constraints": [
            {"id": "no-ssh", "type": "SECURITY_GROUP_NO_OPEN_SSH", "severity": "HIGH"}]}
        digest = content_hash(content)
        self.intent = {**content, "intentId": self.intent_id, "version": 1, "contentHash": digest,
                       "status": "APPROVED", "activeVersion": 1}
        self.db.Table("jobs-intents").put_item(Item={"intentId": self.intent_id, "name": "test baseline", "status": "APPROVED",
                                                       "activeVersion": 1, "version": 1, "scopeKey": "123456789012#ap-south-1#dev",
                                                       "updatedAt": "2026-10-15T00:00:00Z"})
        self.db.Table("jobs-versions").put_item(Item={**content, "intentId": self.intent_id, "version": 1,
                                                        "scopeKey": "123456789012#ap-south-1#dev",
                                                        "status": "APPROVED", "contentHash": digest})

    def tearDown(self):
        self.aws.stop()
        self.env.stop()

    def claims(self, role="admin"):
        return {"authorizer": {"jwt": {"claims": {"sub": "actor-1", "name": "Test Actor", "cognito:groups": [role]}}}}

    def test_post_queues_pinned_version_and_history_is_scope_bound(self):
        module = importlib.import_module("evaluations.app")
        event = {"requestContext": {"http": {"method": "POST"}, **self.claims(), "requestId": "request-1"},
                 "body": json.dumps({"intentId": self.intent_id, "intentVersion": 1, "reason": "weekly review"})}
        with patch.object(module, "dynamodb_resource", return_value=self.db):
            result = module.lambda_handler(event, None)
        self.assertEqual(result["statusCode"], 202)
        queued = decoded(result)["evaluation"]
        self.assertEqual(queued["status"], "QUEUED")
        row = self.db.Table("jobs-evaluations").get_item(Key={"evaluationId": queued["evaluationId"]})["Item"]
        self.assertEqual(row["intentHash"], self.intent["contentHash"])
        self.assertEqual(row["intentSnapshot"]["version"], 1)
        self.assertEqual(self.db.Table("jobs-audit").scan()["Items"][0]["action"], "EVALUATION_QUEUED")

        get_event = {"requestContext": {"http": {"method": "GET"}, **self.claims("viewer")},
                     "pathParameters": {"evaluationId": queued["evaluationId"]}}
        with patch.object(module, "dynamodb_resource", return_value=self.db):
            detail = module.lambda_handler(get_event, None)
            page = module.lambda_handler({"requestContext": {"http": {"method": "GET"}, **self.claims("viewer")}}, None)
        self.assertEqual(detail["statusCode"], 200)
        self.assertEqual(decoded(detail)["item"]["status"], "QUEUED")
        self.assertEqual(decoded(page)["count"], 1)
        self.assertNotIn("intentSnapshot", decoded(page)["items"][0])

        with patch.dict(os.environ, {"CIG_ACCOUNT_ID": "999999999999"}), patch.object(module, "dynamodb_resource", return_value=self.db):
            hidden = module.lambda_handler(get_event, None)
        self.assertEqual(hidden["statusCode"], 404)

    def test_queue_requires_worker_and_fixture_mode_never_contacts_cloud(self):
        module = importlib.import_module("evaluations.app")
        event = {"requestContext": {"http": {"method": "POST"}, **self.claims()}, "body": "{}"}
        with patch.dict(os.environ, {"ASYNC_WORKER_ENABLED": "false"}), patch.object(module, "dynamodb_resource", return_value=self.db):
            disabled = module.lambda_handler(event, None)
        self.assertEqual(decoded(disabled)["error"]["code"], "ASYNC_EVALUATION_NOT_ENABLED")
        with patch.dict(os.environ, {"CIG_LOCAL": "true", "INVENTORY_PROVIDER": "aws"}), patch.object(module, "dynamodb_resource") as resource:
            blocked = module.lambda_handler(event, None)
        self.assertEqual(decoded(blocked)["error"]["code"], "AWS_DISCOVERY_DISABLED_LOCAL")
        resource.assert_not_called()

    def test_intent_version_hash_and_approval_are_checked_before_queueing(self):
        module = importlib.import_module("evaluations.app")
        self.db.Table("jobs-versions").update_item(Key={"intentId": self.intent_id, "version": 1},
                                                    UpdateExpression="SET contentHash = :hash", ExpressionAttributeValues={":hash": "bad"})
        event = {"requestContext": {"http": {"method": "POST"}, **self.claims()},
                 "body": json.dumps({"intentId": self.intent_id})}
        with patch.object(module, "dynamodb_resource", return_value=self.db):
            result = module.lambda_handler(event, None)
        self.assertEqual(decoded(result)["error"]["code"], "INTENT_VERSION_HASH_MISMATCH")
        self.assertEqual(self.db.Table("jobs-evaluations").scan()["Count"], 0)

    def test_worker_publishes_artifacts_findings_and_terminal_state_once(self):
        from evaluation_worker import app as worker
        job = new_job(self.db, {"sub": "actor-1", "displayName": "Test Actor"}, self.intent,
                      "fixture-account#ap-south-1#dev", "request-local")
        inventory = {"items": [{"resourceId": "sg-test", "name": "open ssh", "resourceType": "AWS::EC2::SecurityGroup",
                                 "region": "ap-south-1", "attributes": {"ingressRules": [
                                     {"protocol": "tcp", "fromPort": 22, "toPort": 22, "cidr": "0.0.0.0/0"}]}}],
                     "edges": [], "meta": {"accountId": "fixture-account", "region": "ap-south-1", "partial": False,
                                             "totalResources": 1, "warnings": [], "simulated": True}}
        with patch.dict(os.environ, {"CIG_LOCAL": "true", "INVENTORY_PROVIDER": "fixture"}), \
                patch.object(worker, "dynamodb_resource", return_value=self.db), \
                patch.object(worker, "observations", return_value=inventory):
            first = worker.lambda_handler({"evaluationId": job["evaluationId"]}, None)
            second = worker.lambda_handler({"evaluationId": job["evaluationId"]}, None)
        self.assertEqual(first["results"][0]["result"], "SUCCEEDED")
        self.assertEqual(second["results"][0]["result"], "SKIPPED")
        final = self.db.Table("jobs-evaluations").get_item(Key={"evaluationId": job["evaluationId"]})["Item"]
        self.assertEqual(final["status"], "SUCCEEDED")
        self.assertEqual(final["conformance"]["failingRules"], 1)
        artifacts = self.db.Table("jobs-artifacts").query(KeyConditionExpression=Key("evaluationId").eq(job["evaluationId"]))["Items"]
        self.assertTrue(any(row["artifactKey"] == "manifest" and row["complete"] for row in artifacts))
        self.assertEqual(self.db.Table("jobs-findings").scan()["Count"], 1)
        actions = [row["action"] for row in self.db.Table("jobs-audit").scan()["Items"]]
        self.assertIn("FINDING_DETECTED", actions)
        self.assertIn("EVALUATION_SUCCEEDED", actions)

    def test_retry_after_complete_artifacts_reuses_snapshot_and_is_idempotent(self):
        from evaluation_worker import app as worker
        job = new_job(self.db, {"sub": "actor-1", "displayName": "Test Actor"}, self.intent,
                      "fixture-account#ap-south-1#dev", "request-retry")
        inventory = {"items": [], "edges": [], "meta": {"accountId": "fixture-account", "region": "ap-south-1",
                     "partial": False, "totalResources": 0, "coverage": {"resourceTypes": {"AWS::EC2::SecurityGroup": "COMPLETE"}},
                     "warnings": [], "simulated": True}}
        with patch.dict(os.environ, {"CIG_LOCAL": "true", "INVENTORY_PROVIDER": "fixture"}), \
                patch.object(worker, "dynamodb_resource", return_value=self.db), \
                patch.object(worker, "observations", return_value=inventory), \
                patch.object(worker, "_publish_terminal", side_effect=RuntimeError("simulated crash after artifacts")):
            with self.assertRaisesRegex(RuntimeError, "simulated crash"):
                worker.lambda_handler({"evaluationId": job["evaluationId"]}, None)
        artifact_rows = self.db.Table("jobs-artifacts").query(
            KeyConditionExpression=Key("evaluationId").eq(job["evaluationId"]))["Items"]
        self.assertTrue(any(row["artifactKey"] == "manifest" and row["complete"] for row in artifact_rows))
        self.db.Table("jobs-evaluations").update_item(Key={"evaluationId": job["evaluationId"]},
            UpdateExpression="SET leaseExpiresAt = :expired", ExpressionAttributeValues={":expired": "2000-01-01T00:00:00Z"})
        with patch.dict(os.environ, {"CIG_LOCAL": "true", "INVENTORY_PROVIDER": "fixture"}), \
                patch.object(worker, "dynamodb_resource", return_value=self.db), \
                patch.object(worker, "observations", side_effect=AssertionError("retry must reuse artifacts")):
            retried = worker.lambda_handler({"evaluationId": job["evaluationId"]}, None)
        self.assertEqual(retried["results"][0]["result"], "SUCCEEDED")
        final = self.db.Table("jobs-evaluations").get_item(Key={"evaluationId": job["evaluationId"]})["Item"]
        self.assertEqual(final["status"], "SUCCEEDED")
        self.assertEqual(final["attemptCount"], 2)

    def test_chunking_is_hash_checked_and_keeps_items_below_bound(self):
        from common.evaluation_jobs import artifact_limit_check, chunk_artifacts
        chunks, manifest = chunk_artifacts("ev-1", [{"payload": "x" * 600000}])
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            artifact_limit_check(chunk)
            self.assertEqual(hashlib.sha256(chunk["data"].encode()).hexdigest(), chunk["sha256"])
        self.assertTrue(manifest["complete"])


if __name__ == "__main__":
    unittest.main()
