"""Bind advisory topology candidates to exact version-pinned snapshot facts."""
import os
from common.drift import enabled, complete, changes, canonical
from common.topology import STRUCTURAL_TYPES


def prepare_history(db, job, evaluation, inventory, load_artifacts):
    context = {'status': 'UNKNOWN', 'reason': 'HISTORY_DISABLED', 'previousEvaluationId': None, 'events': []}
    if not enabled():
        return context
    if not complete(inventory, evaluation):
        return {**context, 'reason': 'CURRENT_SNAPSHOT_INCOMPLETE'}
    try:
        intent = db.Table(os.environ['INTENTS_TABLE']).get_item(Key={'intentId': job['intentId']}, ConsistentRead=True).get('Item') or {}
        prior = intent.get('driftBaseline') or {}
        drift_prior = dict(prior)
        latest = intent.get('latestEvaluationId')
        if latest:
            published = db.Table(os.environ['EVALUATIONS_TABLE']).get_item(Key={'evaluationId': latest}, ConsistentRead=True).get('Item') or {}
            if published.get('intentId') == job['intentId'] and published.get('intentVersion') == job['intentVersion'] and published.get('scopeKey') == job['scopeKey'] and published.get('status') in {'SUCCEEDED', 'PARTIAL'}:
                prior = {'evaluationId': latest, 'intentVersion': job['intentVersion'], 'scopeKey': job['scopeKey']}
        if not prior:
            return {**context, 'status': 'FIRST_OBSERVATION', 'reason': 'NO_PREVIOUS_COMPLETE_SAME_VERSION_SNAPSHOT'}
        if prior.get('intentVersion') != job['intentVersion'] or prior.get('scopeKey') != job['scopeKey']:
            return {**context, 'status': 'FIRST_OBSERVATION', 'reason': 'NO_PREVIOUS_COMPLETE_SAME_VERSION_SNAPSHOT'}
        previous_id = prior.get('evaluationId')
        artifact = load_artifacts(db, os.environ['EVALUATION_ARTIFACTS_TABLE'], previous_id)
        context['previousEvaluationId'] = previous_id
        if not artifact or not complete(artifact[1], artifact[0]):
            return {**context, 'reason': 'PREVIOUS_ARTIFACT_INCOMPLETE'}
        previous_eval, previous = artifact[:2]
        if previous_eval.get('intentId') != job['intentId'] or previous_eval.get('intentVersion') != job['intentVersion']:
            return {**context, 'reason': 'PREVIOUS_ARTIFACT_PIN_MISMATCH'}
        if previous.get('meta', {}).get('accountId') != inventory.get('meta', {}).get('accountId') or previous.get('meta', {}).get('region') != inventory.get('meta', {}).get('region'):
            return {**context, 'reason': 'PREVIOUS_ARTIFACT_SCOPE_MISMATCH'}
        if previous.get('meta', {}).get('coverage') != inventory.get('meta', {}).get('coverage'):
            return {**context, 'reason': 'COVERAGE_CHANGED'}
        return {**context, 'status': 'COMPARABLE', 'reason': 'COMPLETE_SAME_INTENT_VERSION_SNAPSHOTS', 'previous': previous,
                'events': changes(previous, inventory, job, evaluation.get('finishedAt', ''), previous_id) if (drift_prior.get('evaluationId') == previous_id and drift_prior.get('intentVersion') == job['intentVersion']
                    and drift_prior.get('scopeKey') == job['scopeKey'] and complete(previous, previous_eval) and complete(inventory, evaluation)) else []}
    except Exception:
        # Missing/denied/corrupt history never converts advisory evidence into NEW.
        return {**context, 'reason': 'HISTORY_UNAVAILABLE'}


def candidate_history(candidate, inventory, context=None):
    context = context or {}
    result = {'status': context.get('status', 'UNKNOWN'), 'reason': context.get('reason', 'HISTORY_NOT_COLLECTED'),
              'previousEvaluationId': context.get('previousEvaluationId'), 'driftEventIds': [],
              'comparisonScope': 'SAME_INTENT_VERSION', 'isHistoricalChange': False}
    if result['status'] != 'COMPARABLE':
        return result
    path = candidate.get('pathEdges') or []
    if not path:
        return {**result, 'status': 'UNKNOWN', 'reason': 'EXACT_PATH_NOT_RETAINED'}
    previous = context['previous']
    def identity(row):
        return (row.get('sourceId'), row.get('targetId'), row.get('type'),
                canonical({key: row.get(key) for key in ('protocol', 'ports', 'observationKind')}))
    identities = {identity(r) for r in previous.get('edges', [])}
    current = {identity(r) for r in inventory.get('edges', [])}
    exact = []
    for row in path:
        edge_id = identity(row)
        if not all(edge_id[:3]) or edge_id not in current:
            return {**result, 'status': 'UNKNOWN', 'reason': 'EXACT_PATH_UNVERIFIED'}
        typ = edge_id[2]
        for snapshot in (previous, inventory):
            states = snapshot.get('meta', {}).get('coverage', {}).get('relationshipTypes', {})
            family = 'STRUCTURAL' if typ in STRUCTURAL_TYPES else typ
            if states.get(typ, states.get(family)) != 'COMPLETE':
                return {**result, 'status': 'UNKNOWN', 'reason': 'PATH_COVERAGE_INCOMPLETE'}
        exact.append(edge_id)
    missing = [identity for identity in exact if identity not in identities]
    if not missing:
        return {**result, 'status': 'PREVIOUSLY_OBSERVED', 'reason': 'EXACT_PATH_PRESENT_IN_PREVIOUS_COMPLETE_SNAPSHOT'}
    # Only actual exact edge creation/modification records may link to a candidate.
    linked = []
    for event in context.get('events', []):
        row = event.get('currentState') or {}
        if event.get('entityKind') == 'EDGE' and event.get('eventType') in {'CREATED', 'MODIFIED'} and identity(row) in missing:
            linked.append(event['id'])
    return {**result, 'status': 'NEW', 'reason': 'EXACT_PATH_EDGES_ABSENT_FROM_PREVIOUS_COMPLETE_SNAPSHOT',
            'driftEventIds': sorted(linked), 'isHistoricalChange': True}
