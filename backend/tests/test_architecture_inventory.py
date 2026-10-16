"""Architecture metadata contracts validated with real SDK shapes and no network."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import boto3
from botocore.stub import Stubber
from common.architecture_inventory import collect_architecture, simulate_declared_permission, API, ROUTE

ROLE = "arn:aws:iam::123456789012:role/worker"
TABLE = "arn:aws:dynamodb:ap-south-1:123456789012:table/guardian"
FUNCTION = "arn:aws:lambda:ap-south-1:123456789012:function:worker"

class ArchitectureTests(unittest.TestCase):
    def setUp(self):
        self.session = boto3.Session(region_name="ap-south-1", aws_access_key_id="CIGLOCAL", aws_secret_access_key="CIGLOCAL")

    def collect(self, client, **kwargs):
        class Session:
            def client(self, name):
                return client
        nodes = {FUNCTION: {"resourceId": FUNCTION, "resourceType": "AWS::Lambda::Function", "attributes": {"role": ROLE}, "relationships": []}}
        nodes[TABLE] = {"resourceId": TABLE, "resourceType": "AWS::DynamoDB::Table", "attributes": {}, "relationships": []}
        edges, warnings, coverage = [], [], {}
        states = collect_architecture(Session(), nodes, edges, warnings, coverage, "ap-south-1", "123456789012", "2026-10-16T00:00:00Z", **kwargs)
        return nodes, edges, warnings, coverage, states

    def test_api_routes_exact_integration_and_authorizer(self):
        client = self.session.client("apigatewayv2")
        with Stubber(client) as stub:
            stub.add_response("get_apis", {"Items": [{"ApiId": "abc123", "Name": "guardian", "ProtocolType": "HTTP", "RouteSelectionExpression": "$request.method $request.path"}]}, {})
            stub.add_response("get_integrations", {"Items": [{"IntegrationId": "int1", "IntegrationType": "AWS_PROXY", "IntegrationUri": FUNCTION}]}, {"ApiId": "abc123"})
            stub.add_response("get_authorizers", {"Items": [{"AuthorizerId": "auth1", "AuthorizerType": "JWT", "Name": "guardian", "JwtConfiguration": {"Issuer": "https://example.org", "Audience": ["client"]}}]}, {"ApiId": "abc123"})
            stub.add_response("get_routes", {"Items": [{"RouteId": "route1", "RouteKey": "GET /v1/intents", "AuthorizationType": "JWT", "AuthorizerId": "auth1", "Target": "integrations/int1"}]}, {"ApiId": "abc123"})
            nodes, edges, warnings, coverage, states = self.collect(client, api_enabled=True)
            stub.assert_no_pending_responses()
        self.assertFalse(warnings)
        self.assertEqual({e["type"] for e in edges}, {"API_ROUTE", "API_INTEGRATION", "JWT_AUTHORIZER"})
        self.assertTrue(all(e["observationKind"] == "STRUCTURAL" for e in edges))
        self.assertEqual(coverage[API], "COMPLETE")

    def test_api_denied_is_partial(self):
        client = self.session.client("apigatewayv2")
        with Stubber(client) as stub:
            stub.add_client_error("get_apis", service_error_code="AccessDeniedException", expected_params={})
            _, edges, warnings, coverage, states = self.collect(client, api_enabled=True)
        self.assertFalse(edges)
        self.assertEqual(coverage[ROUTE], "PARTIAL")
        self.assertEqual(warnings[0]["code"], "AccessDeniedException")

    def test_disabled_does_not_create_clients(self):
        class Session:
            def client(self, name):
                raise AssertionError("disabled collector called AWS")
        self.assertTrue(all(s == "UNSUPPORTED" for s in collect_architecture(Session(), {}, [], [], {}, "ap-south-1", "123456789012", "now").values()))

    def test_simulator_allowed_is_not_effective_authorization(self):
        client = self.session.client("iam")
        with Stubber(client) as stub:
            stub.add_response("simulate_principal_policy", {"EvaluationResults": [{"EvalActionName": "dynamodb:GetItem", "EvalResourceName": TABLE, "EvalDecision": "allowed", "MissingContextValues": ["aws:SourceVpce"]}]}, {"PolicySourceArn": ROLE, "ActionNames": ["dynamodb:GetItem"], "ResourceArns": [TABLE]})
            result = simulate_declared_permission(client, ROLE, "dynamodb:GetItem", TABLE)
        self.assertEqual(result["simulationDecision"], "allowed")
        self.assertEqual(result["effectiveAuthorization"], "UNKNOWN")

    def test_simulation_denied_and_scope_guard(self):
        client = self.session.client("iam")
        with Stubber(client) as stub:
            stub.add_client_error("simulate_principal_policy", service_error_code="AccessDenied", expected_params={"PolicySourceArn": ROLE, "ActionNames": ["dynamodb:GetItem"], "ResourceArns": [TABLE]})
            self.assertEqual(simulate_declared_permission(client, ROLE, "dynamodb:GetItem", TABLE)["simulationDecision"], "UNKNOWN")
        with self.assertRaises(ValueError):
            simulate_declared_permission(client, ROLE, "dynamodb:*", TABLE)
        with self.assertRaises(ValueError):
            simulate_declared_permission(client, ROLE, "dynamodb:GetItem", TABLE.replace("123456789012", "999999999999"))

    def test_row_cap_marks_incomplete(self):
        client = self.session.client("apigatewayv2")
        with Stubber(client) as stub, patch("common.architecture_inventory.MAX_ITEMS", 1):
            stub.add_response("get_apis", {"Items": [{"ApiId": "abc123", "Name": "guardian", "ProtocolType": "HTTP", "RouteSelectionExpression": "$request.method $request.path"}]}, {})
            for operation in ("get_integrations", "get_authorizers", "get_routes"):
                stub.add_response(operation, {"Items": []}, {"ApiId": "abc123"})
            _, _, warnings, coverage, states = self.collect(client, api_enabled=True)
        self.assertTrue(any(w["code"] == "RESOURCE_CAP" for w in warnings))
        self.assertEqual(states["API_ROUTE"], "PARTIAL")

    def test_iam_declarations_remain_unknown(self):
        client = self.session.client("iam")
        with Stubber(client) as stub:
            stub.add_response("list_role_policies", {"PolicyNames": ["data"]}, {"RoleName": "worker"})
            stub.add_response("get_role_policy", {"RoleName": "worker", "PolicyName": "data", "PolicyDocument": '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"dynamodb:GetItem","Resource":"*"}]}'}, {"RoleName": "worker", "PolicyName": "data"})
            stub.add_response("list_attached_role_policies", {"AttachedPolicies": []}, {"RoleName": "worker"})
            nodes, edges, warnings, coverage, states = self.collect(client, iam_enabled=True)
        self.assertFalse(warnings)
        self.assertEqual(nodes[ROLE]["attributes"]["effectiveAuthorization"], "UNKNOWN")
        self.assertEqual(edges[0]["type"], "ASSUMES_ROLE")
        self.assertEqual(states["IAM_DECLARED_PERMISSION"], "PARTIAL")
        declared = next(e for e in edges if e["type"] == "IAM_DECLARED_PERMISSION")
        self.assertEqual(declared["targetId"], TABLE)
        self.assertEqual(declared["evidence"][0]["effectiveAuthorization"], "UNKNOWN")
