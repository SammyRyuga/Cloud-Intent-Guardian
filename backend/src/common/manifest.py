"""Pure validation and normalization for legacy and topology-aware intents."""
from __future__ import annotations

import fnmatch
import json
import re
from decimal import Decimal
from typing import Any


ATTRIBUTE_TYPES = {
    "S3_BLOCK_PUBLIC_ACCESS": "AWS::S3::Bucket",
    "EC2_NO_PUBLIC_IP": "AWS::EC2::Instance",
    "RDS_NOT_PUBLICLY_ACCESSIBLE": "AWS::RDS::DBInstance",
    "SECURITY_GROUP_NO_OPEN_SSH": "AWS::EC2::SecurityGroup",
}
TOPOLOGY_TYPES = {
    "ALLOWED_PATH",
    "FORBIDDEN_PATH",
    "TRUST_BOUNDARY_CROSSING",
    "REQUIRED_INTERMEDIARY",
    "EXPOSURE_BLAST_RADIUS",
}
SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}
EDGE_TYPES = {"STRUCTURAL", "NETWORK_PERMISSION", "NETWORK_REACHABILITY"}
PROTOCOLS = {"tcp", "udp"}
CRITICALITIES = SEVERITIES - {"INFO"}

MAX_COMPONENTS = 100
MAX_RELATIONSHIPS = 250
MAX_TRUST_BOUNDARIES = 20
MAX_CONSTRAINTS = 50
MAX_MANIFEST_BYTES = 200 * 1024
MAX_STRING = 1000
MAX_SELECTOR_IDS = 100
MAX_SELECTOR_PATTERNS = 100
MAX_SELECTOR_TAGS = 20
MAX_SELECTOR_LIST = 100


class ManifestValidationError(ValueError):
    """Validation error with the existing API error-code/message contract."""

    def __init__(self, code: str, message: str, details: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


def _fail(code: str, message: str, details: Any = None) -> None:
    raise ManifestValidationError(code, message, details)


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail("INVALID_MANIFEST", f"{path} must be an object.")
    return value


def _string(value: Any, path: str, *, maximum: int = MAX_STRING, nonempty: bool = True) -> str:
    if not isinstance(value, str):
        _fail("INVALID_MANIFEST", f"{path} must be a string.")
    result = value.strip()
    if (nonempty and not result) or len(result) > maximum:
        _fail("INVALID_MANIFEST", f"{path} must contain 1 to {maximum} characters." if nonempty else f"{path} must be at most {maximum} characters.")
    return result


def _id(value: Any, path: str) -> str:
    result = _string(value, path, maximum=120)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]*", result):
        _fail("INVALID_MANIFEST_ID", f"{path} contains unsupported characters.")
    return result


def _integer(value: Any, path: str, *, minimum: int, maximum: int, code: str) -> int:
    """Accept integral DynamoDB Decimals and normalize them to plain integers."""
    if isinstance(value, bool):
        _fail(code, f"{path} must be an integer from {minimum} to {maximum}.")
    if isinstance(value, int):
        result = value
    elif isinstance(value, Decimal) and value.is_finite() and value == value.to_integral_value():
        result = int(value)
    else:
        _fail(code, f"{path} must be an integer from {minimum} to {maximum}.")
    if not minimum <= result <= maximum:
        _fail(code, f"{path} must be an integer from {minimum} to {maximum}.")
    return result


def _keys(obj: dict[str, Any], allowed: set[str], path: str) -> None:
    unknown = sorted(set(obj) - allowed)
    if unknown:
        _fail("INVALID_MANIFEST", f"{path} contains unsupported fields.", {"fields": unknown})


def _string_list(value: Any, path: str, *, minimum: int = 1, maximum: int = MAX_SELECTOR_LIST,
                 identifiers: bool = False) -> list[str]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        _fail("INVALID_MANIFEST", f"{path} must contain {minimum} to {maximum} values.")
    result = [_id(item, f"{path}[{index}]") if identifiers else _string(item, f"{path}[{index}]")
              for index, item in enumerate(value)]
    if len(result) != len(set(result)):
        _fail("DUPLICATE_MANIFEST_VALUE", f"{path} must not contain duplicates.")
    return result


