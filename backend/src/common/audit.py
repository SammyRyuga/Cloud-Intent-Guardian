"""Append-only application audit events, transacted with state mutations."""
import hashlib
import json
import os
import uuid

from common.auth import configured_scope
from common.http import utc_now


def audit_event(actor, action, target, requestId=None, metadata=None, scope=None):
    timestamp = utc_now()
    correlation = requestId or str(uuid.uuid4())
    identity = f'{correlation}|{action}|{json.dumps(target, sort_keys=True, default=str)}'
    audit_id = hashlib.sha256(identity.encode()).hexdigest()[:32]
    return {'auditId': audit_id, 'timestamp': timestamp, 'actor': {'sub': actor['sub'], 'displayName': actor.get('displayName', actor['sub'])},
            'action': action, 'target': target, 'result': 'SUCCESS', 'requestId': correlation,
            'scopeKey': scope or configured_scope(), 'eventOrder': timestamp + '#' + audit_id,
            'metadata': metadata or {}}


def transaction_write(db, operations):
    """DynamoDB resource client recursively marshals native transaction values."""
    return db.meta.client.transact_write_items(TransactItems=operations)


def audit_put(event):
    return {'Put': {'TableName': os.environ['AUDIT_TABLE'], 'Item': event,
                    'ConditionExpression': 'attribute_not_exists(auditId)'}}


def request_id(event):
    return event.get('requestContext', {}).get('requestId') or str(uuid.uuid4())
