"""Collected serverless wiring feeds a complete, structural-only evaluation."""
import unittest
from unittest.mock import patch
from test_serverless_inventory import session_for, mapping, TABLE, FUNCTION, FLAGS
from common import inventory
from common.manifest import validate_manifest
from evaluations.app import run_pinned_evaluation


def guardian_intent():
    return validate_manifest({
        'schemaVersion': 2, 'name': 'Guardian stream baseline', 'constraints': [],
        'components': [
            {'id': 'queue', 'resourceTypes': ['AWS::DynamoDB::Table'], 'selector': {'resourceIds': [TABLE]}},
            {'id': 'worker', 'resourceTypes': ['AWS::Lambda::Function'], 'selector': {'resourceIds': [FUNCTION]}},
        ],
        'relationships': [{'id': 'trigger', 'from': 'queue', 'to': 'worker', 'effect': 'ALLOW',
                           'required': True, 'relationshipType': 'STRUCTURAL'}],
        'trustBoundaries': [
            {'id': 'data', 'members': ['queue'], 'edgeTypes': ['STRUCTURAL'],
             'crossingRules': [{'id': 'stream', 'to': 'compute', 'effect': 'ALLOW', 'via': ['worker']}]},
            {'id': 'compute', 'members': ['worker'], 'edgeTypes': ['STRUCTURAL'], 'crossingRules': []},
        ],
    })


class GuardianTopologyIntegrationTests(unittest.TestCase):
    def evaluate(self, mappings):
        session = session_for(mappings=mappings)
        with patch('common.inventory.boto3.session.Session', return_value=session), patch.dict('os.environ', FLAGS, clear=True):
            observed = inventory.collect_inventory('ap-south-1')
        intent = {**guardian_intent(), 'intentId': 'guardian-test', 'version': 1}
        result, findings = run_pinned_evaluation(intent, observed, 'guardian-run')
        return result, findings, observed

    def test_exact_stream_wiring_establishes_structural_conformance_without_network_claim(self):
        result, findings, observed = self.evaluate([mapping()])
        self.assertEqual(result['status'], 'SUCCEEDED')
        self.assertEqual(result['conformance']['percent'], 100)
        self.assertFalse(findings)
        self.assertEqual(observed['meta']['coverage']['relationshipTypes']['NETWORK_REACHABILITY'], 'UNSUPPORTED')
        self.assertTrue(all(row['outcome'] == 'PASS' for row in result['ruleResults']))

    def test_disabled_trigger_is_confirmed_missing_not_a_fabricated_positive(self):
        result, findings, _ = self.evaluate([mapping(State='Disabled')])
        self.assertEqual(result['status'], 'SUCCEEDED')
        required = next(row for row in result['ruleResults'] if row['ruleId'] == 'relationship:trigger')
        self.assertEqual(required['outcome'], 'VIOLATION')
        self.assertTrue(findings)
        self.assertLess(result['conformance']['percent'], 100)
