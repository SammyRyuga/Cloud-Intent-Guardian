"""Shared local test setup for the application's declared table schemas."""
import json
from common.http import _json_default
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from local_db import TABLES, table_schema


def authed(request=None, role='admin'):
    request = dict(request or {})
    context = dict(request.get('requestContext', {}))
    context['authorizer'] = {'jwt': {'claims': {'sub': 'contract-user', 'cognito:groups': [role]}}}
    request['requestContext'] = context
    return request


def create_tables(db):
    for env_key, (default, _) in TABLES.items():
        os.environ.setdefault(env_key, 'contract-' + default.removeprefix('cloud-intent-guardian-dev-'))
        db.create_table(TableName=os.environ[env_key], BillingMode='PAY_PER_REQUEST', **table_schema(env_key))


def finish(db, queued):
    from evaluation_worker.app import _process
    result = _process(db, queued['evaluation']['evaluationId'])
    if result['result'] not in {'SUCCEEDED', 'PARTIAL'}:
        raise AssertionError(result)
    job = db.Table(os.environ['EVALUATIONS_TABLE']).get_item(
        Key={'evaluationId': queued['evaluation']['evaluationId']}, ConsistentRead=True)['Item']
    findings = [row for row in db.Table(os.environ['FINDINGS_TABLE']).scan()['Items']
                if row.get('evaluationId') == job['evaluationId']]
    # Compatibility wrapper used only by assertions for completed deterministic results.
    return {'evaluation': job, 'findings': json.loads(json.dumps(findings, default=_json_default)), 'inventory': {}}
