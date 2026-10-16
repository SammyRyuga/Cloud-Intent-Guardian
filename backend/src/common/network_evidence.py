"""Optional bounded enrichment from existing, read-only network evidence.

Only explicit, concrete protocol/port bindings are queried. Positive records
never establish exhaustive graph coverage; negative records remain independent
verdicts and cannot prove absence of other packets, ports, or paths.
"""
from copy import deepcopy
from decimal import Decimal
import hashlib
import os

from common.contracts import is_local
from common.evidence_sources import collect_verdicts
from common.topology import resolve_components

MAX_CANDIDATES = 2


def enrich_network_evidence(intent, inventory):
    """Return an enriched copy when enabled; local execution performs no reads."""
    if (is_local() or os.environ.get("NETWORK_EVIDENCE_ENABLED", "false").lower() != "true"
            or not isinstance(intent, dict)):
        return inventory
    resolved = resolve_components(intent, inventory)
    meta = inventory.get("meta") or {}
    if not meta.get("collectedAt"):
        return inventory
    candidates = {}
    truncated = False
    for declaration in sorted(intent.get("relationships") or [], key=lambda row: str(row.get("id", ""))):
        if declaration.get("relationshipType") not in {"NETWORK_REACHABILITY", "NETWORK_PERMISSION"}:
            continue
        protocol, ports = declaration.get("protocol"), declaration.get("ports")
        if protocol not in {"tcp", "udp"} or not isinstance(ports, list) or len(ports) != 1:
            continue
        port = ports[0]
        if isinstance(port, bool) or not isinstance(port, (int, Decimal)):
            continue
        if isinstance(port, Decimal) and not port.is_finite():
            continue
        if not 1 <= port <= 65535 or port != int(port):
            continue
        port = int(port)
        starts = sorted(row["resourceId"] for row in resolved["components"].get(declaration.get("from"), []))
        ends = sorted(row["resourceId"] for row in resolved["components"].get(declaration.get("to"), []))
        for source in starts:
            for target in ends:
                key = (source, target, protocol, port)
                if key in candidates:
                    continue
                if len(candidates) >= MAX_CANDIDATES:
                    truncated = True
                    break
                identifier = hashlib.sha256("|".join(map(str, key)).encode()).hexdigest()[:24]
                candidates[key] = {"candidateId": identifier, "predicate": "DIRECTED_PATH_PRESENT",
                                   "sourceId": source, "targetId": target, "protocol": protocol, "ports": [port],
                                   "snapshotId": meta.get("snapshotId") or f"network:{meta['collectedAt']}",
                                   "observedAt": meta["collectedAt"]}
            if truncated:
                break
        if truncated:
            break
    enriched = deepcopy(inventory)
    records = []
    clients = {}
    edges = enriched.setdefault("edges", [])
    for candidate in candidates.values():
        verdicts = collect_verdicts(candidate, inventory, network_evidence=True, client_cache=clients)
        records.append({"candidate": candidate, "verdicts": verdicts})
        # Conflicting sources cannot silently promote a deterministic witness.
        if any(row.get("verdict") == "DISAGREES" for row in verdicts):
            continue
        for row in verdicts:
            if row.get("verdict") != "CORROBORATES":
                continue
            family = row.get("sourceFamily")
            if family not in {"flowLogs", "reachabilityAnalyzer"}:
                continue
            observed = family == "flowLogs"
            edge = {"sourceId": candidate["sourceId"], "targetId": candidate["targetId"],
                    "type": "NETWORK_REACHABILITY" if observed else "NETWORK_PERMISSION",
                    "observationKind": "OBSERVED" if observed else "CONFIGURED",
                    "evidenceScope": "EXACT_FLOW",
                    "protocol": candidate["protocol"], "ports": candidate["ports"],
                    "observedAt": candidate["observedAt"], "evidence": [row]}
            if edge not in edges:
                edges.append(edge)
    output_meta = enriched.setdefault("meta", {})
    output_meta["networkEvidence"] = {"candidateLimit": MAX_CANDIDATES, "truncated": truncated,
                                      "candidates": records, "coverage": "PARTIAL"}
    coverage = output_meta.setdefault("coverage", {}).setdefault("relationshipTypes", {})
    # This adapter samples explicit bindings only. It cannot authorize absence.
    for kind in ("NETWORK_REACHABILITY", "NETWORK_PERMISSION"):
        coverage[kind] = "PARTIAL"
    if truncated:
        output_meta.setdefault("warnings", []).append({"code": "TRUNCATED", "source": "networkEvidence",
                                                       "message": "Network evidence candidate limit reached."})
    return enriched
