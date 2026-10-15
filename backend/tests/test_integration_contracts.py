"""Real handler contracts against Moto; discovery observations are explicit test fixtures."""
import importlib
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import boto3
from phase_support import authed, create_tables, finish
from moto import mock_aws
from common.contracts import scan_all


def decoded(result, expected=200):
    if result['statusCode'] != expected:
        raise AssertionError(result)
    return json.loads(result['body'])


class IntegrationContracts(unittest.TestCase):
    def setUp(self):
        self.contract_output = os.environ.get("CIG_CONTRACT_OUTPUT")
        self.env = patch.dict(os.environ, {'AWS_REGION': 'ap-south-1', 'AWS_DEFAULT_REGION': 'ap-south-1',
            'AWS_ACCESS_KEY_ID': 'testing', 'AWS_SECRET_ACCESS_KEY': 'testing', 'CIG_LOCAL': 'false',
            'INTENTS_TABLE': 'contract-intents', 'FINDINGS_TABLE': 'contract-findings',
            'CIG_ACCOUNT_ID': '123456789012', 'ASYNC_WORKER_ENABLED': 'true', 'EVALUATIONS_TABLE': 'contract-evaluations'}, clear=True)
        self.env.start()
        self.aws = mock_aws()
        self.aws.start()
        self.db = boto3.resource('dynamodb', region_name='ap-south-1')
        create_tables(self.db)

    def tearDown(self):
        self.aws.stop()
        self.env.stop()

    def test_handler_workflow_and_cross_language_contract(self):
        intents = importlib.import_module('intents.app')
        detail = importlib.import_module('intent_detail.app')
        approve = importlib.import_module('approve_intent.app')
        evaluation = importlib.import_module('evaluations.app')
        views = importlib.import_module('views.app')
        findings = importlib.import_module('findings.app')
        status = importlib.import_module('status.app')
        manifest = {'name': 'Contract baseline', 'description': 'Test observation, not live AWS evidence',
                    'constraints': [{'id': 'ssh', 'type': 'SECURITY_GROUP_NO_OPEN_SSH', 'severity': 'HIGH'}]}
        created = decoded(intents.lambda_handler(authed({'requestContext': {'http': {'method': 'POST'}}, 'body': json.dumps(manifest)}), None), 201)
        key = {'intentId': created['item']['intentId']}
        self.assertEqual(decoded(detail.lambda_handler(authed({'pathParameters': key}), None)), created)
        listed = decoded(intents.lambda_handler(authed({}), None))
        self.assertEqual(listed['items'], [created['item']])
        approved = decoded(approve.lambda_handler(authed({'pathParameters': key}), None))
        self.assertEqual(approved['item']['status'], 'APPROVED')
        observations = {'items': [{'resourceId': 'sg-contract', 'name': 'Contract group', 'resourceType': 'AWS::EC2::SecurityGroup',
            'region': 'ap-south-1', 'source': 'Explicit test fixture', 'lastObservedAt': '2026-10-13T00:00:00Z',
            'attributes': {'ingressRules': [{'protocol': 'tcp', 'fromPort': 22, 'toPort': 22, 'cidr': '0.0.0.0/0'}]}}],
            'edges': [], 'meta': {'accountId': '123456789012', 'region': 'ap-south-1', 'totalResources': 1, 'partial': False, 'warnings': []}}
        with patch('evaluation_worker.app.observations', return_value=observations):
            queued = decoded(evaluation.lambda_handler(authed({'body': json.dumps(key)}), None), 202)
            evaluated = finish(self.db, queued)
        self.assertEqual(evaluated['evaluation']['status'], 'SUCCEEDED')
        self.assertEqual(evaluated['evaluation']['conformance']['percent'], 0)
        found = decoded(findings.lambda_handler(authed({}), None))
        self.assertEqual(len(found['items']), 1)
        finding_id = found['items'][0]['findingId']
        finding = decoded(views.lambda_handler(authed({'pathParameters': {'findingId': finding_id}}), None))
        self.assertEqual(finding['item']['findingId'], finding_id)
        self.assertTrue(finding['item']['remediationAvailable'])
        self.assertEqual(finding['item']['remediationActionId'], 'REMOVE_OPEN_SSH')
        dashboard = decoded(views.lambda_handler(authed({}), None))
        self.assertEqual(dashboard['totalFindings'], 1)
        self.assertEqual(dashboard['severityCounts']['high'], 1)
        self.assertIsNone(dashboard['openRemediations'])
        with patch.dict(os.environ, {'CIG_LOCAL': 'true'}):
            local_status = decoded(status.lambda_handler(authed({}), None))
            self.assertFalse(local_status['awsSourcesConnected'])
            self.assertTrue(local_status['backendReachable'])
            self.assertEqual(evaluation.lambda_handler(authed({'body': '{}'}), None)['statusCode'], 409)
        fixture = {'created': created, 'intents': listed, 'approved': approved, 'findings': found,
                   'finding': finding, 'dashboard': dashboard, 'evaluation': queued, 'evaluationDetail': decoded(evaluation.lambda_handler(authed({'requestContext': {'http': {'method': 'GET'}}, 'pathParameters': {'id': queued['evaluation']['evaluationId']}}), None)),
                   'evaluations': decoded(evaluation.lambda_handler(authed({'requestContext': {'http': {'method': 'GET'}}}), None)), 'status': local_status}
        version_api = importlib.import_module('versions.app')
        audit_api = importlib.import_module('audit.app')
        version_id = {'intentId': key['intentId'], 'version': '1'}
        fixture['versions'] = decoded(version_api.lambda_handler(authed({'rawPath': '/v1/intents/x/versions', 'pathParameters': key}), None))
        fixture['versionDetail'] = decoded(version_api.lambda_handler(authed({'rawPath': '/v1/intents/x/versions/1', 'pathParameters': version_id}), None))
        fixture['versionDiff'] = decoded(version_api.lambda_handler(authed({'rawPath': '/v1/intents/x/diff', 'pathParameters': key,
            'queryStringParameters': {'fromVersion': '1', 'toVersion': '1'}}), None))
        revision = self.db.Table(os.environ['FINDINGS_TABLE']).get_item(Key={'findingId': finding_id})['Item'].get('revision', 0)
        fixture['findingAcknowledged'] = decoded(findings.lambda_handler(authed({'requestContext': {'http': {'method': 'PATCH'}},
            'pathParameters': {'findingId': finding_id}, 'body': json.dumps({'action': 'ACKNOWLEDGE', 'expectedRevision': int(revision)})}), None))
        fixture['audit'] = decoded(audit_api.lambda_handler(authed({}), None))
        destination = self.contract_output
        if destination:
            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(fixture, indent=2) + '\n')

    def test_udp_22_is_not_ssh(self):
        module = importlib.import_module('evaluations.app')
        resource = {'resourceType': 'AWS::EC2::SecurityGroup', 'attributes': {'ingressRules': [
            {'protocol': 'udp', 'fromPort': 22, 'toPort': 22, 'cidr': '0.0.0.0/0'}]}}
        from common.attribute_rules import _violates
        self.assertFalse(_violates({'type': 'SECURITY_GROUP_NO_OPEN_SSH'}, resource)[0])

    def test_capped_scan_reports_incomplete(self):
        table = MagicMock()
        table.scan.return_value = {'Items': [{'id': 'a'}], 'LastEvaluatedKey': {'id': 'a'}}
        _, incomplete = scan_all(table, max_pages=2)
        self.assertTrue(incomplete)
        self.assertEqual(table.scan.call_count, 2)

    def test_unevaluated_dashboard_never_claims_compliance(self):
        result = decoded(importlib.import_module('views.app').lambda_handler(authed({}), None))
        self.assertIsNone(result['conformance']['percent'])
        self.assertIsNone(result['lastEvaluatedAt'])
        self.assertEqual(result['totalFindings'], 0)

    def test_missing_finding_is_404(self):
        result = importlib.import_module('views.app').lambda_handler(authed({'pathParameters': {'findingId': 'absent'}}), None)
        self.assertEqual(result['statusCode'], 404)

    def test_actual_graph_uses_only_observed_nodes_and_edges(self):
        module = importlib.import_module('resources.app')
        observation = {'items': [{'resourceId': 'vpc-test', 'name': 'Test VPC', 'resourceType': 'AWS::EC2::VPC', 'attributes': {}}],
                       'edges': [{'sourceId': 'not-collected', 'targetId': 'vpc-test', 'type': 'IN_VPC'}],
                       'meta': {'accountId': '123456789012', 'partial': False, 'warnings': [], 'collectedAt': '2026-10-13T00:00:00Z'}}
        with patch.object(module, 'collect_inventory', return_value=observation):
            graph = decoded(module.lambda_handler(authed({'rawPath': '/v1/architecture/graph', 'queryStringParameters': {'view': 'ACTUAL'}}), None))
        self.assertEqual(graph['nodes'][0]['id'], 'vpc-test')
        self.assertEqual(graph['nodes'][0]['diffState'], 'UNKNOWN')
        self.assertEqual(graph['edges'], [])
        self.assertEqual(module.lambda_handler(authed({'rawPath': '/v1/architecture/graph', 'queryStringParameters': {'view': 'DIFF'}}), None)['statusCode'], 409)


if __name__ == '__main__':
    unittest.main()
