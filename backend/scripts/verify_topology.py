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
from common.http import _json_default
from local_db import TABLES


def decoded(result, expected=200):
    if result['statusCode'] != expected:
        raise RuntimeError(f'Expected {expected}: {result}')
    return json.loads(result['body'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', default='http://127.0.0.1:18000')
    parser.add_argument('--evidence', default='local-evidence/phase1-topology.json')
    parser.add_argument('--escalation', action='store_true', help='Use the deterministic local LLM mock and simulated corroboration.')
    args = parser.parse_args()
    os.environ.update(LLM_ENABLED='true' if args.escalation else 'false', LLM_PROVIDER='mock')
    os.environ.update(CIG_LOCAL='true', DYNAMODB_ENDPOINT_URL=args.endpoint, AWS_REGION='ap-south-1',
        INVENTORY_PROVIDER='fixture', CIG_FIXTURE_SCENARIO='benign')
    for key, (default, _) in TABLES.items():
        os.environ.setdefault(key, default)
    db = dynamodb_resource()  # Validates the local-only endpoint before network access.
    intents, approve, evaluation, graph = [importlib.import_module(name + '.app')
        for name in ('intents', 'approve_intent', 'evaluations', 'resources')]
    created = decoded(intents.lambda_handler({'requestContext': {'http': {'method': 'POST'}},
        'body': json.dumps(scenario_manifest())}, None), 201)['item']
    key = {'intentId': created['intentId']}
    decoded(approve.lambda_handler({'pathParameters': key}, None))
    assert db.Table(os.environ['INTENTS_TABLE']).get_item(Key=key, ConsistentRead=True)['Item']['status'] == 'APPROVED'
    results = {}
    worker = importlib.import_module('evaluation_worker.app')
    # A provider regression must fail loudly, never read a live account.
    with patch.object(worker, 'collect_inventory', side_effect=AssertionError('Live collector must not run')):
        for name in ['benign', 'open-ssh', 'lambda-db-bypass', 'unruled-crossing', 'source-disagreement']:
            os.environ['CIG_FIXTURE_SCENARIO'] = name
            queued = decoded(evaluation.lambda_handler({'body': json.dumps(key)}, None), 202)
            worker_result = worker._process(db, queued['evaluation']['evaluationId'])
            assert worker_result['result'] in {'SUCCEEDED', 'PARTIAL'}, worker_result
            job_id = queued['evaluation']['evaluationId']
            detail = decoded(evaluation.lambda_handler({'requestContext': {'http': {'method': 'GET'}},
                'pathParameters': {'id': job_id}}, None))
            rows = [row for row in db.Table(os.environ['FINDINGS_TABLE']).scan()['Items'] if row.get('evaluationId') == job_id and row.get('status') != 'RESOLVED']
            result = {'evaluation': detail['item'], 'findings': rows}
            stored = db.Table(os.environ['EVALUATIONS_TABLE']).get_item(
                Key={'evaluationId': job_id}, ConsistentRead=True)['Item']
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
                if args.escalation:
                    candidates = [f for f in rows if f.get('tier') == 'TIER_2']
                    assert candidates, rows
                    expected = 'NEEDS_HUMAN_REVIEW' if name == 'source-disagreement' else 'CORROBORATED'
                    assert all(f['reviewStatus'] == expected and not f['actionEligible'] for f in candidates)
                    if name == 'source-disagreement':
                        assert all(f['confidence'] == 'LOW' for f in candidates)
            results[name] = {'evaluationId': stored['evaluationId'], 'status': stored['status'],
                             'findingTypes': sorted({row['ruleId'] for row in result['findings']})}
    with patch.object(graph, 'collect_inventory', side_effect=AssertionError('Live collector must not run')):
        for view in ['INTENT', 'ACTUAL', 'DIFF']:
            value = decoded(graph.lambda_handler({'rawPath': '/v1/architecture/graph',
                'queryStringParameters': {'view': view, **key}}, None))
            ids = {node['id'] for node in value['nodes']}
            assert all(edge['source'] in ids and edge['target'] in ids for edge in value['edges'])
    versions = importlib.import_module('versions.app')
    root = db.Table(os.environ['INTENTS_TABLE']).get_item(Key=key, ConsistentRead=True)['Item']
    snapshot = db.Table(os.environ['INTENT_VERSIONS_TABLE']).get_item(Key={**key, 'version': 1}, ConsistentRead=True)['Item']
    changed = scenario_manifest(); changed['description'] = 'Second local approved revision'
    draft = decoded(versions.lambda_handler({'rawPath': '/v1/intents/x/versions',
        'requestContext': {'http': {'method': 'POST'}}, 'pathParameters': key,
        'body': json.dumps({'manifest': changed, 'expectedRevision': int(root['revision'])})}, None), 201)['item']
    root = db.Table(os.environ['INTENTS_TABLE']).get_item(Key=key, ConsistentRead=True)['Item']
    activated = decoded(versions.lambda_handler({'rawPath': '/v1/intents/x/versions/2/approve',
        'requestContext': {'http': {'method': 'POST'}}, 'pathParameters': {**key, 'version': str(draft['version'])},
        'body': json.dumps({'expectedRevision': int(root['revision'])})}, None))['item']
    rolled = decoded(versions.lambda_handler({'rawPath': '/v1/intents/x/rollback',
        'requestContext': {'http': {'method': 'POST'}}, 'pathParameters': key,
        'body': json.dumps({'targetVersion': 1, 'expectedRevision': int(activated['revision']), 'reason': 'Local rollback verification'})}, None))['item']
    assert rolled['activeVersion'] == 1 and rolled['latestVersion'] == 2
    assert db.Table(os.environ['INTENT_VERSIONS_TABLE']).get_item(Key={**key, 'version': 1}, ConsistentRead=True)['Item'] == snapshot
    audit = importlib.import_module('audit.app')
    page = decoded(audit.lambda_handler({'queryStringParameters': {'limit': '100'}}, None))
    assert any(row['target'].get('id') == created['intentId'] for row in page['items'])
    evidence = {'scope': 'DynamoDB Local + direct async Lambda handlers/worker, not API Gateway/Cognito',
                'intentId': created['intentId'], 'simulated': True, 'scenarios': results, 'versioningPassed': True, 'auditPassed': True, 'passed': True}
    destination = Path(args.evidence)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(evidence, indent=2, default=_json_default) + '\n')
    print(json.dumps(evidence))


if __name__ == '__main__':
    main()
