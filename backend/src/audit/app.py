"""Read-only audit history. No client can create an arbitrary event."""
import os

from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import BotoCoreError, ClientError
from common.auth import authorize, configured_scope, AuthorizationError
from common.dynamodb import dynamodb_resource
from common.http import response, error, query_params
from common.pagination import page_options, encode_cursor


def lambda_handler(event, context):
    try:
        authorize(event)
        scope = configured_scope()
        params = query_params(event)
        filters = {key: params[key] for key in ('action', 'from', 'to') if params.get(key)}
        options = page_options(params, scope, 'audit', filters)
        condition = Key('scopeKey').eq(scope)
        if filters.get('from') and filters.get('to'):
            condition &= Key('eventOrder').between(filters['from'], filters['to'] + '\uffff')
        elif filters.get('from'):
            condition &= Key('eventOrder').gte(filters['from'])
        elif filters.get('to'):
            condition &= Key('eventOrder').lte(filters['to'] + '\uffff')
        options.update(IndexName='scope-time', KeyConditionExpression=condition, ScanIndexForward=False)
        if filters.get('action'):
            options['FilterExpression'] = Attr('action').eq(filters['action'])
        page = dynamodb_resource().Table(os.environ['AUDIT_TABLE']).query(**options)
        rows = page.get('Items', [])
        return response(200, {'items': rows, 'count': len(rows), 'limit': options['Limit'],
            'nextToken': encode_cursor(page.get('LastEvaluatedKey'), scope, 'audit', filters)})
    except AuthorizationError as exc:
        return error(exc.status, exc.code, str(exc))
    except ValueError as exc:
        return error(400, 'INVALID_AUDIT_QUERY', str(exc))
    except (ClientError, BotoCoreError) as exc:
        return error(502, 'AUDIT_READ_FAILED', 'Could not read audit events.', type(exc).__name__)