def _add_id(seen: set[str], value: str, path: str) -> None:
    if value in seen:
        _fail("DUPLICATE_MANIFEST_ID", f"Duplicate ID: {value}.", {"path": path, "id": value})
    seen.add(value)


def _normalize_constraint(item: Any, index: int, *, strict: bool, seen: set[str]) -> dict[str, Any]:
    path = f"constraints[{index}]"
    if not isinstance(item, dict):
        _fail("INVALID_CONSTRAINT", f"{path} must be an object.")
    if strict:
        if "type" in item and not isinstance(item["type"], str):
            _fail("INVALID_CONSTRAINT", f"{path}.type must be a string.")
        if "severity" in item and not isinstance(item["severity"], str):
            _fail("INVALID_SEVERITY", f"{path}.severity must be a string.")
        if "id" in item and not isinstance(item["id"], str):
            _fail("INVALID_MANIFEST_ID", f"{path}.id must be a string.")
        if not str(item.get("id", "")).strip():
            _fail("INVALID_MANIFEST_ID", f"{path}.id is required.")
    ctype = str(item.get("type", "")).upper()
    cid = str(item.get("id", "")).strip() or f"constraint-{index + 1}"
    severity = str(item.get("severity", "MEDIUM")).upper()
    if ctype not in ATTRIBUTE_TYPES and not (strict and ctype in TOPOLOGY_TYPES):
        _fail("UNSUPPORTED_CONSTRAINT_TYPE", f"Unsupported constraint type: {ctype}.",
              {"allowedTypes": sorted(ATTRIBUTE_TYPES if not strict else set(ATTRIBUTE_TYPES) | TOPOLOGY_TYPES)})
    if severity not in SEVERITIES:
        _fail("INVALID_SEVERITY", f"Unsupported severity: {severity}.", {"allowedSeverities": sorted(SEVERITIES)})
    if strict:
        cid = _id(cid, f"{path}.id")
        _add_id(seen, cid, path)
    elif cid in seen:
        _fail("DUPLICATE_CONSTRAINT_ID", f"Constraint ID must be unique: {cid}.")
    else:
        seen.add(cid)
    if strict and "description" in item and not isinstance(item["description"], str):
        _fail("INVALID_MANIFEST", f"{path}.description must be a string.")
    description = str(item.get("description", cid))[:500]
    enabled = item.get("enabled", True) is not False
    if strict and "enabled" in item and not isinstance(item["enabled"], bool):
        _fail("INVALID_MANIFEST", f"{path}.enabled must be a boolean.")

    base_fields = {"id", "type", "severity", "description", "enabled"}
    normalized: dict[str, Any] = {"id": cid, "type": ctype, "severity": severity,
                                  "description": description, "enabled": enabled}
    if ctype in ATTRIBUTE_TYPES:
        if strict:
            _keys(item, base_fields, path)
        return normalized

    allowed = {
        "ALLOWED_PATH": base_fields | {"target", "allowedSources", "pathMode", "edgeTypes"},
        "FORBIDDEN_PATH": base_fields | {"from", "to", "pathMode", "edgeTypes"},
        "TRUST_BOUNDARY_CROSSING": base_fields,
        "REQUIRED_INTERMEDIARY": base_fields | {"from", "to", "via", "edgeTypes"},
        "EXPOSURE_BLAST_RADIUS": base_fields | {"from", "maxReachableNodes", "edgeTypes"},
    }[ctype]
    _keys(item, allowed, path)
    if ctype == "ALLOWED_PATH":
        normalized["target"] = _id(item.get("target"), f"{path}.target")
        normalized["allowedSources"] = _string_list(item.get("allowedSources"), f"{path}.allowedSources", identifiers=True)
        mode = str(item.get("pathMode", "DIRECT")).upper()
        if mode not in {"DIRECT", "TRANSITIVE"}:
            _fail("INVALID_RULE_SEMANTICS", f"{path}.pathMode must be DIRECT or TRANSITIVE.")
        normalized["pathMode"] = mode
        normalized["edgeTypes"] = _edge_types(item.get("edgeTypes", ["NETWORK_REACHABILITY"]), f"{path}.edgeTypes")
    elif ctype == "FORBIDDEN_PATH":
        normalized["from"] = _id(item.get("from"), f"{path}.from")
        normalized["to"] = _id(item.get("to"), f"{path}.to")
        mode = str(item.get("pathMode", "DIRECT")).upper()
        if mode not in {"DIRECT", "TRANSITIVE"}:
            _fail("INVALID_RULE_SEMANTICS", f"{path}.pathMode must be DIRECT or TRANSITIVE.")
        normalized["pathMode"] = mode
        normalized["edgeTypes"] = _edge_types(item.get("edgeTypes", ["NETWORK_REACHABILITY"]), f"{path}.edgeTypes")
    elif ctype == "REQUIRED_INTERMEDIARY":
        normalized["from"] = _id(item.get("from"), f"{path}.from")
        normalized["to"] = _id(item.get("to"), f"{path}.to")
        normalized["via"] = _string_list(item.get("via"), f"{path}.via", identifiers=True)
        if normalized["from"] == normalized["to"] or set(normalized["via"]) & {normalized["from"], normalized["to"]}:
            _fail("INVALID_RULE_SEMANTICS", f"{path} must declare distinct endpoints and intermediaries.")
        normalized["edgeTypes"] = _edge_types(item.get("edgeTypes", ["NETWORK_REACHABILITY"]), f"{path}.edgeTypes")
    elif ctype == "EXPOSURE_BLAST_RADIUS":
        normalized["from"] = _id(item.get("from"), f"{path}.from")
        maximum = _integer(item.get("maxReachableNodes"), f"{path}.maxReachableNodes",
                           minimum=0, maximum=100_000, code="INVALID_RULE_SEMANTICS")
        normalized["maxReachableNodes"] = maximum
        normalized["edgeTypes"] = _edge_types(item.get("edgeTypes", ["NETWORK_REACHABILITY"]), f"{path}.edgeTypes")
    return normalized


