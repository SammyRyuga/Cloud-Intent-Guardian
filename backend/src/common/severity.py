"""Pure, evidence-bounded finding severity scoring."""
from __future__ import annotations

from collections import deque
from typing import Any

from common.topology import resolve_components


FORMULA_VERSION = "1"
BASE_POINTS = {"INFO": 5, "LOW": 15, "MEDIUM": 35, "HIGH": 60, "CRITICAL": 80}
CRITICALITY_POINTS = {"LOW": 0, "MEDIUM": 5, "HIGH": 10, "CRITICAL": 15}
EXPOSURE_POINTS = {"PUBLIC": 10, "INTERNAL": 0, "UNKNOWN": 5}
CONFIDENCE_POINTS = {"HIGH": 0, "MEDIUM": 2, "LOW": 5}
LABEL_THRESHOLDS = ((85, "CRITICAL"), (60, "HIGH"), (30, "MEDIUM"), (10, "LOW"))
MAX_VISITED = 20_000
MAX_DEPTH = 64
MAX_EDGES = 50_000


def _label(score: int) -> str:
    for threshold, label in LABEL_THRESHOLDS:
        if score >= threshold:
            return label
    return "INFO"


def _severity(value: Any, default: str = "MEDIUM") -> str:
    label = str(value or default).upper()
    return label if label in BASE_POINTS else default


