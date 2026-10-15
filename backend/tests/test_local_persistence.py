"""SDK-stubbed contract tests. These do not prove Docker/SAM connectivity."""
import importlib
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import EndpointConnectionError
from botocore.stub import ANY, Stubber
from common.dynamodb import DynamoDBConfigurationError, dynamodb_resource

LOCAL = {"CIG_LOCAL": "true", "DYNAMODB_ENDPOINT_URL": "http://127.0.0.1:8000",
         "AWS_REGION": "ap-south-1", "INTENTS_TABLE": "test-intents",
         "INVENTORY_PROVIDER": "fixture", "INTENT_VERSIONS_TABLE": "test-versions", "AUDIT_TABLE": "test-audit"}
PAYLOAD = {"name": "Local AWS Baseline", "constraints": [
    {"id": "s3", "type": "S3_BLOCK_PUBLIC_ACCESS", "severity": "HIGH"}]}


def body(result):
    return json.loads(result["body"])


class LocalPersistenceTests(unittest.TestCase):
    def test_local_endpoint_required(self):
        with patch.dict(os.environ, {"AWS_SAM_LOCAL": "true"}, clear=True):
            with self.assertRaises(DynamoDBConfigurationError):
                dynamodb_resource()

    def test_cloud_endpoint_rejected_in_local_mode(self):
        with patch.dict(os.environ, {**LOCAL, "DYNAMODB_ENDPOINT_URL": "https://dynamodb.ap-south-1.amazonaws.com"}, clear=True):
            with self.assertRaises(DynamoDBConfigurationError):
                dynamodb_resource()

    def test_local_endpoint_rejected_without_local_flag(self):
        with patch.dict(os.environ, {"DYNAMODB_ENDPOINT_URL": "http://127.0.0.1:8000"}, clear=True):
            with self.assertRaises(DynamoDBConfigurationError):
                dynamodb_resource()

    def test_production_uses_default_role_session(self):
        with patch.dict(os.environ, {"DYNAMODB_ENDPOINT_URL": "", "CIG_LOCAL": "false"}, clear=True):
            with patch("common.dynamodb.boto3.resource") as factory:
                dynamodb_resource()
                factory.assert_called_once_with("dynamodb")

    def test_local_client_is_bounded_and_ignores_inherited_credentials(self):
        with patch.dict(os.environ, {**LOCAL, "AWS_ACCESS_KEY_ID": "inherited", "AWS_SESSION_TOKEN": "inherited"}, clear=True):
            resource = dynamodb_resource()
            client = resource.meta.client
            self.assertEqual(client.meta.endpoint_url, LOCAL["DYNAMODB_ENDPOINT_URL"])
            self.assertEqual(client.meta.config.connect_timeout, 2)
            self.assertEqual(client.meta.config.read_timeout, 3)
            self.assertEqual(client.meta.config.retries["total_max_attempts"], 1)
            self.assertEqual(client.meta.config.proxies, {})
            credentials = client._request_signer._credentials
            self.assertEqual(credentials.access_key, "CIGLOCAL")
            self.assertIsNone(credentials.token)

    def test_create_list_detail_and_approval_contract_with_sdk_stubs(self):
        intents = importlib.import_module('intents.app')
        detail = importlib.import_module('intent_detail.app')
        approval = importlib.import_module('approve_intent.app')
        with patch.dict(os.environ, LOCAL, clear=True):
            resource = dynamodb_resource()
            serializer = TypeSerializer()
            wire = lambda item: {key: serializer.serialize(value) for key, value in item.items()}
            with Stubber(resource.meta.client) as stub:
                stub.add_response('transact_write_items', {}, {'TransactItems': ANY})
                with patch.object(intents, 'dynamodb_resource', return_value=resource):
                    created = intents.lambda_handler({'requestContext': {'http': {'method': 'POST'}},
                        'body': json.dumps(PAYLOAD)}, None)
                self.assertEqual(created['statusCode'], 201)
                record = body(created)['item']; key = {'intentId': record['intentId']}
                stub.add_response('scan', {'Items': [wire(record)]},
                    {'TableName': 'test-intents', 'Limit': 25, 'FilterExpression': ANY})
                with patch.object(intents, 'dynamodb_resource', return_value=resource):
                    listed = intents.lambda_handler({}, None)
                self.assertEqual(body(listed)['items'], [record])
                stub.add_response('get_item', {'Item': wire(record)},
                    {'TableName': 'test-intents', 'Key': key, 'ConsistentRead': True})
                with patch.object(detail, 'dynamodb_resource', return_value=resource):
                    fetched = detail.lambda_handler({'pathParameters': key}, None)
                self.assertEqual(body(fetched)['item'], record)
                stub.add_response('get_item', {'Item': wire(record)},
                    {'TableName': 'test-intents', 'Key': key, 'ConsistentRead': True})
                stub.add_response('get_item', {'Item': wire(record)},
                    {'TableName': 'test-versions', 'Key': {**key, 'version': 1}, 'ConsistentRead': True})
                stub.add_response('transact_write_items', {}, {'TransactItems': ANY})
                with patch.object(approval, 'dynamodb_resource', return_value=resource):
                    result = approval.lambda_handler({'pathParameters': key}, None)
                self.assertEqual(result['statusCode'], 200)
                self.assertEqual(body(result)['item']['status'], 'APPROVED')
                self.assertEqual(body(result)['item']['activeVersion'], 1)
                stub.assert_no_pending_responses()

    def test_connection_failure_is_structured(self):
        intents = importlib.import_module("intents.app")
        with patch.dict(os.environ, LOCAL, clear=True):
            resource = dynamodb_resource()
            table = resource.Table("test-intents")
            with patch.object(resource, "Table", return_value=table), patch.object(intents, "dynamodb_resource", return_value=resource), patch("common.versions.transaction_write", side_effect=EndpointConnectionError(endpoint_url=LOCAL["DYNAMODB_ENDPOINT_URL"])):
                result = intents.lambda_handler({"requestContext": {"http": {"method": "POST"}}, "body": json.dumps(PAYLOAD)}, None)
            self.assertEqual(result["statusCode"], 502)
            self.assertEqual(body(result)["error"]["code"], "INTENT_WRITE_FAILED")


if __name__ == "__main__":
    unittest.main()
