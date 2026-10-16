"""No-network execution-role diagnostic boundaries and SDK contract."""
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from common.runtime_verification import DIAGNOSTIC_EVENT, MODEL_ID, verify_bedrock_runtime


class RuntimeVerificationTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {'CIG_LOCAL': 'false', 'AWS_SAM_LOCAL': 'false',
            'BEDROCK_DIAGNOSTIC_ENABLED': 'true', 'LLM_ENABLED': 'true',
            'BEDROCK_MODEL_ID': MODEL_ID, 'AWS_REGION': 'ap-south-1'})
        env.start()
        self.addCleanup(env.stop)

    def test_disabled_local_invalid_or_mismatched_requests_make_no_client(self):
        with patch('boto3.client') as create:
            for overrides in ({'BEDROCK_DIAGNOSTIC_ENABLED': 'false'}, {'LLM_ENABLED': 'false'},
                              {'CIG_LOCAL': 'true'}, {'AWS_REGION': 'us-east-1'},
                              {'BEDROCK_MODEL_ID': 'other-model'}):
                with self.subTest(overrides=overrides), patch.dict(os.environ, overrides):
                    self.assertNotEqual(verify_bedrock_runtime(DIAGNOSTIC_EVENT)['status'], 'VALIDATED')
            self.assertEqual(verify_bedrock_runtime({**DIAGNOSTIC_EVENT, 'jobId': 'anything'})['status'], 'INVALID_REQUEST')
            self.assertEqual(verify_bedrock_runtime({**DIAGNOSTIC_EVENT, 'text': 'anything'})['status'], 'INVALID_REQUEST')
            create.assert_not_called()

    def test_sdk_one_call_hardcoded_fiction_and_strict_validated_result(self):
        import boto3
        from botocore.stub import Stubber, ANY
        sdk = boto3.client('bedrock-runtime', region_name='ap-south-1',
                           aws_access_key_id='test', aws_secret_access_key='test')
        conclusion = {'candidateId': 'synthetic-worker-role-verification',
                      'verdict': 'UNCERTAIN', 'explanation': 'No real evidence supplied.'}
        with Stubber(sdk) as stub, patch('boto3.client', return_value=sdk) as create:
            stub.add_response('converse', {'output': {'message': {'role': 'assistant',
                'content': [{'text': json.dumps(conclusion)}]}}, 'stopReason': 'end_turn',
                'usage': {'inputTokens': 1, 'outputTokens': 1, 'totalTokens': 2},
                'metrics': {'latencyMs': 1}}, {'modelId': MODEL_ID, 'system': ANY,
                'messages': ANY, 'inferenceConfig': {'maxTokens': 512, 'temperature': 0}})
            result = verify_bedrock_runtime(DIAGNOSTIC_EVENT)
            self.assertEqual(result['status'], 'VALIDATED')
            self.assertEqual(result['conclusion'], conclusion)
            self.assertEqual(create.call_args.kwargs['config'].retries['total_max_attempts'], 1)
            stub.assert_no_pending_responses()

    def test_invalid_response_fails_closed_and_does_not_expose_service_message(self):
        with patch('boto3.client') as create:
            create.return_value.converse.side_effect = RuntimeError('private service detail')
            result = verify_bedrock_runtime(DIAGNOSTIC_EVENT)
            self.assertEqual(result['status'], 'INVALID_OR_UNAVAILABLE')
            self.assertNotIn('private', json.dumps(result))
            self.assertEqual(create.return_value.converse.call_count, 1)
