"""Local-only diagnostics and persistence verification; never calls AWS endpoints."""
import argparse
import json
import os
from pathlib import Path
import socket
import sys
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.environ.get("CIG_SOURCE_DIR", str(ROOT / "src")))
from common.dynamodb import dynamodb_resource

TABLES = {
    'INTENTS_TABLE': ('cloud-intent-guardian-dev-intents', 'intentId'),
    'FINDINGS_TABLE': ('cloud-intent-guardian-dev-findings', 'findingId'),
    'EVALUATIONS_TABLE': ('cloud-intent-guardian-dev-evaluations', 'evaluationId'),
    'INTENT_VERSIONS_TABLE': ('cloud-intent-guardian-dev-intent-versions', 'intentId'),
    'AUDIT_TABLE': ('cloud-intent-guardian-dev-audit', 'auditId'),
    'REMEDIATIONS_TABLE': ('cloud-intent-guardian-dev-remediations', 'proposalId'),
    'EVALUATION_ARTIFACTS_TABLE': ('cloud-intent-guardian-dev-evaluation-artifacts', 'evaluationId'),
}
SORT_KEYS = {'INTENT_VERSIONS_TABLE': ('version', 'N'), 'EVALUATION_ARTIFACTS_TABLE': ('artifactKey', 'S')}
INDEXES = {'REMEDIATIONS_TABLE': ('scope-created', 'scopeKey', 'createdOrder'), 'FINDINGS_TABLE': ('scope-intent', 'scopeIntentKey', 'findingId'),
           'EVALUATIONS_TABLE': ('scope-created', 'scopeKey', 'createdOrder'),
           'AUDIT_TABLE': ('scope-time', 'scopeKey', 'eventOrder')}


def table_schema(env_key):
    key = TABLES[env_key][1]
    schema = [{'AttributeName': key, 'KeyType': 'HASH'}]
    definitions = {key: 'S'}
    if env_key in SORT_KEYS:
        sort, typ = SORT_KEYS[env_key]
        schema.append({'AttributeName': sort, 'KeyType': 'RANGE'})
        definitions[sort] = typ
    indexes = []
    if env_key in INDEXES:
        index, partition, sort = INDEXES[env_key]
        definitions.update({partition: 'S', sort: 'S'})
        indexes.append({'IndexName': index, 'KeySchema': [{'AttributeName': partition, 'KeyType': 'HASH'},
            {'AttributeName': sort, 'KeyType': 'RANGE'}], 'Projection': {'ProjectionType': 'ALL'}})
    result = {'KeySchema': schema, 'AttributeDefinitions': [
        {'AttributeName': name, 'AttributeType': typ} for name, typ in definitions.items()]}
    if indexes:
        result['GlobalSecondaryIndexes'] = indexes
    return result



def report(stage, **fields):
    print(json.dumps({"stage": stage, **fields}, default=str), flush=True)


def configure(args):
    if args.env_file:
        config = json.loads(Path(args.env_file).read_text())
        values = dict(config.get("Parameters", {}))
        values.update(config.get("IntentsFunction", {}))
        for key in ["DYNAMODB_ENDPOINT_URL", "CIG_LOCAL", *TABLES]:
            if key in values:
                os.environ[key] = str(values[key])
    os.environ["CIG_LOCAL"] = "true"
    os.environ["AWS_REGION"] = args.region
    if args.endpoint:
        os.environ["DYNAMODB_ENDPOINT_URL"] = args.endpoint
    for key, (name, _) in TABLES.items():
        os.environ.setdefault(key, name)
    # Validate the endpoint before any network call.
    resource = dynamodb_resource()
    parsed = urlsplit(resource.meta.client.meta.endpoint_url)
    report("effective_config", endpoint=resource.meta.client.meta.endpoint_url,
           region=args.region, tables={key: os.environ[key] for key in TABLES})
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 80, type=socket.SOCK_STREAM)
    report("dns_ok", host=parsed.hostname, addresses=sorted({row[4][0] for row in addresses}))
    with socket.create_connection((parsed.hostname, parsed.port or 80), timeout=2):
        report("tcp_ok")
    return resource


