"""Bounded attachment impact, not traffic or end-to-end reachability evidence."""
import time
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

MAX_ATTACHMENTS = 250
MAX_PAGES = 5
DEADLINE_SECONDS = 4
ENI = 'AWS::EC2::NetworkInterface'
SOURCES = ('AWS::EC2::Instance', 'AWS::RDS::DBInstance', 'AWS::Lambda::Function')


def collect_attachments(session, nodes, edges, warnings, coverage, region, account_id, observed_at):
    groups = sorted(rid for rid, row in nodes.items() if row.get('resourceType') == 'AWS::EC2::SecurityGroup')
    if not groups:
        return 'COMPLETE' if coverage.get('AWS::EC2::SecurityGroup') == 'COMPLETE' else 'PARTIAL'
    state = 'COMPLETE'
    source_coverage = {kind: coverage.get(kind, 'UNSUPPORTED') for kind in (*SOURCES, 'AWS::EC2::SecurityGroup')}
    attachments = {rid: {} for rid in groups}
    for edge in edges:
        source, target = edge.get('sourceId'), edge.get('targetId')
        if edge.get('type') == 'USES_SECURITY_GROUP' and target in attachments and source in nodes:
            attachments[target][source] = {'resourceId': source, 'resourceType': nodes[source]['resourceType'], 'source': nodes[source].get('source')}
    def warn(code):
        nonlocal state
        state = 'PARTIAL'
        warnings.append({'source': 'ec2:sg-attachments', 'code': code, 'message': 'Attachment impact is a lower bound; unobserved attachments remain unknown.'})
    if len(groups) > 100:
        warn('GROUP_CAP')
    deadline = time.monotonic() + DEADLINE_SECONDS
    count = 0
    try:
        client = session.client('ec2', config=Config(connect_timeout=1, read_timeout=2, retries={'total_max_attempts': 1}))
        pages = iter(client.get_paginator('describe_network_interfaces').paginate(Filters=[{'Name': 'group-id', 'Values': groups[:100]}]))
        for page_index in range(MAX_PAGES):
            if time.monotonic() >= deadline:
                warn('DEADLINE')
                break
            try:
                page = next(pages)
            except StopIteration:
                break
            for eni in page.get('NetworkInterfaces', []):
                if count >= MAX_ATTACHMENTS:
                    warn('ATTACHMENT_CAP')
                    break
                count += 1
                rid = eni.get('NetworkInterfaceId')
                if not rid or eni.get('OwnerId') != account_id:
                    warn('UNVERIFIED_INTERFACE_SCOPE')
                    continue
                rels = []
                attrs = {'interfaceType': eni.get('InterfaceType'), 'status': eni.get('Status'),
                         'vpcId': eni.get('VpcId'), 'subnetId': eni.get('SubnetId'),
                         'instanceId': eni.get('Attachment', {}).get('InstanceId')}
                for group in eni.get('Groups', []):
                    gid = group.get('GroupId')
                    if gid not in attachments:
                        continue
                    attachments[gid][rid] = {'resourceId': rid, 'resourceType': ENI, 'source': 'EC2 DescribeNetworkInterfaces', **attrs}
            if count >= MAX_ATTACHMENTS:
                warn("ATTACHMENT_CAP")
                break
            if not page.get('NextToken'):
                break
        else:
            warn('PAGE_CAP')
    except (BotoCoreError, ClientError) as exc:
        warn(exc.response.get('Error', {}).get('Code', 'AWS_ERROR') if isinstance(exc, ClientError) else type(exc).__name__)
    # ENIs are a scoped contributing set, not a complete account resource inventory.
    source_coverage[ENI] = state
    complete = state == 'COMPLETE' and all(value == 'COMPLETE' for value in source_coverage.values())
    if state == 'COMPLETE' and not complete:
        warn('SOURCE_COVERAGE_INCOMPLETE')
    for gid in groups:
        rows = [attachments[gid][rid] for rid in sorted(attachments[gid])]
        nodes[gid]['attributes']['attachmentImpact'] = {
            'coverage': 'COMPLETE' if complete else 'PARTIAL', 'sourceCoverage': source_coverage,
            'knownAttachmentCount': len(rows), 'attachmentCount': len(rows) if complete else None,
            'attachments': rows, 'observedAt': observed_at, 'requiresHumanApproval': True,
            'interpretation': 'Configuration attachment records potentially affected by an SG change. An ENI and its workload may both appear; this is not a unique workload count, traffic, outage, or reachability proof.'}
    return 'COMPLETE' if complete else 'PARTIAL'