def _edge_types(value: Any, path: str) -> list[str]:
    result = _string_list(value, path)
    result = [item.upper() for item in result]
    if any(item not in EDGE_TYPES for item in result):
        _fail("INVALID_RULE_SEMANTICS", f"{path} contains an unsupported edge type.", {"allowedTypes": sorted(EDGE_TYPES)})
    return result


def _normalize_component(item: Any, index: int, all_ids: set[str]) -> dict[str, Any]:
    path = f"components[{index}]"
    obj = _object(item, path)
    _keys(obj, {"id", "resourceTypes", "selector", "minMatches"}, path)
    cid = _id(obj.get("id"), f"{path}.id")
    _add_id(all_ids, cid, path)
    resource_types = _string_list(obj.get("resourceTypes"), f"{path}.resourceTypes", maximum=50)
    for resource_type in resource_types:
        if not re.fullmatch(r"AWS::[A-Za-z0-9]+::[A-Za-z0-9]+", resource_type):
            _fail("INVALID_COMPONENT", f"{path}.resourceTypes contains an invalid AWS resource type.")
    selector = _object(obj.get("selector"), f"{path}.selector")
    _keys(selector, {"resourceIds", "idPatterns", "tags"}, f"{path}.selector")
    normalized_selector: dict[str, Any] = {}
    if "resourceIds" in selector:
        normalized_selector["resourceIds"] = _string_list(selector["resourceIds"], f"{path}.selector.resourceIds", maximum=MAX_SELECTOR_IDS)
    if "idPatterns" in selector:
        patterns = _string_list(selector["idPatterns"], f"{path}.selector.idPatterns", maximum=MAX_SELECTOR_PATTERNS)
        for pattern in patterns:
            if len(pattern) > 256 or not re.fullmatch(r"[A-Za-z0-9_./:*?-]+", pattern):
                _fail("INVALID_SELECTOR", f"{path}.selector.idPatterns may use only bounded IDs and * or ? globs.")
        normalized_selector["idPatterns"] = patterns
    if "tags" in selector:
        tags = _object(selector["tags"], f"{path}.selector.tags")
        if not 1 <= len(tags) <= MAX_SELECTOR_TAGS:
            _fail("INVALID_SELECTOR", f"{path}.selector.tags must contain 1 to {MAX_SELECTOR_TAGS} entries.")
        normalized_tags: dict[str, str] = {}
        for key, value in tags.items():
            normalized_key = _string(key, f"{path}.selector.tags key", maximum=128)
            if normalized_key in normalized_tags:
                _fail("INVALID_SELECTOR", f"{path}.selector.tags contains duplicate normalized keys.")
            normalized_tags[normalized_key] = _string(value, f"{path}.selector.tags.{key}", maximum=256)
        normalized_selector["tags"] = dict(sorted(normalized_tags.items()))
    if not normalized_selector:
        _fail("INVALID_SELECTOR", f"{path}.selector must declare resourceIds, idPatterns, or tags.")
    minimum = _integer(obj.get("minMatches", 1), f"{path}.minMatches",
                       minimum=0, maximum=100_000, code="INVALID_COMPONENT")
    return {"id": cid, "resourceTypes": resource_types, "selector": normalized_selector, "minMatches": minimum}


