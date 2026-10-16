"""Pure, deterministic topology evaluation and graph projection helpers.

The module deliberately does not collect inventory or infer traffic from
containment/configuration. Callers provide a manifest and a bounded inventory
snapshot; this module only interprets those values.
"""
from __future__ import annotations

from collections import defaultdict, deque
from fnmatch import fnmatchcase
from datetime import datetime, timezone
import hashlib
from typing import Any, Iterable

OUTCOMES = {"PASS", "VIOLATION", "UNKNOWN", "NOT_APPLICABLE"}
TOPOLOGY_TYPES = {
    "ALLOWED_PATH", "FORBIDDEN_PATH", "TRUST_BOUNDARY_CROSSING",
    "REQUIRED_INTERMEDIARY", "EXPOSURE_BLAST_RADIUS",
}
DEFAULT_EDGE_TYPES = ("NETWORK_REACHABILITY",)
MAX_VISITED = 20_000
MAX_PATH_DEPTH = 64
STRUCTURAL_TYPES = {
    "BELONGS_TO_VPC", "IN_SUBNET", "USES_SECURITY_GROUP", "IN_VPC",
    "HAS_BELONGS_TO_VPC", "HAS_IN_SUBNET", "HAS_USES_SECURITY_GROUP", "HAS_IN_VPC",
    "DYNAMODB_STREAM_TRIGGER",
    "API_ROUTE", "API_INTEGRATION", "JWT_AUTHORIZER", "JWT_ISSUER", "ASSUMES_ROLE", "IAM_DECLARED_PERMISSION",
}


def _coverage_state(inventory: dict[str, Any], family: str, key: str) -> str:
    """Return explicit coverage, or UNKNOWN for legacy/unstructured snapshots."""
    meta = inventory.get("meta") or {}
    coverage = meta.get("coverage") or inventory.get("coverage") or {}
    group = coverage.get(family, {}) if isinstance(coverage, dict) else {}
    value = group.get(key) if isinstance(group, dict) else None
    if isinstance(value, dict):
        value = value.get("status")
    if isinstance(value, str):
        normalized = value.upper()
        if normalized in {"COMPLETE", "PARTIAL", "UNSUPPORTED"}:
            return normalized
    # Older snapshots have no typed coverage. partial=False is insufficient to
    # prove an individual collection source completed, so absence stays UNKNOWN.
    return "UNKNOWN"


def _resource_coverage(inventory: dict[str, Any], resource_type: str) -> str:
    return _coverage_state(inventory, "resourceTypes", resource_type)


def _relationship_coverage(inventory: dict[str, Any], relationship_type: str) -> str:
    return _coverage_state(inventory, "relationshipTypes", relationship_type)


