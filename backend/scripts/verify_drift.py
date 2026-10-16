"""Verify drift with eight DynamoDB Local tables and simulated direct handlers.

No AWS services or cloud configuration are changed. Safe configuration changes
are made only to copied observation fixtures. Run local_db.py init first.
"""
import argparse
from copy import deepcopy
import importlib
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from common.dynamodb import dynamodb_resource
from common.http import _json_default
from common.scenarios import scenario_inventory, scenario_manifest
from local_db import TABLES, check_tables
from verify_topology import decoded


def verify(db):
    intents, approve, evaluations, drift, versions = [importlib.import_module(name + '.app')
        for name in ('intents', 'approve_intent', 'evaluations', 'drift_events', 'versions')]
    worker = importlib.import_module('evaluation_worker.app')
    created = decoded(intents.lambda_handler({'requestContext': {'http': {'method': 'POST'}},
        'body': json.dumps(scenario_manifest())}, None), 201)['item']
    key = {'intentId': created['intentId']}
    decoded(approve.lambda_handler({'pathParameters': key}, None))
    evidence = {'intentId': key['intentId'], 'snapshots': {}, 'checks': []}
    original = scenario_inventory()
    original['meta']['coverage']['relationshipTypes']['TAGS'] = 'PARTIAL'
    changed = deepcopy(original)
    # Two safe changes to actual observation data, without changing intent.
    changed['items'][0]['tags']['local-verification'] = 'changed'
    changed['edges'][0]['ports'] = [8443]
    def run(name, inventory, retry=False):
        queued = decoded(evaluations.lambda_handler({'body': json.dumps(key)}, None), 202)['evaluation']
        ident = queued['evaluationId']
        with patch.object(worker, 'observations', return_value=deepcopy(inventory)), patch.object(worker, 'collect_inventory', side_effect=AssertionError('AWS collector forbidden')):
            if retry:
                real_publish = worker._publish_terminal
                def interrupt(*args, **kwargs):
                    raise RuntimeError('Injected failure after staging before publication')
                with patch.object(worker, '_publish_terminal', side_effect=interrupt):
                    try:
                        worker._process(db, ident)
                    except RuntimeError:
                        pass
                    else:
                        raise AssertionError('Retry injection did not execute')
                assert not listing(), 'Unpublished staged events must stay hidden'
                first = [row for row in db.Table(os.environ['DRIFT_EVENTS_TABLE']).scan()['Items'] if row.get('evaluationId') == ident]
                assert len(first) == 2
                with patch.object(worker, '_publish_terminal', real_publish):
                    result = worker._process(db, ident)
                assert first == [row for row in db.Table(os.environ['DRIFT_EVENTS_TABLE']).scan()['Items'] if row.get('evaluationId') == ident]
            else:
                result = worker._process(db, ident)
        assert result['result'] in {'SUCCEEDED', 'PARTIAL'}, result
        assert worker._process(db, ident)['result'] == 'SKIPPED'
        evidence['snapshots'][name] = {'evaluationId': ident, 'result': result['result'], 'inventory': inventory}
        return ident
    def listing():
        rows, cursor, seen = [], None, set()
        while True:
            params = {'limit': '1', 'intentId': key['intentId']}
            if cursor:
                params['nextToken'] = cursor
            page = decoded(drift.lambda_handler({'queryStringParameters': params}, None))
            rows.extend(page['items'])
            cursor = page['meta']['nextCursor']
            if not cursor:
                return rows
            assert cursor not in seen
            seen.add(cursor)
    first = run('baseline', original)
    assert listing() == []
    second = run('changed', changed, retry=True)
    rows = listing()
    assert len(rows) == 2 and all(row['simulated'] for row in rows)
    edge = next(row for row in rows if row['entityKind'] == 'EDGE')
    assert edge['previousState']['ports'] == [443] and edge['currentState']['ports'] == [8443]
    assert all(row['previousEvaluationId'] == first and row['evaluationId'] == second for row in rows)
    for row in rows:
        assert decoded(drift.lambda_handler({'pathParameters': {'id': row['id']}}, None))['item'] == row
    partial = deepcopy(changed)
    partial['items'] = []
    partial['edges'] = []
    partial['meta']['partial'] = True
    partial['meta']['coverage']['resourceTypes'] = {kind: 'PARTIAL' for kind in partial['meta']['coverage']['resourceTypes']}
    run('partial-empty', partial)
    root = db.Table(os.environ['INTENTS_TABLE']).get_item(Key=key, ConsistentRead=True)['Item']
    assert root['driftBaseline']['evaluationId'] == second
    assert listing() == rows
    manifest = scenario_manifest(); manifest['description'] = 'New local approved intent version'
    decoded(versions.lambda_handler({'rawPath': '/v1/intents/x/versions', 'requestContext': {'http': {'method': 'POST'}},
        'pathParameters': key, 'body': json.dumps({'manifest': manifest, 'expectedRevision': int(root['revision'])})}, None), 201)
    root = db.Table(os.environ['INTENTS_TABLE']).get_item(Key=key, ConsistentRead=True)['Item']
    decoded(versions.lambda_handler({'rawPath': '/v1/intents/x/versions/2/approve', 'requestContext': {'http': {'method': 'POST'}},
        'pathParameters': {**key, 'version': '2'}, 'body': json.dumps({'expectedRevision': int(root['revision'])})}, None))
    versioned = run('version-two-baseline', original)
    root = db.Table(os.environ['INTENTS_TABLE']).get_item(Key=key, ConsistentRead=True)['Item']
    assert int(root['driftBaseline']['intentVersion']) == 2 and root['driftBaseline']['evaluationId'] == versioned
    assert listing() == rows
    evidence.update(passed=True, simulated=True, events=rows,
        checks=['first baseline has no events', 'copied observation configuration changes', 'unpublished staging hidden',
                'interrupted worker retry idempotent', 'one-item cursor pagination', 'detail equals list',
                'partial empty inventory cannot delete or replace baseline', 'new approved version establishes fresh baseline'],
        scope='Eight DynamoDB Local tables and direct Lambda handlers/worker; no API Gateway or Cognito')
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', default='http://127.0.0.1:18000')
    parser.add_argument('--evidence', default='local-evidence/drift-verification.json')
    args = parser.parse_args()
    os.environ.update(CIG_LOCAL='true', DYNAMODB_ENDPOINT_URL=args.endpoint, AWS_REGION='ap-south-1',
        INVENTORY_PROVIDER='fixture', CIG_FIXTURE_SCENARIO='benign', DRIFT_HISTORY_ENABLED='true', LLM_ENABLED='false')
    for key, (default, _) in TABLES.items():
        os.environ.setdefault(key, default)
    db = dynamodb_resource()
    check_tables(db, False)
    evidence = verify(db)
    output = Path(args.evidence); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, default=_json_default) + '\n')
    print(json.dumps({'passed': True, 'evidence': str(output)}))


if __name__ == '__main__':
    main()