def _selector_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    lt, rt = left["selector"].get("tags", {}), right["selector"].get("tags", {})
    if any(key in rt and rt[key] != value for key, value in lt.items()):
        return False
    left_ids, right_ids = left["selector"].get("resourceIds"), right["selector"].get("resourceIds")
    left_patterns, right_patterns = left["selector"].get("idPatterns", []), right["selector"].get("idPatterns", [])
    if left_ids is not None and right_ids is not None:
        return bool(set(left_ids) & set(right_ids))
    if left_ids is not None and right_patterns:
        return any(fnmatch.fnmatchcase(value, pattern) for value in left_ids for pattern in right_patterns)
    if right_ids is not None and left_patterns:
        return any(fnmatch.fnmatchcase(value, pattern) for value in right_ids for pattern in left_patterns)
    # Glob languages can overlap without sharing a literal pattern. Treat them as
    # potentially overlapping unless tags or exact IDs proved them disjoint.
    return True


def _normalize_relationship(item: Any, index: int, ids: set[str]) -> dict[str, Any]:
    path = f"relationships[{index}]"
    obj = _object(item, path)
    _keys(obj, {"id", "from", "to", "effect", "relationshipType", "protocol", "ports", "required"}, path)
    rid = _id(obj.get("id"), f"{path}.id")
    _add_id(ids, rid, path)
    source, target = _id(obj.get("from"), f"{path}.from"), _id(obj.get("to"), f"{path}.to")
    effect = str(obj.get("effect", "")).upper()
    if effect not in {"ALLOW", "DENY"}:
        _fail("INVALID_RELATIONSHIP", f"{path}.effect must be ALLOW or DENY.")
    relationship_type = str(obj.get("relationshipType", "")).upper()
    if relationship_type not in EDGE_TYPES:
        _fail("INVALID_RELATIONSHIP", f"{path}.relationshipType is unsupported.", {"allowedTypes": sorted(EDGE_TYPES)})
    raw_protocol = obj.get("protocol")
    if raw_protocol is None:
        protocol = None
    elif isinstance(raw_protocol, str) and raw_protocol.lower() in PROTOCOLS:
        protocol = raw_protocol.lower()
    else:
        _fail("INVALID_RELATIONSHIP", f"{path}.protocol must be tcp, udp, or null.")
    raw_ports = obj.get("ports")
    if protocol is None:
        if raw_ports not in (None, []):
            _fail("INVALID_RELATIONSHIP", f"{path}.ports requires a tcp or udp protocol.")
        ports = []
    else:
        if not isinstance(raw_ports, list) or not 1 <= len(raw_ports) <= 128:
            _fail("INVALID_RELATIONSHIP", f"{path}.ports must contain 1 to 128 ports when protocol is set.")
        ports = [_integer(port, f"{path}.ports[{port_index}]", minimum=1, maximum=65535,
                          code="INVALID_RELATIONSHIP") for port_index, port in enumerate(raw_ports)]
    if len(ports) != len(set(ports)):
        _fail("INVALID_RELATIONSHIP", f"{path}.ports must not contain duplicates.")
    required = obj.get("required", False)
    if not isinstance(required, bool):
        _fail("INVALID_RELATIONSHIP", f"{path}.required must be a boolean.")
    return {"id": rid, "from": source, "to": target, "effect": effect,
            "relationshipType": relationship_type, "protocol": protocol,
            "ports": sorted(ports), "required": required}


