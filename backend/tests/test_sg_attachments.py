"""Real SDK shapes for bounded, read-only SG attachment impact."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import boto3
from botocore.stub import Stubber
from common.sg_attachments import collect_attachments, SOURCES
from common.attribute_rules import attribute_outcome
from common.remediation import build_plan

SG='sg-0123456789abcdef0'
class AttachmentTests(unittest.TestCase):
    def collect(self, client, coverage=None):
        class Session:
            def client(self, *args, **kwargs): return client
        nodes={SG:{'resourceId':SG,'resourceType':'AWS::EC2::SecurityGroup','attributes':{'ingressRules':[{'protocol':'tcp','fromPort':22,'toPort':22,'cidr':'0.0.0.0/0'}]},'lastObservedAt':'now'},
               'i-instance':{'resourceId':'i-instance','resourceType':'AWS::EC2::Instance','source':'EC2 DescribeInstances'}}
        edges=[{'sourceId':'i-instance','targetId':SG,'type':'USES_SECURITY_GROUP'}]
        warnings=[]
        collect_attachments(Session(),nodes,edges,warnings,coverage or {kind:'COMPLETE' for kind in (*SOURCES,'AWS::EC2::SecurityGroup')},'ap-south-1','123456789012','now')
        return nodes,warnings
    def client(self):
        return boto3.client('ec2',region_name='ap-south-1',aws_access_key_id='local',aws_secret_access_key='local')
    def test_attachment_records_flow_through_finding_and_proposal_without_reachability_claim(self):
        client=self.client()
        with Stubber(client) as stub:
            stub.add_response('describe_network_interfaces',{'NetworkInterfaces':[{'NetworkInterfaceId':'eni-123','OwnerId':'123456789012','Groups':[{'GroupId':SG}],'Attachment':{'InstanceId':'i-instance'}}]}, {'Filters':[{'Name':'group-id','Values':[SG]}]})
            nodes,warnings=self.collect(client)
            stub.assert_no_pending_responses()
        self.assertFalse(warnings)
        impact=nodes[SG]['attributes']['attachmentImpact']
        self.assertEqual(impact['coverage'],'COMPLETE')
        self.assertEqual(impact['attachmentCount'],2)  # interface and known workload are distinct contributing records
        outcome,observed,_=attribute_outcome({'type':'SECURITY_GROUP_NO_OPEN_SSH'},nodes[SG])
        self.assertEqual(outcome,'VIOLATION')
        plan=build_plan({'ruleId':'SECURITY_GROUP_NO_OPEN_SSH','tier':'TIER_1','confidence':'HIGH','status':'OPEN','observed':observed})
        self.assertEqual(plan['attachmentImpact'],{**impact,'observedAt':'now'})
        self.assertTrue(plan['attachmentImpact']['requiresHumanApproval'])
    def test_denied_or_unsupported_source_never_claims_zero(self):
        client=self.client()
        with Stubber(client) as stub:
            stub.add_client_error('describe_network_interfaces',service_error_code='UnauthorizedOperation',expected_params={'Filters':[{'Name':'group-id','Values':[SG]}]})
            nodes,warnings=self.collect(client)
        impact=nodes[SG]['attributes']['attachmentImpact']
        self.assertEqual(impact['coverage'],'PARTIAL');self.assertIsNone(impact['attachmentCount'])
        self.assertEqual(impact['knownAttachmentCount'],1)
        self.assertEqual(warnings[0]['code'],'UnauthorizedOperation')
        with Stubber(client) as stub:
            stub.add_response('describe_network_interfaces',{'NetworkInterfaces':[]},{'Filters':[{'Name':'group-id','Values':[SG]}]})
            nodes,_=self.collect(client,{kind:'UNSUPPORTED' for kind in SOURCES})
        self.assertIsNone(nodes[SG]['attributes']['attachmentImpact']['attachmentCount'])
    def test_row_cap_is_partial(self):
        client=self.client()
        with Stubber(client) as stub,patch('common.sg_attachments.MAX_ATTACHMENTS',1):
            stub.add_response('describe_network_interfaces',{'NetworkInterfaces':[{'NetworkInterfaceId':'eni-123','OwnerId':'123456789012','Groups':[{'GroupId':SG}]}]}, {'Filters':[{'Name':'group-id','Values':[SG]}]})
            nodes,warnings=self.collect(client)
        self.assertTrue(any(w['code']=='ATTACHMENT_CAP' for w in warnings))
        self.assertIsNone(nodes[SG]['attributes']['attachmentImpact']['attachmentCount'])
    def test_paginated_read_and_unverified_owner_are_conservative(self):
        client=self.client()
        expected={'Filters':[{'Name':'group-id','Values':[SG]}]}
        with Stubber(client) as stub:
            stub.add_response('describe_network_interfaces',{'NetworkInterfaces':[],'NextToken':'next'},expected)
            stub.add_response('describe_network_interfaces',{'NetworkInterfaces':[{'NetworkInterfaceId':'eni-other','OwnerId':'999999999999','Groups':[{'GroupId':SG}]}]}, {**expected,'NextToken':'next'})
            nodes,warnings=self.collect(client)
            stub.assert_no_pending_responses()
        self.assertEqual(nodes[SG]['attributes']['attachmentImpact']['coverage'],'PARTIAL')
        self.assertEqual(warnings[0]['code'],'UNVERIFIED_INTERFACE_SCOPE')

    def test_deadline_stops_before_request_and_group_coverage_blocks_complete(self):
        client=self.client()
        with Stubber(client),patch('common.sg_attachments.DEADLINE_SECONDS',0):
            nodes,warnings=self.collect(client)
        self.assertIsNone(nodes[SG]['attributes']['attachmentImpact']['attachmentCount'])
        self.assertEqual(warnings[0]['code'],'DEADLINE')
        with Stubber(client) as stub:
            stub.add_response('describe_network_interfaces',{'NetworkInterfaces':[]},{'Filters':[{'Name':'group-id','Values':[SG]}]})
            coverage={kind:'COMPLETE' for kind in SOURCES};coverage['AWS::EC2::SecurityGroup']='PARTIAL'
            nodes,_=self.collect(client,coverage)
        self.assertIsNone(nodes[SG]['attributes']['attachmentImpact']['attachmentCount'])

    def test_no_groups_makes_no_aws_calls(self):
        collect_attachments(None,{},[],[],{},'region','account','now')
