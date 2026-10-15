"""Authorize verified API Gateway group claims; local fixtures use synthetic actors."""
import json
import os
from functools import wraps

from common.contracts import is_local

LEVELS = {'viewer': 0, 'approver': 1, 'admin': 2}


class AuthorizationError(ValueError):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code = status, code


def authorize(event, required='viewer'):
    claims = event.get('requestContext', {}).get('authorizer', {}).get('jwt', {}).get('claims', {})
    if is_local() and os.environ.get('INVENTORY_PROVIDER') == 'fixture' and not claims:
        role = os.environ.get('CIG_LOCAL_ROLE', 'admin')
        claims = {'sub': 'local-fixture-actor', 'name': 'Local fixture actor', 'cognito:groups': [role]}
    if not isinstance(claims, dict) or not isinstance(claims.get('sub'), str) or not claims['sub']:
        raise AuthorizationError(401, 'UNAUTHENTICATED', 'A verified user identity is required.')
    groups = claims.get('cognito:groups', [])
    if isinstance(groups, str):
        # HTTP API fixtures and Cognito serializers may supply JSON, bracketed,
        # or comma-separated groups. Exact allowlisted group names only.
        try:
            groups = json.loads(groups)
        except (ValueError, TypeError):
            groups = [part.strip() for part in groups.strip('[]').split(',')]
    if not isinstance(groups, list) or not all(isinstance(group, str) for group in groups):
        raise AuthorizationError(403, 'FORBIDDEN', 'No recognized application role is assigned.')
    roles = [group for group in groups if group in LEVELS]
    role = max(roles, key=LEVELS.get) if roles else None
    if role is None or LEVELS[role] < LEVELS[required]:
        raise AuthorizationError(403, 'FORBIDDEN', 'You do not have permission to perform this action.')
    return {'sub': claims['sub'], 'displayName': claims.get('name') or claims.get('email') or claims['sub'], 'role': role}


def configured_scope():
    region = os.environ.get('AWS_REGION', 'ap-south-1')
    account = 'fixture-account' if is_local() else os.environ.get('CIG_ACCOUNT_ID')
    if not account:
        raise AuthorizationError(409, 'ACCOUNT_SCOPE_NOT_CONFIGURED', 'Configure the account scope before using this workflow.')
    return f"{account}#{region}#{os.environ.get('STAGE_NAME', 'dev')}"


def require_role(required='viewer'):
    def decorate(handler):
        @wraps(handler)
        def checked(event, context):
            try:
                authorize(event, required)
            except AuthorizationError as exc:
                from common.http import error
                return error(exc.status, exc.code, str(exc))
            return handler(event, context)
        return checked
    return decorate
