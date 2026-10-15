"""Authorization, append-only audit and finding transitions with local SDK emulation."""
import importlib
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import boto3
from moto import mock_aws
from common.auth import authorize, AuthorizationError
from local_db import TABLES, table_schema


def event(role='admin', method='GET', body=None, params=None, query=None, request_id='request-test'):
    return {'requestContext': {'requestId': request_id, 'http': {'method': method},
        'authorizer': {'jwt': {'claims': {'sub': 'user-test', 'cognito:groups': [role]}}}},
        'body': json.dumps(body or {}), 'pathParameters': params or {}, 'queryStringParameters': query or {}}


class AuthorizationTests(unittest.TestCase):
    def test_production_missing_identity_and_roles_fail_closed(self):
        with patch.dict(os.environ, {'CIG_LOCAL': 'false', 'INVENTORY_PROVIDER': 'fixture'}, clear=True):
            with self.assertRaises(AuthorizationError) as result:
                authorize({})
            self.assertEqual(result.exception.status, 401)
            with self.assertRaises(AuthorizationError):
                authorize(event('unrecognized'))
            with self.assertRaises(AuthorizationError):
                authorize(event('viewer'), 'approver')

    def test_claim_representations_and_group_hierarchy(self):
        with patch.dict(os.environ, {'CIG_LOCAL': 'false'}, clear=True):
            for groups in [['viewer', 'admin'], '["viewer", "admin"]', '[viewer, admin]', 'viewer,admin']:
                request = event()
                request['requestContext']['authorizer']['jwt']['claims']['cognito:groups'] = groups
                self.assertEqual(authorize(request, 'admin')['role'], 'admin')
            for groups in [{}, ['admin', 1], '[]', '"admin"', 'admin evil']:
                request = event()
                request['requestContext']['authorizer']['jwt']['claims']['cognito:groups'] = groups
                with self.assertRaises(AuthorizationError):
                    authorize(request, 'admin')

    def test_synthetic_actor_is_local_fixture_only(self):
        with patch.dict(os.environ, {'CIG_LOCAL': 'true', 'INVENTORY_PROVIDER': 'fixture'}, clear=True):
            self.assertEqual(authorize({}, 'admin')['sub'], 'local-fixture-actor')
        with patch.dict(os.environ, {'CIG_LOCAL': 'true', 'INVENTORY_PROVIDER': 'aws'}, clear=True):
            with self.assertRaises(AuthorizationError):
                authorize({})


class Phase2StateTests(unittest.TestCase):
    def setUp(self):
        settings = {'AWS_REGION': 'ap-south-1', 'AWS_DEFAULT_REGION': 'ap-south-1',
            'AWS_ACCESS_KEY_ID': 'testing', 'AWS_SECRET_ACCESS_KEY': 'testing',
            'CIG_LOCAL': 'false', 'CIG_ACCOUNT_ID': '123456789012', 'STAGE_NAME': 'dev'}
        settings.update({key: 'state-' + value[0].removeprefix('cloud-intent-guardian-dev-') for key, value in TABLES.items()})
        self.env = patch.dict(os.environ, settings, clear=True); self.env.start()
        self.aws = mock_aws(); self.aws.start()
        self.db = boto3.resource('dynamodb', region_name='ap-south-1')
        for key in TABLES:
            self.db.create_table(TableName=os.environ[key], BillingMode='PAY_PER_REQUEST', **table_schema(key))
        self.findings = importlib.import_module('findings.app')
        self.audit = importlib.import_module('audit.app')
        self.key = {'findingId': 'finding-state'}
        self.db.Table(os.environ['FINDINGS_TABLE']).put_item(Item={**self.key, 'status': 'OPEN',
            'accountId': '123456789012', 'region': 'ap-south-1', 'revision': 0, 'severity': 'HIGH'})

    def tearDown(self):
        self.aws.stop(); self.env.stop()

    def mutate(self, action, revision, role='approver', reason='', request='mutation-test'):
        return self.findings.lambda_handler(event(role, 'PATCH', {'action': action, 'expectedRevision': revision,
            'reason': reason}, self.key, request_id=request), None)

    def test_viewer_cannot_mutate_suppression_requires_reason_stale_is_conflict(self):
        self.assertEqual(self.mutate('ACKNOWLEDGE', 0, role='viewer')['statusCode'], 403)
        self.assertEqual(self.mutate('SUPPRESS', 0)['statusCode'], 400)
        self.assertEqual(self.mutate('ACKNOWLEDGE', 0)['statusCode'], 200)
        self.assertEqual(self.mutate('ACKNOWLEDGE', 0)['statusCode'], 409)
        self.assertEqual(self.mutate('SUPPRESS', 1, reason='Approved temporary exception', request='suppress')['statusCode'], 200)
        self.assertEqual(self.mutate('REOPEN', 2, request='reopen')['statusCode'], 200)
        stored = self.db.Table(os.environ['FINDINGS_TABLE']).get_item(Key=self.key)['Item']
        self.assertEqual(stored['status'], 'OPEN')
        self.assertEqual(stored['suppressionReason'], 'Approved temporary exception')
        events = self.db.Table(os.environ['AUDIT_TABLE']).scan()['Items']
        self.assertEqual(len(events), 3)
        self.assertTrue(all(row['actor']['sub'] == 'user-test' for row in events))

    def test_audit_and_state_commit_together(self):
        self.db.Table(os.environ['AUDIT_TABLE']).delete()
        self.assertNotEqual(self.mutate('ACKNOWLEDGE', 0)['statusCode'], 200)
        self.assertEqual(self.db.Table(os.environ['FINDINGS_TABLE']).get_item(Key=self.key)['Item']['status'], 'OPEN')

    def test_other_scope_finding_cannot_be_changed(self):
        self.db.Table(os.environ['FINDINGS_TABLE']).update_item(Key=self.key,
            UpdateExpression='SET accountId=:account', ExpressionAttributeValues={':account': 'other-account'})
        self.assertEqual(self.mutate('ACKNOWLEDGE', 0)['statusCode'], 404)

    def test_audit_pagination_filters_and_cursor_scope(self):
        self.mutate('ACKNOWLEDGE', 0)
        self.mutate('SUPPRESS', 1, reason='reviewed', request='suppress')
        page = self.audit.lambda_handler(event('viewer', query={'limit': '1'}), None)
        self.assertEqual(page['statusCode'], 200)
        data = json.loads(page['body'])
        self.assertEqual(len(data['items']), 1)
        self.assertIsNotNone(data['nextToken'])
        next_page = json.loads(self.audit.lambda_handler(event('viewer', query={'limit': '1', 'nextToken': data['nextToken']}), None)['body'])
        self.assertNotEqual(next_page['items'][0]['auditId'], data['items'][0]['auditId'])
        invalid = self.audit.lambda_handler(event('viewer', query={'nextToken': data['nextToken'], 'action': 'OTHER'}), None)
        self.assertEqual(invalid['statusCode'], 400)
