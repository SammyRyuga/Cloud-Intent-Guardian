import os
import hashlib
from common.http import response, error, query_params
from common.inventory import collect_inventory
from common.contracts import is_local
from common.dynamodb import dynamodb_resource
from common.intent_selection import approved_intent, IntentSelectionError
from common.observations import observations, ObservationUnavailable
from common.topology import build_graph
from botocore.exceptions import BotoCoreError, ClientError


def lambda_handler(event, context):
    graph = 'architecture' in (event.get('rawPath', '') or event.get('routeKey', ''))
    params = query_params(event)
    view = params.get('view', 'ACTUAL')
    if graph and view not in {'ACTUAL', 'INTENT', 'DIFF'}:
        return error(400, 'INVALID_GRAPH_VIEW', 'view must be ACTUAL, INTENT or DIFF.')
    region = os.environ.get('AWS_REGION')
    try:
        intent = None
        if graph and view != 'ACTUAL':
            if os.environ.get('TOPOLOGY_ENABLED', 'true').lower() != 'true':
                return error(409, 'GRAPH_COMPARISON_NOT_ENABLED', 'Topology comparison is disabled.')
            table = dynamodb_resource().Table(os.environ['INTENTS_TABLE'])
            intent = approved_intent(table, params.get('intentId'), params.get('version'))
            if view == 'INTENT':
                empty = {'items': [], 'edges': [], 'meta': {'partial': False, 'warnings': [], 'coverage': {}}}
                return response(200, build_graph(intent, empty, view))
        inventory = observations(collect_inventory, region)
    except IntentSelectionError as exc:
        return error(exc.status, exc.code, str(exc))
    except ObservationUnavailable as exc:
        return error(409, 'AWS_DISCOVERY_DISABLED_LOCAL', str(exc))
    except (ClientError, BotoCoreError) as exc:
        return error(502, 'INVENTORY_FAILED', 'The backend could not read intent or inventory.', {'reason': type(exc).__name__})
    if not inventory["meta"].get("accountId"):
        return error(502, "AWS_IDENTITY_UNAVAILABLE", "AWS account identity could not be confirmed. Check the Lambda execution role.")
    if graph and view == 'DIFF':
        return response(200, build_graph(intent, inventory, view))
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
                              'totalNodeCount': len(ids), 'asOf': inventory['meta']['collectedAt'],
                              'simulated': inventory['meta'].get('simulated', False),
                              'coverage': inventory['meta'].get('coverage', {})})
    return response(200, inventory)
