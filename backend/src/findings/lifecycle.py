"""Human lifecycle transitions; evaluation remains the authority for resolution."""
import os

from boto3.dynamodb.conditions import Attr
from botocore.exceptions import BotoCoreError, ClientError
from common.auth import authorize, AuthorizationError, configured_scope
from common.audit import audit_event, audit_put, transaction_write, request_id
from common.dynamodb import dynamodb_resource
from common.http import parse_body, response, error, utc_now
from common.contracts import finding_view


def transition(event, context):
    try:
        actor = authorize(event, 'approver')
        body = parse_body(event)
        action = body.get('action')
        revision = body.get('expectedRevision')
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
            return error(400, 'INVALID_REVISION', 'expectedRevision must be a non-negative integer.')
        reason = body.get('reason', '')
        if not isinstance(reason, str) or len(reason) > 1000:
            return error(400, 'INVALID_REASON', 'reason must be a string of at most 1000 characters.')
        reason = reason.strip()
        targets = {'ACKNOWLEDGE': ('ACKNOWLEDGED', {'OPEN'}),
                   'SUPPRESS': ('SUPPRESSED', {'OPEN', 'ACKNOWLEDGED'}),
                   'REOPEN': ('OPEN', {'ACKNOWLEDGED', 'SUPPRESSED'})}
        if action not in targets:
            return error(400, 'INVALID_FINDING_ACTION', 'action must be ACKNOWLEDGE, SUPPRESS or REOPEN.')
        if action == 'SUPPRESS' and not reason:
            return error(400, 'SUPPRESSION_REASON_REQUIRED', 'Suppression requires a reason.')
        finding_id = (event.get('pathParameters') or {}).get('findingId')
        if not finding_id:
            return error(400, 'MISSING_FINDING_ID', 'findingId is required.')
        db = dynamodb_resource()
        item = db.Table(os.environ['FINDINGS_TABLE']).get_item(Key={'findingId': finding_id}, ConsistentRead=True).get('Item')
        if not item:
            return error(404, 'FINDING_NOT_FOUND', 'No finding exists with that ID.')
        scope = configured_scope()
        expected_scope = f"{item.get('accountId')}#{item.get('region')}#{os.environ.get('STAGE_NAME', 'dev')}"
        if item.get('scopeKey', expected_scope) != scope:
            return error(404, 'FINDING_NOT_FOUND', 'No finding exists in the configured account scope.')
        status, allowed = targets[action]
        if item.get('status') not in allowed or int(item.get('revision', 0)) != revision:
            return error(409, 'STATE_CONFLICT', 'The finding changed or this transition is not available.')
        now = utc_now()
        updated = {**item, 'status': status, 'revision': revision + 1, 'updatedAt': now}
        if action == 'SUPPRESS':
            updated.update(suppressionReason=reason, suppressedAt=now, suppressedBy=actor['sub'])
        if action == 'ACKNOWLEDGE':
            updated.update(acknowledgedAt=now, acknowledgedBy=actor['sub'])
        condition = '(attribute_not_exists(revision) OR revision = :revision) AND #status = :status'
        transaction_write(db, [{'Put': {'TableName': os.environ['FINDINGS_TABLE'], 'Item': updated,
            'ConditionExpression': condition, 'ExpressionAttributeNames': {'#status': 'status'},
            'ExpressionAttributeValues': {':revision': revision, ':status': item['status']}}},
            audit_put(audit_event(actor, 'FINDING_' + {'ACKNOWLEDGE': 'ACKNOWLEDGED', 'SUPPRESS': 'SUPPRESSED', 'REOPEN': 'REOPENED'}[action],
                {'type': 'FINDING', 'id': finding_id}, request_id(event), {'reason': reason, 'previousStatus': item['status']}))])
        return response(200, {'item': finding_view(updated)})
    except AuthorizationError as exc:
        return error(exc.status, exc.code, str(exc))
    except (ValueError, TypeError) as exc:
        return error(400, 'INVALID_FINDING_REQUEST', str(exc))
    except (ClientError, BotoCoreError) as exc:
        if isinstance(exc, ClientError) and exc.response['Error']['Code'] == 'TransactionCanceledException':
            return error(409, 'STATE_CONFLICT', 'The finding changed during this operation; refresh it.')
        return error(502, 'FINDING_UPDATE_FAILED', 'Could not persist finding status and audit event.', type(exc).__name__)