def _normalize_boundaries(value: Any, ids: set[str], components: set[str]) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) > MAX_TRUST_BOUNDARIES:
        _fail("INVALID_TRUST_BOUNDARIES", f"trustBoundaries must contain 0 to {MAX_TRUST_BOUNDARIES} entries.")
    result = []
    memberships: set[str] = set()
    zones: set[str] = set()
    for index, item in enumerate(value):
        path = f"trustBoundaries[{index}]"
        obj = _object(item, path)
        _keys(obj, {"id", "members", "crossingRules"}, path)
        zid = _id(obj.get("id"), f"{path}.id")
        _add_id(ids, zid, path)
        zones.add(zid)
        members = _string_list(obj.get("members"), f"{path}.members", maximum=MAX_COMPONENTS, identifiers=True)
        if any(member not in components for member in members):
            _fail("UNKNOWN_COMPONENT_REFERENCE", f"{path}.members references an unknown component.")
        duplicates = memberships.intersection(members)
        if duplicates:
            _fail("OVERLAPPING_TRUST_BOUNDARIES", "Trust boundary members must belong to at most one zone.", {"components": sorted(duplicates)})
        memberships.update(members)
        crossings = obj.get("crossingRules", [])
        if not isinstance(crossings, list) or len(crossings) > 100:
            _fail("INVALID_TRUST_BOUNDARIES", f"{path}.crossingRules must contain 0 to 100 entries.")
        normalized_crossings = []
        for cindex, crossing in enumerate(crossings):
            cpath = f"{path}.crossingRules[{cindex}]"
            rule = _object(crossing, cpath)
            _keys(rule, {"id", "to", "effect", "via"}, cpath)
            cid = _id(rule.get("id"), f"{cpath}.id")
            _add_id(ids, cid, cpath)
            to = _id(rule.get("to"), f"{cpath}.to")
            effect = str(rule.get("effect", "")).upper()
            if effect not in {"ALLOW", "DENY"}:
                _fail("INVALID_TRUST_BOUNDARY_RULE", f"{cpath}.effect must be ALLOW or DENY.")
            via = _string_list(rule["via"], f"{cpath}.via", maximum=MAX_COMPONENTS, identifiers=True) if "via" in rule else []
            if any(component not in components for component in via):
                _fail("UNKNOWN_COMPONENT_REFERENCE", f"{cpath}.via references an unknown component.")
            normalized_crossings.append({"id": cid, "to": to, "effect": effect, "via": via})
        result.append({"id": zid, "members": members, "crossingRules": normalized_crossings})
    crossing_effects: dict[tuple[str, str], tuple[str, str]] = {}
    for zone in result:
        for crossing in zone["crossingRules"]:
            if crossing["to"] not in zones:
                _fail("UNKNOWN_TRUST_BOUNDARY_REFERENCE", f"Crossing rule {crossing['id']} references an unknown zone.")
            key = (zone["id"], crossing["to"])
            previous = crossing_effects.get(key)
            if previous and previous[0] != crossing["effect"]:
                _fail("CONTRADICTORY_RELATIONSHIPS", "Trust boundary declarations contain contradictory allow/deny rules.",
                      {"rules": sorted([crossing["id"], previous[1]])})
            crossing_effects[key] = (crossing["effect"], crossing["id"])
    return result


