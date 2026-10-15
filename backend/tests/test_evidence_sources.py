"""Stubbed tests for bounded, read-only VPC Flow Logs and Reachability Analyzer evidence."""
import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import boto3
from botocore.stub import Stubber

from common.evidence_sources import collect_verdicts


SNAPSHOT = datetime(2026, 10, 16, 10, 0, 0, tzinfo=timezone.utc)
SNAPSHOT_TEXT = SNAPSHOT.isoformat().replace('+00:00', 'Z')
SOURCE = 'eni-source'
TARGET = 'eni-target'
PATH_ID = 'nip-0123456789abcdef0'
ANALYSIS_ID = 'nia-0123456789abcdef0'
FLOW_GROUP = '/aws/vpc/flow-logs'
PATH_MAP = json.dumps({f'{SOURCE}|{TARGET}': PATH_ID})


def candidate(**overrides):
    row = {
        'candidateId': 'candidate-1', 'predicate': 'DIRECTED_PATH_PRESENT',
        'sourceId': SOURCE, 'targetId': TARGET, 'protocol': 'tcp', 'ports': [5432],
        'snapshotId': 'snapshot-1', 'observedAt': SNAPSHOT_TEXT,
    }
    row.update(overrides)
    return row


def inventory(**overrides):
    value = {
        'items': [
            {'resourceId': SOURCE, 'attributes': {'privateIpAddress': '10.0.0.10'}},
            {'resourceId': TARGET, 'attributes': {'privateIpAddress': '10.0.0.20'}},
        ],
        'meta': {'region': 'ap-south-1', 'accountId': '123456789012',
                 'snapshotId': 'snapshot-1', 'collectedAt': SNAPSHOT_TEXT},
    }
    value.update(overrides)
    return value


def flow_message(action='ACCEPT', protocol=6, dst_port=5432, start=None, end=None,
                 source='10.0.0.10', target='10.0.0.20', account='123456789012', status='OK'):
    start = int((SNAPSHOT - timedelta(seconds=30)).timestamp()) if start is None else start
    end = int((SNAPSHOT - timedelta(seconds=5)).timestamp()) if end is None else end
    return f'2 {account} eni-0123456789abcdef0 {source} {target} 41000 {dst_port} {protocol} 5 420 {start} {end} {action} {status}'


def log_event(message, timestamp=None, event_id='event-1'):
    return {
        'eventId': event_id, 'ingestionTime': int(SNAPSHOT.timestamp() * 1000),
        'logStreamName': 'eni-0123456789abcdef0', 'message': message,
        'timestamp': int((SNAPSHOT if timestamp is None else timestamp).timestamp() * 1000),
    }


class EvidenceSourceTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            'AWS_REGION': 'ap-south-1', 'AWS_DEFAULT_REGION': 'ap-south-1',
            'AWS_ACCESS_KEY_ID': 'fake', 'AWS_SECRET_ACCESS_KEY': 'fake',
            'CROSS_VALIDATION_ENABLED': 'true', 'FLOW_LOGS_GROUP_NAME': FLOW_GROUP,
            'CROSS_VALIDATION_PATHS_JSON': PATH_MAP,
        }, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.local = patch('common.evidence_sources.is_local', return_value=False)
        self.local.start()
        self.addCleanup(self.local.stop)
        self.factory = patch('common.evidence_sources._client', return_value=None)
        self.factory.start()
        self.addCleanup(self.factory.stop)

    @staticmethod
    def logs_client():
        return boto3.client('logs', region_name='ap-south-1', aws_access_key_id='fake', aws_secret_access_key='fake')

    @staticmethod
    def ec2_client():
        return boto3.client('ec2', region_name='ap-south-1', aws_access_key_id='fake', aws_secret_access_key='fake')

    def log_params(self):
        return {
            'logGroupName': FLOW_GROUP,
            'startTime': int((SNAPSHOT - timedelta(minutes=5)).timestamp() * 1000),
            'endTime': int((SNAPSHOT + timedelta(minutes=5)).timestamp() * 1000),
            'limit': 20,
        }

    def path_response(self, **overrides):
        path = {
            'NetworkInsightsPathId': PATH_ID, 'Source': SOURCE, 'Destination': TARGET,
            'Protocol': 'tcp', 'DestinationPort': 5432,
        }
        path.update(overrides)
        return {'NetworkInsightsPaths': [path]}

    def analysis_response(self, found=True, start=None, **overrides):
        analysis = {
            'NetworkInsightsAnalysisId': ANALYSIS_ID, 'NetworkInsightsPathId': PATH_ID,
            'StartDate': SNAPSHOT if start is None else start,
            'Status': 'succeeded', 'NetworkPathFound': found,
        }
        analysis.update(overrides)
        return {'NetworkInsightsAnalyses': [analysis]}

    def test_two_native_stubbed_sources_pass_cross_validation(self):
        from common.escalation import cross_validate
        logs, ec2 = self.logs_client(), self.ec2_client()
        with Stubber(logs) as log_stub, Stubber(ec2) as ec2_stub:
            log_stub.add_response('filter_log_events', {'events': [log_event(flow_message())]}, self.log_params())
            ec2_stub.add_response('describe_network_insights_paths', self.path_response(), {'NetworkInsightsPathIds': [PATH_ID]})
            ec2_stub.add_response('describe_network_insights_analyses', self.analysis_response(), {'NetworkInsightsPathId': PATH_ID, 'MaxResults': 100})
            rows = collect_verdicts(candidate(), inventory(), logs=logs, ec2=ec2)
            with patch('common.escalation.is_local', return_value=False):
                validation = cross_validate(candidate(), inventory(), rows)
            self.assertTrue(validation['accepted'])
            self.assertFalse(validation['simulated'])
            log_stub.assert_no_pending_responses()
            ec2_stub.assert_no_pending_responses()

    def test_flow_logs_accept_exact_private_ip_tuple_and_bound_read(self):
        client = self.logs_client()
        with Stubber(client) as stub:
            stub.add_response('filter_log_events', {'events': [log_event(flow_message())]}, self.log_params())
            rows = collect_verdicts(candidate(), inventory(), logs=client)
            self.assertEqual(rows[0]['verdict'], 'CORROBORATES')
            self.assertIn('event-1:', rows[0]['evidenceId'])
            self.assertIn(FLOW_GROUP, rows[0]['originId'])
            self.assertEqual(set(rows[0]), {
                'sourceFamily', 'verdict', 'evidenceId', 'originId', 'predicate',
                'sourceId', 'targetId', 'snapshotId', 'observedAt',
            })
            stub.assert_no_pending_responses()

    def test_flow_logs_reject_disagrees_only_for_exact_protocol_and_port(self):
        client = self.logs_client()
        with Stubber(client) as stub:
            stub.add_response('filter_log_events', {'events': [log_event(flow_message(action='REJECT'))]}, self.log_params())
            rows = collect_verdicts(candidate(), inventory(), logs=client)
            self.assertEqual(rows[0]['verdict'], 'DISAGREES')
            stub.assert_no_pending_responses()

        generic = candidate(ports=None)
        client = self.logs_client()
        with Stubber(client) as stub:
            stub.add_response('filter_log_events', {'events': [log_event(flow_message(action='REJECT'))]}, self.log_params())
            rows = collect_verdicts(generic, inventory(), logs=client)
            self.assertEqual(rows[0]['verdict'], 'UNKNOWN')
            stub.assert_no_pending_responses()

    def test_flow_logs_stale_tuple_and_missing_private_ips_remain_unknown(self):
        stale_start = int((SNAPSHOT - timedelta(minutes=12)).timestamp())
        stale_end = int((SNAPSHOT - timedelta(minutes=11)).timestamp())
        client = self.logs_client()
        with Stubber(client) as stub:
            stub.add_response('filter_log_events', {'events': [log_event(
                flow_message(start=stale_start, end=stale_end), timestamp=SNAPSHOT)]}, self.log_params())
            rows = collect_verdicts(candidate(), inventory(), logs=client)
            self.assertEqual(rows[0]['verdict'], 'UNKNOWN')
            stub.assert_no_pending_responses()

        client = self.logs_client()
        with Stubber(client) as stub:
            rows = collect_verdicts(candidate(), inventory(items=[
                {'resourceId': SOURCE, 'attributes': {'securityGroupIds': ['sg-source']}},
                {'resourceId': TARGET, 'attributes': {'privateIpAddress': '10.0.0.20'}},
            ]), logs=client)
            self.assertEqual(rows[0]['verdict'], 'UNKNOWN')
            stub.assert_no_pending_responses()

    def test_flow_logs_access_denial_is_unknown(self):
        client = self.logs_client()
        with Stubber(client) as stub:
            stub.add_client_error('filter_log_events', service_error_code='AccessDeniedException',
                http_status_code=400, expected_params=self.log_params())
            rows = collect_verdicts(candidate(), inventory(), logs=client)
            self.assertEqual(rows[0]['verdict'], 'UNKNOWN')
            stub.assert_no_pending_responses()

    def test_reachability_analyzer_fresh_existing_success_corroborates(self):
        client = self.ec2_client()
        with Stubber(client) as stub:
            stub.add_response('describe_network_insights_paths', self.path_response(), {
                'NetworkInsightsPathIds': [PATH_ID],
            })
            stub.add_response('describe_network_insights_analyses', self.analysis_response(found=True), {
                'NetworkInsightsPathId': PATH_ID, 'MaxResults': 100,
            })
            rows = collect_verdicts(candidate(), inventory(), ec2=client)
            self.assertEqual(rows[1]['sourceFamily'], 'reachabilityAnalyzer')
            self.assertEqual(rows[1]['verdict'], 'CORROBORATES')
            self.assertIn(ANALYSIS_ID, rows[1]['evidenceId'])
            self.assertIn(PATH_ID, rows[1]['originId'])
            stub.assert_no_pending_responses()

    def test_reachability_analyzer_fresh_no_path_disagrees(self):
        client = self.ec2_client()
        with Stubber(client) as stub:
            stub.add_response('describe_network_insights_paths', self.path_response(), {
                'NetworkInsightsPathIds': [PATH_ID],
            })
            stub.add_response('describe_network_insights_analyses', self.analysis_response(found=False), {
                'NetworkInsightsPathId': PATH_ID, 'MaxResults': 100,
            })
            rows = collect_verdicts(candidate(), inventory(), ec2=client)
            self.assertEqual(rows[1]['verdict'], 'DISAGREES')
            stub.assert_no_pending_responses()

    def test_reachability_analyzer_access_denial_is_unknown(self):
        client = self.ec2_client()
        with Stubber(client) as stub:
            stub.add_client_error('describe_network_insights_paths', service_error_code='UnauthorizedOperation',
                http_status_code=403, expected_params={'NetworkInsightsPathIds': [PATH_ID]})
            rows = collect_verdicts(candidate(), inventory(), ec2=client)
            self.assertEqual(rows[1]['verdict'], 'UNKNOWN')
            stub.assert_no_pending_responses()

    def test_reachability_analyzer_stale_mismatched_and_scoped_paths_are_unknown(self):
        stale = self.ec2_client()
        with Stubber(stale) as stub:
            stub.add_response('describe_network_insights_paths', self.path_response(), {
                'NetworkInsightsPathIds': [PATH_ID],
            })
            stub.add_response('describe_network_insights_analyses', self.analysis_response(
                start=SNAPSHOT - timedelta(minutes=6)), {
                'NetworkInsightsPathId': PATH_ID, 'MaxResults': 100,
            })
            rows = collect_verdicts(candidate(), inventory(), ec2=stale)
            self.assertEqual(rows[1]['verdict'], 'UNKNOWN')
            stub.assert_no_pending_responses()

        mismatched = self.ec2_client()
        with Stubber(mismatched) as stub:
            stub.add_response('describe_network_insights_paths', self.path_response(Destination='eni-other'), {
                'NetworkInsightsPathIds': [PATH_ID],
            })
            rows = collect_verdicts(candidate(), inventory(), ec2=mismatched)
            self.assertEqual(rows[1]['verdict'], 'UNKNOWN')
            stub.assert_no_pending_responses()

        scoped = self.ec2_client()
        with Stubber(scoped) as stub:
            stub.add_response('describe_network_insights_paths', self.path_response(
                FilterAtDestination={'DestinationPortRange': {'FromPort': 5432, 'ToPort': 5432}}), {
                'NetworkInsightsPathIds': [PATH_ID],
            })
            rows = collect_verdicts(candidate(), inventory(), ec2=scoped)
            self.assertEqual(rows[1]['verdict'], 'UNKNOWN')
            stub.assert_no_pending_responses()

    def test_missing_config_access_denial_and_local_mode_stay_unknown(self):
        with patch.dict(os.environ, {'FLOW_LOGS_GROUP_NAME': '', 'CROSS_VALIDATION_PATHS_JSON': '{}'}):
            rows = collect_verdicts(candidate(), inventory())
            self.assertEqual([row['verdict'] for row in rows], ['UNKNOWN', 'UNKNOWN'])

        with patch('common.evidence_sources._client', side_effect=AssertionError('local mode must not create clients')):
            with patch('common.evidence_sources.is_local', return_value=True):
                rows = collect_verdicts(candidate(), inventory())
                self.assertEqual([row['verdict'] for row in rows], ['UNKNOWN', 'UNKNOWN'])

    def test_malformed_candidate_scoping_is_unknown_without_broad_match(self):
        client = self.logs_client()
        with Stubber(client) as stub:
            rows = collect_verdicts(candidate(protocol='icmp', ports=['all']), inventory(), logs=client)
            self.assertEqual(rows[0]['verdict'], 'UNKNOWN')
            stub.assert_no_pending_responses()


if __name__ == '__main__':
    unittest.main()