def check_tables(resource, initialize):
    client = resource.meta.client
    for env_key in TABLES:
        name = os.environ[env_key]
        spec = table_schema(env_key)
        try:
            table = client.describe_table(TableName=name)['Table']
        except client.exceptions.ResourceNotFoundException:
            if not initialize:
                raise RuntimeError(f'Missing table {name}. Run init explicitly on this local database.')
            client.create_table(TableName=name, BillingMode='PAY_PER_REQUEST', **spec)
            client.get_waiter('table_exists').wait(TableName=name, WaiterConfig={'Delay': 1, 'MaxAttempts': 10})
            table = client.describe_table(TableName=name)['Table']
            report('table_created', table=name)
        if sorted(table['KeySchema'], key=lambda row: row['KeyType']) != sorted(spec['KeySchema'], key=lambda row: row['KeyType']):
            raise RuntimeError(f'Incorrect key schema on {name}; existing tables are never replaced.')
        if env_key in INDEXES:
            index_name = INDEXES[env_key][0]
            existing = next((row for row in table.get('GlobalSecondaryIndexes', []) if row['IndexName'] == index_name), None)
            expected = spec['GlobalSecondaryIndexes'][0]
            if not existing and initialize:
                client.update_table(TableName=name, AttributeDefinitions=spec['AttributeDefinitions'],
                    GlobalSecondaryIndexUpdates=[{'Create': expected}])
                report('index_created', table=name, index=index_name)
            elif not existing:
                raise RuntimeError(f'Missing index {name}/{index_name}; run init explicitly.')
            elif existing['KeySchema'] != expected['KeySchema']:
                raise RuntimeError(f'Incorrect index schema on {name}; no destructive correction is performed.')
        definitions = {row['AttributeName']: row['AttributeType'] for row in table['AttributeDefinitions']}
        for row in spec['KeySchema']:
            field = row['AttributeName']
            expected_type = next(value['AttributeType'] for value in spec['AttributeDefinitions'] if value['AttributeName'] == field)
            if definitions.get(field) != expected_type:
                raise RuntimeError(f'Incorrect attribute type for {name}.{field}')
        report('table_ok', table=name, status=table['TableStatus'])


def api(base, path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = Request(base + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=35) as result:
            return result.status, json.load(result)
    except HTTPError as exc:
        raise RuntimeError(f"{method} {path}: HTTP {exc.code}: {exc.read().decode()}") from exc


def verify(resource, args):
    base = args.api.rstrip("/")
    url = urlsplit(base)
    if url.scheme != "http" or url.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Verification requires a loopback local SAM API URL")
    status, created = api(base, "/v1/intents", "POST", {
        "name": "Local AWS Baseline", "description": "Integration test for Cloud Intent Guardian",
        "constraints": [{"id": "s3-public-access", "type": "S3_BLOCK_PUBLIC_ACCESS", "severity": "HIGH",
                         "description": "S3 buckets must block public access"}],
    })
    if status != 201 or not created.get("item", {}).get("intentId"):
        raise RuntimeError(f"Expected HTTP 201 and item.intentId: {status} {created}")
    item = created["item"]
    intent_id = item["intentId"]
    report("post_201", intentId=intent_id)
    persisted = resource.Table(os.environ["INTENTS_TABLE"]).get_item(
        Key={"intentId": intent_id}, ConsistentRead=True).get("Item")
    if not persisted or persisted["name"] != item["name"] or persisted["status"] != "DRAFT" or persisted["constraints"] != item["constraints"]:
        raise RuntimeError("Direct DynamoDB read did not match the created draft")
    report("dynamodb_item_confirmed", intentId=intent_id)
    path, seen = "/v1/intents?limit=100", set()
    while True:
        status, listing = api(base, path)
        if status != 200:
            raise RuntimeError(f"List returned HTTP {status}")
        if any(row.get("intentId") == intent_id for row in listing["items"]):
            break
        token = listing.get("nextToken")
        if not token or token in seen:
            raise RuntimeError("Created intent not found in paginated GET /v1/intents")
        seen.add(token)
        path = "/v1/intents?limit=100&nextToken=" + token
    report("list_200_contains_intent", intentId=intent_id)
    status, detail = api(base, "/v1/intents/" + intent_id)
    if status != 200 or detail.get("item") != created["item"]:
        raise RuntimeError("Detail response does not match the created intent")
    report("detail_200_matches_intent", intentId=intent_id)
    evidence = {"milestone": "intent_persistence", "passed": True, "intentId": intent_id,
                "checks": ["POST 201", "DynamoDB consistent read", "GET list 200", "GET detail 200"],
                "api": base, "endpoint": resource.meta.client.meta.endpoint_url}
    output = Path(args.evidence)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2) + "\n")
    report("milestone_passed", evidence=str(output))


