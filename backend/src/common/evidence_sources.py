"""Bounded, read-only corroboration adapters for topology candidates."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
from datetime import datetime, timedelta, timezone

from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from common.contracts import is_local

WINDOW = timedelta(minutes=5)
FLOW_LIMIT = 20
ANALYSIS_LIMIT = 100
_PATH_ID = re.compile(r"^nip-[A-Za-z0-9]+$")


def _parse_time(value):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            parsed = datetime.fromtimestamp(value, timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    elif isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _safe_text(value, fallback="unknown"):
    return value if isinstance(value, str) and 0 < len(value) <= 512 else fallback


def _base_row(candidate, family):
    return {
        "sourceFamily": family,
        "verdict": "UNKNOWN",
        "evidenceId": f"unavailable:{family}",
        "originId": f"unavailable:{family}",
        "predicate": "DIRECTED_PATH_PRESENT",
        "sourceId": _safe_text(candidate.get("sourceId")),
        "targetId": _safe_text(candidate.get("targetId")),
        "snapshotId": _safe_text(candidate.get("snapshotId")),
        "observedAt": _safe_text(candidate.get("observedAt")),
    }


def _valid_candidate(candidate, inventory):
    if not isinstance(candidate, dict) or not isinstance(inventory, dict):
        return None
    source = candidate.get("sourceId")
    target = candidate.get("targetId")
    snapshot = _parse_time(candidate.get("observedAt"))
    if not (isinstance(source, str) and source and isinstance(target, str) and target and snapshot):
        return None
    return source, target, snapshot


def _candidate_ports(candidate):
    raw = candidate.get("ports")
    if raw is None:
        raw = candidate.get("destinationPorts")
    if raw is None:
        return None
    if not isinstance(raw, (list, tuple)):
        return None
    ports = set()
    for value in raw:
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 65535:
            return None
        ports.add(value)
    return ports or None


def _candidate_scope(candidate):
    protocol_present = candidate.get("protocol") is not None
    protocol = _protocol_number(candidate.get("protocol")) if protocol_present else None
    if protocol_present and protocol is None:
        return None
    ports_present = candidate.get("ports") is not None or candidate.get("destinationPorts") is not None
    ports = _candidate_ports(candidate)
    if ports_present and ports is None:
        return None
    return protocol, ports


def _protocol_number(value):
    if isinstance(value, int) and not isinstance(value, bool):
        return value if value in {6, 17} else None
    if isinstance(value, str):
        normalized = value.strip().lower()
        return {"tcp": 6, "udp": 17}.get(normalized, int(normalized) if normalized in {"6", "17"} else None)
    return None


def _protocol_name(value):
    if isinstance(value, int) and not isinstance(value, bool):
        return {6: "tcp", 17: "udp"}.get(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"tcp", "udp"}:
            return normalized
        if normalized in {"6", "17"}:
            return {"6": "tcp", "17": "udp"}[normalized]
    return None


def _within_snapshot(timestamp, snapshot):
    return snapshot - WINDOW <= timestamp <= snapshot + WINDOW


def _inventory_private_ips(inventory, source, target):
    found = {source: [], target: []}
    items = inventory.get("items", [])
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict):
            continue
        resource_id = item.get("resourceId")
        if resource_id not in found:
            continue
        attrs = item.get("attributes")
        ip = attrs.get("privateIpAddress") if isinstance(attrs, dict) else None
        try:
            normalized = str(ipaddress.ip_address(ip)) if isinstance(ip, str) else None
        except ValueError:
            normalized = None
        if normalized:
            found[resource_id].append(normalized)
    if any(len(found[resource_id]) != 1 for resource_id in (source, target)):
        return None
    source_ip, target_ip = found[source][0], found[target][0]
    if source_ip == target_ip:
        return None
    return source_ip, target_ip


def _parse_flow_record(message):
    if not isinstance(message, str):
        return None
    fields = message.split()
    # The standard VPC Flow Logs format is fourteen whitespace-separated fields.
    if len(fields) != 14:
        return None
    version, account, interface_id, source, target, source_port, target_port, protocol, packets, byte_count, start, end, action, status = fields
    try:
        parsed = {
            "version": int(version), "account": account, "interface": interface_id,
            "source": str(ipaddress.ip_address(source)), "target": str(ipaddress.ip_address(target)),
            "sourcePort": int(source_port), "targetPort": int(target_port), "protocol": int(protocol),
            "packets": int(packets), "bytes": int(byte_count), "start": int(start), "end": int(end),
            "action": action, "status": status,
        }
    except (ValueError, TypeError):
        return None
    if (parsed["version"] <= 0 or parsed["interface"] in {"", "-"}
            or not 0 <= parsed["sourcePort"] <= 65535 or not 0 <= parsed["targetPort"] <= 65535
            or parsed["protocol"] not in {6, 17} or parsed["packets"] <= 0 or parsed["bytes"] < 0
            or parsed["start"] < 0 or parsed["end"] < parsed["start"] or parsed["end"] > 253402300799
            or parsed["action"] not in {"ACCEPT", "REJECT"} or parsed["status"] != "OK"):
        return None
    return parsed


def _flow_logs_verdict(candidate, inventory, logs, group_name):
    row = _base_row(candidate, "flowLogs")
    identity = _valid_candidate(candidate, inventory)
    if not identity or not logs or not isinstance(group_name, str) or not group_name:
        return row
    source, target, snapshot = identity
    scope = _candidate_scope(candidate)
    if scope is None:
        return row
    expected_protocol, expected_ports = scope
    ips = _inventory_private_ips(inventory, source, target)
    if not ips:
        return row
    source_ip, target_ip = ips
    try:
        response = logs.filter_log_events(
            logGroupName=group_name,
            startTime=int((snapshot - WINDOW).timestamp() * 1000),
            endTime=int((snapshot + WINDOW).timestamp() * 1000),
            limit=FLOW_LIMIT,
        )
    except (ClientError, BotoCoreError, ValueError, TypeError):
        return row

    meta = inventory.get("meta", {})
    expected_account = meta.get("accountId") if isinstance(meta, dict) else None
    accepted, rejected = [], []
    events = response.get("events", []) if isinstance(response, dict) else []
    if not isinstance(events, list):
        return row
    for event in events[:FLOW_LIMIT]:
        if not isinstance(event, dict):
            continue
        record = _parse_flow_record(event.get("message"))
        event_time = _parse_time(event.get("timestamp", 0) / 1000) if isinstance(event.get("timestamp"), (int, float)) else None
        if not record or not event_time or not _within_snapshot(event_time, snapshot):
            continue
        record_start = _parse_time(record["start"])
        record_end = _parse_time(record["end"])
        if not record_start or not record_end:
            continue
        if not _within_snapshot(record_end, snapshot) or record_start > snapshot + WINDOW or record_end < snapshot - WINDOW:
            continue
        if expected_account and record["account"] != expected_account:
            continue
        if record["source"] != source_ip or record["target"] != target_ip:
            continue
        if expected_protocol is not None and record["protocol"] != expected_protocol:
            continue
        if expected_ports is not None and record["targetPort"] not in expected_ports:
            continue
        stream = _safe_text(event.get("logStreamName"), "unknown-stream")
        event_id = _safe_text(event.get("eventId"), hashlib.sha256(event["message"].encode()).hexdigest()[:24])
        record_id = f"{event_id}:{record['start']}-{record['end']}"
        record_id = record_id[:512]
        origin_id = f"flowLogs:{record['account']}:{group_name}:{stream}"
        if len(origin_id) > 512:
            origin_id = origin_id[:512]
        evidence = (event_time, record_id, origin_id)
        if record["action"] == "ACCEPT":
            accepted.append(evidence)
        elif (record["action"] == "REJECT" and expected_protocol is not None
              and expected_ports is not None):
            rejected.append(evidence)

    # A single accepted record establishes observed directed packet connectivity.
    # Rejection only disagrees when it matches the selected protocol and destination port.
    chosen = max(accepted, key=lambda item: item[0]) if accepted else max(rejected, key=lambda item: item[0]) if rejected else None
    if chosen:
        timestamp, evidence_id, origin_id = chosen
        row.update({"verdict": "CORROBORATES" if accepted else "DISAGREES",
                    "evidenceId": evidence_id, "originId": origin_id})
    return row


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate mapping key")
        result[key] = value
    return result


def _path_mapping(raw):
    if not isinstance(raw, str) or not raw or len(raw) > 65536:
        return {}
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object)
    except (ValueError, TypeError):
        return {}
    if not isinstance(value, dict) or len(value) > 1000:
        return {}
    result = {}
    for key, path_id in value.items():
        if (isinstance(key, str) and len(key) <= 1024 and "|" in key
                and isinstance(path_id, str) and _PATH_ID.fullmatch(path_id)):
            result[key] = path_id
    return result


def _path_is_unscoped(path):
    for key in ("FilterAtSource", "FilterAtDestination"):
        filters = path.get(key)
        if filters not in (None, {}):
            return False
    if path.get("SourceIp") or path.get("DestinationIp"):
        return False
    return True


def _reachability_verdict(candidate, inventory, ec2, path_mapping):
    row = _base_row(candidate, "reachabilityAnalyzer")
    identity = _valid_candidate(candidate, inventory)
    if not identity or not ec2:
        return row
    source, target, snapshot = identity
    path_id = path_mapping.get(f"{source}|{target}")
    if not path_id:
        return row
    scope = _candidate_scope(candidate)
    if scope is None:
        return row
    protocol_number, expected_ports = scope
    expected_protocol = {6: "tcp", 17: "udp"}.get(protocol_number)
    if expected_ports is not None:
        if not expected_ports or len(expected_ports) != 1:
            return row
    try:
        paths = ec2.describe_network_insights_paths(NetworkInsightsPathIds=[path_id]).get("NetworkInsightsPaths", [])
        if not isinstance(paths, list) or len(paths) != 1 or not isinstance(paths[0], dict):
            return row
        path = paths[0]
        if (path.get("NetworkInsightsPathId") != path_id or path.get("Source") != source
                or path.get("Destination") != target or not _path_is_unscoped(path)):
            return row
        path_protocol = _protocol_name(path.get("Protocol"))
        if path_protocol not in {"tcp", "udp"}:
            return row
        if expected_protocol and path_protocol != expected_protocol:
            return row
        destination_port = path.get("DestinationPort")
        if expected_ports is not None and destination_port not in expected_ports:
            return row
        analyses = ec2.describe_network_insights_analyses(
            NetworkInsightsPathId=path_id, MaxResults=ANALYSIS_LIMIT
        ).get("NetworkInsightsAnalyses", [])
    except (ClientError, BotoCoreError, ValueError, TypeError, KeyError):
        return row

    if not isinstance(analyses, list):
        return row
    if not isinstance(analyses, list):
        return row
    fresh = []
    for analysis in analyses[:ANALYSIS_LIMIT]:
        if (not isinstance(analysis, dict) or analysis.get("NetworkInsightsPathId") != path_id
                or analysis.get("Status") != "succeeded" or not isinstance(analysis.get("NetworkPathFound"), bool)):
            continue
        started = _parse_time(analysis.get("StartDate"))
        analysis_id = analysis.get("NetworkInsightsAnalysisId")
        if started and _within_snapshot(started, snapshot) and isinstance(analysis_id, str) and analysis_id:
            fresh.append((started, analysis_id, analysis["NetworkPathFound"]))
    if not fresh:
        return row
    started, analysis_id, found = max(fresh, key=lambda item: item[0])
    row.update({
        "verdict": "CORROBORATES" if found else "DISAGREES",
        "evidenceId": f"{analysis_id}:{int(started.timestamp())}",
        "originId": f"reachabilityAnalyzer:{path_id}:{analysis_id}",
    })
    return row


def _client(service, region):
    import boto3
    return boto3.client(service, region_name=region, config=Config(
        connect_timeout=2, read_timeout=5,
        retries={"total_max_attempts": 1, "mode": "standard"}))


def _cached_client(service, region, cache):
    if cache is not None and service in cache:
        return cache[service]
    try:
        client = _client(service, region)
    except (BotoCoreError, ValueError, TypeError):
        client = None
    if cache is not None:
        cache[service] = client
    return client


def collect_verdicts(candidate, inventory, ec2=None, logs=None, *, network_evidence=False, client_cache=None):
    """Return exactly one closed-schema row for each optional AWS evidence source.

    This function only describes configured resources and reads existing Flow Log
    events. It never creates Network Insights paths or starts analyses. Both
    sources fail to UNKNOWN when disabled, local, missing configuration, stale,
    malformed, inaccessible, or insufficiently scoped.
    """
    flow = _base_row(candidate if isinstance(candidate, dict) else {}, "flowLogs")
    reachability = _base_row(candidate if isinstance(candidate, dict) else {}, "reachabilityAnalyzer")
    enabled = os.environ.get("CROSS_VALIDATION_ENABLED", "false").lower() == "true"
    if network_evidence:
        enabled = os.environ.get("NETWORK_EVIDENCE_ENABLED", "false").lower() == "true"
    if is_local() or not enabled:
        return [flow, reachability]
    if not _valid_candidate(candidate, inventory):
        return [flow, reachability]

    meta = inventory.get("meta", {})
    region = meta.get("region") if isinstance(meta, dict) else None
    group = os.environ.get("FLOW_LOGS_GROUP_NAME", "")
    mapping = _path_mapping(os.environ.get("CROSS_VALIDATION_PATHS_JSON", ""))
    source, target = candidate["sourceId"], candidate["targetId"]
    configured_path = mapping.get(f"{source}|{target}")

    if group:
        active_logs = logs
        if active_logs is None and isinstance(region, str) and region:
            active_logs = _cached_client("logs", region, client_cache)
        flow = _flow_logs_verdict(candidate, inventory, active_logs, group)
    if configured_path:
        active_ec2 = ec2
        if active_ec2 is None and isinstance(region, str) and region:
            active_ec2 = _cached_client("ec2", region, client_cache)
        reachability = _reachability_verdict(candidate, inventory, active_ec2, mapping)
    return [flow, reachability]