def _validate_references(components: list[dict[str, Any]], relationships: list[dict[str, Any]],
                         constraints: list[dict[str, Any]]) -> None:
    component_ids = {item["id"] for item in components}
    for relation in relationships:
        if relation["from"] not in component_ids or relation["to"] not in component_ids:
            _fail("UNKNOWN_COMPONENT_REFERENCE", f"Relationship {relation['id']} references an unknown component.")
    for rule in constraints:
        ctype = rule["type"]
        refs: list[str] = []
        if ctype == "ALLOWED_PATH":
            refs = [rule["target"], *rule["allowedSources"]]
        elif ctype in {"FORBIDDEN_PATH", "REQUIRED_INTERMEDIARY"}:
            refs = [rule["from"], rule["to"], *rule.get("via", [])]
        elif ctype == "EXPOSURE_BLAST_RADIUS":
            refs = [rule["from"]]
        unknown = sorted(set(refs) - component_ids)
        if unknown:
            _fail("UNKNOWN_COMPONENT_REFERENCE", f"Constraint {rule['id']} references an unknown component.", {"components": unknown})


def _validate_contradictions(relationships: list[dict[str, Any]]) -> None:
    for index, left in enumerate(relationships):
        for right in relationships[index + 1:]:
            same_path = (left["from"], left["to"], left["relationshipType"], left["protocol"]) == (
                right["from"], right["to"], right["relationshipType"], right["protocol"])
            same_scope = (
                left["protocol"] is None and right["protocol"] is None and not left["ports"] and not right["ports"]
            ) or bool(set(left["ports"]) & set(right["ports"]))
            if same_path and left["effect"] != right["effect"] and same_scope:
                _fail("CONTRADICTORY_RELATIONSHIPS", "Relationships contain overlapping ALLOW and DENY declarations.",
                      {"relationships": sorted([left["id"], right["id"]])})


