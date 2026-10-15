"""Human-approved registry proposals with dry-run execution as the default."""
from __future__ import annotations
import os
import uuid
from datetime import datetime, timedelta, timezone
from boto3.dynamodb.conditions import Key
from botocore.exceptions import BotoCoreError, ClientError
from common.audit import audit_event, audit_put, transaction_write, request_id
from common.auth import authorize, configured_scope, AuthorizationError
from common.contracts import is_local
from common.dynamodb import dynamodb_resource
from common.http import error, response, parse_body, query_params, utc_now
from common.pagination import page_options, encode_cursor
from common.remediation import eligible_action, build_plan, fingerprint, current_plan, execute_action


class ProposalError(ValueError):
    def __init__(self, code, message, status=409):
        super().__init__(message)
        self.code, self.status = code, status


def _dry_run():
    return is_local() or os.environ.get('REMEDIATION_ENABLED', 'false').lower() != 'true' or os.environ.get('REMEDIATION_DRY_RUN', 'true').lower() != 'false'


def _finding(db, finding_id, scope):
    item = db.Table(os.environ['FINDINGS_TABLE']).get_item(Key={'findingId': finding_id}, ConsistentRead=True).get('Item')
    if not item or item.get('scopeKey') != scope:
        raise ProposalError('FINDING_NOT_FOUND', 'No finding exists in this scope.', 404)
    if item.get('revision') is None or not isinstance(item.get('evaluationId'), str):
        raise ProposalError('FINDING_REEVALUATION_REQUIRED', 'Re-evaluate this legacy finding before proposing an action.')
    return item


def _save(db, item, actor, action, event, prior=None, finding=None):
    put = {'TableName': os.environ['REMEDIATIONS_TABLE'], 'Item': item}
    if prior:
        put.update(ConditionExpression='revision = :revision AND #s = :status',
                   ExpressionAttributeNames={'#s': 'status'},
                   ExpressionAttributeValues={':revision': prior['revision'], ':status': prior['status']})
    else:
        put['ConditionExpression'] = 'attribute_not_exists(proposalId)'
    operations = [{'Put': put}]
    if finding:
        operations.append({'ConditionCheck': {'TableName': os.environ['FINDINGS_TABLE'],
            'Key': {'findingId': finding['findingId']},
            'ConditionExpression': 'revision = :revision AND evaluationId = :evaluation AND #s = :status AND scopeKey = :scope',
            'ExpressionAttributeNames': {'#s': 'status'},
            'ExpressionAttributeValues': {':revision': finding['revision'], ':evaluation': finding['evaluationId'],
                                          ':status': finding['status'], ':scope': item['scopeKey']}}})
    transaction_write(db, [*operations, audit_put(audit_event(actor, action,
        {'type': 'REMEDIATION', 'id': item['proposalId']}, request_id(event),
        {'findingId': item['findingId'], 'actionId': item['actionId'], 'status': item['status']}, scope=item['scopeKey']))])


def _validate_current(db, proposal, scope):
    if proposal['expiresAt'] <= utc_now():
        raise ProposalError('PROPOSAL_EXPIRED', 'This proposal expired; create a fresh proposal.')
    finding = _finding(db, proposal['findingId'], scope)
    if any(proposal.get(key) != finding.get(key) for key in ('resourceId', 'resourceType', 'accountId', 'region')):
        raise ProposalError('PROPOSAL_TARGET_MISMATCH', 'The proposal target differs from its finding; create a fresh proposal.')
    if fingerprint(finding) != proposal['findingHash'] or eligible_action(finding) != proposal['actionId']:
        raise ProposalError('FINDING_CHANGED', 'The finding changed; create a fresh proposal.')
    if build_plan(finding) != proposal['plan']:
        raise ProposalError('PLAN_CHANGED', 'The registry plan changed; create a fresh proposal.')
    return finding


