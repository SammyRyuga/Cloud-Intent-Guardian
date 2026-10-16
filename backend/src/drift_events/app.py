"""Read-only, scoped, paginated snapshot change history."""
import os
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import BotoCoreError, ClientError
from common.auth import require_role, configured_scope, AuthorizationError
from common.drift import enabled
from common.dynamodb import dynamodb_resource
from common.http import response, error, query_params
from common.pagination import page_options, encode_cursor


def published(db, row, scope):
    job = db.Table(os.environ['EVALUATIONS_TABLE']).get_item(Key={'evaluationId': row['evaluationId']}, ConsistentRead=True).get('Item') or {}
    return row.get('scopeKey') == scope and job.get('scopeKey') == scope and job.get('status') == 'SUCCEEDED'


@require_role('viewer')
def lambda_handler(event, context):
    if not enabled():
        return error(409, 'DRIFT_HISTORY_DISABLED', 'Snapshot drift history is not enabled.')
    try:
        scope = configured_scope()
        db = dynamodb_resource()
        table = db.Table(os.environ['DRIFT_EVENTS_TABLE'])
        identity = (event.get('pathParameters') or {}).get('id')
        if identity:
            row = table.get_item(Key={'id': identity}, ConsistentRead=True).get('Item')
            if not row or not published(db, row, scope):
                return error(404, 'DRIFT_EVENT_NOT_FOUND', 'No published drift event exists with that ID.')
            return response(200, {'item': row})
        params = query_params(event)
        filters = {key: params[key] for key in ('intentId', 'eventType') if params.get(key)}
        if filters.get('eventType') and filters['eventType'] not in {'CREATED', 'MODIFIED', 'DELETED'}:
            raise ValueError('eventType must be CREATED, MODIFIED, or DELETED.')
        options = page_options(params, scope, 'drift', filters)
        options.update(IndexName='scope-time', KeyConditionExpression=Key('scopeKey').eq(scope), ScanIndexForward=False)
        for key, value in filters.items():
            condition = Attr(key).eq(value)
            options['FilterExpression'] = options['FilterExpression'] & condition if options.get('FilterExpression') else condition
        page = table.query(**options)
        rows = [row for row in page.get('Items', []) if published(db, row, scope)]
        return response(200, {'items': rows, 'meta': {'nextCursor': encode_cursor(page.get('LastEvaluatedKey'), scope, 'drift', filters)}})
    except AuthorizationError as exc:
        return error(exc.status, exc.code, str(exc))
    except ValueError as exc:
        return error(400, 'INVALID_DRIFT_QUERY', str(exc))
    except (ClientError, BotoCoreError) as exc:
        return error(502, 'DRIFT_READ_FAILED', 'Could not read snapshot drift history.', type(exc).__name__)
