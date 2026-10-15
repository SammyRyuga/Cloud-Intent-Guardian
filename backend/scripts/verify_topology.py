"""Run the Phase 1 handlers against DynamoDB Local and bundled simulated graphs."""
import argparse
import importlib
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from common.dynamodb import dynamodb_resource
from common.scenarios import scenario_manifest


def decoded(result, expected=200):
    if result['statusCode'] != expected:
        raise RuntimeError(f'Expected {expected}: {result}')
    return json.loads(result['body'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', default='http://127.0.0.1:18000')
    parser.add_argument('--evidence', default='local-evidence/phase1-topology.json')
    args = parser.parse_args()
    os.environ.update(CIG_LOCAL='true', DYNAMODB_ENDPOINT_URL=args.endpoint, AWS_REGION='ap-south-1',
        INVENTORY_PROVIDER='fixture', CIG_FIXTURE_SCENARIO='benign')
    for key, suffix in [('INTENTS_TABLE', 'intents'), ('FINDINGS_TABLE', 'findings'), ('EVALUATIONS_TABLE', 'evaluations')]:
        os.environ.setdefault(key, 'cloud-intent-guardian-dev-' + suffix)
    db = dynamodb_resource()  # Validates the local-only endpoint before network access.
    intents, approve, evaluation, graph = [importlib.import_module(name + '.app')
        for name in ('intents', 'approve_intent', 'evaluations', 'resources')]
    created = decoded(intents.lambda_handler({'requestContext': {'http': {'method': 'POST'}},
        'body': json.dumps(scenario_manifest())}, None), 201)['item']
    key = {'intentId': created['intentId']}
    decoded(approve.lambda_handler({'pathParameters': key}, None))
    assert db.Table(os.environ['INTENTS_TABLE']).get_item(Key=key, ConsistentRead=True)['Item']['status'] == 'APPROVED'
    results = {}
    # A provider regression must fail loudly, never read a live account.
    with patch.object(evaluation, 'collect_inventory', side_effect=AssertionError('Live collector must not run')):
        for name in ['benign', 'open-ssh', 'lambda-db-bypass', 'unruled-crossing', 'source-disagreement']:
            os.environ['CIG_FIXTURE_SCENARIO'] = name
            result = decoded(evaluation.lambda_handler({'body': json.dumps(key)}, None))
            stored = db.Table(os.environ['EVALUATIONS_TABLE']).get_item(
                Key={'evaluationId': result['evaluation']['evaluationId']}, ConsistentRead=True)['Item']
            assert stored['status'] == result['evaluation']['status']
            if name == 'benign':
                assert not result['findings'], result
            if name == 'open-ssh':
                assert any(row['ruleId'] == 'SECURITY_GROUP_NO_OPEN_SSH' for row in result['findings'])
            if name == 'lambda-db-bypass':
                assert any(row['ruleId'] == 'REQUIRED_INTERMEDIARY' and row['severity'] == 'HIGH' for row in result['findings'])
            if name in {'unruled-crossing', 'source-disagreement'}:
                assert stored['status'] == 'PARTIAL'
                assert stored['conformance']['percent'] is None
            results[name] = {'evaluationId': stored['evaluationId'], 'status': stored['status'],
                             'findingTypes': sorted({row['ruleId'] for row in result['findings']})}
    with patch.object(graph, 'collect_inventory', side_effect=AssertionError('Live collector must not run')):
        for view in ['INTENT', 'ACTUAL', 'DIFF']:
            value = decoded(graph.lambda_handler({'rawPath': '/v1/architecture/graph',
                'queryStringParameters': {'view': view, **key}}, None))
            ids = {node['id'] for node in value['nodes']}
            assert all(edge['source'] in ids and edge['target'] in ids for edge in value['edges'])
    evidence = {'scope': 'DynamoDB Local + direct Lambda handler calls, not API Gateway/Cognito',
                'intentId': created['intentId'], 'simulated': True, 'scenarios': results, 'passed': True}
    destination = Path(args.evidence)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence))


if __name__ == '__main__':
    main()
