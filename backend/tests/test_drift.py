import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from common.drift import changes, complete


class DriftEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.job = {'scopeKey': 'account#region', 'evaluationId': 'new', 'intentId': 'intent', 'intentVersion': 2}
        self.before = {'items': [{'resourceId': 'bucket', 'resourceType': 'AWS::S3::Bucket', 'attributes': {'publicAccessBlockEnabled': True}, 'observedAt': 'old'}],
                       'edges': [{'sourceId': 'function', 'targetId': 'bucket', 'type': 'DYNAMODB_STREAM_TRIGGER', 'evidence': [{'observedAt': 'old'}]}],
                       'meta': {'coverage': {'resourceTypes': {'AWS::S3::Bucket': 'COMPLETE'}, 'relationshipTypes': {'STRUCTURAL': 'COMPLETE'}}, 'partial': False}}

    def diff(self, after):
        return changes(self.before, after, self.job, '2026-10-16T00:00:00Z', 'old')

    def test_collection_time_does_not_create_configuration_changes(self):
        after = copy.deepcopy(self.before)
        after['items'][0]['observedAt'] = 'new'
        after['edges'][0]['evidence'][0]['observedAt'] = 'new'
        self.assertEqual(self.diff(after), [])

    def test_actual_attribute_and_edge_removal_retain_observed_before(self):
        after = copy.deepcopy(self.before)
        after['items'][0]['attributes']['publicAccessBlockEnabled'] = False
        after['edges'] = []
        events = self.diff(after)
        self.assertEqual({r['eventType'] for r in events}, {'MODIFIED', 'DELETED'})
        resource = next(r for r in events if r['entityKind'] == 'RESOURCE')
        self.assertTrue(resource['previousState']['attributes']['publicAccessBlockEnabled'])
        self.assertFalse(resource['currentState']['attributes']['publicAccessBlockEnabled'])
        removed = next(r for r in events if r['eventType'] == 'DELETED')
        self.assertNotIn('currentState', removed)
        self.assertEqual(events, self.diff(after))

    def test_edge_port_changes_and_simulation_are_factual(self):
        self.before['edges'][0].update(protocol='tcp', ports=[443])
        after = copy.deepcopy(self.before)
        after['meta']['simulated'] = True
        after['edges'][0]['ports'] = [8443]
        event, = self.diff(after)
        self.assertEqual(event['eventType'], 'MODIFIED')
        self.assertEqual(event['previousState']['ports'], [443])
        self.assertEqual(event['currentState']['ports'], [8443])
        self.assertTrue(event['simulated'])

    def test_unrelated_partial_coverage_does_not_hide_complete_edges(self):
        self.before['meta']['coverage']['relationshipTypes'] = {
            'TAGS': 'PARTIAL', 'STRUCTURAL': 'PARTIAL', 'DYNAMODB_STREAM_TRIGGER': 'COMPLETE'}
        self.before['edges'][0]['ports'] = [443]
        after = copy.deepcopy(self.before)
        after['edges'][0]['ports'] = [8443]
        event, = self.diff(after)
        self.assertEqual(event['eventType'], 'MODIFIED')
        self.assertEqual(event['currentState']['ports'], [8443])

    def test_selected_partial_edge_type_cannot_inherit_complete_family(self):
        self.before['meta']['coverage']['relationshipTypes'] = {
            'TAGS': 'PARTIAL', 'STRUCTURAL': 'COMPLETE', 'DYNAMODB_STREAM_TRIGGER': 'PARTIAL'}
        after = copy.deepcopy(self.before)
        after['edges'] = []
        self.assertEqual(self.diff(after), [])

    def test_coverage_change_cannot_claim_removed_resources(self):
        after = copy.deepcopy(self.before)
        after['items'] = []
        after['meta']['coverage']['resourceTypes']['AWS::S3::Bucket'] = 'UNSUPPORTED'
        self.assertEqual(self.diff(after), [])

    def test_partial_or_missing_coverage_is_not_baseline(self):
        self.assertTrue(complete(self.before, {'status': 'SUCCEEDED'}))
        for inventory, evaluation in [({}, {'status': 'SUCCEEDED'}), (self.before, {'status': 'PARTIAL'}),
                                       (self.before, {'status': 'SUCCEEDED', 'summary': {'inventoryPartial': True}})]:
            self.assertFalse(complete(inventory, evaluation))

