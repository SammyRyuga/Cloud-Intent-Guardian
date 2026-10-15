"""Pure severity formula and evidence-bound traversal regressions."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from common.severity import _label, decorate_finding


def component(cid, rid):
    return {"id": cid, "resourceTypes": ["AWS::EC2::Instance"],
            "selector": {"resourceIds": [rid]}, "minMatches": 1}


def inventory(items, edges=None, coverage="COMPLETE", partial=False):
    return {"items": items, "edges": edges or [], "meta": {
        "partial": partial, "coverage": {"relationshipTypes": {"NETWORK_REACHABILITY": coverage}}}}


def node(rid, resource_type="AWS::EC2::Instance", attributes=None):
    return {"resourceId": rid, "resourceType": resource_type, "attributes": attributes or {}}


def observed(source, target):
    return {"sourceId": source, "targetId": target, "type": "NETWORK_REACHABILITY",
            "observationKind": "OBSERVED", "evidence": [{"kind": "OBSERVED"}]}


class SeverityTests(unittest.TestCase):
    def test_invalid_confidence_fails_closed(self):
        scored = decorate_finding({"severity": "HIGH", "confidence": "invalid"}, {}, inventory([]))
        self.assertEqual(scored["confidence"], "LOW")
        self.assertEqual(scored["severityFactors"]["confidence"]["points"], 5)

    def test_label_thresholds_are_exact(self):
        cases = [(9, "INFO"), (10, "LOW"), (29, "LOW"), (30, "MEDIUM"),
                 (59, "MEDIUM"), (60, "HIGH"), (84, "HIGH"), (85, "CRITICAL"), (100, "CRITICAL")]
        for score, expected in cases:
            with self.subTest(score=score):
                self.assertEqual(_label(score), expected)

    def test_high_base_is_not_lowered_by_low_confidence(self):
        intent = {"components": [], "criticality": {}}
        inv = inventory([node("db", "AWS::RDS::DBInstance", {"publiclyAccessible": True})])
        high = decorate_finding({"severity": "HIGH", "ruleId": "RDS_NOT_PUBLICLY_ACCESSIBLE", "resourceId": "db"}, intent, inv)
        low_confidence = decorate_finding({"severity": "HIGH", "confidence": "LOW",
                                           "ruleId": "RDS_NOT_PUBLICLY_ACCESSIBLE", "resourceId": "db"}, intent, inv)
        self.assertEqual(high["constraintSeverity"], "HIGH")
        self.assertGreaterEqual(low_confidence["severityScore"], high["severityScore"])
        self.assertGreaterEqual(low_confidence["severityScore"], 70)
        self.assertIn(low_confidence["severity"], {"HIGH", "CRITICAL"})
        self.assertEqual(low_confidence["severityFactors"]["confidence"]["points"], 5)

    def test_highest_criticality_across_multicomponent_witness_is_used(self):
        intent = {"components": [component("web", "web-i"), component("database", "db-i")],
                  "criticality": {"web": "LOW", "database": "CRITICAL"}}
        inv = inventory([node("web-i"), node("db-i")], [observed("web-i", "db-i")])
        finding = {"severity": "HIGH", "resourceId": "db-i", "observed": {
            "sourceId": "web-i", "targetId": "db-i", "path": [observed("web-i", "db-i")]}}
        scored = decorate_finding(finding, intent, inv)
        component_factor = scored["severityFactors"]["componentCriticality"]
        self.assertEqual(component_factor["label"], "CRITICAL")
        self.assertEqual(component_factor["points"], 15)
        self.assertEqual(component_factor["componentIds"], ["database", "web"])
        self.assertFalse(component_factor["defaulted"])

    def test_missing_component_criticality_defaults_to_medium(self):
        intent = {"components": [component("service", "svc")], "criticality": {}}
        scored = decorate_finding({"severity": "MEDIUM", "resourceId": "svc"}, intent,
                                  inventory([node("svc")]))
        factor = scored["severityFactors"]["componentCriticality"]
        self.assertEqual((factor["label"], factor["points"], factor["defaulted"]), ("MEDIUM", 5, True))
        self.assertIn("defaults to MEDIUM", factor["explanation"])

    def test_blast_radius_counts_unique_observed_reachability_only(self):
        intent = {"components": [], "criticality": {}}
        edges = [observed("source", "a"), observed("a", "b"), observed("b", "source"),
                 {"sourceId": "b", "targetId": "structural", "type": "IN_VPC",
                  "observationKind": "STRUCTURAL"},
                 {"sourceId": "b", "targetId": "configured", "type": "NETWORK_PERMISSION",
                  "observationKind": "CONFIGURED"}]
        inv = inventory([node(value) for value in ("source", "a", "b", "structural", "configured")], edges)
        scored = decorate_finding({"severity": "MEDIUM", "resourceId": "source", "sourceId": "source"}, intent, inv)
        factor = scored["severityFactors"]["blastRadius"]
        self.assertEqual(factor["count"], 2)
        self.assertEqual(factor["points"], 2)
        self.assertTrue(factor["complete"])
        self.assertEqual(factor["downstreamResourceIds"], ["a", "b"])

    def test_incomplete_reachability_is_a_lower_bound_not_zero_complete(self):
        intent = {"components": [], "criticality": {}}
        inv = inventory([node("source"), node("target")], [observed("source", "target")],
                        coverage="PARTIAL", partial=True)
        scored = decorate_finding({"severity": "HIGH", "resourceId": "source", "sourceId": "source"}, intent, inv)
        factor = scored["severityFactors"]["blastRadius"]
        self.assertEqual(factor["count"], 1)
        self.assertFalse(factor["complete"])
        self.assertIn("lower bound", factor["explanation"])

    def test_exposure_requires_explicit_positive_or_negative_evidence(self):
        intent = {"components": [], "criticality": {}}
        unknown = decorate_finding({"severity": "LOW", "resourceId": "db"}, intent,
                                   inventory([node("db", "AWS::RDS::DBInstance", {})]))
        public = decorate_finding({"severity": "LOW", "ruleId": "RDS_NOT_PUBLICLY_ACCESSIBLE", "resourceId": "db"}, intent,
                                  inventory([node("db", "AWS::RDS::DBInstance", {"publiclyAccessible": True})]))
        internal = decorate_finding({"severity": "LOW", "ruleId": "RDS_NOT_PUBLICLY_ACCESSIBLE", "resourceId": "db"}, intent,
                                    inventory([node("db", "AWS::RDS::DBInstance", {"publiclyAccessible": False})]))
        self.assertEqual(unknown["severityFactors"]["exposure"]["label"], "UNKNOWN")
        self.assertEqual(unknown["severityFactors"]["exposure"]["points"], 5)
        self.assertEqual(public["severityFactors"]["exposure"]["label"], "PUBLIC")
        self.assertEqual(public["severityFactors"]["exposure"]["points"], 10)
        self.assertEqual(internal["severityFactors"]["exposure"]["label"], "INTERNAL")
        self.assertEqual(internal["severityFactors"]["exposure"]["points"], 0)

    def test_score_caps_at_100_and_does_not_mutate_input(self):
        intent = {"components": [component("critical", "i")], "criticality": {"critical": "CRITICAL"}}
        inv = inventory([node("i", attributes={"publicIpAddress": "198.51.100.9"})],
                        [observed("i", f"n{index}") for index in range(12)] +
                        [node(f"n{index}") for index in range(12)])
        original = {"severity": "CRITICAL", "confidence": "LOW", "resourceId": "i", "sourceId": "i"}
        scored = decorate_finding(original, intent, inv)
        self.assertEqual(scored["severityScore"], 100)
        self.assertEqual(scored["severity"], "CRITICAL")
        self.assertNotIn("severityScore", original)
        self.assertEqual(original["severity"], "CRITICAL")


if __name__ == "__main__":
    unittest.main()
