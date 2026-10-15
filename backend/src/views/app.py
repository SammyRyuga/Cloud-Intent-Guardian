from common.auth import require_role, configured_scope
"""Dashboard and finding detail use stored evidence; no fabricated history."""
import os
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import BotoCoreError, ClientError
from common.dynamodb import dynamodb_resource
from common.contracts import finding_view, scan_all
from common.http import response, error, query_params


@require_role('viewer')
def lambda_handler(event, context):
    try:
        db = dynamodb_resource()
        findings = db.Table(os.environ['FINDINGS_TABLE'])
        finding_id = (event.get('pathParameters') or {}).get('findingId')
        if finding_id:
            item = findings.get_item(Key={'findingId': finding_id}, ConsistentRead=True).get('Item')
            if not item or item.get('scopeKey') != configured_scope():
                return error(404, 'FINDING_NOT_FOUND', 'No finding exists with that ID.')
            return response(200, {'item': finding_view(item)})

        region = query_params(event).get('region') or os.environ.get('AWS_REGION', 'ap-south-1')
        if region != os.environ.get('AWS_REGION', 'ap-south-1'):
            return error(409, 'REGION_SCOPE_MISMATCH', 'Only the configured region is available.')
        items, findings_partial = scan_all(findings, FilterExpression=Attr('scopeKey').eq(configured_scope()))
        evaluations, evaluations_partial = scan_all(db.Table(os.environ['EVALUATIONS_TABLE']), FilterExpression=Attr('scopeKey').eq(configured_scope()))
        proposals, proposals_partial = scan_all(db.Table(os.environ['REMEDIATIONS_TABLE']), FilterExpression=Attr('scopeKey').eq(configured_scope()))
        pending_proposals = sum(row.get('status') in {'PROPOSED', 'APPROVED', 'EXECUTING'} for row in proposals)
        evaluations = [row for row in evaluations if row.get('status') in {'SUCCEEDED', 'PARTIAL'} and row.get('finishedAt')]
        evaluations.sort(key=lambda row: row['finishedAt'], reverse=True)
        latest = evaluations[0] if evaluations else None
        active = [row for row in items if row.get('status') in {'OPEN', 'ACKNOWLEDGED'}]
        severity = {level: sum(row.get('severity', '').lower() == level for row in active)
                    for level in ['critical', 'high', 'medium', 'low', 'info']}
        metrics = (latest or {}).get('conformance')
        evaluation_incomplete = findings_partial or evaluations_partial
        incomplete = evaluation_incomplete or proposals_partial
        if not metrics or evaluation_incomplete or latest.get('status') != 'SUCCEEDED':
            metrics = {'percent': None, 'totalRules': 0, 'passingRules': 0, 'failingRules': 0}
        return response(200, {'conformance': metrics, 'severityCounts': severity,
                              'totalFindings': len(active), 'activeDriftCount': None,
                              'openRemediations': None if proposals_partial else pending_proposals,
                              'lastEvaluatedAt': latest.get('finishedAt') if latest else None,
                              'evaluatedRegion': region, 'partial': incomplete,
                              'evaluationStatus': latest.get('status') if latest else None,
                              'features': {'driftEvents': False, 'remediation': True}})
    except (ClientError, BotoCoreError) as exc:
        return error(502, 'VIEW_READ_FAILED', 'Could not read stored dashboard or finding data.', type(exc).__name__)
