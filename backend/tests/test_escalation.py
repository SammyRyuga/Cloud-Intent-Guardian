"""No-network escalation and adversarial model/source boundary tests."""
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from common.escalation import (BedrockLLMClient, MockLLMClient, candidates,
                               cross_validate, escalate, validate_conclusion)
from common.scenarios import scenario_inventory, scenario_manifest
from evaluations.app import run_pinned_evaluation


class EscalationTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'CIG_LOCAL': 'true', 'INVENTORY_PROVIDER': 'fixture', 'LLM_ENABLED': 'true', 'LLM_PROVIDER': 'mock'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.intent = {**scenario_manifest(), 'intentId': 'test-intent', 'version': 1}

    def run_scenario(self, name, client=None):
        inventory = scenario_inventory(name)
        evaluation, findings = run_pinned_evaluation(self.intent, inventory, 'eval-test')
        return escalate(self.intent, inventory, evaluation, findings, client=client)

    def test_clear_results_make_no_model_calls(self):
        client = MockLLMClient()
        for name in ('benign', 'open-ssh', 'lambda-db-bypass'):
            self.run_scenario(name, client)
        self.assertEqual(client.calls, 0)

    def test_two_independent_simulated_sources_corroborate(self):
        _, findings = self.run_scenario('unruled-crossing')
        self.assertTrue(findings)
        output = os.environ.get('CIG_ESCALATION_CONTRACT_OUTPUT')
        if output:
            Path(output).write_text(json.dumps({'findings': findings}, indent=2) + '\n')
        self.assertTrue(all(f['reviewStatus'] == 'CORROBORATED' and f['crossValidation']['accepted'] for f in findings))
        self.assertTrue(all(f['actionEligible'] is False for f in findings))

    def test_disagreement_requires_human_and_low_confidence(self):
        _, findings = self.run_scenario('source-disagreement')
        self.assertTrue(findings)
        self.assertTrue(all(f['reviewStatus'] == 'NEEDS_HUMAN_REVIEW' and f['confidence'] == 'LOW' for f in findings))
        self.assertTrue(all(f['actionEligible'] is False for f in findings))

    def test_disabled_makes_no_model_calls(self):
        client = MockLLMClient()
        with patch.dict(os.environ, {'LLM_ENABLED': 'false'}):
            _, findings = self.run_scenario('unruled-crossing', client)
        self.assertEqual((client.calls, findings), (0, []))

    def test_model_error_degrades_without_breaking_evaluation(self):
        class Broken:
            def assess(self, candidate):
                raise RuntimeError('denied')
        evaluation, findings = self.run_scenario('unruled-crossing', Broken())
        self.assertEqual(evaluation['status'], 'PARTIAL')
        self.assertTrue(all(f['confidence'] == 'LOW' and f['llmStatus'] == 'INVALID_OR_UNAVAILABLE' for f in findings))

    def test_injected_commands_unknown_keys_and_duplicate_json_rejected(self):
        good = {'candidateId': 'id', 'verdict': 'CONCERN', 'explanation': 'test'}
        for bad in ({**good, 'command': 'anything'}, {**good, 'candidateId': 'other'},
                    {**good, 'verdict': 'EXECUTE'}, {**good, 'explanation': 'x' * 1001},
                    '{"candidateId":"id","candidateId":"id","verdict":"CONCERN","explanation":"test"}'):
            with self.assertRaises((ValueError, TypeError)):
                validate_conclusion(bad, 'id')

    def test_missing_duplicate_stale_and_derived_sources_fail_closed(self):
        original = scenario_inventory('unruled-crossing')
        candidate = candidates(self.intent, original)[0]
        for mode in ('missing', 'same-family', 'same-origin', 'stale', 'wrong-path', 'cloudtrail', 'not-fixture'):
            inventory = scenario_inventory('unruled-crossing')
            sources = inventory['meta']['sourceVerdicts']
            if mode == 'missing': sources.pop()
            if mode == 'same-family': sources[1]['sourceFamily'] = sources[0]['sourceFamily']
            if mode == 'same-origin': sources[1]['originId'] = sources[0]['originId']
            if mode == 'stale': sources[1]['observedAt'] = 'old'
            if mode == 'wrong-path': sources[1]['targetId'] = 'elsewhere'
            if mode == 'cloudtrail': sources[1]['sourceFamily'] = 'cloudTrail'
            if mode == 'not-fixture': inventory['meta']['simulated'] = False
            with self.subTest(mode=mode):
                self.assertFalse(cross_validate(candidate, inventory)['accepted'])

    def test_bedrock_converse_sdk_stubbed(self):
        import boto3
        from botocore.stub import Stubber, ANY
        sdk = boto3.client('bedrock-runtime', region_name='ap-south-1', aws_access_key_id='test', aws_secret_access_key='test')
        conclusion = {'candidateId': 'id', 'verdict': 'UNCERTAIN', 'explanation': 'Review required.'}
        with Stubber(sdk) as stub:
            stub.add_response('converse', {'output': {'message': {'role': 'assistant', 'content': [{'text': json.dumps(conclusion)}]}},
                'stopReason': 'end_turn', 'usage': {'inputTokens': 1, 'outputTokens': 1, 'totalTokens': 2}, 'metrics': {'latencyMs': 1}},
                {'modelId': 'test-model', 'system': ANY, 'messages': ANY, 'inferenceConfig': {'maxTokens': 512, 'temperature': 0}})
            self.assertEqual(BedrockLLMClient(sdk, 'test-model').assess({'candidateId': 'id'}), conclusion)
            stub.assert_no_pending_responses()
