"""Bounded metadata-only DynamoDB inventory and observed stream wiring."""
import re

from botocore.exceptions import BotoCoreError, ClientError

MAX_SERVERLESS_ITEMS = 100
TABLE_TYPE = "AWS::DynamoDB::Table"
FUNCTION_TYPE = "AWS::Lambda::Function"
STREAM_EDGE = "DYNAMODB_STREAM_TRIGGER"


def collect_serverless(session, nodes, edges, warnings, coverage, region, account_id,
                       observed_at, *, tables_enabled, mappings_enabled, lambda_enabled):
    """Mutate one observation; never read table items, policies or function environment."""
    def warn(source, code, message):
        warnings.append({"source": source, "code": code, "message": message[:300]})

    def error(source, exc):
        code = exc.response.get("Error", {}).get("Code", "AWS_ERROR") if isinstance(exc, ClientError) else type(exc).__name__
        warn(source, code, "Metadata enumeration failed; coverage is incomplete.")

    coverage[TABLE_TYPE] = "UNSUPPORTED"
    table_count = 0
    if tables_enabled:
        coverage[TABLE_TYPE] = "COMPLETE"
        try:
            client = session.client("dynamodb")
            pages = client.get_paginator("list_tables").paginate(PaginationConfig={"MaxItems": MAX_SERVERLESS_ITEMS})
            for page in pages:
                for name in page.get("TableNames", []):
                    if table_count >= MAX_SERVERLESS_ITEMS:
                        break
                    table_count += 1
                    try:
                        table = client.describe_table(TableName=name).get("Table", {})
                        arn = table.get("TableArn")
                        if not arn:
                            coverage[TABLE_TYPE] = "PARTIAL"
                            warn("dynamodb:tables", "MISSING_ARN", "DescribeTable did not return an actual table ARN.")
                            continue
                        arn_parts = arn.split(":", 5) if isinstance(arn, str) else []
                        if (len(arn_parts) != 6 or arn_parts[0] != "arn"
                                or not re.fullmatch(r"aws(?:-[a-z0-9]+)*", arn_parts[1])
                                or arn_parts[2] != "dynamodb" or arn_parts[3] != region
                                or not account_id or arn_parts[4] != account_id
                                or arn_parts[5] != f"table/{name}" or table.get("TableName") != name):
                            coverage[TABLE_TYPE] = "PARTIAL"
                            warn("dynamodb:tables", "INVALID_TABLE_SCOPE", "Table ARN/name did not match the observed account, region and listed table.")
                            continue
                        nodes[arn] = {
                            "resourceId": arn, "resourceType": TABLE_TYPE, "name": table.get("TableName", name),
                            "region": region, "accountId": account_id, "tags": None,
                            "attributes": {"status": table.get("TableStatus"),
                                           "streamEnabled": table.get("StreamSpecification", {}).get("StreamEnabled"),
                                           "latestStreamArn": table.get("LatestStreamArn"),
                                           "eventSourceMappings": []},
                            "relationships": [], "source": "DynamoDB ListTables + DescribeTable", "lastObservedAt": observed_at,
                        }
                    except (ClientError, BotoCoreError) as exc:
                        error("dynamodb:describe-table", exc)
                        coverage[TABLE_TYPE] = "PARTIAL"
                if table_count >= MAX_SERVERLESS_ITEMS:
                    coverage[TABLE_TYPE] = "PARTIAL"
                    warn("dynamodb:tables", "RESOURCE_CAP", "Table metadata cap reached; completeness is not established.")
                    break
        except (ClientError, BotoCoreError) as exc:
            error("dynamodb:tables", exc)
            coverage[TABLE_TYPE] = "PARTIAL"

    if not mappings_enabled or not lambda_enabled or not tables_enabled:
        return "UNSUPPORTED"
    state = "COMPLETE" if all(coverage.get(kind) == "COMPLETE" for kind in (TABLE_TYPE, FUNCTION_TYPE)) else "PARTIAL"
    count = 0
    try:
        client = session.client("lambda")
        for page in client.get_paginator("list_event_source_mappings").paginate(PaginationConfig={"MaxItems": MAX_SERVERLESS_ITEMS}):
            for mapping in page.get("EventSourceMappings", []):
                if count >= MAX_SERVERLESS_ITEMS:
                    break
                count += 1
                stream = mapping.get("EventSourceArn", "")
                if ":dynamodb:" not in stream or "/stream/" not in stream:
                    continue
                table_arn = stream.split("/stream/", 1)[0]
                function_arn = mapping.get("FunctionArn")
                table = nodes.get(table_arn)
                function = nodes.get(function_arn)
                if not table or table.get("resourceType") != TABLE_TYPE or not function or function.get("resourceType") != FUNCTION_TYPE:
                    state = "PARTIAL"
                    warn("lambda:event-source-mappings", "UNRESOLVED_ENDPOINT", "A DynamoDB stream mapping endpoint was not observed exactly in this inventory.")
                    continue
                observation = {"uuid": mapping.get("UUID"), "eventSourceArn": stream,
                               "functionArn": function_arn, "state": mapping.get("State")}
                table["attributes"]["eventSourceMappings"].append(observation)
                if mapping.get("State") == "Disabled":
                    continue
                if mapping.get("State") != "Enabled":
                    state = "PARTIAL"
                    warn("lambda:event-source-mappings", "MAPPING_TRANSITION", "A mapping is not in a stable enabled or disabled state.")
                    continue
                if (table["attributes"].get("streamEnabled") is not True
                        or table["attributes"].get("latestStreamArn") != stream):
                    state = "PARTIAL"
                    warn("lambda:event-source-mappings", "STREAM_NOT_CURRENT", "Enabled mapping does not match the table's current enabled stream.")
                    continue
                edges.append({"sourceId": table_arn, "targetId": function_arn, "type": STREAM_EDGE,
                              "status": "OBSERVED", "observationKind": "STRUCTURAL", "configurationState": "CONFIGURED",
                              "mappingState": "Enabled", "evidence": [{"kind": "STRUCTURAL", "source": "Lambda ListEventSourceMappings",
                                                                         "observedAt": observed_at, **observation}]})
                table["relationships"].append({"type": STREAM_EDGE, "targetId": function_arn})
            if count >= MAX_SERVERLESS_ITEMS:
                state = "PARTIAL"
                warn("lambda:event-source-mappings", "RESOURCE_CAP", "Mapping cap reached; completeness is not established.")
                break
    except (ClientError, BotoCoreError) as exc:
        error("lambda:event-source-mappings", exc)
        state = "PARTIAL"
    return state
