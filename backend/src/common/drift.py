"""Factual changes between complete, version-bound immutable observations."""
import hashlib
import json
import os
from boto3.dynamodb.conditions import Attr
from common.http import _json_default
from common.evaluation_jobs import JobError


def enabled():
    return os.environ.get('DRIFT_HISTORY_ENABLED', 'false').lower() == 'true'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), default=_json_default)


def complete(inventory, evaluation):
    coverage = inventory.get('meta', {}).get('coverage', {})
    resources = coverage.get('resourceTypes', {})
    return (evaluation.get('status') == 'SUCCEEDED' and not inventory.get('meta', {}).get('partial')
            and not evaluation.get('summary', {}).get('inventoryPartial')
            and bool(resources) and all(state in {'COMPLETE', 'UNSUPPORTED'} for state in resources.values())
            and any(state == 'COMPLETE' for state in resources.values()))


def factual(row):
    # Collection-time evidence is retained in the immutable source artifact, not
    # compared as configuration. Unknown fields are deliberately not copied.
    return {key: row[key] for key in ('id', 'resourceId', 'resourceType', 'type', 'name', 'region', 'accountId', 'properties',
            'attributes', 'tags', 'sourceId', 'targetId', 'relationship', 'edgeType', 'observationKind', 'status') if key in row}


def changes(before, after, job, timestamp, previous_id):
    if before.get('meta', {}).get('coverage') != after.get('meta', {}).get('coverage'):
        return []  # coverage changes establish a new baseline, never deletions
    rows = []
    for kind, collection in [('RESOURCE', 'items'), ('EDGE', 'edges')]:
        if kind == 'EDGE' and (not after.get('meta', {}).get('coverage', {}).get('relationshipTypes') or any(state not in {'COMPLETE', 'UNSUPPORTED'} for state in after.get('meta', {}).get('coverage', {}).get('relationshipTypes', {}).values())):
            continue
        def identity(row):
            return row.get('resourceId') or row.get('id') or (canonical([row.get('sourceId'), row.get('targetId'), row.get('type')]) if kind == 'EDGE' else None)
        old = {identity(r): factual(r) for r in before.get(collection, []) if identity(r)}
        new = {identity(r): factual(r) for r in after.get(collection, []) if identity(r)}
        for identity in sorted(old.keys() | new.keys()):
            if old.get(identity) == new.get(identity):
                continue
            event_type = 'CREATED' if identity not in old else 'DELETED' if identity not in new else 'MODIFIED'
            event_id = hashlib.sha256(f"{job['scopeKey']}|{job['evaluationId']}|{kind}|{identity}".encode()).hexdigest()
            row = {'id': event_id, 'scopeKey': job['scopeKey'], 'eventOrder': timestamp + '#' + event_id,
                   'timestamp': timestamp, 'resourceId': identity, 'resourceType': (new.get(identity) or old[identity]).get('resourceType', (new.get(identity) or old[identity]).get('type', kind)),
                   'entityKind': kind, 'eventType': event_type, 'diffSummary': f'{kind.title()} {event_type.lower()} between complete observations',
                   'evaluationId': job['evaluationId'], 'previousEvaluationId': previous_id,
                   'intentId': job['intentId'], 'intentVersion': job['intentVersion'], 'simulated': bool(after.get('simulated'))}
            if identity in old:
                row['previousState'] = old[identity]
            if identity in new:
                row['currentState'] = new[identity]
            if len(canonical(row).encode()) > 240000:
                raise JobError(413, 'DRIFT_EVENT_TOO_LARGE', 'A drift event exceeds its safe persistence limit.')
            rows.append(row)
    return rows


def stage(db, job, evaluation, inventory, load_artifacts):
    if not enabled() or not complete(inventory, evaluation):
        return None
    intent = db.Table(os.environ['INTENTS_TABLE']).get_item(Key={'intentId': job['intentId']}, ConsistentRead=True).get('Item') or {}
    prior = intent.get('driftBaseline') or {}
    rows = []
    if prior.get('intentVersion') == job['intentVersion'] and prior.get('scopeKey') == job['scopeKey']:
        artifact = load_artifacts(db, os.environ['EVALUATION_ARTIFACTS_TABLE'], prior['evaluationId'])
        if not artifact or not complete(artifact[1], artifact[0]):
            raise JobError(409, 'DRIFT_BASELINE_UNAVAILABLE', 'The complete drift baseline artifact is unavailable.')
        rows = changes(artifact[1], inventory, job, evaluation['finishedAt'], prior['evaluationId'])
    if len(rows) > 2000:
        raise JobError(413, 'DRIFT_EVENT_LIMIT', 'The snapshot exceeds the bounded drift event limit.')
    table = db.Table(os.environ['DRIFT_EVENTS_TABLE'])
    for row in rows:
        try:
            table.put_item(Item=row, ConditionExpression=Attr('id').not_exists())
        except table.meta.client.exceptions.ConditionalCheckFailedException:
            existing = table.get_item(Key={'id': row['id']}, ConsistentRead=True).get('Item')
            if existing != row:
                raise JobError(409, 'DRIFT_EVENT_CONFLICT', 'A retry produced conflicting drift evidence.')
    evaluation.setdefault('summary', {})['driftEventCount'] = len(rows)
    return {'evaluationId': job['evaluationId'], 'intentVersion': job['intentVersion'], 'scopeKey': job['scopeKey']}
