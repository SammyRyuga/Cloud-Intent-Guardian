"""IAM-invoke-only, hardcoded synthetic Bedrock execution-role verification."""
from __future__ import annotations

import os

from common.contracts import is_local
from common.escalation import BedrockLLMClient

MODEL_ID = 'google.gemma-3-4b-it'
REGION = 'ap-south-1'
DIAGNOSTIC_EVENT = {'diagnostic': 'BEDROCK_SYNTHETIC'}


def verify_bedrock_runtime(event):
    """Never reads application state or incorporates caller-supplied model data."""
    if event != DIAGNOSTIC_EVENT:
        return {'diagnostic': 'BEDROCK_SYNTHETIC', 'status': 'INVALID_REQUEST'}
    if (is_local() or os.environ.get('BEDROCK_DIAGNOSTIC_ENABLED', 'false').lower() != 'true'
            or os.environ.get('LLM_ENABLED', 'false').lower() != 'true'):
        return {'diagnostic': 'BEDROCK_SYNTHETIC', 'status': 'DISABLED'}
    if os.environ.get('BEDROCK_MODEL_ID') != MODEL_ID or os.environ.get('AWS_REGION') != REGION:
        return {'diagnostic': 'BEDROCK_SYNTHETIC', 'status': 'CONFIGURATION_MISMATCH'}
    try:
        import boto3
        from botocore.config import Config
        sdk = boto3.client('bedrock-runtime', region_name=REGION, config=Config(
            connect_timeout=2, read_timeout=10,
            retries={'total_max_attempts': 1, 'mode': 'standard'}))
        class Capture:
            def converse(self, **request):
                self.response = sdk.converse(**request)
                return self.response
        capture = Capture()
        conclusion = BedrockLLMClient(capture, MODEL_ID).assess({
            'candidateId': 'synthetic-worker-role-verification',
            'sourceId': 'fictional-component-a', 'targetId': 'fictional-component-b',
            'relationship': 'unconfirmed fictional directed crossing', 'evidence': [],
            'instruction': 'Synthetic diagnostic only; no actual architecture data is supplied.'})
        return {'diagnostic': 'BEDROCK_SYNTHETIC', 'status': 'VALIDATED',
                'syntheticOnly': True, 'modelId': MODEL_ID, 'region': REGION,
                'maxTokens': 512, 'conclusion': conclusion,
                'requestId': capture.response.get('ResponseMetadata', {}).get('RequestId'),
                'usage': capture.response.get('usage', {}),
                'limits': 'Execution-role synthetic inference only; no application or network-path evidence.'}
    except Exception as exc:
        # Do not expose service messages, caller data, or retry a model request.
        return {'diagnostic': 'BEDROCK_SYNTHETIC', 'status': 'INVALID_OR_UNAVAILABLE',
                'errorType': type(exc).__name__, 'syntheticOnly': True}
