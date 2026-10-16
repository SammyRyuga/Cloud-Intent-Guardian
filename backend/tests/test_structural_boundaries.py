"""Boundary evidence classes remain explicit for serverless trigger topology."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from common.manifest import validate_manifest, ManifestValidationError
from common.topology import evaluate_topology


def manifest():
    return {'schemaVersion': 2, 'name': 'Guardian structural boundary', 'constraints': [{'id': 'boundary-check', 'type': 'TRUST_BOUNDARY_CROSSING', 'severity': 'HIGH'}],
            'components': [
                {'id': 'data', 'resourceTypes': ['AWS::DynamoDB::Table'], 'selector': {'resourceIds': ['table']}},
                {'id': 'compute', 'resourceTypes': ['AWS::Lambda::Function'], 'selector': {'resourceIds': ['worker']}},
            ], 'trustBoundaries': [
                {'id': 'data-zone', 'members': ['data'], 'edgeTypes': ['STRUCTURAL'],
                 'crossingRules': [{'id': 'trigger-worker', 'to': 'compute-zone', 'effect': 'ALLOW'}]},
                {'id': 'compute-zone', 'members': ['compute'], 'edgeTypes': ['STRUCTURAL'], 'crossingRules': []},
            ]}


def inventory():
    return {'items': [{'resourceId': 'table', 'resourceType': 'AWS::DynamoDB::Table'},
                      {'resourceId': 'worker', 'resourceType': 'AWS::Lambda::Function'}],
            'edges': [{'sourceId': 'table', 'targetId': 'worker', 'type': 'DYNAMODB_STREAM_TRIGGER',
                       'evidence': [{'source': 'lambda:ListEventSourceMappings'}]}],
            'meta': {'coverage': {'resourceTypes': {'AWS::DynamoDB::Table': 'COMPLETE',
                                                   'AWS::Lambda::Function': 'COMPLETE'},
                                  'relationshipTypes': {'STRUCTURAL': 'COMPLETE',
                                                        'NETWORK_REACHABILITY': 'UNSUPPORTED'}}}}


class StructuralBoundaryTests(unittest.TestCase):
    def test_structural_stream_trigger_can_comply_without_network_claim(self):
        intent = validate_manifest(manifest())
        results = evaluate_topology(intent, inventory())
        boundary = next(row for row in results if row['ruleId'] == 'constraint:trigger-worker')
        self.assertEqual(boundary['outcome'], 'PASS')
        self.assertEqual(boundary['evidence'][0]['edgeTypes'], ['STRUCTURAL'])
        intent['trustBoundaries'][0]['crossingRules'][0]['effect'] = 'DENY'
        result = next(row for row in evaluate_topology(intent, inventory()) if row['ruleId'] == 'constraint:trigger-worker')
        self.assertEqual(result['outcome'], 'VIOLATION')

    def test_omitted_boundary_edge_types_preserve_network_default_and_hash_shape(self):
        raw = manifest()
        for zone in raw['trustBoundaries']:
            zone.pop('edgeTypes')
        intent = validate_manifest(raw)
        self.assertNotIn('edgeTypes', intent['trustBoundaries'][0])
        result = next(row for row in evaluate_topology(intent, inventory()) if row['ruleId'] == 'constraint:trigger-worker')
        self.assertEqual(result['outcome'], 'UNKNOWN')
        self.assertEqual(result['evidence'][0]['edgeTypes'], ['NETWORK_REACHABILITY'])

    def test_boundary_edge_types_are_closed_and_strict(self):
        for bad in [[], 'STRUCTURAL', ['DYNAMODB_STREAM_TRIGGER'], ['garbage'], None]:
            raw = manifest()
            raw['trustBoundaries'][0]['edgeTypes'] = bad
            with self.assertRaises(ManifestValidationError):
                validate_manifest(raw)
        raw = manifest()
        raw['trustBoundaries'][0]['edgeTypes'] = ['STRUCTURAL', 'NETWORK_PERMISSION', 'NETWORK_REACHABILITY']
        self.assertEqual(len(validate_manifest(raw)['trustBoundaries'][0]['edgeTypes']), 3)


if __name__ == '__main__':
    unittest.main()