def migrate(resource):
    """Explicit, resumable local backfill. Never called by read/API paths."""
    from common.contracts import scan_all
    from common.auth import configured_scope
    from common.audit import audit_event, audit_put, transaction_write
    from common.versions import migrate_legacy
    scope = configured_scope()
    actor = {'sub': 'local-migration-operator', 'displayName': 'Local migration operator', 'role': 'admin'}
    rows, incomplete = scan_all(resource.Table(os.environ['INTENTS_TABLE']))
    if incomplete:
        raise RuntimeError('Intent migration scan incomplete; no records changed.')
    for item in rows:
        migrate_legacy(resource, item, actor, 'migrate-intent:' + item['intentId'])
    for env_key, primary in [('EVALUATIONS_TABLE', 'evaluationId'), ('FINDINGS_TABLE', 'findingId')]:
        table = resource.Table(os.environ[env_key])
        records, incomplete = scan_all(table)
        if incomplete:
            raise RuntimeError(f'{env_key} migration scan incomplete; retry after narrowing local data.')
        for item in records:
            if item.get('scopeKey'):
                continue
            # This operator command only assigns records from the configured local scope.
            if item.get('accountId') not in {None, 'fixture-account'} or item.get('region', os.environ['AWS_REGION']) != os.environ['AWS_REGION']:
                report('record_skipped_other_scope', table=table.name, id=item[primary])
                continue
            changed = {**item, 'scopeKey': scope}
            if env_key == 'EVALUATIONS_TABLE':
                changed['createdAt'] = item.get('createdAt') or item.get('startedAt') or item.get('finishedAt')
                if not changed['createdAt']:
                    raise RuntimeError('Historical evaluation has no source timestamp; reconcile it explicitly.')
                changed['createdOrder'] = changed['createdAt'] + '#' + item[primary]
            else:
                changed['scopeIntentKey'] = scope + '#' + item['intentId']
                changed['revision'] = item.get('revision', 0)
            event = audit_event(actor, 'LEGACY_RECORD_BACKFILLED', {'type': env_key, 'id': item[primary]},
                'migrate:' + table.name + ':' + item[primary], {'historical': True})
            transaction_write(resource, [{'Put': {'TableName': table.name, 'Item': changed,
                'ConditionExpression': 'attribute_not_exists(scopeKey)'}}, audit_put(event)])
    report('migration_completed', scope=scope)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["probe", "init", "verify", "migrate"])
    parser.add_argument("--endpoint", help="Host: http://127.0.0.1:8000; Docker network: http://cig-dynamodb-local:8000")
    parser.add_argument("--env-file")
    parser.add_argument("--region", default="ap-south-1")
    parser.add_argument("--api", default="http://127.0.0.1:3000")
    parser.add_argument("--evidence", default="local-evidence/intent-persistence.json")
    args = parser.parse_args()
    try:
        resource = configure(args)
        check_tables(resource, args.action == "init")
        if args.action == "migrate":
            migrate(resource)
        if args.action == "verify":
            verify(resource, args)
        return 0
    except Exception as exc:
        report("failed", exception=type(exc).__name__, message=str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
