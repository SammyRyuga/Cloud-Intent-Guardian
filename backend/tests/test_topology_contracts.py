"""Phase 1 handler contracts: fictional observations, no AWS service calls."""
import importlib
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import boto3
from moto import mock_aws
from common.scenarios import scenario_manifest


def payload(result, status=200):
    if result['statusCode'] != status:
        raise AssertionError(result)
    return json.loads(result['body'])


class TopologyContracts(unittest.TestCase):
    def setUp(self):
        self.contract_output = os.environ.get('CIG_TOPOLOGY_CONTRACT_OUTPUT')
        self.env = patch.dict(os.environ, {'AWS_REGION': 'ap-south-1', 'AWS_DEFAULT_REGION': 'ap-south-1',
            'AWS_ACCESS_KEY_ID': 'testing', 'AWS_SECRET_ACCESS_KEY': 'testing',
            'CIG_LOCAL': 'true', 'DYNAMODB_ENDPOINT_URL': 'http://127.0.0.1:18000',
            'INVENTORY_PROVIDER': 'fixture', 'CIG_FIXTURE_SCENARIO': 'benign',
            'INTENTS_TABLE': 'v2-intents', 'FINDINGS_TABLE': 'v2-findings', 'EVALUATIONS_TABLE': 'v2-evaluations'}, clear=True)
        self.env.start()
        self.aws = mock_aws(); self.aws.start()
        self.db = boto3.resource('dynamodb', region_name='ap-south-1')
        for table, key in [('v2-intents', 'intentId'), ('v2-findings', 'findingId'), ('v2-evaluations', 'evaluationId')]:
            self.db.create_table(TableName=table, KeySchema=[{'AttributeName': key, 'KeyType': 'HASH'}],
                AttributeDefinitions=[{'AttributeName': key, 'AttributeType': 'S'}], BillingMode='PAY_PER_REQUEST')
        self.patches = []
        for name in ['intents', 'approve_intent', 'resources', 'evaluations']:
            module = importlib.import_module(name + '.app')
            setting = patch.object(module, 'dynamodb_resource', return_value=self.db)
            setting.start(); self.patches.append(setting)

    def tearDown(self):
        for setting in self.patches:
            setting.stop()
        self.aws.stop(); self.env.stop()

    def create(self, manifest=None):
        module = importlib.import_module('intents.app')
        item = payload(module.lambda_handler({'requestContext': {'http': {'method': 'POST'}},
            'body': json.dumps(manifest or scenario_manifest())}, None), 201)['item']
        self.created = {'item': item}
        approved = payload(importlib.import_module('approve_intent.app').lambda_handler(
            {'pathParameters': {'intentId': item['intentId']}}, None))['item']
        return approved

    def evaluate(self, intent):
        return payload(importlib.import_module('evaluations.app').lambda_handler(
            {'body': json.dumps({'intentId': intent['intentId']})}, None))

    def test_v2_create_approve_read_and_intent_graph_never_collects(self):
        intent = self.create()
        self.assertEqual(intent['components'], scenario_manifest()['components'])
        graph_module = importlib.import_module('resources.app')
        with patch.object(graph_module, 'collect_inventory', side_effect=AssertionError('AWS call')):
            graph = payload(graph_module.lambda_handler({'rawPath': '/v1/architecture/graph',
                'queryStringParameters': {'view': 'INTENT', 'intentId': intent['intentId']}}, None))
        self.assertEqual(graph['view'], 'INTENT')
        self.assertEqual(len(graph['nodes']), 4)
        self.assertIsInstance(graph['asOf'], str)

    def test_benign_is_not_a_violation_and_bypass_is_high(self):
        intent = self.create()
        benign = self.evaluate(intent)
        self.assertEqual(benign['findings'], [])
        with patch.dict(os.environ, {'CIG_FIXTURE_SCENARIO': 'lambda-db-bypass'}):
            bypass = self.evaluate(intent)
        types = {row['ruleId'] for row in bypass['findings']}
        self.assertIn('FORBIDDEN_PATH', types)
        self.assertIn('REQUIRED_INTERMEDIARY', types)
        self.assertTrue(all(row['severity'] == 'HIGH' for row in bypass['findings'] if row['ruleId'] in {'FORBIDDEN_PATH', 'REQUIRED_INTERMEDIARY'}))
        self.assertTrue(bypass['evaluation']['simulated'])
        destination = self.contract_output
        if destination:
            module = importlib.import_module('resources.app')
            request = {'rawPath': '/v1/architecture/graph', 'queryStringParameters': {'view': 'INTENT', 'intentId': intent['intentId']}}
            intent_graph = payload(module.lambda_handler(request, None))
            request['queryStringParameters']['view'] = 'DIFF'
            with patch.dict(os.environ, {'CIG_FIXTURE_SCENARIO': 'lambda-db-bypass'}):
                diff_graph = payload(module.lambda_handler(request, None))
            Path(destination).write_text(json.dumps({'created': self.created, 'approved': {'item': intent},
                'intentGraph': intent_graph, 'diffGraph': diff_graph, 'bypassEvaluation': bypass}, indent=2) + '\n')

    def test_open_ssh_is_deduplicated_and_resolves_when_complete(self):
        intent = self.create()
        with patch.dict(os.environ, {'CIG_FIXTURE_SCENARIO': 'open-ssh'}):
            first = self.evaluate(intent)
            repeated = self.evaluate(intent)
        ssh = next(row for row in first['findings'] if row['ruleId'] == 'SECURITY_GROUP_NO_OPEN_SSH')
        again = next(row for row in repeated['findings'] if row['ruleId'] == 'SECURITY_GROUP_NO_OPEN_SSH')
        self.assertEqual(ssh['findingId'], again['findingId'])
        self.evaluate(intent)
        stored = self.db.Table('v2-findings').get_item(Key={'findingId': ssh['findingId']})['Item']
        self.assertEqual(stored['status'], 'RESOLVED')

    def test_local_without_fixture_refuses_before_collector(self):
        module = importlib.import_module('evaluations.app')
        with patch.dict(os.environ, {'INVENTORY_PROVIDER': 'aws'}), patch.object(module, 'collect_inventory', side_effect=AssertionError('AWS call')):
            self.assertEqual(module.lambda_handler({}, None)['statusCode'], 409)

    def test_fixture_cannot_enable_production_observations(self):
        module = importlib.import_module('evaluations.app')
        intent = self.create()
        with patch.dict(os.environ, {'CIG_LOCAL': 'false'}), patch.object(module, 'collect_inventory', side_effect=AssertionError('AWS call')):
            self.assertEqual(module.lambda_handler({'body': json.dumps({'intentId': intent['intentId']})}, None)['statusCode'], 409)

    def test_missing_attribute_retains_finding_and_unknown_is_not_pass(self):
        intent = self.create({'name': 'Bucket intent', 'constraints': [
            {'id': 'pab', 'type': 'S3_BLOCK_PUBLIC_ACCESS', 'severity': 'HIGH'}]})
        from common.scenarios import scenario_inventory
        inventory = scenario_inventory()
        inventory['items'] = [{'resourceId': 'fixture-bucket', 'resourceType': 'AWS::S3::Bucket',
            'region': 'ap-south-1', 'attributes': {'publicAccessBlockEnabled': False}}]
        module = importlib.import_module('evaluations.app')
        with patch.object(module, 'observations', return_value=inventory):
            first = self.evaluate(intent)
        inventory['items'][0]['attributes'] = {'publicAccessBlockEnabled': None}
        with patch.object(module, 'observations', return_value=inventory):
            unknown = self.evaluate(intent)
        self.assertEqual(unknown['evaluation']['status'], 'PARTIAL')
        self.assertIsNone(unknown['evaluation']['conformance']['percent'])
        stored = self.db.Table('v2-findings').get_item(Key={'findingId': first['findings'][0]['findingId']})['Item']
        self.assertEqual(stored['status'], 'OPEN')

    def test_graph_diff_endpoints_are_real_and_forbidden_is_unexpected(self):
        intent = self.create()
        module = importlib.import_module('resources.app')
        with patch.dict(os.environ, {'CIG_FIXTURE_SCENARIO': 'lambda-db-bypass'}):
            graph = payload(module.lambda_handler({'rawPath': '/v1/architecture/graph',
                'queryStringParameters': {'view': 'DIFF', 'intentId': intent['intentId']}}, None))
        ids = {row['id'] for row in graph['nodes']}
        self.assertTrue(all(row['source'] in ids and row['target'] in ids for row in graph['edges']))
        self.assertIn('UNEXPECTED', {row['diffState'] for row in graph['edges']})


if __name__ == '__main__':
    unittest.main()
