"""SDK-stubbed serverless metadata tests; never contact AWS."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from common import inventory, serverless_inventory
from test_inventory_v2 import FakeClient, FakePaginator, make_session, denied

TABLE = "arn:aws:dynamodb:ap-south-1:123456789012:table/guardian"
FUNCTION = "arn:aws:lambda:ap-south-1:123456789012:function:worker"
STREAM = TABLE + "/stream/2026-10-16T00:00:00.000"
FLAGS = {"DYNAMODB_INVENTORY_ENABLED": "true", "LAMBDA_INVENTORY_ENABLED": "true", "SERVERLESS_RELATIONSHIPS_ENABLED": "true"}


def session_for(mappings=None, table_pages=None, describe=None):
    session = make_session(functions=[{"FunctionArn": FUNCTION, "FunctionName": "worker"}])
    dynamodb = FakeClient(describe_table=describe or {"Table": {"TableName": "guardian", "TableArn": TABLE,
        "TableStatus": "ACTIVE", "LatestStreamArn": STREAM, "StreamSpecification": {"StreamEnabled": True}}})
    dynamodb.paginators["list_tables"] = FakePaginator(table_pages or [{"TableNames": ["guardian"]}])
    session.clients["dynamodb"] = dynamodb
    session.clients["lambda"].paginators["list_event_source_mappings"] = FakePaginator(
        [{"EventSourceMappings": mappings if mappings is not None else [mapping()]}])
    return session


def mapping(**changes):
    return {"UUID": "00000000-0000-0000-0000-000000000001", "EventSourceArn": STREAM, "FunctionArn": FUNCTION, "State": "Enabled", **changes}


class ServerlessInventoryTests(unittest.TestCase):
    def collect(self, session, flags=None):
        with patch("common.inventory.boto3.session.Session", return_value=session), patch.dict("os.environ", FLAGS if flags is None else flags, clear=True):
            return inventory.collect_inventory("ap-south-1")

    def test_botocore_stubber_validates_api_shapes_and_exact_calls(self):
        import boto3
        from botocore.stub import Stubber
        session = boto3.Session(region_name="ap-south-1", aws_access_key_id="CIGLOCAL", aws_secret_access_key="CIGLOCAL")
        dynamodb = session.client("dynamodb")
        lambda_client = session.client("lambda")
        clients = {"dynamodb": dynamodb, "lambda": lambda_client}
        class Session:
            def client(self, name):
                return clients[name]
        nodes = {FUNCTION: {"resourceId": FUNCTION, "resourceType": serverless_inventory.FUNCTION_TYPE}}
        edges, warnings = [], []
        coverage = {serverless_inventory.FUNCTION_TYPE: "COMPLETE"}
        with Stubber(dynamodb) as tables, Stubber(lambda_client) as mappings:
            tables.add_response("list_tables", {"TableNames": ["guardian"]}, {})
            tables.add_response("describe_table", {"Table": {"TableName": "guardian", "TableArn": TABLE, "LatestStreamArn": STREAM, "StreamSpecification": {"StreamEnabled": True}}}, {"TableName": "guardian"})
            mappings.add_response("list_event_source_mappings", {"EventSourceMappings": [mapping()]}, {})
            state = serverless_inventory.collect_serverless(Session(), nodes, edges, warnings, coverage,
                "ap-south-1", "123456789012", "2026-10-16T00:00:00Z", tables_enabled=True,
                mappings_enabled=True, lambda_enabled=True)
            tables.assert_no_pending_responses()
            mappings.assert_no_pending_responses()
        self.assertEqual(state, "COMPLETE")
        self.assertEqual(len(edges), 1)
        self.assertFalse(warnings)

    def test_local_hard_guard_precedes_any_session_creation(self):
        for variable in ("CIG_LOCAL", "AWS_SAM_LOCAL"):
            with self.subTest(variable=variable), patch.dict("os.environ", {**FLAGS, variable: "true"}, clear=True), patch("common.inventory.boto3.session.Session") as session:
                with self.assertRaises(inventory.ObservationUnavailable):
                    inventory.collect_inventory("ap-south-1")
                session.assert_not_called()

    def test_actual_arn_name_and_configured_structural_edge(self):
        session = session_for()
        result = self.collect(session)
        table = next(x for x in result["items"] if x["resourceId"] == TABLE)
        self.assertEqual(table["name"], "guardian")
        self.assertEqual(table["resourceType"], "AWS::DynamoDB::Table")
        self.assertIsNone(table["tags"])
        edges = [x for x in result["edges"] if x["type"] == "DYNAMODB_STREAM_TRIGGER"]
        self.assertEqual(len(edges), 1)
        self.assertEqual((edges[0]["sourceId"], edges[0]["targetId"]), (TABLE, FUNCTION))
        self.assertEqual(edges[0]["configurationState"], "CONFIGURED")
        self.assertEqual(edges[0]["observationKind"], "STRUCTURAL")
        self.assertEqual(edges[0]["evidence"][0]["eventSourceArn"], STREAM)
        self.assertEqual(result["meta"]["coverage"]["relationshipTypes"]["DYNAMODB_STREAM_TRIGGER"], "COMPLETE")
        self.assertEqual(session.clients["dynamodb"].calls, [("get_paginator", {"operation": "list_tables"}), ("describe_table", {"TableName": "guardian"})])

    def test_flags_off_create_no_new_clients_or_mapping_reads(self):
        session = session_for()
        result = self.collect(session, {})
        self.assertNotIn("dynamodb", [s for s, _ in session.created])
        self.assertNotIn("lambda", [s for s, _ in session.created])
        self.assertEqual(result["meta"]["coverage"]["resourceTypes"]["AWS::DynamoDB::Table"], "UNSUPPORTED")
        self.assertEqual(result["meta"]["coverage"]["relationshipTypes"]["DYNAMODB_STREAM_TRIGGER"], "UNSUPPORTED")
        session = session_for()
        self.collect(session, {"LAMBDA_INVENTORY_ENABLED": "true", "DYNAMODB_INVENTORY_ENABLED": "true"})
        self.assertNotIn(("get_paginator", {"operation": "list_event_source_mappings"}), session.clients["lambda"].calls)

    def test_disabled_mapping_retains_state_but_no_active_edge(self):
        result = self.collect(session_for([mapping(State="Disabled")]))
        self.assertFalse(any(x["type"] == "DYNAMODB_STREAM_TRIGGER" for x in result["edges"]))
        table = next(x for x in result["items"] if x["resourceId"] == TABLE)
        self.assertEqual(table["attributes"]["eventSourceMappings"][0]["state"], "Disabled")
        self.assertEqual(result["meta"]["coverage"]["relationshipTypes"]["DYNAMODB_STREAM_TRIGGER"], "COMPLETE")

    def test_exact_endpoint_binding_rejects_other_account_alias_and_missing_table(self):
        for changes in ({"FunctionArn": FUNCTION + ":alias"}, {"EventSourceArn": STREAM.replace("123456789012", "999999999999")}, {"FunctionArn": FUNCTION.replace("ap-south-1", "us-east-1")}):
            with self.subTest(changes=changes):
                result = self.collect(session_for([mapping(**changes)]))
                self.assertFalse(any(x["type"] == "DYNAMODB_STREAM_TRIGGER" for x in result["edges"]))
                self.assertEqual(result["meta"]["coverage"]["relationshipTypes"]["DYNAMODB_STREAM_TRIGGER"], "PARTIAL")

    def test_transitional_mapping_unknown_and_non_dynamodb_not_an_edge(self):
        result = self.collect(session_for([mapping(State="Enabling"), mapping(EventSourceArn="arn:aws:sqs:ap-south-1:123456789012:q")]))
        self.assertFalse(any(x["type"] == "DYNAMODB_STREAM_TRIGGER" for x in result["edges"]))
        self.assertEqual(result["meta"]["coverage"]["relationshipTypes"]["DYNAMODB_STREAM_TRIGGER"], "PARTIAL")

    def test_describe_denial_and_list_denial_are_partial(self):
        for session in (session_for(describe=denied("DescribeTable")), session_for(table_pages=[denied("ListTables")])):
            result = self.collect(session)
            self.assertEqual(result["meta"]["coverage"]["resourceTypes"]["AWS::DynamoDB::Table"], "PARTIAL")
            self.assertEqual(result["meta"]["coverage"]["relationshipTypes"]["DYNAMODB_STREAM_TRIGGER"], "PARTIAL")
            self.assertTrue(result["meta"]["partial"])

    def test_mapping_denial_preserves_table_metadata(self):
        session = session_for()
        session.clients["lambda"].paginators["list_event_source_mappings"] = FakePaginator([denied("ListEventSourceMappings")])
        result = self.collect(session)
        self.assertTrue(any(x["resourceId"] == TABLE for x in result["items"]))
        self.assertEqual(result["meta"]["coverage"]["relationshipTypes"]["DYNAMODB_STREAM_TRIGGER"], "PARTIAL")

    def test_table_arn_must_match_observed_account_region_and_listed_name(self):
        for arn, name in ((TABLE.replace("123456789012", "999999999999"), "guardian"),
                          (TABLE.replace("ap-south-1", "us-east-1"), "guardian"),
                          (TABLE + "/suffix", "guardian"), ("malformed", "guardian"),
                          (TABLE, "other")):
            with self.subTest(arn=arn, name=name):
                result = self.collect(session_for(describe={"Table": {"TableName": name, "TableArn": arn}}))
                self.assertFalse(any(x["resourceType"] == "AWS::DynamoDB::Table" for x in result["items"]))
                self.assertEqual(result["meta"]["coverage"]["resourceTypes"]["AWS::DynamoDB::Table"], "PARTIAL")
                self.assertFalse(any(x["type"] == "DYNAMODB_STREAM_TRIGGER" for x in result["edges"]))

    def test_enabled_mapping_requires_exact_current_enabled_table_stream(self):
        for stream, enabled in ((STREAM + "-old", True), (STREAM, False), (None, True), (STREAM, None)):
            with self.subTest(stream=stream, enabled=enabled):
                result = self.collect(session_for(describe={"Table": {"TableName": "guardian", "TableArn": TABLE,
                    "LatestStreamArn": stream, "StreamSpecification": {"StreamEnabled": enabled}}}))
                self.assertFalse(any(x["type"] == "DYNAMODB_STREAM_TRIGGER" for x in result["edges"]))
                self.assertEqual(result["meta"]["coverage"]["relationshipTypes"]["DYNAMODB_STREAM_TRIGGER"], "PARTIAL")
                table = next(x for x in result["items"] if x["resourceId"] == TABLE)
                self.assertEqual(len(table["attributes"]["eventSourceMappings"]), 1)

    def test_caps_bound_tables_and_mappings_and_mark_partial(self):
        session = session_for([mapping(), mapping(UUID="mapping-2")], [{"TableNames": ["guardian", "other"]}])
        with patch.object(serverless_inventory, "MAX_SERVERLESS_ITEMS", 1):
            result = self.collect(session)
        self.assertEqual(sum(name == "describe_table" for name, _ in session.clients["dynamodb"].calls), 1)
        self.assertEqual(sum(x["type"] == "DYNAMODB_STREAM_TRIGGER" for x in result["edges"]), 1)
        self.assertEqual(result["meta"]["coverage"]["resourceTypes"]["AWS::DynamoDB::Table"], "PARTIAL")
        self.assertEqual(result["meta"]["coverage"]["relationshipTypes"]["DYNAMODB_STREAM_TRIGGER"], "PARTIAL")

    def test_partial_later_mapping_page_retains_positive_edge(self):
        session = session_for()
        session.clients["lambda"].paginators["list_event_source_mappings"] = FakePaginator([{"EventSourceMappings": [mapping()]}, denied("ListEventSourceMappings")])
        result = self.collect(session)
        self.assertTrue(any(x["type"] == "DYNAMODB_STREAM_TRIGGER" for x in result["edges"]))
        self.assertEqual(result["meta"]["coverage"]["relationshipTypes"]["DYNAMODB_STREAM_TRIGGER"], "PARTIAL")


if __name__ == "__main__":
    unittest.main()
