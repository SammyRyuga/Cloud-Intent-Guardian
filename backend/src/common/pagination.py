"""Opaque cursors bound to the endpoint, account scope, and filters."""
import base64
import json


def encode_cursor(key, scope, kind, filters):
    if not key:
        return None
    return base64.urlsafe_b64encode(json.dumps({'key': key, 'scope': scope, 'kind': kind, 'filters': filters},
        separators=(',', ':'), default=str).encode()).decode().rstrip('=')


def page_options(params, scope, kind, filters):
    try:
        limit = int(params.get('limit', '25'))
        if not 1 <= limit <= 100:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError('limit must be an integer between 1 and 100.')
    result = {'Limit': limit}
    token = params.get('nextToken')
    if token:
        try:
            if not isinstance(token, str) or len(token) > 8192:
                raise ValueError()
            decoded = json.loads(base64.urlsafe_b64decode(token + '=' * (-len(token) % 4)))
            if (decoded['scope'] != scope or decoded['kind'] != kind or decoded['filters'] != filters
                    or not isinstance(decoded['key'], dict) or not decoded['key']):
                raise ValueError()
            result['ExclusiveStartKey'] = decoded['key']
        except (ValueError, KeyError, TypeError, UnicodeError):
            raise ValueError('The nextToken cursor is invalid or belongs to different filters.')
    return result