def _resources(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    return [r for r in inventory.get("items", []) if isinstance(r, dict) and r.get("resourceId")]


def _tags(resource: dict[str, Any]) -> dict[str, str] | None:
    tags = resource.get("tags")
    if isinstance(tags, dict):
        return {str(k): str(v) for k, v in tags.items()}
    if isinstance(tags, list):
        return {str(t.get("Key")): str(t.get("Value")) for t in tags if isinstance(t, dict) and t.get("Key") is not None and t.get("Value") is not None}
    attrs = resource.get("attributes") or {}
    tags = attrs.get("tags")
    if isinstance(tags, dict):
        return {str(k): str(v) for k, v in tags.items()}
    if isinstance(tags, list):
        return {str(t.get("Key")): str(t.get("Value")) for t in tags if isinstance(t, dict) and t.get("Key") is not None and t.get("Value") is not None}
    return None


def _tag_coverage(inventory: dict[str, Any]) -> str:
    """Tags have their own completeness signal; resource coverage is unrelated."""
    meta = inventory.get("meta") or {}
    coverage = meta.get("coverage") or inventory.get("coverage") or {}
    tags = coverage.get("tags") if isinstance(coverage, dict) else None
    if isinstance(tags, dict):
        tags = tags.get("status")
    if isinstance(tags, str) and tags.upper() in {"COMPLETE", "PARTIAL", "UNSUPPORTED"}:
        return tags.upper()
    return _coverage_state(inventory, "relationshipTypes", "TAGS")


def _exposure_state(resource: dict[str, Any]) -> bool | None:
    """Read explicit resource-level exposure evidence without inferring it."""
    attrs = resource.get("attributes") or {}
    for key in ("isExposed", "exposed"):
        if isinstance(attrs.get(key), bool):
            return attrs[key]
    for key in ("publiclyAccessible", "publicAccess"):
        if isinstance(attrs.get(key), bool):
            return attrs[key]
    for key in ("publicIpAddress", "publicIpv4Address"):
        if key in attrs:
            return bool(attrs[key])
    if resource.get("resourceType") == "AWS::EC2::SecurityGroup" and "ingressRules" in attrs:
        for rule in attrs.get("ingressRules") or []:
            if not isinstance(rule, dict):
                continue
            if str(rule.get("cidr", "")) not in {"0.0.0.0/0", "::/0"}:
                continue
            protocol = str(rule.get("protocol", ""))
            if protocol == "-1" or (protocol in {"tcp", "udp", "6", "17"} and rule.get("fromPort") is not None):
                return True
        return False
    return None


def _selector_match(resource: dict[str, Any], selector: dict[str, Any], inventory: dict[str, Any]) -> tuple[bool, bool]:
    """Return (matched, uncertain); alternatives within fields are OR."""
    rid = str(resource.get("resourceId", ""))
    has_criteria = False
    uncertain = False
    ids = selector.get("resourceIds", selector.get("ids"))
    if ids:
        has_criteria = True
        if rid not in ids:
            return False, False
    patterns = selector.get("idPatterns", [])
    if patterns:
        has_criteria = True
        if not any(fnmatchcase(rid, str(pattern)) for pattern in patterns):
            return False, False
    tag_selector = selector.get("tags")
    if tag_selector:
        has_criteria = True
        actual = _tags(resource)
        if actual is None:
            if _tag_coverage(inventory) != "COMPLETE":
                return False, True
            actual = {}
        if not all(actual.get(str(k)) == str(v) for k, v in tag_selector.items()):
            return False, False
    return True, uncertain


def resolve_components(intent: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    """Resolve component selectors without guessing ambiguous membership.

    Returns ``{components: {id: [resource, ...]}, ambiguous: [...], unknown: {...}}``.
    A component may resolve to multiple resources; overlap between components is
    reported as ambiguous and is not silently assigned to either component.
    """
    components = intent.get("components") or []
    resources = _resources(inventory)
    raw: dict[str, list[dict[str, Any]]] = {}
    uncertain: dict[str, list[str]] = defaultdict(list)
    for component in components:
        cid = component.get("id")
        if not cid:
            continue
        types = component.get("resourceTypes") or []
        selector = component.get("selector") or {}
        matches = []
        for resource in resources:
            if types and resource.get("resourceType") not in types:
                continue
            matched, unknown = _selector_match(resource, selector, inventory)
            if matched:
                matches.append(resource)
            elif unknown:
                uncertain[cid].append(resource["resourceId"])
        raw[cid] = matches
    memberships: dict[str, list[str]] = defaultdict(list)
    for cid, matches in raw.items():
        for resource in matches:
            memberships[resource["resourceId"]].append(cid)
    ambiguous = sorted(rid for rid, cids in memberships.items() if len(cids) > 1)
    ambiguous_set = set(ambiguous)
    resolved = {cid: [r for r in matches if r["resourceId"] not in ambiguous_set] for cid, matches in raw.items()}
    ambiguous_components = {cid: sorted(rid for rid, cids in memberships.items() if len(cids) > 1 and cid in cids)
                            for cid in raw if any(len(cids) > 1 and cid in cids for cids in memberships.values())}
    unknown = {cid: sorted(set(ids)) for cid, ids in uncertain.items() if ids}
    return {"components": resolved, "ambiguous": ambiguous, "ambiguousComponents": ambiguous_components, "unknown": unknown}


def _component_ids(resolved: dict[str, Any], cid: str | None) -> set[str]:
    return {r["resourceId"] for r in (resolved.get("components", {}).get(cid, []) if cid else [])}


def _edge_kind(edge: dict[str, Any]) -> str | None:
    kind = edge.get("observationKind")
    if isinstance(kind, str):
        return kind.upper()
    evidence = edge.get("evidence")
    if isinstance(evidence, dict):
        kind = evidence.get("kind") or evidence.get("observationKind")
        if isinstance(kind, str):
            return kind.upper()
    elif isinstance(evidence, list):
        for row in evidence:
            if isinstance(row, dict) and isinstance(row.get("kind"), str):
                return row["kind"].upper()
    typ = str(edge.get("type", edge.get("relationshipType", ""))).upper()
    if typ in STRUCTURAL_TYPES:
        return "STRUCTURAL"
    if typ == "NETWORK_PERMISSION":
        return "CONFIGURED"
    # A NETWORK_REACHABILITY label alone does not establish its evidence class.
    return None


def _edge_category(edge: dict[str, Any]) -> str:
    """Map concrete relationship names to manifest edge evidence categories."""
    typ = str(edge.get("type", edge.get("relationshipType", ""))).upper()
    if typ == "STRUCTURAL" or typ in STRUCTURAL_TYPES:
        return "STRUCTURAL"
    if typ == "NETWORK_PERMISSION":
        return "NETWORK_PERMISSION"
    if typ == "NETWORK_REACHABILITY":
        return "NETWORK_REACHABILITY"
    kind = _edge_kind(edge)
    if kind == "STRUCTURAL":
        return "STRUCTURAL"
    if kind == "CONFIGURED":
        return "NETWORK_PERMISSION"
    if kind == "OBSERVED":
        return "NETWORK_REACHABILITY"
    return "UNKNOWN"


def _expected_edge_kind(relationship_type: str) -> str:
    typ = relationship_type.upper()
    if typ == "STRUCTURAL" or typ in STRUCTURAL_TYPES:
        return "STRUCTURAL"
    if typ == "NETWORK_PERMISSION":
        return "CONFIGURED"
    return "OBSERVED"


def _edge_list(inventory: dict[str, Any], edge_types: Iterable[str]) -> tuple[list[dict[str, Any]], bool]:
    selected = {str(t).upper() for t in edge_types}
    all_edges = inventory.get("edges", []) or []
    edges = []
    uncertain = False
    for edge in all_edges:
        if not isinstance(edge, dict):
            continue
        typ = str(edge.get("type", edge.get("relationshipType", ""))).upper()
        category = _edge_category(edge)
        if category not in selected:
            continue
        kind = _edge_kind(edge)
        if kind is None:
            uncertain = True
        else:
            edges.append({**edge, "_kind": kind, "_type": typ, "_category": category})
    return edges, uncertain


def _adequate_edge(edge: dict[str, Any], accepted: set[str]) -> bool:
    return edge.get("_kind") in accepted


def _selected_edges(inventory: dict[str, Any], edge_types: list[str] | None, accepted: set[str] | None = None) -> tuple[list[dict[str, Any]], bool, bool]:
    types = edge_types or list(DEFAULT_EDGE_TYPES)
    edges, unlabeled = _edge_list(inventory, types)
    valid, insufficient = [], unlabeled
    for edge in edges:
        if edge.get("evidenceScope") == "EXACT_FLOW":
            # Path/boundary rules currently have no protocol/port selector.
            # A sampled tuple cannot establish their unscoped predicate or be
            # joined to another tuple as a transitive path.
            insufficient = True
            continue
        edge_types_allowed = accepted or ({"STRUCTURAL"} if edge["_category"] == "STRUCTURAL" else
                                          {"CONFIGURED"} if edge["_category"] == "NETWORK_PERMISSION" else {"OBSERVED"})
        if _adequate_edge(edge, edge_types_allowed):
            valid.append(edge)
        else:
            insufficient = True
    coverage = all(_relationship_coverage(inventory, t) == "COMPLETE" for t in types)
    return valid, insufficient, coverage


def _witness_edge(edge: dict[str, Any]) -> dict[str, Any]:
    row = {k: v for k, v in edge.items() if not k.startswith("_")}
    row.setdefault("sourceId", edge.get("sourceId"))
    row.setdefault("targetId", edge.get("targetId"))
    row.setdefault("relationshipType", edge.get("type", edge.get("relationshipType")))
    return row


def _declaration_matches_edge(edge: dict[str, Any], declaration: dict[str, Any]) -> bool | None:
    """Match protocol/ports when the observation records them; None is unknown."""
    protocol = declaration.get("protocol")
    ports = declaration.get("ports") or []
    if edge.get("evidenceScope") == "EXACT_FLOW":
        if not protocol or not ports:
            return None
        observed_ports = edge.get("ports") or []
        if set(ports) != set(observed_ports):
            return False if not set(ports).intersection(observed_ports) else None
    if protocol:
        observed_protocol = edge.get("protocol")
        if observed_protocol is None:
            return None
        if str(observed_protocol).lower() != str(protocol).lower():
            return False
    if ports:
        observed_ports = edge.get("ports")
        if observed_ports is None:
            return None
        if isinstance(observed_ports, int):
            observed_ports = [observed_ports]
        if not (set(ports) & set(observed_ports)):
            return False
    return True


def _paths(edges: list[dict[str, Any]], starts: set[str], ends: set[str], *, blocked: set[str] | None = None, max_depth: int = MAX_PATH_DEPTH) -> tuple[list[list[dict[str, Any]]], bool]:
    """Bounded simple-path enumeration; returns paths and whether bound hit."""
    adjacency: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        adjacency[str(edge.get("sourceId"))].append(edge)
    for rows in adjacency.values():
        rows.sort(key=lambda e: (str(e.get("targetId")), str(e.get("_type"))))
    paths: list[list[dict[str, Any]]] = []
    visited_count = 0
    limit_hit = False
    blocked = blocked or set()
    for start in sorted(starts):
        stack = [(start, [], frozenset({start}))]
        while stack:
            node, path, seen = stack.pop()
            if node in ends and path:
                paths.append(path)
                continue
            if len(path) >= max_depth:
                if adjacency.get(node):
                    limit_hit = True
                continue
            for edge in reversed(adjacency.get(node, [])):
                target = str(edge.get("targetId"))
                if target in blocked or target in seen:
                    continue
                visited_count += 1
                if visited_count > MAX_VISITED:
                    return paths, True
                stack.append((target, path + [edge], seen | {target}))
    return paths, limit_hit


def _outcome(rule_id: str, rule_type: str, outcome: str, severity: str, explanation: str,
             witnesses: list[dict[str, Any]] | None = None, evidence: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"ruleId": rule_id, "type": rule_type, "outcome": outcome, "severity": severity,
            "explanation": explanation, "witnesses": witnesses or [], "evidence": evidence or []}


def _rule_id(rule: dict[str, Any], prefix: str = "constraint") -> str:
    return f"{prefix}:{rule.get('id') or rule.get('type') or 'unknown'}"


def _component_outcome(component: dict[str, Any], intent: dict[str, Any], inventory: dict[str, Any],
                       resolved: dict[str, Any]) -> dict[str, Any]:
    cid = str(component.get("id", "unknown"))
    minimum = int(component.get("minMatches", 1))
    severity = str((intent.get("criticality") or {}).get(cid, "MEDIUM")).upper()
    matched = resolved.get("components", {}).get(cid, [])
    ambiguous = resolved.get("ambiguousComponents", {}).get(cid, [])
    unresolved = resolved.get("unknown", {}).get(cid, [])
    resource_types = component.get("resourceTypes") or []
    coverage = {rtype: _resource_coverage(inventory, rtype) for rtype in resource_types}
    coverage_complete = bool(resource_types) and all(state == "COMPLETE" for state in coverage.values())
    selector = component.get("selector") or {}
    tag_coverage = _tag_coverage(inventory) if selector.get("tags") else None
    if minimum == 0:
        return _outcome(f"component:{cid}", "REQUIRED_COMPONENT", "NOT_APPLICABLE", severity,
                        "This component does not require any matches.",
                        evidence=[{"componentId": cid, "minMatches": minimum, "matchedCount": len(matched)}])
    if len(matched) >= minimum:
        return _outcome(f"component:{cid}", "REQUIRED_COMPONENT", "PASS", severity,
                        "The component meets its minimum match count.",
                        [{"resourceId": r["resourceId"], "observed": {"componentId": cid}} for r in matched],
                        [{"componentId": cid, "minMatches": minimum, "matchedCount": len(matched),
                          "ambiguousResourceIds": ambiguous, "unresolvedResourceIds": unresolved}])
    if ambiguous or unresolved or not coverage_complete:
        return _outcome(f"component:{cid}", "REQUIRED_COMPONENT", "UNKNOWN", severity,
                        "The available inventory or selector evidence cannot establish whether the component meets its minimum match count.",
                        evidence=[{"componentId": cid, "minMatches": minimum, "matchedCount": len(matched),
                                   "ambiguousResourceIds": ambiguous, "unresolvedResourceIds": unresolved,
                                   "resourceCoverage": coverage, "tagCoverage": tag_coverage}])
    logical_id = _logical_node_id(intent, cid)
    return _outcome(f"component:{cid}", "REQUIRED_COMPONENT", "VIOLATION", severity,
                    "Complete coverage establishes that the component has fewer matches than required.",
                    [{"resourceId": logical_id, "observed": {"componentId": cid, "matchedCount": len(matched),
                                                               "minMatches": minimum}}],
                    [{"componentId": cid, "minMatches": minimum, "matchedCount": len(matched),
                      "resourceCoverage": coverage, "tagCoverage": tag_coverage}])


def _constraint_outcome(rule: dict[str, Any], intent: dict[str, Any], inventory: dict[str, Any], resolved: dict[str, Any]) -> dict[str, Any]:
    kind = str(rule.get("type", "")).upper()
    rid = _rule_id(rule)
    severity = str(rule.get("severity", "MEDIUM")).upper()
    if kind not in TOPOLOGY_TYPES:
        return _outcome(rid, kind, "NOT_APPLICABLE", severity, "This rule is outside the topology evaluator.")
    edge_types = rule.get("edgeTypes") or list(DEFAULT_EDGE_TYPES)
    edges, edge_uncertain, coverage_complete = _selected_edges(inventory, edge_types)
    witnesses: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = [{"edgeTypes": edge_types, "relationshipCoverage": {t: _relationship_coverage(inventory, t) for t in edge_types}}]
    component_refs = [rule.get(k) for k in ("from", "to", "target", "exposedComponent") if isinstance(rule.get(k), str)]
    for ref in component_refs:
        if resolved.get("unknown", {}).get(ref):
            evidence.append({"componentId": ref, "unresolvedResourceIds": resolved["unknown"][ref]})
    if resolved.get("ambiguous"):
        evidence.append({"ambiguousResourceIds": resolved["ambiguous"]})
    unknown_mapping = bool(resolved.get("ambiguous")) or any(resolved.get("unknown", {}).get(ref) for ref in component_refs)

    if kind == "ALLOWED_PATH":
        target = rule.get("target")
        ends = _component_ids(resolved, target)
        allowed = set(rule.get("allowedSources") or [])
        sources = set().union(*(_component_ids(resolved, cid) for cid in allowed)) if allowed else set()
        target_components = (intent.get("components") or [])
        target_def = next((c for c in target_components if c.get("id") == target), {})
        minimum = int(target_def.get("minMatches", 1))
        if not ends and minimum > 0 and not resolved.get("unknown", {}).get(target):
            state = _resource_coverage(inventory, next(iter(target_def.get("resourceTypes", [])), "")) if target_def.get("resourceTypes") else "UNKNOWN"
            if state == "COMPLETE":
                return _outcome(rid, kind, "UNKNOWN", severity, "No target resource matched; required component absence is distinct from an allowed-path violation.", evidence=evidence)
        mode = str(rule.get("pathMode", "DIRECT")).upper()
        starts = {str(e.get("sourceId")) for e in edges}
        if mode == "DIRECT":
            paths = [[edge] for edge in edges if str(edge.get("targetId")) in ends]
            limited = False
        else:
            paths, limited = _paths(edges, starts, ends)
        for path in paths:
            source = str(path[0].get("sourceId"))
            source_cids = [cid for cid in (rule.get("allowedSources") or []) if source in _component_ids(resolved, cid)]
            if not source_cids:
                witnesses.append({"resourceId": str(path[-1].get("targetId")), "sourceId": source,
                                  "targetId": str(path[-1].get("targetId")), "path": [_witness_edge(e) for e in path],
                                  "observed": {"sourceComponents": source_cids}})
        if witnesses:
            return _outcome(rid, kind, "VIOLATION", severity, "A witnessed path reaches the target from a source outside the explicit allowlist.", witnesses, evidence)
        if limited or edge_uncertain or unknown_mapping or not coverage_complete:
            return _outcome(rid, kind, "UNKNOWN", severity, "No forbidden source was witnessed, but component or relationship coverage cannot establish absence.", evidence=evidence)
        if not ends:
            return _outcome(rid, kind, "NOT_APPLICABLE", severity, "The target component has no applicable resources.", evidence=evidence)
        return _outcome(rid, kind, "PASS", severity, "All evaluated incoming paths originate in the allowed source components.", evidence=evidence)

    if kind in {"FORBIDDEN_PATH", "REQUIRED_INTERMEDIARY"}:
        start = _component_ids(resolved, rule.get("from"))
        end = _component_ids(resolved, rule.get("to"))
        mode = str(rule.get("pathMode", "DIRECT" if kind == "FORBIDDEN_PATH" else "TRANSITIVE")).upper()
        if mode == "DIRECT":
            paths = [[edge] for edge in edges if edge.get("sourceId") in start and edge.get("targetId") in end]
            limited = False
        else:
            paths, limited = _paths(edges, start, end)
        if kind == "FORBIDDEN_PATH":
            for path in paths:
                witnesses.append({"resourceId": str(path[-1].get("targetId")), "sourceId": str(path[0].get("sourceId")),
                                  "targetId": str(path[-1].get("targetId")), "path": [_witness_edge(e) for e in path]})
            if witnesses:
                return _outcome(rid, kind, "VIOLATION", severity, "A forbidden directed path is supported by the selected edge evidence.", witnesses, evidence)
        else:
            via = list(rule.get("via") or [])
            via_ids = [ _component_ids(resolved, cid) for cid in via ]
            for path in paths:
                nodes = [str(path[0].get("sourceId"))] + [str(e.get("targetId")) for e in path]
                ordered = []
                cursor = 1
                for group in via_ids:
                    found = next((i for i in range(cursor, len(nodes) - 1) if nodes[i] in group), None)
                    if found is None:
                        ordered = []
                        break
                    ordered.append(nodes[found]); cursor = found + 1
                if not ordered:
                    witnesses.append({"resourceId": nodes[-1], "sourceId": nodes[0], "targetId": nodes[-1],
                                      "path": [_witness_edge(e) for e in path], "observed": {"requiredIntermediaries": via}})
            if witnesses:
                return _outcome(rid, kind, "VIOLATION", severity, "A source-to-target path bypasses the required intermediary sequence.", witnesses, evidence)
        if limited or edge_uncertain or unknown_mapping or not coverage_complete:
            return _outcome(rid, kind, "UNKNOWN", severity, "The selected graph or component mapping is incomplete, so absence cannot be established.", evidence=evidence)
        if not start or not end:
            return _outcome(rid, kind, "NOT_APPLICABLE", severity, "No source-to-target path is applicable to this snapshot.", evidence=evidence)
        if kind == "REQUIRED_INTERMEDIARY" and not paths:
            return _outcome(rid, kind, "NOT_APPLICABLE", severity, "No source-to-target path is applicable to this snapshot.", evidence=evidence)
        return _outcome(rid, kind, "PASS", severity, "No forbidden path was observed." if kind == "FORBIDDEN_PATH" else "Every evaluated path passes through the required intermediaries.", evidence=evidence)

    if kind == "EXPOSURE_BLAST_RADIUS":
        source_component = rule.get("from", rule.get("exposedComponent"))
        source_resources = resolved.get("components", {}).get(source_component, [])
        exposure_yes = set()
        exposure_no = set()
        exposure_unknown = set()
        for resource in source_resources:
            state = _exposure_state(resource)
            resource_id = resource["resourceId"]
            if state is True:
                exposure_yes.add(resource_id)
            elif state is False:
                exposure_no.add(resource_id)
            else:
                exposure_unknown.add(resource_id)
        starts = exposure_yes
        evidence.append({"sourceComponent": source_component, "exposedResourceIds": sorted(exposure_yes),
                         "unexposedResourceIds": sorted(exposure_no), "exposureUnknownResourceIds": sorted(exposure_unknown)})
        if not starts and exposure_unknown:
            return _outcome(rid, kind, "UNKNOWN", severity, "No source exposure evidence establishes which resources should seed the blast-radius count.", evidence=evidence)
        if not starts:
            if exposure_no:
                return _outcome(rid, kind, "NOT_APPLICABLE", severity, "The source resources have explicit evidence that they are not exposed.", evidence=evidence)
            if resolved.get("unknown", {}).get(source_component) or unknown_mapping:
                return _outcome(rid, kind, "UNKNOWN", severity, "The exposed source component could not be resolved with adequate evidence.", evidence=evidence)
            return _outcome(rid, kind, "NOT_APPLICABLE", severity, "The exposed component has no applicable resources.", evidence=evidence)
        if exposure_unknown:
            unknown_mapping = True
        maximum = int(rule.get("maxReachableNodes", 0))
        adjacency: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for edge in edges:
            adjacency[str(edge.get("sourceId"))].append(edge)
        seen = set(starts)
        queue = deque((node, 0) for node in sorted(starts))
        limited = False
        while queue:
            node, depth = queue.popleft()
            if depth >= MAX_PATH_DEPTH and adjacency.get(node):
                limited = True
            for edge in adjacency.get(node, []):
                target = str(edge.get("targetId"))
                if target not in seen:
                    seen.add(target); queue.append((target, depth + 1))
                    if len(seen) > MAX_VISITED:
                        limited = True; break
        downstream = sorted(seen - starts)
        evidence.append({"sourceComponent": source_component, "reachableNodeCount": len(downstream), "maxReachableNodes": maximum,
                         "reachableResourceIds": downstream})
        if len(downstream) > maximum:
            return _outcome(rid, kind, "VIOLATION", severity, "The observed downstream resource count exceeds the declared blast-radius limit.",
                            [{"resourceId": source, "sourceId": source, "observed": {"reachableResourceIds": downstream, "count": len(downstream)}} for source in sorted(starts)], evidence)
        if limited or edge_uncertain or unknown_mapping or not coverage_complete:
            return _outcome(rid, kind, "UNKNOWN", severity, "The observed count is only a lower bound because graph coverage is incomplete.", evidence=evidence)
        return _outcome(rid, kind, "PASS", severity, "The complete observed downstream count is within the declared limit.", evidence=evidence)

    if kind == "TRUST_BOUNDARY_CROSSING":
        return _boundary_outcome(rule, intent, inventory, resolved, edges, edge_uncertain, coverage_complete, evidence)
    return _outcome(rid, kind, "UNKNOWN", severity, "Rule evaluation is indeterminate.", evidence=evidence)


def _boundary_outcome(rule: dict[str, Any], intent: dict[str, Any], inventory: dict[str, Any], resolved: dict[str, Any],
                      edges: list[dict[str, Any]], edge_uncertain: bool, coverage_complete: bool,
                      evidence: list[dict[str, Any]]) -> dict[str, Any]:
    rid = _rule_id(rule)
    severity = str(rule.get("severity", "MEDIUM")).upper()
    boundaries = intent.get("trustBoundaries") or []
    crossing_rules = rule.get("crossingRules")
    source_zone = rule.get("from")
    if crossing_rules is None:
        # This form evaluates a single explicit crossing declaration.
        crossing_rules = [rule]
    zones = {z.get("id"): z for z in boundaries if z.get("id")}
    from_zone = zones.get(source_zone) if source_zone else None
    if from_zone is None and crossing_rules:
        crossing_id = crossing_rules[0].get("id")
        from_zone = next((z for z in boundaries if any(c.get("id") == crossing_id for c in z.get("crossingRules", []))), None)
    if from_zone is None:
        return _outcome(rid, "TRUST_BOUNDARY_CROSSING", "UNKNOWN", severity,
                        "The source trust boundary could not be resolved.", evidence=evidence)
    source_zone = from_zone.get("id")
    from_ids = set().union(*(_component_ids(resolved, cid) for cid in from_zone.get("members", []))) if from_zone.get("members") else set()
    witnesses: list[dict[str, Any]] = []
    incomplete = edge_uncertain or not coverage_complete or bool(resolved.get("ambiguous"))
    unlisted_witnesses: list[dict[str, Any]] = []
    for crossing in crossing_rules:
        to_zone = zones.get(crossing.get("to"))
        if not to_zone:
            incomplete = True
            evidence.append({"crossingRuleId": crossing.get("id"), "reason": "Boundary reference could not be resolved."})
            continue
        to_ids = set().union(*(_component_ids(resolved, cid) for cid in to_zone.get("members", []))) if to_zone.get("members") else set()
        via = crossing.get("via") or []
        via_sets = [_component_ids(resolved, cid) for cid in via]
        paths, limited = _paths(edges, from_ids, to_ids)
        incomplete = incomplete or limited
        for path in paths:
            source, target = str(path[0].get("sourceId")), str(path[-1].get("targetId"))
            if str(crossing.get("effect", "ALLOW")).upper() == "DENY":
                witnesses.append({"resourceId": target, "sourceId": source, "targetId": target, "path": [_witness_edge(e) for e in path], "observed": {"crossingRuleId": crossing.get("id"), "effect": "DENY"}})
            elif via_sets:
                chain = [source] + [str(e.get("targetId")) for e in path]
                cursor = 0
                passed = True
                for group in via_sets:
                    # Boundary entrypoints may be either endpoint of a crossing.
                    found = next((i for i in range(cursor, len(chain)) if chain[i] in group), None)
                    if found is None:
                        passed = False; break
                    cursor = found + 1
                if not passed:
                    witnesses.append({"resourceId": target, "sourceId": source, "targetId": target, "path": [_witness_edge(e) for e in path], "observed": {"crossingRuleId": crossing.get("id"), "requiredIntermediaries": via}})
        evidence.append({"crossingRuleId": crossing.get("id"), "fromBoundary": from_zone.get("id"), "toBoundary": to_zone.get("id"), "effect": crossing.get("effect", "ALLOW"), "via": via})

    # Only a concrete edge from a zone member into another zone is an unlisted
    # crossing. Transitive paths can traverse several explicitly allowed zones.
    declared_targets = {c.get("to") for c in from_zone.get("crossingRules", []) or []}
    zoned_resources = set().union(*(
        _component_ids(resolved, cid)
        for zone in boundaries for cid in zone.get("members", [])
    )) if boundaries else set()
    unzoned_resources = {r["resourceId"] for r in _resources(inventory)} - zoned_resources
    for other_zone in boundaries:
        if other_zone.get("id") == source_zone or other_zone.get("id") in declared_targets:
            continue
        other_ids = set().union(*(_component_ids(resolved, cid) for cid in other_zone.get("members", []))) if other_zone.get("members") else set()
        for edge in edges:
            if edge.get("sourceId") in from_ids and edge.get("targetId") in other_ids:
                unlisted_witnesses.append({"resourceId": str(edge.get("targetId")), "sourceId": str(edge.get("sourceId")),
                                           "targetId": str(edge.get("targetId")), "path": [_witness_edge(edge)],
                                           "observed": {"unlistedBoundaryCrossing": [source_zone, other_zone.get("id")]}})
    for edge in edges:
        if edge.get("sourceId") in from_ids and edge.get("targetId") in unzoned_resources:
            incomplete = True
            evidence.append({"sourceId": edge.get("sourceId"), "targetId": edge.get("targetId"), "reason": "Target trust boundary is unknown."})
    if witnesses:
        return _outcome(rid, "TRUST_BOUNDARY_CROSSING", "VIOLATION", severity, "An explicit boundary DENY or bypassed required intermediary has a witnessed path.", witnesses, evidence)
    # Unlisted crossings are intentionally ambiguous candidates, not violations.
    if incomplete:
        return _outcome(rid, "TRUST_BOUNDARY_CROSSING", "UNKNOWN", severity, "Boundary membership or directed edge coverage is insufficient to assess crossings.", evidence=evidence)
    if unlisted_witnesses:
        evidence.append({"candidateCrossings": unlisted_witnesses})
        return _outcome(rid, "TRUST_BOUNDARY_CROSSING", "UNKNOWN", severity, "An observed boundary crossing has no explicit rule and remains an ambiguous candidate.", unlisted_witnesses, evidence)
    return _outcome(rid, "TRUST_BOUNDARY_CROSSING", "PASS", severity, "No explicitly denied or bypassing boundary crossing was observed.", evidence=evidence)


def _relationship_outcome(relationship: dict[str, Any], intent: dict[str, Any], inventory: dict[str, Any], resolved: dict[str, Any]) -> dict[str, Any] | None:
    effect = str(relationship.get("effect", "ALLOW")).upper()
    if effect == "ALLOW" and not relationship.get("required", False):
        return None
    rule = {**relationship, "type": "FORBIDDEN_PATH" if effect == "DENY" else "REQUIRED_RELATIONSHIP",
            "pathMode": "DIRECT", "edgeTypes": [relationship.get("relationshipType", DEFAULT_EDGE_TYPES[0])]}
    rid = _rule_id(relationship, "relationship")
    severity = str(relationship.get("severity", "MEDIUM")).upper()
    edge_type = str(relationship.get("relationshipType", DEFAULT_EDGE_TYPES[0])).upper()
    # Relationship edges may declare a structural/configured/observed type. They
    # must match that semantic class exactly; no evidence class is inferred from
    # an untyped NETWORK_REACHABILITY edge.
    accepted = {_expected_edge_kind(edge_type)}
    edges, edge_uncertain = _edge_list(inventory, [edge_type])
    adequate = [e for e in edges if _adequate_edge(e, accepted)]
    incomplete = edge_uncertain or any(not _adequate_edge(e, accepted) for e in edges) or _relationship_coverage(inventory, edge_type) != "COMPLETE"
    starts = _component_ids(resolved, relationship.get("from"))
    ends = _component_ids(resolved, relationship.get("to"))
    matches = []
    flow_unknown_pairs: set[tuple[str, str]] = set()
    for edge in adequate:
        if edge.get("sourceId") not in starts or edge.get("targetId") not in ends:
            continue
        flow_match = _declaration_matches_edge(edge, relationship)
        if flow_match is True:
            matches.append(edge)
        elif flow_match is None:
            incomplete = True
            flow_unknown_pairs.add((str(edge.get("sourceId")), str(edge.get("targetId"))))
    if effect == "DENY" and matches:
        witnesses = [{"resourceId": e.get("targetId"), "sourceId": e.get("sourceId"), "targetId": e.get("targetId"), "path": [_witness_edge(e)]} for e in matches]
        return _outcome(rid, "FORBIDDEN_PATH", "VIOLATION", severity, "An explicitly denied relationship is present in the observed graph.", witnesses,
                        [{"declarationId": relationship.get("id"), "relationshipType": edge_type, "observationKind": _edge_kind(matches[0])}])
    if effect == "ALLOW" and matches:
        # Continue below: one successful binding cannot mask another missing
        # concrete source/target binding.
        pass
    mapping_unknown = (resolved.get("unknown", {}).get(relationship.get("from"))
                       or resolved.get("unknown", {}).get(relationship.get("to"))
                       or resolved.get("ambiguous"))
    if mapping_unknown:
        incomplete = True
    if effect == "DENY":
        if incomplete:
            return _outcome(rid, "FORBIDDEN_PATH", "UNKNOWN", severity,
                            "The selected edge type or component mapping lacks complete evidence, so absence cannot be established.",
                            evidence=[{"declarationId": relationship.get("id"), "relationshipType": edge_type, "coverage": _relationship_coverage(inventory, edge_type)}])
        return _outcome(rid, "FORBIDDEN_PATH", "PASS", severity, "No matching denied relationship was observed.", evidence=[{"declarationId": relationship.get("id"), "relationshipType": edge_type}])
    if not starts or not ends:
        if incomplete:
            return _outcome(rid, "REQUIRED_RELATIONSHIP", "UNKNOWN", severity, "Source or target component resolution is incomplete.", evidence=[{"declarationId": relationship.get("id")}])
        return _outcome(rid, "REQUIRED_RELATIONSHIP", "NOT_APPLICABLE", severity, "The required relationship has no applicable source or target resources.", evidence=[{"declarationId": relationship.get("id")}])
    expected_pairs = {(source, target) for source in starts for target in ends}
    if len(expected_pairs) > MAX_VISITED:
        return _outcome(rid, "REQUIRED_RELATIONSHIP", "UNKNOWN", severity, "The concrete relationship binding count exceeded the evaluation bound.",
                        evidence=[{"declarationId": relationship.get("id"), "bindingCount": len(expected_pairs), "limit": MAX_VISITED}])
    matched_pairs = {(str(edge.get("sourceId")), str(edge.get("targetId"))) for edge in matches}
    missing_pairs = sorted(expected_pairs - matched_pairs)
    unresolved_pairs = sorted(set(missing_pairs) & flow_unknown_pairs)
    proven_missing = [pair for pair in missing_pairs if pair not in flow_unknown_pairs]
    witnesses = [{"resourceId": target, "sourceId": source, "targetId": target,
                  "observed": {"missingRelationshipType": edge_type}}
                 for source, target in proven_missing]
    witnesses.extend({"resourceId": edge.get("targetId"), "sourceId": edge.get("sourceId"),
                      "targetId": edge.get("targetId"), "path": [_witness_edge(edge)]} for edge in matches)
    evidence = [{"declarationId": relationship.get("id"), "relationshipType": edge_type,
                 "expectedBindingCount": len(expected_pairs), "matchedBindingCount": len(matched_pairs),
                 "unknownBindings": [list(pair) for pair in unresolved_pairs]}]
    if unresolved_pairs or mapping_unknown or (missing_pairs and incomplete):
        return _outcome(rid, "REQUIRED_RELATIONSHIP", "UNKNOWN", severity,
                        "At least one concrete source-target binding is unresolved under available evidence.", witnesses, evidence)
    if proven_missing:
        return _outcome(rid, "REQUIRED_RELATIONSHIP", "VIOLATION", severity,
                        "Complete relationship coverage establishes that one or more required concrete bindings are missing.", witnesses,
                        evidence + [{"coverage": "COMPLETE", "missingBindings": [list(pair) for pair in proven_missing]}])
    return _outcome(rid, "REQUIRED_RELATIONSHIP", "PASS", severity,
                    "Every concrete source-target binding has an adequate matching edge witness.", witnesses, evidence)


def evaluate_topology(intent: dict[str, Any], inventory: dict[str, Any]) -> list[dict[str, Any]]:
    """Evaluate topology constraints and declarative relationships.

    The return value is a stable, sorted list of per-rule outcomes. Rule
    declarations are not mutated, and every result carries its coverage/evidence.
    """
    resolved = resolve_components(intent, inventory)
    outcomes: list[dict[str, Any]] = []
    for component in intent.get("components", []) or []:
        if int(component.get("minMatches", 1)) > 0:
            outcomes.append(_component_outcome(component, intent, inventory, resolved))
    represented: set[tuple[Any, ...]] = set()
    for rule in intent.get("constraints", []) or []:
        if rule.get("enabled", True) is False:
            continue
        if str(rule.get("type", "")).upper() not in TOPOLOGY_TYPES:
            continue
        # Boundary constraints enable/report the declared crossing rules. Each
        # crossing is evaluated below under its own stable declaration ID.
        if str(rule.get("type", "")).upper() == "TRUST_BOUNDARY_CROSSING" and intent.get("trustBoundaries"):
            continue
        outcomes.append(_constraint_outcome(rule, intent, inventory, resolved))
        if rule.get("type") == "FORBIDDEN_PATH":
            represented.add(("DENY", rule.get("from"), rule.get("to"), tuple(rule.get("edgeTypes") or DEFAULT_EDGE_TYPES)))
    for relationship in intent.get("relationships", []) or []:
        key = (str(relationship.get("effect", "ALLOW")).upper(), relationship.get("from"), relationship.get("to"), (relationship.get("relationshipType", DEFAULT_EDGE_TYPES[0]),))
        if key in represented:
            continue
        result = _relationship_outcome(relationship, intent, inventory, resolved)
        if result:
            outcomes.append(result)
    # Boundary declarations are independent topology rules, one per crossing.
    for boundary in intent.get("trustBoundaries", []) or []:
        crossings = boundary.get("crossingRules", []) or []
        if not crossings:
            rule = {"id": f"boundary:{boundary.get('id')}", "type": "TRUST_BOUNDARY_CROSSING", "from": boundary.get("id"),
                    "crossingRules": [], "severity": "MEDIUM", "edgeTypes": boundary.get("edgeTypes", list(DEFAULT_EDGE_TYPES))}
            outcomes.append(_constraint_outcome(rule, intent, inventory, resolved))
        for crossing in crossings:
            rule = {"id": crossing.get("id"), "type": "TRUST_BOUNDARY_CROSSING", "from": boundary.get("id"),
                    "crossingRules": [crossing], "severity": crossing.get("severity", "MEDIUM"),
                    "edgeTypes": boundary.get("edgeTypes", list(DEFAULT_EDGE_TYPES))}
            outcomes.append(_constraint_outcome(rule, intent, inventory, resolved))
    return sorted(outcomes, key=lambda row: row["ruleId"])


def _logical_node_id(intent: dict[str, Any], component_id: str) -> str:
    return f"intent:{intent.get('intentId', 'unknown')}:component:{component_id}"


def _graph_node(resource: dict[str, Any], state: str) -> dict[str, Any]:
    return {"id": resource["resourceId"], "label": resource.get("name") or resource["resourceId"],
            "resourceType": resource.get("resourceType"), "diffState": state,
            "properties": resource.get("attributes", {}), "source": resource.get("source"),
            "evidence": resource.get("evidence", [])}


def _graph_edge_id(source: str, typ: str, target: str) -> str:
    raw = f"{source}|{typ}|{target}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def build_graph(intent: dict[str, Any], inventory: dict[str, Any], view: str) -> dict[str, Any]:
    """Build ACTUAL, INTENT, or DIFF graph envelope with stable identifiers."""
    view = str(view).upper()
    if view not in {"ACTUAL", "INTENT", "DIFF"}:
        raise ValueError("view must be ACTUAL, INTENT, or DIFF")
    meta = inventory.get("meta") or {}
    resolved = resolve_components(intent, inventory)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    component_ids = {c.get("id") for c in intent.get("components", []) or [] if c.get("id")}
    relationships = intent.get("relationships", []) or []
    if view in {"ACTUAL", "DIFF"}:
        for resource in sorted(_resources(inventory), key=lambda r: r["resourceId"]):
            mapped = sorted(cid for cid, rows in resolved.get("components", {}).items() if any(x["resourceId"] == resource["resourceId"] for x in rows))
            if view == "ACTUAL":
                state = "UNKNOWN"
            elif mapped:
                state = "MATCHED"
            else:
                # A resource is unexpected only when all declared resource types
                # were covered; otherwise model membership is unresolved.
                wanted_types = {t for c in (intent.get("components") or []) for t in c.get("resourceTypes", [])}
                unzoned_scope = bool(intent.get("trustBoundaries"))
                state = "UNEXPECTED" if not unzoned_scope and wanted_types and all(_resource_coverage(inventory, t) == "COMPLETE" for t in wanted_types) else "UNKNOWN"
            node = _graph_node(resource, state)
            if mapped:
                node["componentIds"] = mapped
            elif view == "DIFF":
                node["explanation"] = "No declared component maps to this observed resource." if state == "UNEXPECTED" else "Component membership is unresolved under available coverage."
            nodes.append(node)
        observed_ids = {r["resourceId"] for r in _resources(inventory)}
        for edge in inventory.get("edges", []) or []:
            source, target = edge.get("sourceId"), edge.get("targetId")
            if not source or not target or source not in observed_ids or target not in observed_ids:
                continue
            typ = str(edge.get("type", edge.get("relationshipType", "UNKNOWN")))
            state = "UNKNOWN"
            if view == "DIFF":
                applicable = [declaration for declaration in relationships
                              if _edge_category(edge) == str(declaration.get("relationshipType", "")).upper()
                              and source in _component_ids(resolved, declaration.get("from"))
                              and target in _component_ids(resolved, declaration.get("to"))]
                if applicable:
                    exact = [declaration for declaration in applicable if _declaration_matches_edge(edge, declaration) is True
                             and _edge_kind(edge) == _expected_edge_kind(str(declaration.get("relationshipType", "")))]
                    unresolved = (_edge_kind(edge) is None
                                  or _edge_kind(edge) != _expected_edge_kind(_edge_category(edge))
                                  or any(_declaration_matches_edge(edge, declaration) is None for declaration in applicable))
                    if exact and any(str(d.get("effect", "ALLOW")).upper() == "DENY" for d in exact):
                        state = "UNEXPECTED"
                    elif exact:
                        state = "MATCHED"
                    elif unresolved:
                        state = "UNKNOWN"
                    else:
                        state = "UNEXPECTED"
                elif _relationship_coverage(inventory, _edge_category(edge)) == "COMPLETE" and _edge_kind(edge):
                    state = "UNEXPECTED"
            edges.append({"id": _graph_edge_id(str(source), typ, str(target)), "source": source, "target": target,
                          "relationshipType": typ, "diffState": state, "observationKind": _edge_kind(edge),
                          "evidence": edge.get("evidence", [])})
    if view in {"INTENT", "DIFF"}:
        for component in intent.get("components", []) or []:
            cid = component.get("id")
            if not cid:
                continue
            mapped = resolved.get("components", {}).get(cid, [])
            minimum = int(component.get("minMatches", 1))
            coverage_complete = bool(component.get("resourceTypes")) and all(_resource_coverage(inventory, t) == "COMPLETE" for t in component.get("resourceTypes", []))
            if view == "INTENT":
                state = "UNKNOWN"
            elif len(mapped) >= minimum:
                state = "MATCHED"
            elif resolved.get("unknown", {}).get(cid):
                state = "UNKNOWN"
            else:
                state = "MISSING" if coverage_complete else "UNKNOWN"
            if view == "INTENT" or state != "MATCHED":
                logical_id = _logical_node_id(intent, cid)
                nodes.append({"id": logical_id, "label": component.get("name", cid), "resourceType": "INTENT_COMPONENT",
                              "diffState": state, "properties": {"componentId": cid, "resourceTypes": component.get("resourceTypes", []),
                              "selector": component.get("selector", {}), "minMatches": minimum}, "componentId": cid,
                              "resourceIds": [r["resourceId"] for r in mapped], "evidence": []})
        for declaration in relationships:
            source_component, target_component = declaration.get("from"), declaration.get("to")
            typ = str(declaration.get("relationshipType", "UNKNOWN"))
            if view == "INTENT":
                source_id = _logical_node_id(intent, source_component or "unknown")
                target_id = _logical_node_id(intent, target_component or "unknown")
                state = "UNKNOWN"
                edges.append({"id": _graph_edge_id(source_id, typ, target_id), "source": source_id, "target": target_id,
                              "relationshipType": typ, "diffState": state, "declarationId": declaration.get("id"),
                              "effect": declaration.get("effect", "ALLOW"), "evidence": []})
            else:
                if str(declaration.get("effect", "ALLOW")).upper() == "DENY" or not declaration.get("required"):
                    continue
                source_rows = resolved.get("components", {}).get(source_component, [])
                target_rows = resolved.get("components", {}).get(target_component, [])
                unknown_component = source_component in resolved.get("unknown", {}) or target_component in resolved.get("unknown", {})
                source_ids = [r["resourceId"] for r in source_rows] or [_logical_node_id(intent, source_component or "unknown")]
                target_ids = [r["resourceId"] for r in target_rows] or [_logical_node_id(intent, target_component or "unknown")]
                if len(source_ids) * len(target_ids) > MAX_VISITED:
                    source_ids = [_logical_node_id(intent, source_component or "unknown")]
                    target_ids = [_logical_node_id(intent, target_component or "unknown")]
                    unknown_component = True
                for source_id in source_ids:
                    for target_id in target_ids:
                        candidates = [e for e in inventory.get("edges", []) or []
                                      if e.get("sourceId") == source_id and e.get("targetId") == target_id
                                      and _edge_category(e) == typ.upper()]
                        exact = [e for e in candidates if _edge_kind(e) == _expected_edge_kind(typ)
                                 and _declaration_matches_edge(e, declaration) is True]
                        uncertain = any(_edge_kind(e) is None or _declaration_matches_edge(e, declaration) is None for e in candidates)
                        if exact:
                            continue  # the observed edge is already in the graph with MATCHED state
                        if candidates:
                            continue  # the observed edge is UNEXPECTED or UNKNOWN and has the stable observed ID
                        if unknown_component:
                            state = "UNKNOWN"
                        elif _relationship_coverage(inventory, typ) == "COMPLETE":
                            state = "MISSING"
                        else:
                            state = "UNKNOWN"
                        if uncertain:
                            state = "UNKNOWN"
                        edges.append({"id": _graph_edge_id(str(source_id), typ, str(target_id)), "source": source_id, "target": target_id,
                                      "relationshipType": typ, "diffState": state, "declarationId": declaration.get("id"),
                                      "effect": declaration.get("effect", "ALLOW"), "evidence": []})
    # Deduplicate identical projections while preserving deterministic order.
    unique_nodes = {node["id"]: node for node in nodes}
    unique_edges = {edge["id"]: edge for edge in edges}
    as_of = meta.get("collectedAt") or intent.get("updatedAt") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {"view": view, "nodes": sorted(unique_nodes.values(), key=lambda n: n["id"]),
            "edges": sorted(unique_edges.values(), key=lambda e: e["id"]),
            "truncated": any(w.get("code") in {"RESOURCE_CAP", "TRUNCATED"} for w in meta.get("warnings", [])),
            "partial": bool(meta.get("partial", False)), "warnings": meta.get("warnings", []),
            "totalNodeCount": len(unique_nodes), "asOf": as_of,
            "intentId": intent.get("intentId"), "intentVersion": intent.get("version"),
            "snapshotId": meta.get("snapshotId"), "coverage": meta.get("coverage", inventory.get("coverage", {}))}
