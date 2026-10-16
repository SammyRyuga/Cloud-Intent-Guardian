"""Unit tests for pure legacy and v2 manifest validation."""
from pathlib import Path
from decimal import Decimal
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from common.manifest import ManifestValidationError, validate_manifest


def component(cid, resource_type="AWS::EC2::Instance", tag=None):
    return {
        "id": cid,
        "resourceTypes": [resource_type],
        "selector": {"tags": {"cig:tier": tag or cid}},
    }


def v2(**updates):
    body = {
        "schemaVersion": 2,
        "name": "Three tier app",
        "description": "A normalized topology policy",
        "components": [component("web"), component("api", tag="api"),
                       component("database", "AWS::RDS::DBInstance", "db")],
        "constraints": [],
    }
    body.update(updates)
    return body


def dynamodb_numbers(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, list):
        return [dynamodb_numbers(item) for item in value]
    if isinstance(value, dict):
        return {key: dynamodb_numbers(item) for key, item in value.items()}
    return value


class ManifestV2Tests(unittest.TestCase):
    def assert_code(self, code, body):
        with self.assertRaises(ManifestValidationError) as caught:
            validate_manifest(body)
        self.assertEqual(caught.exception.code, code)
        self.assertTrue(caught.exception.message)

    def test_legacy_normalization_and_existing_error_codes(self):
        result = validate_manifest({
            "name": "  Legacy  ", "description": " baseline ",
            "constraints": [{"type": "s3_block_public_access", "severity": "high"}],
        })
        self.assertEqual(result["name"], "Legacy")
        self.assertEqual(result["description"], "baseline")
        self.assertNotIn("schemaVersion", result)
        self.assertEqual(result["constraints"][0]["id"], "constraint-1")
        self.assertEqual(result["constraints"][0]["type"], "S3_BLOCK_PUBLIC_ACCESS")
        self.assertTrue(result["constraints"][0]["enabled"])
        self.assert_code("INVALID_NAME", {"name": " ", "constraints": [{"type": "S3_BLOCK_PUBLIC_ACCESS"}]})
        self.assert_code("INVALID_CONSTRAINTS", {"name": "x", "constraints": []})
        self.assert_code("INVALID_CONSTRAINT", {"name": "x", "constraints": [None]})
        self.assert_code("UNSUPPORTED_CONSTRAINT_TYPE", {"name": "x", "constraints": [{"type": "NOPE"}]})
        self.assert_code("INVALID_SEVERITY", {"name": "x", "constraints": [{"type": "S3_BLOCK_PUBLIC_ACCESS", "severity": "URGENT"}]})
        self.assert_code("DUPLICATE_CONSTRAINT_ID", {"name": "x", "constraints": [
            {"id": "same", "type": "S3_BLOCK_PUBLIC_ACCESS"},
            {"id": "same", "type": "S3_BLOCK_PUBLIC_ACCESS"},
        ]})

    def test_v2_validates_and_normalizes_all_topology_rules(self):
        body = v2(
            constraints=[
                {"id": "ssh", "type": "SECURITY_GROUP_NO_OPEN_SSH", "severity": "HIGH"},
                {"id": "allow-db", "type": "ALLOWED_PATH", "target": "database",
                 "allowedSources": ["api"], "pathMode": "transitive"},
                {"id": "forbid-web-db", "type": "FORBIDDEN_PATH", "from": "web", "to": "database"},
                {"id": "zone-check", "type": "TRUST_BOUNDARY_CROSSING"},
                {"id": "via-api", "type": "REQUIRED_INTERMEDIARY", "from": "web", "to": "database", "via": ["api"]},
                {"id": "blast", "type": "EXPOSURE_BLAST_RADIUS", "from": "web", "maxReachableNodes": 5},
            ],
            relationships=[{"id": "api-db", "from": "api", "to": "database", "effect": "allow",
                            "relationshipType": "NETWORK_REACHABILITY", "protocol": "TCP", "ports": [5432], "required": True}],
            trustBoundaries=[
                {"id": "services", "members": ["api"]},
                {"id": "data", "members": ["database"], "crossingRules": [
                    {"id": "api-only", "to": "services", "effect": "ALLOW", "via": ["api"]}]},
            ],
            criticality={"database": "critical"},
        )
        result = validate_manifest(body)
        self.assertEqual(result["schemaVersion"], 2)
        self.assertEqual(result["relationships"][0]["protocol"], "tcp")
        self.assertEqual(result["relationships"][0]["ports"], [5432])
        self.assertEqual(result["constraints"][1]["pathMode"], "TRANSITIVE")
        self.assertEqual(result["criticality"], {"api": "MEDIUM", "database": "CRITICAL", "web": "MEDIUM"})

    def test_topology_only_policy_requires_an_evaluable_declaration(self):
        relation = {"id": "deny", "from": "web", "to": "database", "effect": "DENY",
                    "relationshipType": "NETWORK_REACHABILITY", "protocol": "tcp", "ports": [5432]}
        self.assertEqual(validate_manifest(v2(relationships=[relation]))["relationships"][0]["effect"], "DENY")
        self.assert_code("INVALID_CONSTRAINTS", v2(constraints=[], relationships=[]))
        self.assert_code("INVALID_CONSTRAINTS", v2(constraints=[], relationships=[dict(relation, effect="ALLOW")]))
        self.assert_code("INVALID_CONSTRAINTS", v2(constraints=[], trustBoundaries=[
            {"id": "zone", "members": ["web"]}]))

    def test_component_overlap_and_trust_zone_overlap_are_rejected(self):
        self.assert_code("COMPONENT_SELECTOR_OVERLAP", v2(components=[component("a", tag="same"), component("b", tag="same")]))
        self.assert_code("OVERLAPPING_TRUST_BOUNDARIES", v2(trustBoundaries=[
            {"id": "one", "members": ["web"]}, {"id": "two", "members": ["web"]}],
            relationships=[{"id": "required", "from": "web", "to": "api", "effect": "ALLOW",
                            "relationshipType": "NETWORK_REACHABILITY", "protocol": "tcp", "ports": [443], "required": True}]))

    def test_references_and_duplicate_ids_are_checked(self):
        self.assert_code("UNKNOWN_COMPONENT_REFERENCE", v2(constraints=[
            {"id": "wrong", "type": "FORBIDDEN_PATH", "from": "ghost", "to": "database"}]))
        self.assert_code("INVALID_MANIFEST_ID", v2(constraints=[
            {"type": "SECURITY_GROUP_NO_OPEN_SSH"}]))
        self.assert_code("DUPLICATE_MANIFEST_ID", v2(relationships=[
            {"id": "web", "from": "web", "to": "api", "effect": "ALLOW", "relationshipType": "NETWORK_REACHABILITY", "protocol": "tcp", "ports": [443], "required": True}]))
        self.assert_code("UNKNOWN_TRUST_BOUNDARY_REFERENCE", v2(trustBoundaries=[
            {"id": "zone", "members": ["web"], "crossingRules": [{"id": "cross", "to": "missing", "effect": "DENY"}]}]))
        self.assert_code("UNKNOWN_COMPONENT_REFERENCE", v2(criticality={"ghost": "HIGH"}))

    def test_trust_boundary_allow_deny_conflict_is_rejected(self):
        self.assert_code("CONTRADICTORY_RELATIONSHIPS", v2(trustBoundaries=[
            {"id": "services", "members": ["api"], "crossingRules": [
                {"id": "allow", "to": "data", "effect": "ALLOW", "via": ["api"]},
                {"id": "deny", "to": "data", "effect": "DENY"}]},
            {"id": "data", "members": ["database"]}], constraints=[
                {"id": "ssh", "type": "SECURITY_GROUP_NO_OPEN_SSH"}]))

    def test_ports_protocols_and_contradictory_relationships_are_checked(self):
        base = {"id": "allow", "from": "web", "to": "database", "effect": "ALLOW",
                "relationshipType": "NETWORK_REACHABILITY", "protocol": "tcp", "ports": [5432]}
        self.assert_code("INVALID_RELATIONSHIP", v2(relationships=[dict(base, ports=[0])]))
        self.assert_code("INVALID_RELATIONSHIP", v2(relationships=[dict(base, protocol="icmp")]))
        self.assert_code("CONTRADICTORY_RELATIONSHIPS", v2(relationships=[base, dict(base, id="deny", effect="DENY")]))

    def test_optional_protocol_normalization_is_idempotent_after_dynamodb_round_trip(self):
        payload = v2(
            constraints=[{"id": "blast", "type": "EXPOSURE_BLAST_RADIUS", "from": "web", "maxReachableNodes": 5}],
            relationships=[{"id": "web-api", "from": "web", "to": "api", "effect": "ALLOW",
                            "relationshipType": "NETWORK_REACHABILITY", "required": True}],
            components=[dict(component("web"), minMatches=1), dict(component("api", tag="api"), minMatches=0)],
        )
        normalized = validate_manifest(payload)
        self.assertIsNone(normalized["relationships"][0]["protocol"])
        self.assertEqual(normalized["relationships"][0]["ports"], [])
        self.assertEqual(validate_manifest(normalized), normalized)
        self.assertEqual(validate_manifest(dynamodb_numbers(normalized)), normalized)

    def test_boundary_optional_via_normalization_is_idempotent(self):
        payload = v2(
            relationships=[{"id": "web-api", "from": "web", "to": "api", "effect": "ALLOW", "required": True, "relationshipType": "STRUCTURAL"}],
            trustBoundaries=[
                {"id": "ingress", "members": ["web"], "crossingRules": [
                    {"id": "ingress-services", "to": "services", "effect": "ALLOW"}]},
                {"id": "services", "members": ["api"], "crossingRules": [
                    {"id": "services-data", "to": "data", "effect": "DENY", "via": []}]},
                {"id": "data", "members": ["database"], "crossingRules": []},
            ])
        normalized = validate_manifest(payload)
        self.assertEqual(normalized["trustBoundaries"][0]["crossingRules"][0]["via"], [])
        self.assertEqual(validate_manifest(normalized), normalized)
        self.assertEqual(validate_manifest(dynamodb_numbers(normalized)), normalized)
        from common.versions import content_hash
        self.assertEqual(content_hash(normalized), content_hash(validate_manifest(normalized)))

    def test_required_intermediary_still_rejects_empty_via(self):
        self.assert_code("INVALID_MANIFEST", v2(constraints=[{
            "id": "via-api", "type": "REQUIRED_INTERMEDIARY", "from": "web", "to": "database", "via": []}]))

    def test_dynamodb_decimal_rule_values_normalize_and_fractional_values_fail(self):
        payload = v2(
            constraints=[{"id": "blast", "type": "EXPOSURE_BLAST_RADIUS", "from": "web", "maxReachableNodes": Decimal("2.0")}],
            components=[dict(component("web"), minMatches=Decimal("1.0"))],
        )
        normalized = validate_manifest(payload)
        self.assertIs(type(normalized["constraints"][0]["maxReachableNodes"]), int)
        self.assertIs(type(normalized["components"][0]["minMatches"]), int)
        self.assert_code("INVALID_RULE_SEMANTICS", v2(
            constraints=[{"id": "blast", "type": "EXPOSURE_BLAST_RADIUS", "from": "web", "maxReachableNodes": Decimal("2.5")}],
            components=[component("web")],
        ))

    def test_selector_bounds_glob_grammar_and_size_cap(self):
        too_many = component("bounded")
        too_many["selector"] = {"resourceIds": [f"id-{index}" for index in range(101)]}
        self.assert_code("INVALID_MANIFEST", v2(components=[too_many], constraints=[
            {"id": "ssh", "type": "SECURITY_GROUP_NO_OPEN_SSH"}]))
        invalid_pattern = component("glob")
        invalid_pattern["selector"] = {"idPatterns": ["(.*)\\.exe"]}
        self.assert_code("INVALID_SELECTOR", v2(components=[invalid_pattern], constraints=[
            {"id": "ssh", "type": "SECURITY_GROUP_NO_OPEN_SSH"}]))
        large_components = []
        for index in range(100):
            tags = {f"tag-{index}-{tag}": "v" * 256 for tag in range(20)}
            large_components.append({"id": f"c{index}", "resourceTypes": [f"AWS::Service{index}::Thing"],
                                     "selector": {"tags": tags}})
        self.assert_code("MANIFEST_TOO_LARGE", v2(components=large_components, constraints=[
            {"id": "ssh", "type": "SECURITY_GROUP_NO_OPEN_SSH"}]))

    def test_component_only_manifest_is_not_a_policy(self):
        self.assert_code("INVALID_CONSTRAINTS", v2(constraints=[], relationships=[],
            components=[component("web")]))


if __name__ == "__main__":
    unittest.main()