def validate_manifest(body: Any) -> dict[str, Any]:
    """Validate and normalize an API manifest without I/O or mutation."""
    obj = _object(body, "manifest")
    schema_version = obj.get("schemaVersion", 1)
    if schema_version == 1 and "schemaVersion" not in obj:
        strict = False
    elif (isinstance(schema_version, (int, Decimal)) and not isinstance(schema_version, bool)
          and schema_version == 2):
        strict = True
    else:
        _fail("UNSUPPORTED_SCHEMA_VERSION", "schemaVersion must be 2 when supplied.", {"supported": [1, 2]})

    if not strict:
        _keys(obj, {"name", "description", "constraints"}, "manifest")
        name = str(obj.get("name", "")).strip()
        description = str(obj.get("description", "")).strip()
        constraints = obj.get("constraints")
        if not name or len(name) > 120:
            _fail("INVALID_NAME", "name is required and must be at most 120 characters.")
        if not isinstance(constraints, list) or not constraints or len(constraints) > MAX_CONSTRAINTS:
            _fail("INVALID_CONSTRAINTS", "constraints must be a list containing 1 to 50 constraints.")
        seen: set[str] = set()
        normalized = [_normalize_constraint(item, index, strict=False, seen=seen) for index, item in enumerate(constraints)]
        return {"name": name, "description": description[:1000], "constraints": normalized}

    _keys(obj, {"schemaVersion", "name", "description", "constraints", "components", "relationships", "trustBoundaries", "criticality"}, "manifest")
    name = _string(obj.get("name"), "name", maximum=120)
    description = _string(obj.get("description", ""), "description", maximum=1000, nonempty=False)
    raw_constraints = obj.get("constraints", [])
    if not isinstance(raw_constraints, list) or len(raw_constraints) > MAX_CONSTRAINTS:
        _fail("INVALID_CONSTRAINTS", "constraints must be a list containing 0 to 50 constraints.")
    raw_components = obj.get("components", [])
    if not isinstance(raw_components, list) or len(raw_components) > MAX_COMPONENTS:
        _fail("INVALID_COMPONENTS", f"components must contain 0 to {MAX_COMPONENTS} entries.")
    raw_relationships = obj.get("relationships", [])
    if not isinstance(raw_relationships, list) or len(raw_relationships) > MAX_RELATIONSHIPS:
        _fail("INVALID_RELATIONSHIPS", f"relationships must contain 0 to {MAX_RELATIONSHIPS} entries.")

    all_ids: set[str] = set()
    components = [_normalize_component(item, index, all_ids) for index, item in enumerate(raw_components)]
    for index, left in enumerate(components):
        for right in components[index + 1:]:
            if set(left["resourceTypes"]) & set(right["resourceTypes"]) and _selector_overlap(left, right):
                _fail("COMPONENT_SELECTOR_OVERLAP", "Component selectors may match the same resource.",
                      {"components": sorted([left["id"], right["id"]])})

    relationships = [_normalize_relationship(item, index, all_ids) for index, item in enumerate(raw_relationships)]
    raw_boundaries = obj.get("trustBoundaries", [])
    if not isinstance(raw_boundaries, list) or len(raw_boundaries) > MAX_TRUST_BOUNDARIES:
        _fail("INVALID_TRUST_BOUNDARIES", f"trustBoundaries must contain 0 to {MAX_TRUST_BOUNDARIES} entries.")
    component_ids = {item["id"] for item in components}
    boundaries = _normalize_boundaries(raw_boundaries, all_ids, component_ids)
    constraints = [_normalize_constraint(item, index, strict=True, seen=all_ids) for index, item in enumerate(raw_constraints)]
    _validate_references(components, relationships, constraints)
    _validate_contradictions(relationships)

    criticality = obj.get("criticality", {})
    criticality = _object(criticality, "criticality")
    unknown_criticality = sorted(set(criticality) - component_ids)
    if unknown_criticality:
        _fail("UNKNOWN_COMPONENT_REFERENCE", "criticality references an unknown component.", {"components": unknown_criticality})
    normalized_criticality = {component_id: "MEDIUM" for component_id in component_ids}
    for component_id, value in sorted(criticality.items()):
        level = str(value).upper()
        if level not in CRITICALITIES:
            _fail("INVALID_CRITICALITY", f"criticality.{component_id} must be CRITICAL, HIGH, MEDIUM, or LOW.")
        normalized_criticality[component_id] = level

    evaluable_relationship = any(item["effect"] == "DENY" or item["required"] for item in relationships)
    evaluable_boundary = any(
        crossing["effect"] == "DENY" or (crossing["effect"] == "ALLOW" and crossing["via"])
        for boundary in boundaries for crossing in boundary["crossingRules"]
    )
    if any(item["type"] == "TRUST_BOUNDARY_CROSSING" for item in constraints) and not any(
        boundary["crossingRules"] for boundary in boundaries
    ):
        _fail("INVALID_RULE_SEMANTICS", "TRUST_BOUNDARY_CROSSING requires trustBoundaries.")
    if not constraints and not (evaluable_relationship or evaluable_boundary):
        _fail("INVALID_CONSTRAINTS", "A v2 manifest needs constraints or an evaluable relationship or boundary rule.")

    normalized: dict[str, Any] = {"schemaVersion": 2, "name": name, "description": description,
                                  "constraints": constraints}
    if components:
        normalized["components"] = components
    if relationships:
        normalized["relationships"] = relationships
    if boundaries:
        normalized["trustBoundaries"] = boundaries
    if components:
        normalized["criticality"] = normalized_criticality
    encoded = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_MANIFEST_BYTES:
        _fail("MANIFEST_TOO_LARGE", "Normalized manifest must not exceed 200 KiB.", {"maxBytes": MAX_MANIFEST_BYTES})
    return normalized
