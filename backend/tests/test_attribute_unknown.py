import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from common.attribute_rules import attribute_outcome


class AttributeUnknownTests(unittest.TestCase):
    def ssh(self, rules):
        return attribute_outcome({'type': 'SECURITY_GROUP_NO_OPEN_SSH'}, {
            'resourceType': 'AWS::EC2::SecurityGroup', 'attributes': {'ingressRules': rules}})[0]

    def test_prefix_list_public_source_is_unknown(self):
        self.assertEqual(self.ssh([{'protocol': 'tcp', 'fromPort': 22, 'toPort': 22,
                                    'prefixListId': 'pl-fixture', 'publicSourceUnknown': True}]), 'UNKNOWN')

    def test_missing_public_tcp_port_range_is_unknown(self):
        self.assertEqual(self.ssh([{'protocol': 'tcp', 'cidr': '0.0.0.0/0'}]), 'UNKNOWN')

    def test_known_violation_survives_unresolved_prefix(self):
        self.assertEqual(self.ssh([{'protocol': 'tcp', 'publicSourceUnknown': True},
                                  {'protocol': 'tcp', 'fromPort': 22, 'toPort': 22, 'cidr': '::/0'}]), 'VIOLATION')

    def test_missing_rds_metadata_is_unknown(self):
        outcome, _, _ = attribute_outcome({'type': 'RDS_NOT_PUBLICLY_ACCESSIBLE'}, {
            'resourceType': 'AWS::RDS::DBInstance', 'attributes': {'publiclyAccessible': None}})
        self.assertEqual(outcome, 'UNKNOWN')


if __name__ == '__main__':
    unittest.main()