def lambda_handler(event, context):
    method = (event.get('requestContext', {}).get('http', {}).get('method') or event.get('httpMethod', 'GET')).upper()
    path = event.get('rawPath', '')
    params = event.get('pathParameters') or {}
    pid = params.get('proposalId') or params.get('id')
    operation = 'approve' if path.endswith('/approve') else 'execute' if path.endswith('/execute') else None
    try:
        actor = authorize(event, 'viewer' if method == 'GET' else 'approver' if operation == 'approve' else 'admin')
        scope = configured_scope()
        db = dynamodb_resource()
        table = db.Table(os.environ['REMEDIATIONS_TABLE'])
        if method == 'GET':
            if pid:
                item = table.get_item(Key={'proposalId': pid}, ConsistentRead=True).get('Item')
                if not item or item.get('scopeKey') != scope:
                    raise ProposalError('PROPOSAL_NOT_FOUND', 'No proposal exists in this scope.', 404)
                return response(200, {'item': item})
            query = query_params(event)
            options = page_options(query, scope, 'remediations', {})
            page = table.query(IndexName='scope-created', KeyConditionExpression=Key('scopeKey').eq(scope), ScanIndexForward=False, **options)
            return response(200, {'items': page.get('Items', []), 'count': len(page.get('Items', [])),
                                  'nextToken': encode_cursor(page.get('LastEvaluatedKey'), scope, 'remediations', {})})
        if method != 'POST':
            return error(405, 'METHOD_NOT_ALLOWED', 'Use GET or POST for this workflow.')
        body = parse_body(event)
        if not pid:
            if set(body) != {'findingId', 'actionId'} or not isinstance(body['findingId'], str) or len(body['findingId']) > 200:
                raise ProposalError('INVALID_REQUEST', 'findingId and actionId are required.', 400)
            finding = _finding(db, body['findingId'], scope)
            if eligible_action(finding) != body['actionId'] or not eligible_action(finding):
                raise ProposalError('ACTION_NOT_ELIGIBLE', 'This finding is not eligible for that registry action.')
            now = utc_now()
            pid = str(uuid.uuid4())
            item = {'proposalId': pid, 'findingId': finding['findingId'], 'findingHash': fingerprint(finding),
                    'actionId': body['actionId'], 'status': 'PROPOSED', 'revision': 1, 'dryRun': _dry_run(),
                    'createdAt': now, 'updatedAt': now, 'createdOrder': now + '#' + pid,
                    'expiresAt': (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat().replace('+00:00', 'Z'),
                    'createdBy': actor, 'scopeKey': scope, 'accountId': finding['accountId'], 'region': finding['region'],
                    'resourceId': finding['resourceId'], 'resourceType': finding['resourceType'],
                    'plan': build_plan(finding), 'approvalRequired': True}
            _save(db, item, actor, 'REMEDIATION_PROPOSED', event)
            return response(201, {'item': item})
        item = table.get_item(Key={'proposalId': pid}, ConsistentRead=True).get('Item')
        if not item or item.get('scopeKey') != scope:
            raise ProposalError('PROPOSAL_NOT_FOUND', 'No proposal exists in this scope.', 404)
        allowed_keys = {'expectedRevision', 'reason'} if operation == 'approve' else {'expectedRevision'}
        revision = body.get('expectedRevision')
        if set(body) - allowed_keys or isinstance(revision, bool) or not isinstance(revision, int):
            raise ProposalError('INVALID_REQUEST', 'A numeric expectedRevision and only the documented fields are accepted.', 400)
        if revision != item['revision']:
            raise ProposalError('STATE_CONFLICT', 'The proposal changed; refresh it.')
        finding = _validate_current(db, item, scope)
        if operation == 'approve':
            reason = body.get('reason')
            if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 1000:
                raise ProposalError('APPROVAL_REASON_REQUIRED', 'Human approval requires a reason of 1-1000 characters.', 400)
            if item['status'] != 'PROPOSED':
                raise ProposalError('STATE_CONFLICT', 'Only a proposed action can be approved.')
            approved = {**item, 'status': 'APPROVED', 'revision': revision + 1, 'approvedBy': actor,
                        'approvedAt': utc_now(), 'updatedAt': utc_now(), 'reason': reason.strip()}
            _save(db, approved, actor, 'REMEDIATION_APPROVED', event, item, finding)
            return response(200, {'item': approved})
        if operation != 'execute' or item['status'] != 'APPROVED' or not item.get('approvedBy'):
            raise ProposalError('APPROVAL_REQUIRED', 'Explicit human approval is required before execution.')
        # Local execution is always simulated, irrespective of environment flags.
        dry_run = item.get('dryRun', True) or _dry_run()
        executing = {**item, 'status': 'EXECUTING', 'revision': revision + 1, 'updatedAt': utc_now(), 'dryRun': dry_run}
        # Claim before any SDK action; concurrent requests cannot execute twice.
        _save(db, executing, actor, 'REMEDIATION_EXECUTION_STARTED', event, item, finding)
        try:
            if not dry_run:
                import boto3
                from botocore.config import Config
                config = Config(connect_timeout=2, read_timeout=5, retries={'total_max_attempts': 1, 'mode': 'standard'})
                identity = boto3.client('sts', config=config).get_caller_identity()
                if identity.get('Account') != item['accountId']:
                    raise ValueError('Execution identity differs from proposal account.')
                service = 'ec2' if item['actionId'] == 'REMOVE_OPEN_SSH' else 's3'
                client = boto3.client(service, region_name=item['region'], config=config)
                if current_plan(finding, client) != item['plan']:
                    raise ValueError('AWS state changed after proposal approval.')
                execute_action(item, client)
            final_status = 'DRY_RUN_COMPLETE' if dry_run else 'EXECUTED'
            execution = {'dryRun': dry_run, 'status': final_status, 'completedAt': utc_now()}
        except Exception:
            # A timeout may mean the API applied the change. Never retry automatically.
            final_status = 'FAILED'
            execution = {'dryRun': dry_run, 'status': 'NEEDS_HUMAN_REVIEW', 'completedAt': utc_now(),
                         'message': 'Execution could not be confirmed. Inspect current state before any new action.'}
        final = {**executing, 'status': final_status, 'revision': revision + 2, 'updatedAt': utc_now(), 'execution': execution}
        _save(db, final, actor, 'REMEDIATION_' + final_status, {**event, 'requestContext': {**event.get('requestContext', {}), 'requestId': request_id(event) + ':complete'}}, executing)
        return response(200, {'item': final})
    except AuthorizationError as exc:
        return error(exc.status, exc.code, str(exc))
    except ProposalError as exc:
        return error(exc.status, exc.code, str(exc))
    except (ValueError, TypeError, KeyError) as exc:
        return error(400, 'INVALID_REMEDIATION_REQUEST', str(exc))
    except (ClientError, BotoCoreError) as exc:
        if isinstance(exc, ClientError) and exc.response['Error']['Code'] in {'TransactionCanceledException', 'ConditionalCheckFailedException'}:
            return error(409, 'STATE_CONFLICT', 'The proposal changed during this operation; refresh it.')
        return error(502, 'REMEDIATION_STORAGE_FAILED', 'Could not persist this workflow and its audit event.')
