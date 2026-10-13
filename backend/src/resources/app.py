import os
import hashlib
from common.http import response, error, query_params
from common.inventory import collect_inventory
from common.contracts import is_local
from botocore.exceptions import BotoCoreError, ClientError


def lambda_handler(event, context):
    if is_local():
        return error(409, 'AWS_DISCOVERY_DISABLED_LOCAL', 'Live AWS inventory is disabled in local API mode.')
    graph = 'architecture' in (event.get('rawPath', '') or event.get('routeKey', ''))
    if graph and query_params(event).get('view', 'ACTUAL') != 'ACTUAL':
        return error(409, 'GRAPH_COMPARISON_NOT_ENABLED', 'Only ACTUAL inventory is available; intent topology comparison is not implemented.')
    region = os.environ.get("AWS_REGION")
    try:
        inventory = collect_inventory(region)
    except (ClientError, BotoCoreError) as exc:
        return error(502, "INVENTORY_FAILED", "The backend could not read the AWS inventory.", {"reason": str(exc)[:300]})
    if not inventory["meta"].get("accountId"):
        return error(502, "AWS_IDENTITY_UNAVAILABLE", "AWS account identity could not be confirmed. Check the Lambda execution role.")
    if graph:
        ids = {row['resourceId'] for row in inventory['items']}
        edges = [row for row in inventory['edges'] if row['sourceId'] in ids and row['targetId'] in ids]
        return response(200, {'view': 'ACTUAL',
                              'nodes': [{'id': row['resourceId'], 'label': row['name'], 'resourceType': row['resourceType'],
                                         'diffState': 'UNKNOWN', 'properties': row['attributes']} for row in inventory['items']],
                              'edges': [{'id': hashlib.sha256(f"{row['sourceId']}|{row['type']}|{row['targetId']}".encode()).hexdigest()[:24],
                                         'source': row['sourceId'], 'target': row['targetId'], 'relationshipType': row['type'],
                                         'diffState': 'UNKNOWN'} for row in edges],
                              'truncated': any(row.get('code') in {'RESOURCE_CAP', 'TRUNCATED'} for row in inventory['meta']['warnings']),
                              'partial': inventory['meta']['partial'], 'warnings': inventory['meta']['warnings'],
                              'totalNodeCount': len(ids), 'asOf': inventory['meta']['collectedAt']})
    return response(200, inventory)
