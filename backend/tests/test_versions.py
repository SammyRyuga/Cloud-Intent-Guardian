"""Intent version transactions and API compatibility against a stubbed DynamoDB."""
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


def decoded(result, expected=200):
    if result["statusCode"] != expected:
        raise AssertionError(result)
    return json.loads(result["body"])


def user_event(role="admin", method="GET", path="", path_parameters=None, body=None, query=None, request_id="request-1"):
    event = {
        "rawPath": path,
        "requestContext": {
            "requestId": request_id,
            "http": {"method": method},
            "authorizer": {"jwt": {"claims": {"sub": "user-123", "name": "Version Tester", "cognito:groups": [role]}}},
        },
        "pathParameters": path_parameters or {},
    }
    if body is not None:
        event["body"] = json.dumps(body)
    if query is not None:
        event["queryStringParameters"] = query
    return event


class IntentVersionTransactions(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "AWS_REGION": "ap-south-1", "AWS_DEFAULT_REGION": "ap-south-1",
            "AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing",
            "CIG_LOCAL": "false", "CIG_ACCOUNT_ID": "123456789012", "STAGE_NAME": "test",
            "INTENTS_TABLE": "version-intents", "INTENT_VERSIONS_TABLE": "intent-versions",
            "AUDIT_TABLE": "audit-events", "INVENTORY_PROVIDER": "aws",
        }, clear=True)
        self.env.start()
        self.aws = mock_aws()
        self.aws.start()
        self.db = boto3.resource("dynamodb", region_name="ap-south-1")
        self.db.create_table(TableName="version-intents", KeySchema=[{"AttributeName": "intentId", "KeyType": "HASH"}],
                             AttributeDefinitions=[{"AttributeName": "intentId", "AttributeType": "S"}], BillingMode="PAY_PER_REQUEST")
        self.db.create_table(TableName="intent-versions", KeySchema=[
            {"AttributeName": "intentId", "KeyType": "HASH"}, {"AttributeName": "version", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "intentId", "AttributeType": "S"}, {"AttributeName": "version", "AttributeType": "N"}],
            BillingMode="PAY_PER_REQUEST")
        self.db.create_table(TableName="audit-events", KeySchema=[{"AttributeName": "auditId", "KeyType": "HASH"}],
                             AttributeDefinitions=[{"AttributeName": "auditId", "AttributeType": "S"}], BillingMode="PAY_PER_REQUEST")

    def tearDown(self):
        self.aws.stop()
        self.env.stop()

    def test_version_activation_rollback_and_legacy_envelopes(self):
        intents = importlib.import_module("intents.app")
        detail = importlib.import_module("intent_detail.app")
        approval = importlib.import_module("approve_intent.app")
        versions = importlib.import_module("versions.app")
        manifest_v1 = {"name": "Baseline", "description": "first approved contract", "constraints": [
            {"id": "ssh", "type": "SECURITY_GROUP_NO_OPEN_SSH", "severity": "HIGH"}]}
        manifest_v2 = {"name": "Baseline v2", "description": "updated approved contract", "constraints": [
            {"id": "ssh", "type": "SECURITY_GROUP_NO_OPEN_SSH", "severity": "CRITICAL"}]}

        created = decoded(intents.lambda_handler(user_event("admin", "POST", "/v1/intents", body=manifest_v1), None), 201)
        self.assertEqual(set(created), {"item"})
        root = created["item"]
        intent_id = root["intentId"]
        listed_intents = decoded(intents.lambda_handler(user_event("viewer", "GET", "/v1/intents"), None))
        self.assertEqual({"items", "count", "nextToken", "limit"}, set(listed_intents))
        self.assertEqual(listed_intents["items"][0]["intentId"], intent_id)
        self.assertEqual(decoded(detail.lambda_handler(user_event("viewer", "GET", f"/v1/intents/{intent_id}",
            {"intentId": intent_id}), None))["item"]["intentId"], intent_id)
        self.assertEqual(root["revision"], 0)
        self.assertEqual(root["latestVersion"], 1)
        v1_key = {"intentId": intent_id, "version": 1}
        v1_before = self.db.Table("intent-versions").get_item(Key=v1_key)["Item"]
        self.assertEqual(v1_before["status"], "DRAFT")
        self.assertEqual(v1_before["contentHash"], self.db.Table("intent-versions").get_item(Key=v1_key)["Item"]["contentHash"])

        approved = decoded(approval.lambda_handler(user_event("approver", "POST", "/v1/intents/x/approve",
            {"intentId": intent_id}, request_id="approve-v1"), None))
        self.assertEqual(approved["item"]["activeVersion"], 1)
        self.assertEqual(approved["item"]["revision"], 1)
        self.assertEqual(self.db.Table("intent-versions").get_item(Key=v1_key)["Item"]["status"], "APPROVED")
        v1_approved_snapshot = self.db.Table("intent-versions").get_item(Key=v1_key)["Item"]
        repeat = decoded(approval.lambda_handler(user_event("approver", "POST", "/v1/intents/x/approve",
            {"intentId": intent_id}, request_id="approve-v1-repeat"), None))
        self.assertEqual(repeat["item"]["revision"], 1)
        self.assertEqual(repeat["message"], "Intent was already approved.")

        created_v2 = decoded(versions.lambda_handler(user_event("admin", "POST", f"/v1/intents/{intent_id}/versions",
            {"intentId": intent_id}, {"manifest": manifest_v2, "expectedRevision": 1}, request_id="create-v2"), None), 201)
        self.assertEqual(created_v2["item"]["version"], 2)
        root_after_draft = self.db.Table("version-intents").get_item(Key={"intentId": intent_id})["Item"]
        self.assertEqual(root_after_draft["activeVersion"], 1)
        self.assertEqual(root_after_draft["name"], "Baseline")
        self.assertEqual(root_after_draft["revision"], 2)

        stale = versions.lambda_handler(user_event("admin", "POST", f"/v1/intents/{intent_id}/versions",
            {"intentId": intent_id}, {"manifest": manifest_v2, "expectedRevision": 1}, request_id="stale-v2"), None)
        self.assertEqual(stale["statusCode"], 409)
        self.assertEqual(json.loads(stale["body"])["error"]["code"], "STALE_INTENT_REVISION")

        activated = decoded(versions.lambda_handler(user_event("approver", "POST",
            f"/v1/intents/{intent_id}/versions/2/approve", {"intentId": intent_id, "version": "2"},
            {"expectedRevision": 2, "comment": "Reviewed by application owner"}, request_id="approve-v2"), None))
        self.assertEqual(activated["item"]["activeVersion"], 2)
        self.assertEqual(activated["item"]["name"], "Baseline v2")
        self.assertEqual(activated["item"]["revision"], 3)
        self.assertEqual(self.db.Table("intent-versions").get_item(Key={"intentId": intent_id, "version": 2})["Item"]["status"], "APPROVED")
        self.assertEqual(self.db.Table("intent-versions").get_item(Key={"intentId": intent_id, "version": 2})["Item"]["approvalComment"], "Reviewed by application owner")
        v2_approved_snapshot = self.db.Table("intent-versions").get_item(Key={"intentId": intent_id, "version": 2})["Item"]

        stale_approval = versions.lambda_handler(user_event("approver", "POST",
            f"/v1/intents/{intent_id}/versions/2/approve", {"intentId": intent_id, "version": "2"},
            {"expectedRevision": 2}, request_id="stale-approve-v2"), None)
        self.assertEqual(stale_approval["statusCode"], 409)
        self.assertEqual(json.loads(stale_approval["body"])["error"]["code"], "STALE_INTENT_REVISION")

        diff = decoded(versions.lambda_handler(user_event("viewer", "GET", f"/v1/intents/{intent_id}/diff",
            {"intentId": intent_id}, query={"fromVersion": "1", "toVersion": "2"}), None))
        self.assertEqual(diff["item"]["constraints"]["changed"][0]["id"], "ssh")
        history = decoded(versions.lambda_handler(user_event("viewer", "GET", f"/v1/intents/{intent_id}/versions",
            {"intentId": intent_id}), None))
        self.assertEqual(history["count"], 2)
        statuses = {row["version"]: row["effectiveStatus"] for row in history["items"]}
        self.assertEqual(statuses, {2: "APPROVED", 1: "SUPERSEDED"})

        rolled = decoded(versions.lambda_handler(user_event("approver", "POST", f"/v1/intents/{intent_id}/rollback",
            {"intentId": intent_id}, {"targetVersion": 1, "expectedRevision": 3, "reason": "Restore reviewed baseline"},
            request_id="rollback-v1"), None))
        self.assertEqual(rolled["item"]["activeVersion"], 1)
        self.assertEqual(rolled["item"]["latestVersion"], 2)
        self.assertEqual(rolled["item"]["name"], "Baseline")
        self.assertEqual(rolled["item"]["revision"], 4)
        self.assertEqual(self.db.Table("intent-versions").get_item(Key=v1_key)["Item"], v1_approved_snapshot)
        self.assertEqual(self.db.Table("intent-versions").get_item(Key={"intentId": intent_id, "version": 2})["Item"], v2_approved_snapshot)
        audit_rows = self.db.Table("audit-events").scan()["Items"]
        self.assertEqual(len(audit_rows), 5)
        self.assertTrue(all(isinstance(row["target"], dict) for row in audit_rows))

    def test_legacy_approval_requires_explicit_snapshot_backfill(self):
        approval = importlib.import_module("approve_intent.app")
        detail = importlib.import_module("intent_detail.app")
        unscoped = {"intentId": "unscoped-legacy", "name": "Legacy", "description": "old row",
                    "constraints": [{"id": "ssh", "type": "SECURITY_GROUP_NO_OPEN_SSH"}],
                    "version": 1, "status": "APPROVED"}
        self.db.Table("version-intents").put_item(Item=unscoped)
        unscoped_result = detail.lambda_handler(user_event("viewer", "GET", "/v1/intents/unscoped-legacy",
            {"intentId": "unscoped-legacy"}), None)
        self.assertEqual(unscoped_result["statusCode"], 409)
        self.assertEqual(json.loads(unscoped_result["body"])["error"]["code"], "INTENT_MIGRATION_REQUIRED")
        legacy = {"intentId": "legacy-draft", "name": "Legacy", "description": "old row",
                  "constraints": [{"id": "ssh", "type": "SECURITY_GROUP_NO_OPEN_SSH"}],
                  "version": 1, "status": "DRAFT", "scopeKey": "123456789012#ap-south-1#test"}
        self.db.Table("version-intents").put_item(Item=legacy)
        result = approval.lambda_handler(user_event("approver", "POST", "/v1/intents/legacy-draft/approve",
            {"intentId": "legacy-draft"}), None)
        self.assertEqual(result["statusCode"], 409)
        self.assertEqual(json.loads(result["body"])["error"]["code"], "VERSION_MIGRATION_REQUIRED")
        self.assertEqual(self.db.Table("version-intents").get_item(Key={"intentId": "legacy-draft"})["Item"]["status"], "DRAFT")
        self.assertIsNone(self.db.Table("intent-versions").get_item(Key={"intentId": "legacy-draft", "version": 1}).get("Item"))

    def test_missing_audit_configuration_leaves_create_unwritten(self):
        from common.versions import VersionError, create_initial
        record = {"intentId": "no-audit-write", "name": "No audit", "description": "must be atomic",
                  "constraints": [{"id": "ssh", "type": "SECURITY_GROUP_NO_OPEN_SSH"}],
                  "status": "DRAFT", "version": 1, "scopeKey": "123456789012#ap-south-1#test"}
        with patch.dict(os.environ, {"AUDIT_TABLE": ""}):
            with self.assertRaisesRegex(VersionError, "not configured"):
                create_initial(self.db, self.db.Table("version-intents"), record,
                               {"sub": "user-123", "displayName": "Tester"}, "missing-audit")
        self.assertIsNone(self.db.Table("version-intents").get_item(Key={"intentId": record["intentId"]}).get("Item"))
        self.assertIsNone(self.db.Table("intent-versions").get_item(Key={"intentId": record["intentId"], "version": 1}).get("Item"))

    def test_explicit_migration_backfills_legacy_scope_and_snapshot(self):
        from common.versions import migrate_legacy
        legacy = {"intentId": "migrate-me", "name": "Legacy", "description": "backfill",
                  "constraints": [{"id": "ssh", "type": "SECURITY_GROUP_NO_OPEN_SSH"}],
                  "version": 1, "status": "APPROVED", "createdAt": "2026-10-01T00:00:00Z",
                  "updatedAt": "2026-10-02T00:00:00Z", "approvedAt": "2026-10-02T00:00:00Z"}
        self.db.Table("version-intents").put_item(Item=legacy)
        migrated = migrate_legacy(self.db, legacy, {"sub": "migration", "displayName": "Migration"}, "backfill-v1")
        self.assertEqual(migrated["activeVersion"], 1)
        self.assertEqual(migrated["scopeKey"], "123456789012#ap-south-1#test")
        snapshot = self.db.Table("intent-versions").get_item(Key={"intentId": "migrate-me", "version": 1})["Item"]
        self.assertEqual(snapshot["status"], "APPROVED")
        self.assertEqual(snapshot["createdBy"], "unknown")
        self.assertEqual(snapshot["createdAt"], legacy["createdAt"])
        self.assertEqual(snapshot["approvedAt"], legacy["approvedAt"])

    def test_semantic_diff_ignores_declaration_reordering(self):
        from common.versions import semantic_diff
        before = {"components": [{"id": "web"}, {"id": "api"}],
                  "relationships": [{"id": "one"}, {"id": "two"}],
                  "trustBoundaries": [], "criticality": {"web": "MEDIUM", "api": "HIGH"},
                  "constraints": [{"id": "ssh"}, {"id": "db"}]}
        after = {"components": list(reversed(before["components"])),
                 "relationships": list(reversed(before["relationships"])),
                 "trustBoundaries": [], "criticality": {"api": "HIGH", "web": "MEDIUM"},
                 "constraints": list(reversed(before["constraints"]))}
        self.assertTrue(all(not group["added"] and not group["removed"] and not group["changed"]
                            for group in semantic_diff(before, after).values()))


if __name__ == "__main__":
    unittest.main()