class DriftPersistenceTests(unittest.TestCase):
    def test_baseline_retry_visibility_pagination_and_scope(self):
        import os
        import json
        import boto3
        from moto import mock_aws
        from unittest.mock import patch
        from phase_support import create_tables, authed
        from common.auth import configured_scope
        from common.drift import stage
        from drift_events.app import lambda_handler
        env = {'AWS_DEFAULT_REGION': 'ap-south-1', 'AWS_REGION': 'ap-south-1',
               'AWS_ACCESS_KEY_ID': 'test', 'AWS_SECRET_ACCESS_KEY': 'test',
               'CIG_LOCAL': 'false', 'CIG_ACCOUNT_ID': '123456789012', 'DRIFT_HISTORY_ENABLED': 'true'}
        with patch.dict(os.environ, env, clear=True), mock_aws():
            db = boto3.resource('dynamodb', region_name='ap-south-1')
            create_tables(db)
            scope = configured_scope()
            intent = db.Table(os.environ['INTENTS_TABLE'])
            intent.put_item(Item={'intentId': 'intent'})
            evaluation = {'status': 'SUCCEEDED', 'finishedAt': '2026-10-16T00:00:00Z'}
            old = {'items': [{'resourceId': 'bucket', 'resourceType': 'AWS::S3::Bucket', 'attributes': {'public': False}}],
                   'edges': [], 'meta': {'coverage': {'resourceTypes': {'AWS::S3::Bucket': 'COMPLETE'}}}}
            job = {'scopeKey': scope, 'evaluationId': 'baseline', 'intentId': 'intent', 'intentVersion': 1}
            baseline = stage(db, job, evaluation, old, lambda *args: None)
            self.assertEqual(db.Table(os.environ['DRIFT_EVENTS_TABLE']).scan()['Items'], [])
            intent.put_item(Item={'intentId': 'intent', 'driftBaseline': baseline})
            new = copy.deepcopy(old)
            new['items'][0]['attributes']['public'] = True
            job['evaluationId'] = 'changed'
            loader = lambda *args: ({'status': 'SUCCEEDED'}, old, [])
            partial = copy.deepcopy(new)
            partial['items'] = []
            partial['meta']['partial'] = True
            self.assertIsNone(stage(db, job, evaluation, partial, loader))
            self.assertEqual(db.Table(os.environ['DRIFT_EVENTS_TABLE']).scan()['Items'], [])
            stage(db, job, evaluation, new, loader)
            stage(db, job, evaluation, new, loader)
            self.assertEqual(intent.get_item(Key={'intentId': 'intent'})['Item']['driftBaseline'], baseline)
            rows = db.Table(os.environ['DRIFT_EVENTS_TABLE']).scan()['Items']
            self.assertEqual(len(rows), 1)
            with patch('drift_events.app.dynamodb_resource', return_value=db):
                self.assertEqual(json.loads(lambda_handler(authed(role='viewer'), None)['body'])['items'], [])
                jobs = db.Table(os.environ['EVALUATIONS_TABLE'])
                jobs.put_item(Item={'evaluationId': 'changed', 'scopeKey': scope, 'status': 'SUCCEEDED'})
                listed = lambda_handler(authed({'queryStringParameters': {'limit': '1'}}, role='viewer'), None)
                self.assertEqual(len(json.loads(listed['body'])['items']), 1)
                detail = lambda_handler(authed({'pathParameters': {'id': rows[0]['id']}}, role='viewer'), None)
                self.assertEqual(detail['statusCode'], 200)
                jobs.put_item(Item={'evaluationId': 'changed', 'scopeKey': 'other', 'status': 'SUCCEEDED'})
                self.assertEqual(lambda_handler(authed({'pathParameters': {'id': rows[0]['id']}}, role='viewer'), None)['statusCode'], 404)


class DriftCapabilityTests(unittest.TestCase):
    def test_local_status_advertises_only_enabled_drift_history(self):
        import os
        import json
        from unittest.mock import patch
        from phase_support import authed
        from status.app import lambda_handler
        for enabled in ('false', 'true'):
            with self.subTest(enabled=enabled), patch.dict(os.environ, {'CIG_LOCAL': 'true', 'DRIFT_HISTORY_ENABLED': enabled}):
                state = json.loads(lambda_handler(authed(role='viewer'), None)['body'])
                self.assertEqual(state['features']['driftEvents'], enabled == 'true')

class DriftWorkerJourneyTests(unittest.TestCase):
    def test_complete_handler_worker_journey(self):
        import os
        import boto3
        from moto import mock_aws
        from unittest.mock import patch
        from phase_support import create_tables
        from verify_drift import verify
        with patch.dict(os.environ, {'CIG_LOCAL': 'true', 'AWS_REGION': 'ap-south-1',
                'DRIFT_HISTORY_ENABLED': 'true', 'INVENTORY_PROVIDER': 'fixture',
                'LLM_ENABLED': 'false', 'AWS_ACCESS_KEY_ID': 'test', 'AWS_SECRET_ACCESS_KEY': 'test'}, clear=True), mock_aws():
            db = boto3.resource('dynamodb', region_name='ap-south-1')
            create_tables(db)
            from contextlib import ExitStack
            with ExitStack() as stack:
                stack.enter_context(patch('common.dynamodb.dynamodb_resource', return_value=db))
                for module in ('intents', 'approve_intent', 'evaluations', 'drift_events', 'versions'):
                    stack.enter_context(patch(module + '.app.dynamodb_resource', return_value=db))
                self.assertTrue(verify(db)['passed'])
