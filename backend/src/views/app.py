"""Dashboard and finding detail use stored evidence; no fabricated history."""
import os
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import BotoCoreError, ClientError
from common.dynamodb import dynamodb_resource
from common.contracts import finding_view, scan_all
from common.http import response, error, query_params


def lambda_handler(event, context):
    try:
        db = dynamodb_resource()
        findings = db.Table(os.environ['FINDINGS_TABLE'])
        finding_id = (event.get('pathParameters') or {}).get('findingId')
        if finding_id:
            item = findings.get_item(Key={'findingId': finding_id}, ConsistentRead=True).get('Item')
            if not item:
                return error(404, 'FINDING_NOT_FOUND', 'No finding exists with that ID.')
            return response(200, {'item': finding_view(item)})

        region = query_params(event).get('region') or os.environ.get('AWS_REGION', 'ap-south-1')
        items, findings_partial = scan_all(findings, FilterExpression=Attr('region').eq(region))
        evaluations, evaluations_partial = scan_all(db.Table(os.environ['EVALUATIONS_TABLE']), FilterExpression=Attr('region').eq(region))
        evaluations.sort(key=lambda row: row.get('finishedAt', ''), reverse=True)
        latest = evaluations[0] if evaluations else None
        active = [row for row in items if row.get('status') in {'OPEN', 'ACKNOWLEDGED'}]
        severity = {level: sum(row.get('severity', '').lower() == level for row in active)
                    for level in ['critical', 'high', 'medium', 'low', 'info']}
        metrics = (latest or {}).get('conformance')
        incomplete = findings_partial or evaluations_partial
        if not metrics or incomplete or latest.get('status') != 'SUCCEEDED':
            metrics = {'percent': None, 'totalRules': 0, 'passingRules': 0, 'failingRules': 0}
        return response(200, {'conformance': metrics, 'severityCounts': severity,
                              'totalFindings': len(active), 'activeDriftCount': None, 'openRemediations': None,
                              'lastEvaluatedAt': latest.get('finishedAt') if latest else None,
                              'evaluatedRegion': region, 'partial': incomplete,
                              'evaluationStatus': latest.get('status') if latest else None,
                              'features': {'driftEvents': False, 'remediation': False}})
    except (ClientError, BotoCoreError) as exc:
        return error(502, 'VIEW_READ_FAILED', 'Could not read stored dashboard or finding data.', type(exc).__name__)
