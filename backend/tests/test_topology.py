"""Contract tests for the pure topology evaluator and graph projector."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from common.topology import build_graph, evaluate_topology, resolve_components
from common.scenarios import scenario_inventory, scenario_manifest


def resource(rid, tier, rtype="AWS::EC2::Instance"):
    return {"resourceId": rid, "resourceType": rtype, "name": rid, "tags": {"tier": tier}, "attributes": {}}


def inventory(items=(), edges=(), *, complete=True, relationship_types=("NETWORK_REACHABILITY",), resource_types=None, partial=False):
    resource_types = resource_types or sorted({row["resourceType"] for row in items})
    return {"items": list(items), "edges": list(edges), "meta": {
        "partial": partial, "collectedAt": "2026-10-15T00:00:00Z", "snapshotId": "snap-1", "warnings": [],
        "coverage": {
            "resourceTypes": {t: ("COMPLETE" if complete else "PARTIAL") for t in resource_types},
            "relationshipTypes": {t: ("COMPLETE" if complete else "PARTIAL") for t in relationship_types},
        },
    }}


def edge(source, target, typ="NETWORK_REACHABILITY", kind="OBSERVED"):
    return {"sourceId": source, "targetId": target, "type": typ, "observationKind": kind,
            "evidence": [{"kind": kind, "source": "fixture", "observedAt": "2026-10-15T00:00:00Z"}]}


def component(cid, tier, min_matches=1):
    return {"id": cid, "resourceTypes": ["AWS::EC2::Instance"], "selector": {"tags": {"tier": tier}}, "minMatches": min_matches}


class TopologyResolutionTests(unittest.TestCase):
    def test_selector_fields_and_or_semantics_and_globs(self):
        a = resource("i-web-a", "web")
        b = resource("i-web-b", "web")
        c = resource("i-api", "api")
        inv = inventory([a, b, c])
        intent = {"components": [{"id": "web", "resourceTypes": ["AWS::EC2::Instance"],
                                   "selector": {"idPatterns": ["i-web-*", "i-other-*"], "tags": {"tier": "web"}}}]}
        result = resolve_components(intent, inv)
        self.assertEqual([r["resourceId"] for r in result["components"]["web"]], ["i-web-a", "i-web-b"])
        self.assertFalse(result["unknown"])

    def test_missing_tags_are_unknown_without_tag_coverage(self):
        item = {"resourceId": "i-1", "resourceType": "AWS::EC2::Instance", "attributes": {}}
        inv = inventory([item], complete=False)
        result = resolve_components({"components": [component("web", "web")]}, inv)
        self.assertEqual(result["components"]["web"], [])
        self.assertEqual(result["unknown"]["web"], ["i-1"])

    def test_missing_tags_stay_unknown_when_resource_coverage_is_complete(self):
        item = {"resourceId": "i-1", "resourceType": "AWS::EC2::Instance", "attributes": {}}
        result = resolve_components({"components": [component("web", "web")]}, inventory([item]))
        self.assertEqual(result["unknown"]["web"], ["i-1"])

    def test_missing_tags_are_definite_only_with_explicit_tag_coverage(self):
        item = {"resourceId": "i-1", "resourceType": "AWS::EC2::Instance", "attributes": {}}
        inv = inventory([item])
        inv["meta"]["coverage"]["tags"] = "COMPLETE"
        result = resolve_components({"components": [component("web", "web")]}, inv)
        self.assertNotIn("web", result["unknown"])

    def test_overlap_is_reported_and_removed_from_guessed_mappings(self):
        item = resource("i-one", "same")
        inv = inventory([item])
        intent = {"components": [
            {"id": "a", "resourceTypes": ["AWS::EC2::Instance"], "selector": {"resourceIds": ["i-one"]}},
            {"id": "b", "resourceTypes": ["AWS::EC2::Instance"], "selector": {"tags": {"tier": "same"}}},
        ]}
        result = resolve_components(intent, inv)
        self.assertEqual(result["ambiguous"], ["i-one"])
        self.assertEqual(result["components"], {"a": [], "b": []})


class TopologyEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.web = resource("web-1", "web")
        self.api = resource("api-1", "api")
        self.db = resource("db-1", "db")
        self.intent = {"intentId": "intent-1", "components": [component("web", "web"), component("api", "api"), component("db", "db")]}

    def outcome(self, intent, inv, rule_id):
        return next(row for row in evaluate_topology(intent, inv) if row["ruleId"] == rule_id)

    def test_required_component_shortfall_is_a_criticality_severity_violation(self):
        intent = {"intentId": "required-component", "components": [
            {"id": "api", "resourceTypes": ["AWS::EC2::Instance"], "selector": {"tags": {"tier": "api"}}, "minMatches": 2}],
            "criticality": {"api": "HIGH"}}
        result = self.outcome(intent, inventory([self.api]), "component:api")
        self.assertEqual(result["type"], "REQUIRED_COMPONENT")
        self.assertEqual(result["outcome"], "VIOLATION")
        self.assertEqual(result["severity"], "HIGH")
        self.assertEqual(result["witnesses"][0]["resourceId"], "intent:required-component:component:api")

    def test_required_component_shortfall_is_unknown_with_incomplete_mapping(self):
        component_def = {"id": "api", "resourceTypes": ["AWS::EC2::Instance"],
                         "selector": {"tags": {"tier": "api"}}, "minMatches": 2}
        intent = {"components": [component_def]}
        no_tags = {"resourceId": "untagged", "resourceType": "AWS::EC2::Instance", "attributes": {}}
        missing_tag_result = self.outcome(intent, inventory([no_tags]), "component:api")
        self.assertEqual(missing_tag_result["outcome"], "UNKNOWN")
        partial_result = self.outcome(intent, inventory([], complete=False), "component:api")
        self.assertEqual(partial_result["outcome"], "UNKNOWN")
        overlap_intent = {"components": [component_def, {"id": "same", "resourceTypes": ["AWS::EC2::Instance"],
                                                             "selector": {"tags": {"tier": "api"}}, "minMatches": 1}]}
        overlap_result = self.outcome(overlap_intent, inventory([self.api]), "component:api")
        self.assertEqual(overlap_result["outcome"], "UNKNOWN")

    def test_required_relationship_missing_only_violates_with_complete_coverage(self):
        intent = {**self.intent, "relationships": [{"id": "web-api", "from": "web", "to": "api", "effect": "ALLOW",
                                                      "relationshipType": "NETWORK_REACHABILITY", "required": True}]}
        complete = inventory([self.web, self.api], [], relationship_types=["NETWORK_REACHABILITY"])
        partial = inventory([self.web, self.api], [], complete=False, relationship_types=["NETWORK_REACHABILITY"])
        self.assertEqual(self.outcome(intent, complete, "relationship:web-api")["outcome"], "VIOLATION")
        self.assertEqual(self.outcome(intent, partial, "relationship:web-api")["outcome"], "UNKNOWN")

    def test_required_relationship_checks_every_concrete_binding(self):
        sources = [resource("web-1", "web"), resource("web-2", "web")]
        targets = [resource("api-1", "api"), resource("api-2", "api")]
        intent = {"components": [component("web", "web"), component("api", "api")],
                  "relationships": [{"id": "all-bindings", "from": "web", "to": "api", "effect": "ALLOW",
                                     "relationshipType": "NETWORK_REACHABILITY", "required": True}]}
        result = self.outcome(intent, inventory(sources + targets, [edge("web-1", "api-1")]), "relationship:all-bindings")
        self.assertEqual(result["outcome"], "VIOLATION")
        missing = [w for w in result["witnesses"] if "observed" in w]
        self.assertEqual(len(missing), 3)

    def test_deny_relationship_is_a_direct_violation_with_witness(self):
        intent = {**self.intent, "relationships": [{"id": "deny", "from": "web", "to": "db", "effect": "DENY",
                                                      "relationshipType": "NETWORK_REACHABILITY"}]}
        inv = inventory([self.web, self.db], [edge("web-1", "db-1")])
        result = self.outcome(intent, inv, "relationship:deny")
        self.assertEqual(result["outcome"], "VIOLATION")
        self.assertEqual(result["witnesses"][0]["path"][0]["observationKind"], "OBSERVED")

    def test_protocol_and_port_declarations_require_matching_observation(self):
        relation = {"id": "deny-db", "from": "web", "to": "db", "effect": "DENY",
                    "relationshipType": "NETWORK_REACHABILITY", "protocol": "tcp", "ports": [5432]}
        intent = {**self.intent, "relationships": [relation]}
        missing_fields = inventory([self.web, self.db], [edge("web-1", "db-1")])
        self.assertEqual(self.outcome(intent, missing_fields, "relationship:deny-db")["outcome"], "UNKNOWN")
        exact = edge("web-1", "db-1")
        exact.update({"protocol": "tcp", "ports": [5432]})
        found = self.outcome(intent, inventory([self.web, self.db], [exact]), "relationship:deny-db")
        self.assertEqual(found["outcome"], "VIOLATION")

    def test_bare_reachability_label_does_not_establish_a_path(self):
        intent = {**self.intent, "relationships": [{"id": "deny", "from": "web", "to": "db", "effect": "DENY",
                                                      "relationshipType": "NETWORK_REACHABILITY"}]}
        inv = inventory([self.web, self.db], [{"sourceId": "web-1", "targetId": "db-1", "type": "NETWORK_REACHABILITY"}])
        self.assertEqual(self.outcome(intent, inv, "relationship:deny")["outcome"], "UNKNOWN")

    def test_configured_kind_on_reachability_type_is_not_observed(self):
        intent = {**self.intent, "relationships": [{"id": "deny", "from": "web", "to": "db", "effect": "DENY",
                                                      "relationshipType": "NETWORK_REACHABILITY"}]}
        inv = inventory([self.web, self.db], [edge("web-1", "db-1", "NETWORK_REACHABILITY", "CONFIGURED")])
        self.assertEqual(self.outcome(intent, inv, "relationship:deny")["outcome"], "UNKNOWN")

    def test_structural_edge_cannot_be_used_as_network_reachability(self):
        intent = {**self.intent, "constraints": [{"id": "no-db-path", "type": "FORBIDDEN_PATH", "from": "web", "to": "db",
                                                   "edgeTypes": ["NETWORK_REACHABILITY"], "severity": "HIGH"}]}
        inv = inventory([self.web, self.db], [edge("web-1", "db-1", "IN_VPC", "STRUCTURAL")])
        self.assertEqual(self.outcome(intent, inv, "constraint:no-db-path")["outcome"], "PASS")

    def test_configured_permission_is_eligible_only_when_explicitly_selected(self):
        intent = {**self.intent, "constraints": [{"id": "configured", "type": "FORBIDDEN_PATH", "from": "web", "to": "db",
                                                   "edgeTypes": ["NETWORK_PERMISSION"]}]}
        inv = inventory([self.web, self.db], [edge("web-1", "db-1", "NETWORK_PERMISSION", "CONFIGURED")],
                        relationship_types=["NETWORK_PERMISSION"])
        self.assertEqual(self.outcome(intent, inv, "constraint:configured")["outcome"], "VIOLATION")

    def test_direct_and_transitive_forbidden_paths(self):
        edges = [edge("web-1", "api-1"), edge("api-1", "db-1")]
        inv = inventory([self.web, self.api, self.db], edges)
        direct = {**self.intent, "constraints": [{"id": "direct", "type": "FORBIDDEN_PATH", "from": "web", "to": "db", "pathMode": "DIRECT"}]}
        transitive = {**self.intent, "constraints": [{"id": "transitive", "type": "FORBIDDEN_PATH", "from": "web", "to": "db", "pathMode": "TRANSITIVE"}]}
        self.assertEqual(self.outcome(direct, inv, "constraint:direct")["outcome"], "PASS")
        found = self.outcome(transitive, inv, "constraint:transitive")
        self.assertEqual(found["outcome"], "VIOLATION")
        self.assertEqual([e["sourceId"] for e in found["witnesses"][0]["path"]], ["web-1", "api-1"])

    def test_allowed_path_detects_an_outside_source(self):
        stranger = resource("rogue-1", "rogue")
        intent = {**self.intent, "components": [component("api", "api"), component("db", "db"), component("rogue", "rogue")],
                  "constraints": [{"id": "allow-api", "type": "ALLOWED_PATH", "target": "db", "allowedSources": ["api"], "pathMode": "DIRECT"}]}
        result = self.outcome(intent, inventory([self.api, self.db, stranger], [edge("rogue-1", "db-1")]), "constraint:allow-api")
        self.assertEqual(result["outcome"], "VIOLATION")
        self.assertEqual(result["witnesses"][0]["sourceId"], "rogue-1")

    def test_required_intermediary_reports_bypass_and_passes_ordered_path(self):
        base = {**self.intent, "constraints": [{"id": "through-api", "type": "REQUIRED_INTERMEDIARY", "from": "web", "to": "db", "via": ["api"]}]}
        path = [edge("web-1", "api-1"), edge("api-1", "db-1")]
        self.assertEqual(self.outcome(base, inventory([self.web, self.api, self.db], path), "constraint:through-api")["outcome"], "PASS")
        bypass = path + [edge("web-1", "db-1")]
        found = self.outcome(base, inventory([self.web, self.api, self.db], bypass), "constraint:through-api")
        self.assertEqual(found["outcome"], "VIOLATION")
        self.assertEqual(found["witnesses"][0]["observed"]["requiredIntermediaries"], ["api"])

    def test_boundary_deny_and_unlisted_crossing(self):
        intent = {**self.intent, "trustBoundaries": [
            {"id": "edge", "members": ["web"], "crossingRules": [{"id": "deny-data", "to": "data", "effect": "DENY"}]},
            {"id": "data", "members": ["db"], "crossingRules": []},
            {"id": "services", "members": ["api"], "crossingRules": []},
        ]}
        denied = inventory([self.web, self.db], [edge("web-1", "db-1")])
        result = self.outcome(intent, denied, "constraint:deny-data")
        self.assertEqual(result["outcome"], "VIOLATION")
        candidate = inventory([self.web, self.api], [edge("web-1", "api-1")])
        result = self.outcome(intent, candidate, "constraint:deny-data")
        self.assertEqual(result["outcome"], "UNKNOWN")
        self.assertTrue(result["witnesses"])

    def test_bundled_benign_scenario_has_no_false_positive_and_unruled_crossing_is_unknown(self):
        intent = scenario_manifest()
        benign = evaluate_topology(intent, scenario_inventory("benign"))
        self.assertFalse([row for row in benign if row["outcome"] == "VIOLATION"])
        crossing = evaluate_topology(intent, scenario_inventory("unruled-crossing"))
        self.assertTrue(any(row["type"] == "TRUST_BOUNDARY_CROSSING" and row["outcome"] == "UNKNOWN" for row in crossing))

    def test_blast_radius_counts_unique_reachable_nodes(self):
        intent = {**self.intent, "constraints": [{"id": "blast", "type": "EXPOSURE_BLAST_RADIUS", "from": "web", "maxReachableNodes": 1}]}
        self.web["attributes"]["isExposed"] = True
        edges = [edge("web-1", "api-1"), edge("web-1", "db-1"), edge("api-1", "db-1"), edge("db-1", "web-1")]
        result = self.outcome(intent, inventory([self.web, self.api, self.db], edges), "constraint:blast")
        self.assertEqual(result["outcome"], "VIOLATION")
        count_evidence = next(e for e in result["evidence"] if "reachableNodeCount" in e)
        self.assertEqual(count_evidence["reachableNodeCount"], 2)

    def test_blast_radius_requires_explicit_exposure_evidence(self):
        intent = {**self.intent, "constraints": [{"id": "blast", "type": "EXPOSURE_BLAST_RADIUS", "from": "web", "maxReachableNodes": 5}]}
        inv = inventory([self.web, self.api], [edge("web-1", "api-1")])
        self.assertEqual(self.outcome(intent, inv, "constraint:blast")["outcome"], "UNKNOWN")
        self.web["attributes"]["isExposed"] = False
        self.assertEqual(self.outcome(intent, inv, "constraint:blast")["outcome"], "NOT_APPLICABLE")

    def test_absence_and_missing_components_are_unknown_without_typed_coverage(self):
        intent = {**self.intent, "relationships": [{"id": "required", "from": "web", "to": "db", "effect": "ALLOW", "required": True}]}
        inv = {"items": [self.web, self.db], "edges": [], "meta": {"partial": False, "warnings": []}}
        self.assertEqual(self.outcome(intent, inv, "relationship:required")["outcome"], "UNKNOWN")
        empty_intent = {"components": [component("web", "web")], "relationships": []}
        self.assertEqual(build_graph(empty_intent, inv, "DIFF")["nodes"][0]["diffState"], "UNKNOWN")

    def test_disabled_constraint_is_not_evaluated_and_non_topology_is_skipped(self):
        intent = {"constraints": [
            {"id": "off", "type": "FORBIDDEN_PATH", "from": "a", "to": "b", "enabled": False},
            {"id": "old", "type": "SECURITY_GROUP_NO_OPEN_SSH"},
        ]}
        self.assertEqual(evaluate_topology(intent, inventory()), [])


class GraphProjectionTests(unittest.TestCase):
    def setUp(self):
        self.web = resource("web-1", "web")
        self.api = resource("api-1", "api")
        self.intent = {"intentId": "intent-1", "version": 3,
                       "components": [component("web", "web"), component("api", "api"), component("db", "db")],
                       "relationships": [{"id": "web-api", "from": "web", "to": "api", "effect": "ALLOW", "required": True,
                                          "relationshipType": "NETWORK_REACHABILITY"}]}

    def test_actual_is_observation_only_and_omits_dangling_edges(self):
        inv = inventory([self.web, self.api], [edge("web-1", "api-1"), edge("missing", "api-1")])
        graph = build_graph(self.intent, inv, "ACTUAL")
        self.assertEqual({n["id"] for n in graph["nodes"]}, {"web-1", "api-1"})
        self.assertEqual(len(graph["edges"]), 1)
        self.assertEqual(graph["nodes"][0]["diffState"], "UNKNOWN")

    def test_intent_projection_uses_stable_namespaced_ids(self):
        graph = build_graph(self.intent, inventory(), "INTENT")
        self.assertIn("intent:intent-1:component:web", {n["id"] for n in graph["nodes"]})
        self.assertIn("intent:intent-1:component:db", {n["id"] for n in graph["nodes"]})
        self.assertTrue(all(n["diffState"] == "UNKNOWN" for n in graph["nodes"]))
        self.assertEqual(graph["intentVersion"], 3)

    def test_diff_distinguishes_matched_missing_unexpected_and_unknown(self):
        unknown_resource = resource("other-1", "other", "AWS::EC2::Volume")
        inv = inventory([self.web, self.api, unknown_resource], [edge("web-1", "api-1")],
                        resource_types=["AWS::EC2::Instance", "AWS::EC2::Volume"])
        graph = build_graph(self.intent, inv, "DIFF")
        states = {n["id"]: n["diffState"] for n in graph["nodes"]}
        self.assertEqual(states["web-1"], "MATCHED")
        self.assertEqual(states["api-1"], "MATCHED")
        self.assertEqual(states["intent:intent-1:component:db"], "MISSING")
        self.assertEqual(states["other-1"], "UNEXPECTED")
        self.assertEqual(graph["edges"][0]["diffState"], "MATCHED")

    def test_untyped_relationship_diff_remains_unknown(self):
        inv = inventory([self.web, self.api], [{"sourceId": "web-1", "targetId": "api-1", "type": "NETWORK_REACHABILITY"}])
        graph = build_graph(self.intent, inv, "DIFF")
        self.assertEqual(next(e for e in graph["edges"] if e["source"] == "web-1")["diffState"], "UNKNOWN")

    def test_required_component_min_matches_cardinality(self):
        intent = {"intentId": "intent-2", "components": [
            {"id": "web", "resourceTypes": ["AWS::EC2::Instance"], "selector": {"tags": {"tier": "web"}}, "minMatches": 2}],
            "relationships": []}
        graph = build_graph(intent, inventory([self.web]), "DIFF")
        logical = next(n for n in graph["nodes"] if n["id"] == "intent:intent-2:component:web")
        self.assertEqual(logical["diffState"], "MISSING")
        self.assertEqual(logical["resourceIds"], ["web-1"])

    def test_diff_edges_never_reference_absent_nodes(self):
        graph = build_graph(self.intent, inventory([self.web, self.api], [edge("web-1", "api-1")]), "DIFF")
        node_ids = {node["id"] for node in graph["nodes"]}
        self.assertTrue(all(edge["source"] in node_ids and edge["target"] in node_ids for edge in graph["edges"]))

    def test_denied_observed_relationship_is_unexpected_in_diff(self):
        intent = {"intentId": "intent-deny", "components": [component("web", "web"), component("api", "api")],
                  "relationships": [{"id": "deny", "from": "web", "to": "api", "effect": "DENY",
                                     "relationshipType": "NETWORK_REACHABILITY"}]}
        graph = build_graph(intent, inventory([self.web, self.api], [edge("web-1", "api-1")]), "DIFF")
        observed = next(e for e in graph["edges"] if e["source"] == "web-1")
        self.assertEqual(observed["diffState"], "UNEXPECTED")

    def test_protocol_mismatch_is_not_a_matched_diff_edge(self):
        intent = {"intentId": "intent-protocol", "components": [component("web", "web"), component("api", "api")],
                  "relationships": [{"id": "web-api", "from": "web", "to": "api", "effect": "ALLOW", "required": True,
                                     "relationshipType": "NETWORK_REACHABILITY", "protocol": "tcp", "ports": [443]}]}
        observed_edge = edge("web-1", "api-1")
        observed_edge.update({"protocol": "udp", "ports": [443]})
        graph = build_graph(intent, inventory([self.web, self.api], [observed_edge]), "DIFF")
        observed = next(e for e in graph["edges"] if e["source"] == "web-1")
        self.assertEqual(observed["diffState"], "UNEXPECTED")

    def test_observed_edge_ids_keep_legacy_hash_and_intent_has_as_of(self):
        graph = build_graph(self.intent, inventory([self.web, self.api], [edge("web-1", "api-1")]), "ACTUAL")
        import hashlib
        expected = hashlib.sha256(b"web-1|NETWORK_REACHABILITY|api-1").hexdigest()[:24]
        self.assertEqual(graph["edges"][0]["id"], expected)
        intent_graph = build_graph(self.intent, {"items": [], "edges": [], "meta": {}}, "INTENT")
        self.assertTrue(intent_graph["asOf"])

    def test_view_validation_and_stable_ids(self):
        inv = inventory([self.web, self.api], [edge("web-1", "api-1")])
        first = build_graph(self.intent, inv, "ACTUAL")
        second = build_graph(self.intent, inv, "ACTUAL")
        self.assertEqual([e["id"] for e in first["edges"]], [e["id"] for e in second["edges"]])
        with self.assertRaises(ValueError):
            build_graph(self.intent, inv, "BAD")


if __name__ == "__main__":
    unittest.main()
