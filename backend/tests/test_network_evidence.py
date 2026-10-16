"""Offline deterministic enrichment tests. No AWS credentials or network needed."""
import copy
from decimal import Decimal
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from common.network_evidence import enrich_network_evidence, MAX_CANDIDATES
from common.topology import evaluate_topology


def fixture():
    intent = {'components': [
        {'id': 'source', 'resourceTypes': ['AWS::EC2::Instance'], 'selector': {'resourceIds': ['source']}},
        {'id': 'target', 'resourceTypes': ['AWS::EC2::Instance'], 'selector': {'resourceIds': ['target']}},
    ], 'relationships': [{'id': 'required', 'from': 'source', 'to': 'target', 'effect': 'ALLOW',
                         'required': True, 'relationshipType': 'NETWORK_REACHABILITY',
                         'protocol': 'tcp', 'ports': [443]}]}
    inventory = {'items': [{'resourceId': name, 'resourceType': 'AWS::EC2::Instance'} for name in ['source', 'target']],
                 'edges': [], 'meta': {'collectedAt': '2026-10-16T10:00:00Z', 'warnings': [], 'partial': False,
                 'coverage': {'resourceTypes': {'AWS::EC2::Instance': 'COMPLETE'},
                              'relationshipTypes': {'NETWORK_REACHABILITY': 'UNSUPPORTED'}}}}
    return intent, inventory


def verdicts(candidate, inventory, **kwargs):
    base = {key: candidate[key] for key in ['sourceId', 'targetId', 'snapshotId', 'observedAt']}
    return [{**base, 'sourceFamily': family, 'verdict': verdict, 'evidenceId': family,
             'originId': family, 'predicate': 'DIRECTED_PATH_PRESENT'}
            for family, verdict in [('flowLogs', 'CORROBORATES'), ('reachabilityAnalyzer', 'UNKNOWN')]]


class NetworkEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'NETWORK_EVIDENCE_ENABLED': 'true'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.local = patch('common.network_evidence.is_local', return_value=False)
        self.local.start()
        self.addCleanup(self.local.stop)
        self.collect = patch('common.network_evidence.collect_verdicts', side_effect=verdicts)
        self.mock = self.collect.start()
        self.addCleanup(self.collect.stop)

    def test_positive_required_binding_passes_without_global_coverage_or_mutation(self):
        intent, inventory = fixture()
        original = copy.deepcopy(inventory)
        enriched = enrich_network_evidence(intent, inventory)
        self.assertEqual(inventory, original)
        self.assertEqual(enriched['edges'][0]['observationKind'], 'OBSERVED')
        self.assertEqual(enriched['meta']['coverage']['relationshipTypes']['NETWORK_REACHABILITY'], 'PARTIAL')
        outcome = next(row for row in evaluate_topology(intent, enriched) if row['ruleId'] == 'relationship:required')
        self.assertEqual(outcome['outcome'], 'PASS')
        denied = copy.deepcopy(intent)
        denied['relationships'][0]['effect'] = 'DENY'
        enriched['edges'] = []
        outcome = next(row for row in evaluate_topology(denied, enriched) if row['ruleId'] == 'relationship:required')
        self.assertEqual(outcome['outcome'], 'UNKNOWN')

    def test_negative_and_conflicting_sources_never_add_edge_or_complete_coverage(self):
        intent, inventory = fixture()
        for values in [('DISAGREES', 'UNKNOWN'), ('CORROBORATES', 'DISAGREES'), ('UNKNOWN', 'UNKNOWN')]:
            def rows(candidate, snapshot, **kwargs):
                result = verdicts(candidate, snapshot)
                for row, value in zip(result, values):
                    row['verdict'] = value
                return result
            self.mock.side_effect = rows
            enriched = enrich_network_evidence(intent, inventory)
            self.assertEqual(enriched['edges'], [])
            self.assertEqual([row['verdict'] for row in enriched['meta']['networkEvidence']['candidates'][0]['verdicts']], list(values))
            outcome = next(row for row in evaluate_topology(intent, enriched) if row['ruleId'] == 'relationship:required')
            self.assertEqual(outcome['outcome'], 'UNKNOWN')

    def test_analyzer_is_configuration_not_observed_packets(self):
        intent, inventory = fixture()
        def analyzer(candidate, snapshot, **kwargs):
            rows = verdicts(candidate, snapshot)
            rows[0]['verdict'], rows[1]['verdict'] = 'UNKNOWN', 'CORROBORATES'
            return rows
        self.mock.side_effect = analyzer
        enriched = enrich_network_evidence(intent, inventory)
        self.assertEqual(enriched['edges'][0]['type'], 'NETWORK_PERMISSION')
        self.assertEqual(enriched['edges'][0]['observationKind'], 'CONFIGURED')
        outcome = next(row for row in evaluate_topology(intent, enriched) if row['ruleId'] == 'relationship:required')
        self.assertEqual(outcome['outcome'], 'UNKNOWN')

    def test_local_and_disabled_never_read(self):
        intent, inventory = fixture()
        with patch('common.network_evidence.is_local', return_value=True):
            self.assertIs(enrich_network_evidence(intent, inventory), inventory)
        with patch.dict(os.environ, {'NETWORK_EVIDENCE_ENABLED': 'false'}):
            self.assertIs(enrich_network_evidence(intent, inventory), inventory)
        self.mock.assert_not_called()

    def test_candidate_bound_and_scope_validation(self):
        intent, inventory = fixture()
        for index in range(MAX_CANDIDATES + 2):
            name = f'target-{index}'
            inventory['items'].append({'resourceId': name, 'resourceType': 'AWS::EC2::Instance'})
            intent['components'][1]['selector']['resourceIds'].append(name)
        enriched = enrich_network_evidence(intent, inventory)
        self.assertEqual(self.mock.call_count, MAX_CANDIDATES)
        self.assertTrue(enriched['meta']['networkEvidence']['truncated'])
        self.mock.reset_mock()
        for protocol, ports in [('icmp', [443]), ('tcp', [443, 80]), ('tcp', [True]), (None, [])]:
            intent['relationships'][0].update(protocol=protocol, ports=ports)
            self.assertEqual(enrich_network_evidence(intent, inventory)['edges'], [])
        self.mock.assert_not_called()

    def test_exact_flow_cannot_prove_other_ports_unscoped_or_transitive_predicates(self):
        intent, inventory = fixture()
        enriched = enrich_network_evidence(intent, inventory)
        for protocol, ports in [('tcp', [80]), ('udp', [443]), (None, []), ('tcp', [80, 443])]:
            changed = copy.deepcopy(intent)
            changed['relationships'][0].update(protocol=protocol, ports=ports)
            outcome = next(row for row in evaluate_topology(changed, enriched)
                           if row['ruleId'] == 'relationship:required')
            self.assertEqual(outcome['outcome'], 'UNKNOWN')
        intent['constraints'] = [{'id': 'unscoped', 'type': 'FORBIDDEN_PATH', 'from': 'source',
                                  'to': 'target', 'pathMode': 'TRANSITIVE'}]
        result = next(row for row in evaluate_topology(intent, enriched) if row['ruleId'] == 'constraint:unscoped')
        self.assertEqual(result['outcome'], 'UNKNOWN')

    def test_dynamodb_integral_decimal_port_is_normalized_and_invalid_numbers_skipped(self):
        intent, inventory = fixture()
        intent['relationships'][0]['ports'] = [Decimal('443')]
        enriched = enrich_network_evidence(intent, inventory)
        self.assertEqual(enriched['edges'][0]['ports'], [443])
        self.assertIs(type(self.mock.call_args.args[0]['ports'][0]), int)
        self.mock.reset_mock()
        for value in [Decimal('443.5'), Decimal('NaN'), Decimal('Infinity'), Decimal('0'), Decimal('65536'), True, '443']:
            intent['relationships'][0]['ports'] = [value]
            self.assertEqual(enrich_network_evidence(intent, inventory)['edges'], [])
        self.mock.assert_not_called()


if __name__ == '__main__':
    unittest.main()
