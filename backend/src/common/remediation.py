"""Closed registry of reversible, pre-written actions. No model-selected commands."""
from __future__ import annotations
import hashlib
import json
from common.http import _json_default

ACTIONS = {'SECURITY_GROUP_NO_OPEN_SSH': 'REMOVE_OPEN_SSH', 'S3_BLOCK_PUBLIC_ACCESS': 'ENABLE_S3_BLOCK_PUBLIC_ACCESS'}
PAB_KEYS = ('BlockPublicAcls', 'IgnorePublicAcls', 'BlockPublicPolicy', 'RestrictPublicBuckets')


def eligible_action(finding):
    if (finding.get('tier') == 'TIER_2' or finding.get('reviewStatus') == 'NEEDS_HUMAN_REVIEW'
            or finding.get('confidence') not in {'HIGH', 'MEDIUM'} or finding.get('status') not in {'OPEN', 'ACKNOWLEDGED'}):
        return None
    return ACTIONS.get(finding.get('ruleId'))


def fingerprint(finding):
    keys = ('findingId', 'evaluationId', 'intentId', 'intentVersion', 'resourceId', 'resourceType',
            'accountId', 'region', 'scopeKey', 'ruleId', 'status', 'revision', 'observed', 'confidence')
    return hashlib.sha256(json.dumps({k: finding.get(k) for k in keys}, sort_keys=True,
                                     default=_json_default).encode()).hexdigest()


def ssh_permissions(rules):
    permissions = []
    for rule in rules:
        protocol = str(rule.get('protocol', ''))
        first, last = rule.get('fromPort'), rule.get('toPort')
        cidr = rule.get('cidr')
        if cidr not in {'0.0.0.0/0', '::/0'}:
            continue
        if protocol != '-1' and not (protocol in {'tcp', '6'} and first is not None and last is not None and first <= 22 <= last):
            continue
        permission = {'IpProtocol': protocol}
        if protocol != '-1':
            permission.update(FromPort=int(first), ToPort=int(last))
        permission['Ipv6Ranges' if ':' in cidr else 'IpRanges'] = [{'CidrIpv6' if ':' in cidr else 'CidrIp': cidr}]
        if permission not in permissions:
            permissions.append(permission)
    return sorted(permissions, key=lambda item: json.dumps(item, sort_keys=True))


def build_plan(finding):
    action = eligible_action(finding)
    if not action:
        raise ValueError('This finding cannot produce an executable registry proposal.')
    observed = finding.get('observed') or {}
    if action == 'REMOVE_OPEN_SSH':
        rules = observed.get('matchingIngressRules', observed.get('ingressRules'))
        if not isinstance(rules, list):
            raise ValueError('Exact ingress rules are required.')
        permissions = ssh_permissions(rules)
        if not permissions:
            raise ValueError('No exact public SSH ingress permission was evidenced.')
        return {'description': 'Revoke only the evidenced public CIDR ingress permissions that include SSH.',
                'before': {'publicSshPermissions': permissions}, 'after': {'publicSshPermissions': []},
                'rollback': {'operation': 'authorize_security_group_ingress', 'permissions': permissions},
                'impact': 'May affect every resource attached to this group. Attachment coverage is unknown; approval is mandatory.'}
    config = observed.get('publicAccessBlock')
    # Inventory's normalized fields are preserved in the finding; do not invent unknown prior state.
    missing = observed.get('publicAccessBlockMissing') is True
    if not missing and (not isinstance(config, dict) or not all(isinstance(config.get(key), bool) for key in PAB_KEYS)):
        raise ValueError('All four prior bucket public-access-block settings are required.')
    return {'description': 'Enable all four bucket public access block controls.',
            'before': {'publicAccessBlock': None if missing else {key: config[key] for key in PAB_KEYS}, 'missing': missing},
            'after': {'publicAccessBlock': {key: True for key in PAB_KEYS}},
            'rollback': {'operation': 'delete_public_access_block' if missing else 'put_public_access_block', 'configuration': None if missing else {key: config[key] for key in PAB_KEYS}},
            'impact': 'Public bucket workflows may stop working; approval is mandatory.'}


def current_plan(finding, client):
    """Read current AWS state using a supplied SDK client; used only by explicit execution."""
    current = dict(finding)
    rid = finding['resourceId']
    if eligible_action(finding) == 'REMOVE_OPEN_SSH':
        response = client.describe_security_groups(GroupIds=[rid])
        groups = response.get('SecurityGroups', [])
        if len(groups) != 1 or groups[0].get('GroupId') != rid:
            raise ValueError('Security-group state is unavailable.')
        rules = []
        for permission in groups[0].get('IpPermissions', []):
            for key, cidr_key in (('IpRanges', 'CidrIp'), ('Ipv6Ranges', 'CidrIpv6')):
                for entry in permission.get(key, []):
                    rules.append({'protocol': permission['IpProtocol'], 'fromPort': permission.get('FromPort'),
                                  'toPort': permission.get('ToPort'), 'cidr': entry.get(cidr_key)})
        current['observed'] = {'ingressRules': rules}
    else:
        from botocore.exceptions import ClientError
        try:
            response = client.get_public_access_block(Bucket=rid, ExpectedBucketOwner=finding['accountId'])
            current['observed'] = {'publicAccessBlock': response['PublicAccessBlockConfiguration']}
        except ClientError as exc:
            if exc.response['Error']['Code'] not in {'NoSuchPublicAccessBlockConfiguration', 'NoSuchConfiguration'}:
                raise
            current['observed'] = {'publicAccessBlockMissing': True}
    return build_plan(current)


def execute_action(proposal, client):
    """Only fixed SDK methods and persisted, validated registry parameters are used."""
    rid, plan = proposal['resourceId'], proposal['plan']
    if proposal['actionId'] == 'REMOVE_OPEN_SSH':
        permissions = []
        for stored in plan['before']['publicSshPermissions']:
            permission = dict(stored)
            for key in ('FromPort', 'ToPort'):
                if key in permission:
                    permission[key] = int(permission[key])
            permissions.append(permission)
        client.revoke_security_group_ingress(GroupId=rid, IpPermissions=permissions)
    elif proposal['actionId'] == 'ENABLE_S3_BLOCK_PUBLIC_ACCESS':
        client.put_public_access_block(Bucket=rid, ExpectedBucketOwner=proposal['accountId'],
                                      PublicAccessBlockConfiguration=plan['after']['publicAccessBlock'])
    else:
        raise ValueError('Action is not registered.')
