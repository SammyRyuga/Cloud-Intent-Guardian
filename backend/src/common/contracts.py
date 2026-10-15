"""Additive presentation fields; persisted resource and finding IDs stay unchanged."""
from common.http import utc_now


def is_local():
    import os
    return any(os.environ.get(key, '').lower() == 'true' for key in ('AWS_SAM_LOCAL', 'CIG_LOCAL'))


def finding_view(item):
    from common.remediation import eligible_action, build_plan
    action = eligible_action(item) if item.get('revision') is not None and item.get('evaluationId') else None
    if action:
        try:
            build_plan(item)
        except (ValueError, TypeError, KeyError):
            action = None
    return {**item, 'remediationAvailable': bool(action), **({'remediationActionId': action} if action else {})}


def scan_all(table, max_pages=20, **options):
    items = []
    for _ in range(max_pages):
        page = table.scan(**options)
        items.extend(page.get('Items', []))
        key = page.get('LastEvaluatedKey')
        if not key:
            return items, False
        options['ExclusiveStartKey'] = key
    return items, True


def local_status(region, stage):
    now = utc_now()
    return {'status': 'LOCAL', 'accountId': None, 'region': region, 'stage': stage,
            'checkedAt': now, 'backendReachable': True, 'awsSourcesConnected': False,
            'evaluatedRegion': region, 'lastSyncAt': now, 'version': '0.2.0',
            'sources': {'awsIdentity': {'status': 'DISABLED_LOCAL'},
                        'awsConfig': {'status': 'DISABLED_LOCAL'},
                        'liveInventory': {'status': 'DISABLED_LOCAL'}},
            'warnings': [{'source': 'local', 'message': 'Local API mode uses DynamoDB Local. AWS discovery and Cognito are not verified.'}]}