def _resource_ids(finding: dict[str, Any]) -> list[str]:
    ids: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key in ("resourceId", "sourceId", "targetId"):
                item = value.get(key)
                if isinstance(item, str) and item:
                    ids.add(item)
            for child in value.values():
                if isinstance(child, (dict, list, tuple)):
                    visit(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                visit(child)

    for key in ("resourceId", "sourceId", "targetId", "observed", "evidence"):
        if key in finding:
            visit(finding[key])
    if not ids and isinstance(finding.get("resourceId"), str):
        ids.add(finding["resourceId"])
    return sorted(ids)


def _component_factors(intent: dict[str, Any], inventory: dict[str, Any],
                       resource_ids: list[str]) -> dict[str, Any]:
    resolution = resolve_components(intent, inventory)
    membership: dict[str, set[str]] = {}
    for component_id, resources in (resolution.get("components") or {}).items():
        for resource in resources:
            rid = resource.get("resourceId")
            if rid:
                membership.setdefault(str(rid), set()).add(str(component_id))
    implicated = sorted({cid for rid in resource_ids for cid in membership.get(rid, set())})
    declared = intent.get("criticality") or {}
    levels = {cid: _severity(declared.get(cid), "MEDIUM") for cid in implicated}
    if levels:
        chosen = max(levels.values(), key=lambda level: CRITICALITY_POINTS[level])
        defaulted = any(cid not in declared for cid in implicated)
    else:
        chosen = "MEDIUM"
        defaulted = True
    points = CRITICALITY_POINTS[chosen]
    if not implicated:
        explanation = "No implicated resource resolved to a declared component; MEDIUM criticality was used by default."
    elif defaulted:
        explanation = f"Highest implicated criticality is {chosen}; missing component criticality defaults to MEDIUM."
    else:
        explanation = f"Highest implicated component criticality is {chosen}."
    return {"label": chosen, "points": points, "componentIds": implicated,
            "defaulted": defaulted, "explanation": explanation}


def _edge_kind(edge: dict[str, Any]) -> str | None:
    kind = edge.get("observationKind")
    if isinstance(kind, str):
        return kind.upper()
    evidence = edge.get("evidence")
    if isinstance(evidence, dict):
        kind = evidence.get("kind") or evidence.get("observationKind")
        if isinstance(kind, str):
            return kind.upper()
    if isinstance(evidence, list):
        kinds = {str(row.get("kind") or row.get("observationKind")).upper()
                 for row in evidence if isinstance(row, dict) and (row.get("kind") or row.get("observationKind"))}
        if len(kinds) == 1:
            return next(iter(kinds))
    return None


def _relationship_coverage(inventory: dict[str, Any]) -> str:
    meta = inventory.get("meta") or {}
    coverage = meta.get("coverage") or inventory.get("coverage") or {}
    relationships = coverage.get("relationshipTypes") if isinstance(coverage, dict) else None
    value = relationships.get("NETWORK_REACHABILITY") if isinstance(relationships, dict) else None
    if isinstance(value, dict):
        value = value.get("status")
    return str(value).upper() if isinstance(value, str) else "UNKNOWN"


def _blast_radius(finding: dict[str, Any], inventory: dict[str, Any], resource_ids: list[str]) -> dict[str, Any]:
    edges = inventory.get("edges") or []
    qualifying: list[dict[str, Any]] = []
    limited = len(edges) > MAX_EDGES
    for edge in edges[:MAX_EDGES]:
        if not isinstance(edge, dict):
            continue
        edge_type = str(edge.get("type", edge.get("relationshipType", ""))).upper()
        if edge_type != "NETWORK_REACHABILITY" or _edge_kind(edge) != "OBSERVED":
            continue
        source, target = edge.get("sourceId"), edge.get("targetId")
        if isinstance(source, str) and source and isinstance(target, str) and target:
            qualifying.append(edge)

    starts: set[str] = set()
    for key in ("sourceId",):
        value = finding.get(key)
        if isinstance(value, str) and value:
            starts.add(value)
    if not starts and isinstance(finding.get("observed"), dict):
        value = finding["observed"].get("sourceId")
        if isinstance(value, str) and value:
            starts.add(value)
    if not starts:
        starts = set(resource_ids)

    adjacency: dict[str, list[str]] = {}
    for edge in qualifying:
        adjacency.setdefault(edge["sourceId"], []).append(edge["targetId"])
    visited = set(starts)
    queue = deque((node, 0) for node in sorted(starts))
    while queue:
        node, depth = queue.popleft()
        targets = adjacency.get(node, [])
        if depth >= MAX_DEPTH and targets:
            limited = True
            continue
        for target in targets:
            if target in visited:
                continue
            visited.add(target)
            if len(visited) > MAX_VISITED:
                limited = True
                break
            queue.append((target, depth + 1))
        if len(visited) > MAX_VISITED:
            break

    downstream = sorted(visited - starts)
    coverage = _relationship_coverage(inventory)
    meta = inventory.get("meta") or {}
    complete = coverage == "COMPLETE" and not meta.get("partial", False) and not limited
    count = len(downstream)
    points = min(10, count)
    if complete:
        explanation = f"Complete observed reachability evidence identifies {count} unique downstream nodes."
    else:
        explanation = f"At least {count} unique downstream nodes are evidenced; coverage is incomplete, so the count is a lower bound."
    return {"count": count, "points": points, "complete": complete,
            "downstreamResourceIds": downstream, "explanation": explanation}


def _public_ssh(resource: dict[str, Any]) -> bool:
    attrs = resource.get("attributes") or {}
    rules = attrs.get("ingressRules")
    if not isinstance(rules, list):
        return False
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        protocol = str(rule.get("protocol", ""))
        cidr = str(rule.get("cidr", ""))
        if cidr not in {"0.0.0.0/0", "::/0"}:
            continue
        if protocol == "-1":
            return True
        first, last = rule.get("fromPort"), rule.get("toPort")
        if protocol in {"tcp", "6"} and isinstance(first, int) and isinstance(last, int) and first <= 22 <= last:
            return True
    return False


def _explicit_exposure(resource: dict[str, Any], finding: dict[str, Any]) -> str:
    attrs = resource.get("attributes") or {}
    resource_type = resource.get("resourceType")
    for key in ("isExposed", "exposed", "publicAccess"):
        if isinstance(attrs.get(key), bool):
            return "PUBLIC" if attrs[key] else "INTERNAL"
    if resource_type == "AWS::EC2::Instance" and "publicIpAddress" in attrs:
        return "PUBLIC" if attrs.get("publicIpAddress") else "INTERNAL"
    if resource_type == "AWS::RDS::DBInstance" and isinstance(attrs.get("publiclyAccessible"), bool):
        return "PUBLIC" if attrs["publiclyAccessible"] else "INTERNAL"
    if resource_type == "AWS::S3::Bucket":
        if attrs.get("bucketPolicyPublic") is True:
            return "PUBLIC"
        if attrs.get("bucketPolicyPublic") is False and attrs.get("publicAccessBlockEnabled") is True:
            return "INTERNAL"
    if (resource_type == "AWS::EC2::SecurityGroup"
            and finding.get("ruleId") == "SECURITY_GROUP_NO_OPEN_SSH"
            and isinstance(attrs.get("ingressRules"), list)):
        if _public_ssh(resource):
            return "PUBLIC"
        return "INTERNAL"
    return "UNKNOWN"


def _exposure(finding: dict[str, Any], inventory: dict[str, Any], resource_ids: list[str]) -> dict[str, Any]:
    resources = {str(row.get("resourceId")): row for row in inventory.get("items", [])
                 if isinstance(row, dict) and row.get("resourceId")}
    states = [_explicit_exposure(resources[rid], finding) for rid in resource_ids if rid in resources]
    if "PUBLIC" in states:
        label = "PUBLIC"
        explanation = "At least one implicated resource has explicit public exposure evidence."
    elif resource_ids and len(states) == len(resource_ids) and states and all(state == "INTERNAL" for state in states):
        label = "INTERNAL"
        explanation = "Every implicated resource has an explicit negative exposure observation adequate for its resource type."
    else:
        label = "UNKNOWN"
        explanation = "Available attributes do not establish public exposure or an adequately evidenced internal state."
    return {"label": label, "points": EXPOSURE_POINTS[label], "explanation": explanation}


def decorate_finding(finding: dict[str, Any], intent: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with explainable impact score and evidence-derived factors."""
    result = dict(finding)
    base_label = _severity(result.get("constraintSeverity") or result.get("severity"))
    result["constraintSeverity"] = result.get("constraintSeverity") or result.get("severity") or base_label
    base_points = BASE_POINTS[base_label]
    resource_ids = _resource_ids(result)
    criticality = _component_factors(intent, inventory, resource_ids)
    blast = _blast_radius(result, inventory, resource_ids)
    exposure = _exposure(result, inventory, resource_ids)
    confidence_label = str(result.get("confidence", "HIGH")).upper()
    if confidence_label not in CONFIDENCE_POINTS:
        confidence_label = "LOW"
    result["confidence"] = confidence_label
    confidence_points = CONFIDENCE_POINTS[confidence_label]
    score = min(100, base_points + criticality["points"] + blast["points"]
                + exposure["points"] + confidence_points)
    severity_label = _label(score)
    explanation = (f"{base_label} base severity ({base_points}) + {criticality['points']} component criticality"
                   f" + {blast['points']} blast-radius points + {exposure['points']} exposure points"
                   f" + {confidence_points} confidence points = {score}/100 ({severity_label}).")
    result["severityScore"] = score
    result["severity"] = severity_label
    result["severityFactors"] = {
        "formulaVersion": FORMULA_VERSION,
        "baseSeverity": {"label": base_label, "points": base_points},
        "componentCriticality": criticality,
        "blastRadius": blast,
        "exposure": exposure,
        "confidence": {"label": confidence_label, "points": confidence_points,
                       "explanation": f"{confidence_label} confidence adds {confidence_points} uncertainty-uplift points."},
        "explanation": explanation,
    }
    return result
