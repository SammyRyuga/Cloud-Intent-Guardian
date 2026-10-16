#!/usr/bin/env python3
"""Read-only correlation of one existing Guardian intent write across DynamoDB and Logs."""
import argparse
import datetime
import json
import subprocess
from pathlib import Path


def correlate(record, events, intent_id, table, start, end):
    item = record.get('Item', {})
    if item.get('intentId', {}).get('S') != intent_id:
        raise ValueError('Exact DynamoDB intent record absent.')
    starts, successes = [], []
    for event in events:
        if (not isinstance(event.get('logStreamName'), str) or not event['logStreamName']
                or not isinstance(event.get('eventId'), str) or not event['eventId']):
            continue
        if not start <= event.get('timestamp', -1) <= end:
            continue
        try:
            message = json.loads(event.get('message', ''))
        except (ValueError, TypeError):
            continue
        if not isinstance(message, dict) or message.get('intentId') != intent_id:
            continue
        if message.get('event') == 'intent_put_started' and message.get('table') == table:
            starts.append(event)
        if message.get('event') == 'intent_put_succeeded':
            successes.append(event)
    pairs = [(a, b) for a in starts for b in successes
             if a.get('logStreamName') == b.get('logStreamName') and a['timestamp'] <= b['timestamp']]
    if not pairs:
        raise ValueError('No exact structured same-stream start/success pair in bounded window.')
    a, b = pairs[0]
    return {'verdict': 'CONFIRMED_SPECIFIC_APP_WRITE', 'intentId': intent_id, 'table': table,
            'createdAt': item.get('createdAt', {}).get('S'), 'consistentRead': True,
            'logEventIds': [a['eventId'], b['eventId']], 'logStreamName': a['logStreamName'],
            'limits': 'One completed application write; not packet reachability or general IAM authorization.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--region', required=True)
    parser.add_argument('--intent-id', required=True)
    parser.add_argument('--table', required=True)
    parser.add_argument('--log-group', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    def read(service, operation, *flags):
        command = ['aws', service, operation, '--profile', args.profile, '--region', args.region,
                   '--cli-connect-timeout', '5', '--cli-read-timeout', '20', '--output', 'json', *flags]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        return json.loads(result.stdout)
    record = read('dynamodb', 'get-item', '--table-name', args.table, '--key',
                  json.dumps({'intentId': {'S': args.intent_id}}), '--consistent-read',
                  '--projection-expression', 'intentId,createdAt')
    created = record.get('Item', {}).get('createdAt', {}).get('S')
    if not created:
        raise ValueError('Existing record creation timestamp required.')
    center = int(datetime.datetime.fromisoformat(created.replace('Z', '+00:00')).timestamp() * 1000)
    start, end = center - 300000, center + 300000
    logs = read('logs', 'filter-log-events', '--log-group-name', args.log_group,
                '--filter-pattern', json.dumps(args.intent_id), '--start-time', str(start), '--end-time', str(end),
                '--limit', '20', '--no-paginate')
    receipt = correlate(record, logs.get('events', []), args.intent_id, args.table, start, end)
    receipt.update(region=args.region, logGroup=args.log_group, verifiedAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
    Path(args.output).write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
