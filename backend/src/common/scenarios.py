"""Fictional, deterministic local observations. These are never live AWS evidence."""
from copy import deepcopy

SCENARIOS = {'benign', 'open-ssh', 'lambda-db-bypass', 'unruled-crossing', 'source-disagreement'}
TIME = '2026-10-15T00:00:00Z'


def scenario_manifest():
    return {
        'schemaVersion': 2, 'name': 'Local three-tier intent', 'description': 'Simulated topology for local development',
        'components': [
            {'id': name, 'resourceTypes': [kind], 'selector': {'resourceIds': [rid]}, 'minMatches': 1}
            for name, rid, kind in [
                ('web', 'i-fixture-web', 'AWS::EC2::Instance'),
                ('api', 'i-fixture-api', 'AWS::EC2::Instance'),
                ('worker', 'fixture-worker', 'AWS::Lambda::Function'),
                ('db', 'fixture-db', 'AWS::RDS::DBInstance')]],
        'relationships': [
            {'id': 'web-api', 'from': 'web', 'to': 'api', 'effect': 'ALLOW',
             'relationshipType': 'NETWORK_REACHABILITY', 'protocol': 'tcp', 'ports': [443], 'required': True},
            {'id': 'api-db', 'from': 'api', 'to': 'db', 'effect': 'ALLOW',
             'relationshipType': 'NETWORK_REACHABILITY', 'protocol': 'tcp', 'ports': [5432], 'required': True}],
        'trustBoundaries': [
            {'id': 'edge', 'members': ['web'], 'crossingRules': [
                {'id': 'web-service', 'to': 'services', 'effect': 'ALLOW', 'via': ['api']}]},
            {'id': 'services', 'members': ['api', 'worker'], 'crossingRules': [
                {'id': 'service-data', 'to': 'data', 'effect': 'ALLOW', 'via': ['api']}]},
            {'id': 'data', 'members': ['db'], 'crossingRules': []}],
        'criticality': {'db': 'CRITICAL', 'api': 'HIGH', 'web': 'MEDIUM', 'worker': 'MEDIUM'},
        'constraints': [
            {'id': 'ssh', 'type': 'SECURITY_GROUP_NO_OPEN_SSH', 'severity': 'HIGH'},
            {'id': 'no-direct-worker-db', 'type': 'FORBIDDEN_PATH', 'from': 'worker', 'to': 'db',
             'pathMode': 'DIRECT', 'edgeTypes': ['NETWORK_REACHABILITY'], 'severity': 'HIGH'},
            {'id': 'worker-via-api', 'type': 'REQUIRED_INTERMEDIARY', 'from': 'worker', 'to': 'db',
             'via': ['api'], 'edgeTypes': ['NETWORK_REACHABILITY'], 'severity': 'HIGH'}],
    }


def scenario_inventory(name='benign'):
    if name not in SCENARIOS:
        raise ValueError('Unknown bundled local fixture scenario.')
    kinds = [('i-fixture-web', 'AWS::EC2::Instance'), ('i-fixture-api', 'AWS::EC2::Instance'),
             ('fixture-worker', 'AWS::Lambda::Function'), ('fixture-db', 'AWS::RDS::DBInstance'),
             ('sg-fixture', 'AWS::EC2::SecurityGroup')]
    items = [{'resourceId': rid, 'resourceType': kind, 'name': rid, 'accountId': 'fixture-account',
              'region': 'ap-south-1', 'tags': {}, 'relationships': [], 'attributes': {},
              'source': 'Bundled simulated inventory', 'lastObservedAt': TIME} for rid, kind in kinds]
    items[0]['attributes'] = {'publicIpAddress': None}
    items[1]['attributes'] = {'publicIpAddress': None}
    items[3]['attributes'] = {'publiclyAccessible': False}
    items[4]['attributes'] = {'ingressRules': []}
    if name == 'open-ssh':
        items[4]['attributes']['ingressRules'] = [
            {'protocol': 'tcp', 'fromPort': 22, 'toPort': 22, 'cidr': '0.0.0.0/0'}]
    pairs = [('i-fixture-web', 'i-fixture-api'), ('i-fixture-api', 'fixture-db'),
             ('fixture-worker', 'i-fixture-api')]
    if name == 'lambda-db-bypass':
        pairs.append(('fixture-worker', 'fixture-db'))
    if name in {'unruled-crossing', 'source-disagreement'}:
        pairs.append(('fixture-db', 'i-fixture-web'))
    edges = [{'sourceId': source, 'targetId': target, 'type': 'NETWORK_REACHABILITY',
              'status': 'OBSERVED', 'observationKind': 'OBSERVED', 'protocol': 'tcp',
              'ports': [5432 if target == 'fixture-db' else 443],
              'evidence': [{'source': 'SIMULATED_FLOW_LOGS', 'observedAt': TIME,
                            'details': {'simulated': True, 'sourceId': source, 'targetId': target}}]}
             for source, target in pairs]
    return deepcopy({'items': items, 'edges': edges, 'meta': {
        'accountId': 'fixture-account', 'region': 'ap-south-1', 'collectedAt': TIME,
        'totalResources': len(items), 'partial': False, 'warnings': [], 'simulated': True,
        'snapshotId': 'fixture-' + name, 'scenario': name,
        'coverage': {'resourceTypes': {kind: 'COMPLETE' for _, kind in kinds},
                     'relationshipTypes': {'NETWORK_REACHABILITY': 'COMPLETE'}},
        'sourceVerdicts': [{'sourceFamily': 'inventory', 'verdict': 'CORROBORATES'},
                           {'sourceFamily': 'flowLogs', 'verdict': 'DISAGREES' if name == 'source-disagreement' else 'CORROBORATES'}],
    }})
