#!/usr/bin/env python3
"""Invoke the gated hardcoded synthetic worker diagnostic once and save its receipt."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--function-name', required=True)
    parser.add_argument('--profile', choices=['ryan'], default='ryan')
    parser.add_argument('--region', choices=['ap-south-1'], default='ap-south-1')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='cig-bedrock-diagnostic-') as directory:
        response_path = Path(directory) / 'response.json'
        result = subprocess.run(['aws', 'lambda', 'invoke', '--profile', args.profile,
            '--region', args.region, '--function-name', args.function_name,
            '--invocation-type', 'RequestResponse', '--cli-binary-format', 'raw-in-base64-out',
            '--payload', '{"diagnostic":"BEDROCK_SYNTHETIC"}', '--cli-connect-timeout', '5',
            '--cli-read-timeout', '30', '--output', 'json', str(response_path)],
            check=True, capture_output=True, text=True)
        invocation = json.loads(result.stdout)
        response = json.loads(response_path.read_text())
    receipt = {'functionName': args.function_name, 'region': args.region,
               'invocation': invocation, 'response': response,
               'limits': 'Synthetic inference under deployed worker role; no job processing or application data.'}
    Path(args.output).write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))
    return 0 if (invocation.get('StatusCode') == 200 and not invocation.get('FunctionError')
                 and response.get('status') == 'VALIDATED') else 1


if __name__ == '__main__':
    raise SystemExit(main())
