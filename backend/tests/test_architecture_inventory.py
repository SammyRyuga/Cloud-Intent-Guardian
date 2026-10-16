"""Architecture metadata contracts validated with real SDK shapes and no network."""
from pathlib import Path
import sys
import unittest
import threading
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
        cfn = self.session.client("cloudformation")
        scope_stub = Stubber(cfn)
        scope_stub.add_response("list_stack_resources", {"StackResourceSummaries": [
            {"LogicalResourceId": "Worker", "PhysicalResourceId": "worker", "ResourceType": "AWS::Lambda::Function", "ResourceStatus": "CREATE_COMPLETE", "LastUpdatedTimestamp": "2026-10-16T00:00:00Z"},
            {"LogicalResourceId": "Role", "PhysicalResourceId": "worker", "ResourceType": "AWS::IAM::Role", "ResourceStatus": "CREATE_COMPLETE", "LastUpdatedTimestamp": "2026-10-16T00:00:00Z"},
            {"LogicalResourceId": "Table", "PhysicalResourceId": "guardian", "ResourceType": "AWS::DynamoDB::Table", "ResourceStatus": "CREATE_COMPLETE", "LastUpdatedTimestamp": "2026-10-16T00:00:00Z"},
            {"LogicalResourceId": "Api", "PhysicalResourceId": "abc123", "ResourceType": API, "ResourceStatus": "CREATE_COMPLETE", "LastUpdatedTimestamp": "2026-10-16T00:00:00Z"},
        ]}, {"StackName": "guardian"})
        scope_stub.activate()
        class Session:
            def client(self, name, **config):
                return cfn if name == "cloudformation" else client
        nodes = {FUNCTION: {"resourceId": FUNCTION, "resourceType": "AWS::Lambda::Function", "attributes": {"role": ROLE}, "relationships": []}}
        nodes[TABLE] = {"resourceId": TABLE, "resourceType": "AWS::DynamoDB::Table", "attributes": {}, "relationships": []}
        edges, warnings, coverage = [], [], {}
        states = collect_architecture(Session(), nodes, edges, warnings, coverage, "ap-south-1", "123456789012", "2026-10-16T00:00:00Z", stack_name="guardian", **kwargs)
        return nodes, edges, warnings, coverage, states

    def test_api_routes_exact_integration_and_authorizer(self):
        client = self.session.client("apigatewayv2")
        with Stubber(client) as stub:
            stub.add_response("get_api", {"ApiId": "abc123", "Name": "guardian", "ProtocolType": "HTTP", "RouteSelectionExpression": "$request.method $request.path"}, {"ApiId": "abc123"})
            stub.add_response("get_integrations", {"Items": [{"IntegrationId": "int1", "IntegrationType": "AWS_PROXY", "IntegrationUri": FUNCTION}]}, {"ApiId": "abc123"})
            stub.add_response("get_authorizers", {"Items": [{"AuthorizerId": "auth1", "AuthorizerType": "JWT", "Name": "guardian", "JwtConfiguration": {"Issuer": "https://example.org", "Audience": ["client"]}}]}, {"ApiId": "abc123"})
            stub.add_response("get_routes", {"Items": [{"RouteId": "route1", "RouteKey": "GET /v1/intents", "AuthorizationType": "JWT", "AuthorizerId": "auth1", "Target": "integrations/int1"}]}, {"ApiId": "abc123"})
            nodes, edges, warnings, coverage, states = self.collect(client, api_enabled=True)
            stub.assert_no_pending_responses()
        self.assertFalse(warnings)
        self.assertEqual({e["type"] for e in edges}, {"API_ROUTE", "API_INTEGRATION", "JWT_AUTHORIZER"})
        self.assertTrue(all(e["observationKind"] == "STRUCTURAL" for e in edges))
        self.assertEqual(coverage[API], "COMPLETE")
        from common.manifest import validate_manifest
        from evaluations.app import run_pinned_evaluation
        ids = {rid: "component-" + str(i) for i, rid in enumerate(sorted(nodes))}
        manifest = validate_manifest({"schemaVersion": 2, "name": "Exact API structural contract", "constraints": [],
            "components": [{"id": ids[rid], "resourceTypes": [n["resourceType"]], "selector": {"resourceIds": [rid]}} for rid, n in nodes.items()],
            "relationships": [{"id": "relationship-" + str(i), "from": ids[e["sourceId"]], "to": ids[e["targetId"]], "effect": "ALLOW", "required": True, "relationshipType": "STRUCTURAL"} for i, e in enumerate(edges)]})
        resource_coverage = {n["resourceType"]: "COMPLETE" for n in nodes.values()}
        result, findings = run_pinned_evaluation({**manifest, "intentId": "sdk-test", "version": 1},
            {"items": list(nodes.values()), "edges": edges, "meta": {"coverage": {"resourceTypes": resource_coverage, "relationshipTypes": {"STRUCTURAL": "COMPLETE"}}}}, "sdk-test")
        self.assertFalse(findings)
        self.assertTrue(all(rule["outcome"] == "PASS" for rule in result["ruleResults"]))

    def test_api_denied_is_partial(self):
        client = self.session.client("apigatewayv2")
        with Stubber(client) as stub:
            stub.add_client_error("get_api", service_error_code="AccessDeniedException", expected_params={"ApiId": "abc123"})
            _, edges, warnings, coverage, states = self.collect(client, api_enabled=True)
        self.assertFalse(edges)
        self.assertEqual(coverage[ROUTE], "PARTIAL")
        self.assertEqual(warnings[0]["code"], "AccessDeniedException")

    def test_disabled_does_not_create_clients(self):
        class Session:
            def client(self, name):
                raise AssertionError("disabled collector called AWS")
        self.assertTrue(all(s == "UNSUPPORTED" for s in collect_architecture(Session(), {}, [], [], {}, "ap-south-1", "123456789012", "now").values()))

    def test_missing_stack_scope_never_calls_aws(self):
        class Session:
            def client(self, *args, **kwargs):
                raise AssertionError("Missing scope must not query AWS")
        warnings, coverage = [], {}
        states = collect_architecture(Session(), {}, [], warnings, coverage, "ap-south-1", "123456789012", "now", api_enabled=True)
        self.assertEqual(warnings[0]["code"], "MISSING_STACK_SCOPE")
        self.assertEqual(states["API_ROUTE"], "PARTIAL")

    def test_stack_denied_never_falls_back(self):
        cfn = self.session.client("cloudformation")
        class Session:
            def client(self, service, **kwargs):
                self_service = service
                if self_service != "cloudformation":
                    raise AssertionError("Incomplete stack scope must stop collection")
                return cfn
        with Stubber(cfn) as stub:
            stub.add_client_error("list_stack_resources", service_error_code="AccessDenied", expected_params={"StackName": "guardian"})
            warnings, coverage = [], {}
            states = collect_architecture(Session(), {}, [], warnings, coverage, "ap-south-1", "123456789012", "now", stack_name="guardian", api_enabled=True, iam_enabled=True)
        self.assertEqual(coverage[API], "PARTIAL")
        self.assertEqual(states["ASSUMES_ROLE"], "PARTIAL")
        self.assertEqual(warnings[0]["code"], "AccessDenied")

    def test_budget_exhaustion_stops_before_optional_service(self):
        client = self.session.client("apigatewayv2")
        with patch("common.architecture_inventory.MAX_CALLS", 0):
            _, edges, warnings, coverage, _ = self.collect(client, api_enabled=True)
        self.assertFalse(edges)
        self.assertEqual(coverage[API], "PARTIAL")
        self.assertEqual(warnings[0]["code"], "CollectionBudgetExceeded")

    def test_exact_scope_excludes_unrelated_lambda_role(self):
        # The observed function's role is not in this stack's physical IDs.
        client = self.session.client("iam")
        with patch(__name__ + ".ROLE", "arn:aws:iam::123456789012:role/unrelated"):
            nodes, edges, warnings, coverage, _ = self.collect(client, iam_enabled=True)
        self.assertFalse(edges)
        self.assertTrue(any(w["code"] == "ROLE_OUTSIDE_STACK" for w in warnings))
        self.assertEqual(coverage["AWS::IAM::Role"], "PARTIAL")

    def test_truncated_worker_physical_id_is_included_without_stack_prefix(self):
        client = self.session.client("iam")
        with Stubber(client) as stub, patch(__name__ + ".FUNCTION", "arn:aws:lambda:ap-south-1:123456789012:function:worker"):
            stub.add_response("list_role_policies", {"PolicyNames": []}, {"RoleName": "worker"})
            stub.add_response("list_attached_role_policies", {"AttachedPolicies": []}, {"RoleName": "worker"})
            _, edges, warnings, _, _ = self.collect(client, iam_enabled=True)
            stub.assert_no_pending_responses()
        self.assertFalse(warnings)
        self.assertEqual(edges[0]["sourceId"], FUNCTION)

    def test_incomplete_second_stack_page_discards_scope(self):
        cfn = self.session.client("cloudformation")
        class Session:
            def client(self, service, **kwargs):
                if service != "cloudformation":
                    raise AssertionError("Partial scope must not query API")
                return cfn
        with Stubber(cfn) as stub:
            stub.add_response("list_stack_resources", {"StackResourceSummaries": [{"LogicalResourceId": "Api", "PhysicalResourceId": "abc123", "ResourceType": API, "ResourceStatus": "CREATE_COMPLETE", "LastUpdatedTimestamp": "2026-10-16T00:00:00Z"}], "NextToken": "next"}, {"StackName": "guardian"})
            stub.add_client_error("list_stack_resources", service_error_code="AccessDenied", expected_params={"StackName": "guardian", "NextToken": "next"})
            warnings, coverage, nodes, edges = [], {}, {}, []
            collect_architecture(Session(), nodes, edges, warnings, coverage, "ap-south-1", "123456789012", "now", stack_name="guardian", api_enabled=True)
            stub.assert_no_pending_responses()
        self.assertFalse(nodes)
        self.assertFalse(edges)
        self.assertEqual(coverage[API], "PARTIAL")

    def test_cognito_pool_requires_stack_id_and_describe_verification(self):
        cfn, api, cognito = (self.session.client(service) for service in ("cloudformation", "apigatewayv2", "cognito-idp"))
        pool_id = "ap-south-1_ABC123"
        pool_arn = "arn:aws:cognito-idp:ap-south-1:123456789012:userpool/" + pool_id
        clients = {"cloudformation": cfn, "apigatewayv2": api, "cognito-idp": cognito}
        class Session:
            def client(self, service, **kwargs):
                return clients[service]
        with Stubber(cfn) as cs, Stubber(api) as aps, Stubber(cognito) as cos:
            cs.add_response("list_stack_resources", {"StackResourceSummaries": [
                {"LogicalResourceId": name, "PhysicalResourceId": physical, "ResourceType": kind, "ResourceStatus": "CREATE_COMPLETE", "LastUpdatedTimestamp": "2026-10-16T00:00:00Z"}
                for name, physical, kind in (("Api", "abc123", API), ("Pool", pool_id, "AWS::Cognito::UserPool"))]}, {"StackName": "guardian"})
            aps.add_response("get_api", {"ApiId": "abc123", "Name": "guardian", "ProtocolType": "HTTP", "RouteSelectionExpression": "$request.method $request.path"}, {"ApiId": "abc123"})
            aps.add_response("get_integrations", {"Items": []}, {"ApiId": "abc123"})
            aps.add_response("get_authorizers", {"Items": [{"AuthorizerId": "auth1", "AuthorizerType": "JWT", "Name": "guardian", "JwtConfiguration": {"Issuer": "https://cognito-idp.ap-south-1.amazonaws.com/" + pool_id}}]}, {"ApiId": "abc123"})
            cos.add_response("describe_user_pool", {"UserPool": {"Id": pool_id, "Arn": pool_arn, "Name": "guardian"}}, {"UserPoolId": pool_id})
            aps.add_response("get_routes", {"Items": []}, {"ApiId": "abc123"})
            nodes, edges, warnings = {}, [], []
            coverage = {}
            states = collect_architecture(Session(), nodes, edges, warnings, coverage, "ap-south-1", "123456789012", "now", stack_name="guardian", api_enabled=True, cognito_enabled=True)
            for stub in (cs, aps, cos):
                stub.assert_no_pending_responses()
        self.assertFalse(warnings)
        self.assertEqual(coverage["AWS::Cognito::UserPool"], "COMPLETE")
        self.assertEqual(states["JWT_ISSUER"], "COMPLETE")
        self.assertIn(pool_arn, nodes)
        self.assertEqual(edges[0]["type"], "JWT_ISSUER")

    def test_concurrent_roles_keep_documents_separate_and_merge_deterministically(self):
        barrier = threading.Barrier(3)
        names = ["role-a", "role-b", "role-c"]
        class Pages:
            def __init__(self, operation):
                self.operation = operation
            def paginate(self, **kwargs):
                if self.operation == "list_stack_resources":
                    yield {"StackResourceSummaries": [
                        {"ResourceType": kind, "PhysicalResourceId": name}
                        for name in names for kind in ("AWS::Lambda::Function", "AWS::IAM::Role")]}
                elif self.operation == "list_role_policies":
                    barrier.wait(timeout=3)
                    yield {"PolicyNames": [kwargs["RoleName"] + "-policy"]}
                else:
                    yield {"AttachedPolicies": []}
        class Client:
            def get_paginator(self, operation):
                return Pages(operation)
            def get_role_policy(self, RoleName, PolicyName):
                if PolicyName != RoleName + "-policy":
                    raise AssertionError("Role policy mixed across workers")
                return {"PolicyDocument": {"Statement": [{"Effect": "Allow", "Action": "dynamodb:GetItem", "Resource": RoleName}]}}
        class Session:
            def client(self, *args, **kwargs):
                return Client()
        nodes = {}
        for name in reversed(names):
            rid = FUNCTION.rsplit(":", 1)[0] + ":" + name
            nodes[rid] = {"resourceId": rid, "resourceType": "AWS::Lambda::Function", "attributes": {"role": ROLE.rsplit("/", 1)[0] + "/" + name}, "relationships": []}
        warnings = []
        collect_architecture(Session(), nodes, [], warnings, {}, "ap-south-1", "123456789012", "now", stack_name="guardian", iam_enabled=True)
        self.assertFalse(warnings)
        for name in names:
            role = ROLE.rsplit("/", 1)[0] + "/" + name
            self.assertEqual(nodes[role]["attributes"]["policyDeclarations"][0]["resources"], [name])

    def test_iam_denial_keeps_role_link_but_marks_policy_coverage_partial(self):
        client = self.session.client("iam")
        with Stubber(client) as stub:
            stub.add_client_error("list_role_policies", service_error_code="AccessDenied", expected_params={"RoleName": "worker"})
            nodes, edges, warnings, coverage, states = self.collect(client, iam_enabled=True)
            stub.assert_no_pending_responses()
        self.assertEqual(edges[0]["type"], "ASSUMES_ROLE")
        self.assertEqual(coverage["AWS::IAM::Role"], "PARTIAL")
        self.assertEqual(nodes[ROLE]["attributes"]["policyDeclarations"], [])
        self.assertEqual(warnings[0]["code"], "AccessDenied")

    def test_policy_request_cap_stops_before_get_role_policy(self):
        client = self.session.client("iam")
        with Stubber(client) as stub, patch("common.architecture_inventory.MAX_CALLS", 2):
            stub.add_response("list_role_policies", {"PolicyNames": ["data"]}, {"RoleName": "worker"})
            _, _, warnings, coverage, _ = self.collect(client, iam_enabled=True)
            stub.assert_no_pending_responses()
        self.assertEqual(coverage["AWS::IAM::Role"], "PARTIAL")
        self.assertTrue(any(w["code"] == "CollectionBudgetExceeded" for w in warnings))

    def test_unobserved_stack_function_never_claims_complete_roles(self):
        client = self.session.client("iam")
        with patch(__name__ + ".FUNCTION", "arn:aws:lambda:ap-south-1:123456789012:function:outside"):
            _, edges, warnings, coverage, _ = self.collect(client, iam_enabled=True)
        self.assertFalse(edges)
        self.assertEqual(coverage["AWS::IAM::Role"], "PARTIAL")
        self.assertTrue(any(w["code"] == "UNOBSERVED_STACK_FUNCTION" for w in warnings))

    def test_api_integration_to_observed_outside_stack_function_is_unresolved(self):
        client = self.session.client("apigatewayv2")
        outside = "arn:aws:lambda:ap-south-1:123456789012:function:outside"
        with Stubber(client) as stub, patch(__name__ + ".FUNCTION", outside):
            stub.add_response("get_api", {"ApiId": "abc123", "Name": "guardian", "ProtocolType": "HTTP", "RouteSelectionExpression": "$request.method $request.path"}, {"ApiId": "abc123"})
            stub.add_response("get_integrations", {"Items": [{"IntegrationId": "int1", "IntegrationType": "AWS_PROXY", "IntegrationUri": outside}]}, {"ApiId": "abc123"})
            stub.add_response("get_authorizers", {"Items": []}, {"ApiId": "abc123"})
            stub.add_response("get_routes", {"Items": [{"RouteId": "route1", "RouteKey": "GET /v1/health", "AuthorizationType": "NONE", "Target": "integrations/int1"}]}, {"ApiId": "abc123"})
            _, edges, warnings, _, states = self.collect(client, api_enabled=True)
            stub.assert_no_pending_responses()
        self.assertFalse(any(e["type"] == "API_INTEGRATION" for e in edges))
        self.assertEqual(states["API_INTEGRATION"], "PARTIAL")
        self.assertTrue(any(w["code"] == "UNRESOLVED_INTEGRATION" for w in warnings))

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
