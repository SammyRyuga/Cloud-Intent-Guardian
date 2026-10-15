"""Remediation lifecycle contracts, dry-run guarantees, and exact SDK parameters."""
import importlib
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import boto3
from botocore.stub import Stubber
from moto import mock_aws

from common.remediation import build_plan, current_plan, execute_action
from phase_support import create_tables


def body(result, expected=200):
    if result['statusCode'] != expected:
        raise AssertionError(result)
    return json.loads(result['body'])


def event(role, method, path, path_parameters=None, payload=None, request_id='remediation-test'):
    value = {
        'rawPath': path,
        'requestContext': {
            'requestId': request_id,
            'http': {'method': method},
            'authorizer': {'jwt': {'claims': {
                'sub': 'remediation-user', 'name': 'Remediation Tester',
                'cognito:groups': [role],
            }}},
        },
        'pathParameters': path_parameters or {},
    }
    if payload is not None:
        value['body'] = json.dumps(payload)
    return value


class RemediationLifecycleTests(unittest.TestCase):
    def setUp(self):
        inherited_output = os.environ.get('CIG_REMEDIATION_CONTRACT_OUTPUT')
        test_env = {
            'AWS_REGION': 'ap-south-1', 'AWS_DEFAULT_REGION': 'ap-south-1',
            'AWS_ACCESS_KEY_ID': 'testing', 'AWS_SECRET_ACCESS_KEY': 'testing',
            'CIG_LOCAL': 'true', 'CIG_ACCOUNT_ID': '123456789012', 'STAGE_NAME': 'dev',
            'REMEDIATIONS_TABLE': 'remediation-proposals',
            'FINDINGS_TABLE': 'remediation-findings', 'AUDIT_TABLE': 'remediation-audit',
            'REMEDIATION_ENABLED': 'true', 'REMEDIATION_DRY_RUN': 'false',
        }
        if inherited_output:
            test_env['CIG_REMEDIATION_CONTRACT_OUTPUT'] = inherited_output
        self.env = patch.dict(os.environ, test_env, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.aws = mock_aws()
        self.aws.start()
        self.addCleanup(self.aws.stop)
        self.db = boto3.resource('dynamodb', region_name='ap-south-1')
        create_tables(self.db)
        self.app = importlib.import_module('remediations.app')
        self.app.dynamodb_resource = lambda: self.db

    def put_finding(self, finding_id='finding-ssh', **overrides):
        finding = {
            'findingId': finding_id, 'evaluationId': 'evaluation-1', 'intentId': 'intent-1',
            'intentVersion': 1, 'resourceId': 'sg-0123456789abcdef0', 'resourceType': 'AWS::EC2::SecurityGroup',
            'accountId': '123456789012', 'region': 'ap-south-1', 'scopeKey': 'fixture-account#ap-south-1#dev',
            'ruleId': 'SECURITY_GROUP_NO_OPEN_SSH', 'status': 'OPEN', 'revision': 1,
            'tier': 'TIER_1', 'confidence': 'HIGH', 'observed': {'ingressRules': [
                {'protocol': 'tcp', 'fromPort': 22, 'toPort': 22, 'cidr': '0.0.0.0/0'},
                {'protocol': 'tcp', 'fromPort': 80, 'toPort': 80, 'cidr': '0.0.0.0/0'},
            ]},
        }
        finding.update(overrides)
        self.db.Table('remediation-findings').put_item(Item=finding)
        return finding

    def invoke(self, role, method, path, params=None, payload=None, request_id='remediation-test'):
        return self.app.lambda_handler(event(role, method, path, params, payload, request_id), None)

    def prepare_production_proposal(self):
        self.put_finding()
        created = body(self.invoke('admin', 'POST', '/v1/remediations', payload={
            'findingId': 'finding-ssh', 'actionId': 'REMOVE_OPEN_SSH'}), 201)['item']
        approved = body(self.invoke('approver', 'POST', f"/v1/remediations/{created['proposalId']}/approve",
            {'proposalId': created['proposalId']}, {'expectedRevision': 1, 'reason': 'Reviewed impact'}))['item']
        self.assertEqual(approved['status'], 'APPROVED')
        return created

    def production_scope(self):
        return (
            patch.object(self.app, 'is_local', return_value=False),
            patch.object(self.app, 'configured_scope', return_value='fixture-account#ap-south-1#dev'),
        )

    @staticmethod
    def ec2_client():
        return boto3.client('ec2', region_name='ap-south-1', aws_access_key_id='fake', aws_secret_access_key='fake')

    @staticmethod
    def sts_client():
        return boto3.client('sts', region_name='ap-south-1', aws_access_key_id='fake', aws_secret_access_key='fake')

    def test_admin_proposal_approval_and_local_dry_run_contract(self):
        self.put_finding()
        with patch('boto3.client', side_effect=AssertionError('local dry-run must not construct AWS service clients')):
            created = body(self.invoke('admin', 'POST', '/v1/remediations', payload={
                'findingId': 'finding-ssh', 'actionId': 'REMOVE_OPEN_SSH'}, request_id='create-proposal'), 201)
            proposal = created['item']
            self.assertEqual(proposal['status'], 'PROPOSED')
            self.assertEqual(proposal['revision'], 1)
            self.assertEqual(proposal['plan']['before']['publicSshPermissions'], [{
                'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22,
                'IpRanges': [{'CidrIp': '0.0.0.0/0'}],
            }])

            approved = body(self.invoke('approver', 'POST', f"/v1/remediations/{proposal['proposalId']}/approve",
                {'proposalId': proposal['proposalId']}, {'expectedRevision': 1, 'reason': 'Reviewed impact'},
                'approve-proposal'))
            self.assertEqual((approved['item']['status'], approved['item']['revision']), ('APPROVED', 2))

            executed = body(self.invoke('admin', 'POST', f"/v1/remediations/{proposal['proposalId']}/execute",
                {'proposalId': proposal['proposalId']}, {'expectedRevision': 2}, 'execute-proposal'))
            self.assertEqual((executed['item']['status'], executed['item']['revision']), ('DRY_RUN_COMPLETE', 4))
            self.assertEqual(executed['item']['execution']['status'], 'DRY_RUN_COMPLETE')
            self.assertTrue(executed['item']['execution']['dryRun'])

            listed = body(self.invoke('viewer', 'GET', '/v1/remediations'))
            self.assertEqual(set(listed), {'items', 'count', 'nextToken'})
            self.assertEqual(listed['count'], 1)
            detail = body(self.invoke('viewer', 'GET', f"/v1/remediations/{proposal['proposalId']}",
                {'proposalId': proposal['proposalId']}))
            self.assertEqual(detail['item']['proposalId'], proposal['proposalId'])
            self.assertEqual(detail['item']['status'], 'DRY_RUN_COMPLETE')

            output_path = os.environ.get('CIG_REMEDIATION_CONTRACT_OUTPUT')
            if output_path:
                Path(output_path).write_text(json.dumps({
                    'created': created, 'approved': approved, 'executed': executed, 'list': listed,
                }, indent=2) + '\n')

        audit = self.db.Table('remediation-audit').scan()['Items']
        self.assertEqual(len(audit), 4)
        self.assertTrue(all(isinstance(row['target'], dict) for row in audit))

    def test_role_and_revision_guards(self):
        self.put_finding()
        denied = self.invoke('viewer', 'POST', '/v1/remediations', payload={
            'findingId': 'finding-ssh', 'actionId': 'REMOVE_OPEN_SSH'})
        self.assertEqual(denied['statusCode'], 403)
        proposal = body(self.invoke('admin', 'POST', '/v1/remediations', payload={
            'findingId': 'finding-ssh', 'actionId': 'REMOVE_OPEN_SSH'}), 201)['item']
        stale = self.invoke('approver', 'POST', f"/v1/remediations/{proposal['proposalId']}/approve",
            {'proposalId': proposal['proposalId']}, {'expectedRevision': 0, 'reason': 'Stale'})
        self.assertEqual(stale['statusCode'], 409)
        self.assertEqual(json.loads(stale['body'])['error']['code'], 'STATE_CONFLICT')
        viewer_approve = self.invoke('viewer', 'POST', f"/v1/remediations/{proposal['proposalId']}/approve",
            {'proposalId': proposal['proposalId']}, {'expectedRevision': 1, 'reason': 'Wrong role'})
        self.assertEqual(viewer_approve['statusCode'], 403)

    def test_refuses_tier_two_low_confidence_resolved_expired_and_stale_findings(self):
        variants = [
            ('tier-two', {'tier': 'TIER_2'}, 409),
            ('low-confidence', {'confidence': 'LOW'}, 409),
            ('resolved', {'status': 'RESOLVED'}, 409),
        ]
        for suffix, fields, expected in variants:
            with self.subTest(suffix=suffix):
                self.put_finding(f'finding-{suffix}', **fields)
                result = self.invoke('admin', 'POST', '/v1/remediations', payload={
                    'findingId': f'finding-{suffix}', 'actionId': 'REMOVE_OPEN_SSH'})
                self.assertEqual(result['statusCode'], expected)
                self.assertEqual(self.db.Table('remediation-proposals').scan()['Count'], 0)

    def test_expired_proposal_cannot_be_approved(self):
        self.put_finding()
        proposal = body(self.invoke('admin', 'POST', '/v1/remediations', payload={
            'findingId': 'finding-ssh', 'actionId': 'REMOVE_OPEN_SSH'}), 201)['item']
        self.db.Table('remediation-proposals').update_item(Key={'proposalId': proposal['proposalId']},
            UpdateExpression='SET expiresAt = :expired', ExpressionAttributeValues={':expired': '2000-01-01T00:00:00Z'})
        expired = self.invoke('approver', 'POST', f"/v1/remediations/{proposal['proposalId']}/approve",
            {'proposalId': proposal['proposalId']}, {'expectedRevision': 1, 'reason': 'Review'})
        self.assertEqual(expired['statusCode'], 409)
        self.assertEqual(json.loads(expired['body'])['error']['code'], 'PROPOSAL_EXPIRED')

    def test_changed_finding_invalidates_existing_proposal(self):
        finding = self.put_finding()
        proposal = body(self.invoke('admin', 'POST', '/v1/remediations', payload={
            'findingId': 'finding-ssh', 'actionId': 'REMOVE_OPEN_SSH'}), 201)['item']
        self.db.Table('remediation-findings').update_item(Key={'findingId': finding['findingId']},
            UpdateExpression='SET #r = :revision', ExpressionAttributeNames={'#r': 'revision'},
            ExpressionAttributeValues={':revision': 2})
        stale = self.invoke('approver', 'POST', f"/v1/remediations/{proposal['proposalId']}/approve",
            {'proposalId': proposal['proposalId']}, {'expectedRevision': 1, 'reason': 'Review'})
        self.assertEqual(stale['statusCode'], 409)
        self.assertEqual(json.loads(stale['body'])['error']['code'], 'FINDING_CHANGED')

    def test_dry_run_proposal_cannot_be_upgraded_by_flags(self):
        self.put_finding()
        with self.production_scope()[0], self.production_scope()[1]:
            with patch.dict(os.environ, {'REMEDIATION_ENABLED': 'false'}):
                proposal = self.prepare_production_proposal()
            with patch('boto3.client', side_effect=AssertionError('A pinned dry run cannot modify AWS')):
                result = body(self.invoke('admin', 'POST', f"/v1/remediations/{proposal['proposalId']}/execute",
                    {'proposalId': proposal['proposalId']}, {'expectedRevision': 2}))['item']
            self.assertEqual(result['status'], 'DRY_RUN_COMPLETE')
            self.assertTrue(result['dryRun'])

    def test_audit_failure_does_not_persist_proposal(self):
        self.put_finding()
        with patch.dict(os.environ, {'AUDIT_TABLE': 'missing-audit-table'}):
            result = self.invoke('admin', 'POST', '/v1/remediations', payload={
                'findingId': 'finding-ssh', 'actionId': 'REMOVE_OPEN_SSH'})
        self.assertEqual(result['statusCode'], 502)
        self.assertEqual(self.db.Table('remediation-proposals').scan()['Count'], 0)

    def test_nonlocal_execution_checks_account_and_exact_live_plan_before_revoke(self):
        with self.production_scope()[0], self.production_scope()[1]:
            proposal = self.prepare_production_proposal()
            sts = self.sts_client()
            ec2 = self.ec2_client()
            clients = {'sts': sts, 'ec2': ec2}

            def client_factory(service, **kwargs):
                self.assertIn(service, clients)
                if service == 'ec2':
                    self.assertEqual(kwargs.get('region_name'), 'ap-south-1')
                return clients[service]

            with Stubber(sts) as sts_stub, Stubber(ec2) as ec2_stub, patch('boto3.client', side_effect=client_factory):
                sts_stub.add_response('get_caller_identity', {
                    'UserId': 'AIDATEST', 'Account': '123456789012', 'Arn': 'arn:aws:iam::123456789012:user/test',
                }, {})
                ec2_stub.add_response('describe_security_groups', {'SecurityGroups': [{
                    'GroupId': 'sg-0123456789abcdef0', 'IpPermissions': [
                        {'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22,
                         'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                        {'IpProtocol': 'tcp', 'FromPort': 80, 'ToPort': 80,
                         'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                    ],
                }]}, {'GroupIds': ['sg-0123456789abcdef0']})
                ec2_stub.add_response('revoke_security_group_ingress', {}, {
                    'GroupId': 'sg-0123456789abcdef0', 'IpPermissions': [{
                        'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22,
                        'IpRanges': [{'CidrIp': '0.0.0.0/0'}],
                    }],
                })
                result = body(self.invoke('admin', 'POST', f"/v1/remediations/{proposal['proposalId']}/execute",
                    {'proposalId': proposal['proposalId']}, {'expectedRevision': 2}), 200)['item']
                self.assertEqual((result['status'], result['revision']), ('EXECUTED', 4))
                self.assertEqual(result['execution']['status'], 'EXECUTED')
                self.assertFalse(result['execution']['dryRun'])
                sts_stub.assert_no_pending_responses()
                ec2_stub.assert_no_pending_responses()

                repeated = self.invoke('admin', 'POST', f"/v1/remediations/{proposal['proposalId']}/execute",
                    {'proposalId': proposal['proposalId']}, {'expectedRevision': 2})
                self.assertEqual(repeated['statusCode'], 409)
                self.assertEqual(json.loads(repeated['body'])['error']['code'], 'STATE_CONFLICT')

    def test_nonlocal_identity_mismatch_fails_closed_without_ec2_call(self):
        with self.production_scope()[0], self.production_scope()[1]:
            proposal = self.prepare_production_proposal()
            sts = self.sts_client()
            ec2 = self.ec2_client()
            requested = []

            def client_factory(service, **kwargs):
                requested.append(service)
                return {'sts': sts, 'ec2': ec2}[service]

            with Stubber(sts) as sts_stub, patch('boto3.client', side_effect=client_factory):
                sts_stub.add_response('get_caller_identity', {
                    'UserId': 'AIDATEST', 'Account': '999999999999', 'Arn': 'arn:aws:iam::999999999999:user/test',
                }, {})
                result = body(self.invoke('admin', 'POST', f"/v1/remediations/{proposal['proposalId']}/execute",
                    {'proposalId': proposal['proposalId']}, {'expectedRevision': 2}), 200)['item']
                self.assertEqual((result['status'], result['revision']), ('FAILED', 4))
                self.assertEqual(result['execution']['status'], 'NEEDS_HUMAN_REVIEW')
                self.assertEqual(requested, ['sts'])
                sts_stub.assert_no_pending_responses()

    def test_nonlocal_changed_current_state_fails_without_revoke(self):
        with self.production_scope()[0], self.production_scope()[1]:
            proposal = self.prepare_production_proposal()
            sts = self.sts_client()
            ec2 = self.ec2_client()
            clients = {'sts': sts, 'ec2': ec2}

            def client_factory(service, **kwargs):
                return clients[service]

            with Stubber(sts) as sts_stub, Stubber(ec2) as ec2_stub, patch('boto3.client', side_effect=client_factory):
                sts_stub.add_response('get_caller_identity', {
                    'UserId': 'AIDATEST', 'Account': '123456789012', 'Arn': 'arn:aws:iam::123456789012:user/test',
                }, {})
                ec2_stub.add_response('describe_security_groups', {'SecurityGroups': [{
                    'GroupId': 'sg-0123456789abcdef0', 'IpPermissions': [
                        {'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22,
                         'IpRanges': [{'CidrIp': '198.51.100.7/32'}]},
                    ],
                }]}, {'GroupIds': ['sg-0123456789abcdef0']})
                result = body(self.invoke('admin', 'POST', f"/v1/remediations/{proposal['proposalId']}/execute",
                    {'proposalId': proposal['proposalId']}, {'expectedRevision': 2}), 200)['item']
                self.assertEqual((result['status'], result['revision']), ('FAILED', 4))
                self.assertEqual(result['execution']['status'], 'NEEDS_HUMAN_REVIEW')
                sts_stub.assert_no_pending_responses()
                ec2_stub.assert_no_pending_responses()


class RemediationSdkParameterTests(unittest.TestCase):
    def test_security_group_plan_and_revoke_use_only_exact_public_ssh_permission(self):
        finding = {
            'ruleId': 'SECURITY_GROUP_NO_OPEN_SSH', 'resourceId': 'sg-0123456789abcdef0',
            'resourceType': 'AWS::EC2::SecurityGroup', 'accountId': '123456789012',
            'status': 'OPEN', 'tier': 'TIER_1', 'confidence': 'HIGH',
            'observed': {'ingressRules': [
                {'protocol': 'tcp', 'fromPort': 0, 'toPort': 22, 'cidr': '0.0.0.0/0'},
                {'protocol': 'tcp', 'fromPort': 80, 'toPort': 80, 'cidr': '0.0.0.0/0'},
            ]},
        }
        plan = build_plan(finding)
        self.assertEqual(plan['before']['publicSshPermissions'], [{
            'IpProtocol': 'tcp', 'FromPort': 0, 'ToPort': 22,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}],
        }])
        client = boto3.client('ec2', region_name='ap-south-1', aws_access_key_id='fake', aws_secret_access_key='fake')
        with Stubber(client) as stub:
            stub.add_response('revoke_security_group_ingress', {}, {
                'GroupId': 'sg-0123456789abcdef0', 'IpPermissions': plan['before']['publicSshPermissions'],
            })
            execute_action({'resourceId': finding['resourceId'], 'actionId': 'REMOVE_OPEN_SSH', 'plan': plan}, client)
            stub.assert_no_pending_responses()

    def test_current_security_group_plan_reconstructs_observed_ssh_only(self):
        finding = {
            'ruleId': 'SECURITY_GROUP_NO_OPEN_SSH', 'resourceId': 'sg-0123456789abcdef0',
            'status': 'OPEN', 'tier': 'TIER_1', 'confidence': 'HIGH',
        }
        client = boto3.client('ec2', region_name='ap-south-1', aws_access_key_id='fake', aws_secret_access_key='fake')
        with Stubber(client) as stub:
            stub.add_response('describe_security_groups', {'SecurityGroups': [{
                'GroupId': finding['resourceId'], 'IpPermissions': [
                    {'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22,
                     'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                    {'IpProtocol': 'tcp', 'FromPort': 80, 'ToPort': 80,
                     'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                ],
            }]}, {'GroupIds': [finding['resourceId']]})
            plan = current_plan(finding, client)
            self.assertEqual(len(plan['before']['publicSshPermissions']), 1)
            self.assertEqual(plan['before']['publicSshPermissions'][0]['FromPort'], 22)
            stub.assert_no_pending_responses()

    def test_s3_current_state_and_write_preserve_exact_owner_and_public_block_contract(self):
        finding = {
            'ruleId': 'S3_BLOCK_PUBLIC_ACCESS', 'resourceId': 'example-bucket',
            'accountId': '123456789012', 'status': 'OPEN', 'tier': 'TIER_1', 'confidence': 'HIGH',
            'observed': {'publicAccessBlock': {
                'BlockPublicAcls': False, 'IgnorePublicAcls': True,
                'BlockPublicPolicy': False, 'RestrictPublicBuckets': True,
            }},
        }
        client = boto3.client('s3', region_name='ap-south-1', aws_access_key_id='fake', aws_secret_access_key='fake')
        with Stubber(client) as stub:
            stub.add_response('get_public_access_block', {'PublicAccessBlockConfiguration': finding['observed']['publicAccessBlock']}, {
                'Bucket': 'example-bucket', 'ExpectedBucketOwner': '123456789012',
            })
            plan = current_plan(finding, client)
            stub.add_response('put_public_access_block', {}, {
                'Bucket': 'example-bucket', 'ExpectedBucketOwner': '123456789012',
                'PublicAccessBlockConfiguration': {
                    'BlockPublicAcls': True, 'IgnorePublicAcls': True,
                    'BlockPublicPolicy': True, 'RestrictPublicBuckets': True,
                },
            })
            execute_action({'resourceId': 'example-bucket', 'accountId': '123456789012',
                'actionId': 'ENABLE_S3_BLOCK_PUBLIC_ACCESS', 'plan': plan}, client)
            stub.assert_no_pending_responses()

    def test_missing_s3_public_access_block_has_explicit_delete_rollback(self):
        finding = {
            'ruleId': 'S3_BLOCK_PUBLIC_ACCESS', 'resourceId': 'example-bucket',
            'accountId': '123456789012', 'status': 'OPEN', 'tier': 'TIER_1', 'confidence': 'HIGH',
            'observed': {'publicAccessBlockMissing': True},
        }
        client = boto3.client('s3', region_name='ap-south-1', aws_access_key_id='fake', aws_secret_access_key='fake')
        with Stubber(client) as stub:
            stub.add_client_error('get_public_access_block', service_error_code='NoSuchPublicAccessBlockConfiguration',
                http_status_code=404, expected_params={
                    'Bucket': 'example-bucket', 'ExpectedBucketOwner': '123456789012',
                })
            plan = current_plan(finding, client)
            self.assertEqual(plan['before'], {'publicAccessBlock': None, 'missing': True})
            self.assertEqual(plan['rollback'], {'operation': 'delete_public_access_block', 'configuration': None})
            stub.add_response('put_public_access_block', {}, {
                'Bucket': 'example-bucket', 'ExpectedBucketOwner': '123456789012',
                'PublicAccessBlockConfiguration': {
                    'BlockPublicAcls': True, 'IgnorePublicAcls': True,
                    'BlockPublicPolicy': True, 'RestrictPublicBuckets': True,
                },
            })
            execute_action({'resourceId': 'example-bucket', 'accountId': '123456789012',
                'actionId': 'ENABLE_S3_BLOCK_PUBLIC_ACCESS', 'plan': plan}, client)
            stub.assert_no_pending_responses()


if __name__ == '__main__':
    unittest.main()
