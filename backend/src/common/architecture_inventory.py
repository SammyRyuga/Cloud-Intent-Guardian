"""Bounded API wiring and declared IAM metadata; never claims effective access."""
import re
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import json
from urllib.parse import unquote
from fnmatch import fnmatchcase
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

MAX_ITEMS = 100
MAX_CALLS = 100
DEADLINE_SECONDS = 12


class CollectionBudgetExceeded(BotoCoreError):
    fmt = "Architecture collection budget exhausted"


API = "AWS::ApiGatewayV2::Api"
ROUTE = "AWS::ApiGatewayV2::Route"
AUTHORIZER = "AWS::ApiGatewayV2::Authorizer"
ROLE = "AWS::IAM::Role"
EDGE_TYPES = {"API_ROUTE", "API_INTEGRATION", "JWT_AUTHORIZER", "ASSUMES_ROLE", "IAM_DECLARED_PERMISSION", "JWT_ISSUER"}


def collect_architecture(session, nodes, edges, warnings, coverage, region, account_id,
                         observed_at, *, api_enabled=False, iam_enabled=False, cognito_enabled=False, stack_name=None):
    """Project metadata only. Policy allows are declarations, never authorization proof."""
    guard = Lock()
    policy_guard = Lock()
    initial_warning_count = len(warnings)
    states = {kind: "UNSUPPORTED" for kind in EDGE_TYPES}
    for kind in (API, ROUTE, AUTHORIZER, ROLE):
        coverage[kind] = "UNSUPPORTED"

    def warn(source, code):
        with guard:
            warnings.append({"source": source, "code": code, "message": "Architecture metadata is incomplete; effective authorization and network reachability remain unknown."})

    def failure(source, exc):
        warn(source, exc.response.get("Error", {}).get("Code", "AWS_ERROR") if isinstance(exc, ClientError) else type(exc).__name__)

    def node(rid, kind, name, attrs, source):
        nodes[rid] = {"resourceId": rid, "resourceType": kind, "name": name, "region": region,
                      "accountId": account_id, "tags": None, "attributes": attrs, "relationships": [],
                      "source": source, "lastObservedAt": observed_at}

    def edge(source, target, kind, **metadata):
        edges.append({"sourceId": source, "targetId": target, "type": kind, "status": "OBSERVED",
                      "observationKind": "STRUCTURAL", "configurationState": "CONFIGURED",
                      "evidence": [{"kind": "STRUCTURAL", "source": "AWS architecture metadata",
                                    "observedAt": observed_at, **metadata}]})
        nodes[source]["relationships"].append({"type": kind, "targetId": target})

    remaining = [MAX_ITEMS * 4]
    deadline = time.monotonic() + DEADLINE_SECONDS
    calls = [0]

    def check_budget():
        with guard:
            if time.monotonic() >= deadline or calls[0] >= MAX_CALLS:
                raise CollectionBudgetExceeded()
            calls[0] += 1

    def client(service):
        return session.client(service, config=Config(connect_timeout=1, read_timeout=2,
                              retries={"total_max_attempts": 1, "mode": "standard"}))

    def call(client, operation, **kwargs):
        check_budget()
        return getattr(client, operation)(**kwargs)


    def rows(client, operation, key, *, row_limit=None, **kwargs):
        limit = MAX_ITEMS if row_limit is None else row_limit
        count = 0
        pages = iter(client.get_paginator(operation).paginate(**kwargs))
        while True:
            check_budget()
            try:
                page = next(pages)
            except StopIteration:
                with guard:
                    calls[0] -= 1
                break
            for item in page.get(key, []):
                with guard:
                    exhausted = count >= limit or remaining[0] <= 0
                    if not exhausted:
                        remaining[0] -= 1
                if exhausted:
                    warn(operation, "RESOURCE_CAP")
                    return
                count += 1
                yield item
            if count >= limit:
                warn(operation, "RESOURCE_CAP")
                return

    if not (api_enabled or iam_enabled or cognito_enabled):
        return states
    # No name-prefix approximation and no account-wide fallback. A complete stack
    # listing is required before any optional architecture service is queried.
    scope = {}
    before_scope = len(warnings)
    try:
        if not stack_name:
            warn("cloudformation:stack", "MISSING_STACK_SCOPE")
        else:
            for resource in rows(client("cloudformation"), "list_stack_resources", "StackResourceSummaries", row_limit=MAX_ITEMS * 4, StackName=stack_name):
                physical = resource.get("PhysicalResourceId")
                if physical:
                    scope.setdefault(resource.get("ResourceType"), set()).add(physical)
    except (ClientError, BotoCoreError) as exc:
        failure("cloudformation:stack", exc)
    if len(warnings) != before_scope:
        for kind in (API, ROUTE, AUTHORIZER, ROLE, "AWS::Cognito::UserPool"):
            if (kind == ROLE and iam_enabled) or (kind in (API, ROUTE, AUTHORIZER) and api_enabled) or (kind == "AWS::Cognito::UserPool" and cognito_enabled):
                coverage[kind] = "PARTIAL"
        return {kind: "PARTIAL" if (iam_enabled and kind in ("ASSUMES_ROLE", "IAM_DECLARED_PERMISSION")) or (api_enabled and kind in ("API_ROUTE", "API_INTEGRATION", "JWT_AUTHORIZER")) or (cognito_enabled and kind == "JWT_ISSUER") else status for kind, status in states.items()}

    partition = "aws"
    for rid in nodes:
        if rid.startswith("arn:"):
            partition = rid.split(":")[1]
            break
    # Roles are restricted to those actually declared by observed Lambda functions.
    roles = {}
    if iam_enabled:
        states["ASSUMES_ROLE"] = "COMPLETE"
        states["IAM_DECLARED_PERMISSION"] = "PARTIAL"  # effective access is intentionally unmodeled
        coverage[ROLE] = "COMPLETE"
        observed_functions = {n["resourceId"].rsplit(":", 1)[-1] for n in nodes.values()
                              if n.get("resourceType") == "AWS::Lambda::Function"}
        if scope.get("AWS::Lambda::Function", set()) - observed_functions:
            warn("iam:roles", "UNOBSERVED_STACK_FUNCTION")
        for function in list(nodes.values()):
            if function.get("resourceType") != "AWS::Lambda::Function":
                continue
            if function["resourceId"].rsplit(":", 1)[-1] not in scope.get("AWS::Lambda::Function", set()):
                continue
            arn = function.get("attributes", {}).get("role") or ""
            if arn.rsplit("/", 1)[-1] not in scope.get(ROLE, set()):
                warn("iam:roles", "ROLE_OUTSIDE_STACK")
                continue
            if not re.fullmatch(r"arn:aws(?:-[a-z0-9]+)*:iam::" + re.escape(account_id or "INVALID") + r":role/[\w+=,.@/-]+", arn):
                states["ASSUMES_ROLE"] = coverage[ROLE] = "PARTIAL"
                warn("iam:roles", "INVALID_ROLE_SCOPE")
                continue
            if len(roles) >= MAX_ITEMS and arn not in roles:
                warn("iam:roles", "RESOURCE_CAP")
                states["ASSUMES_ROLE"] = coverage[ROLE] = "PARTIAL"
                continue
            roles[arn] = arn.rsplit("/", 1)[-1]
            if arn not in nodes:
                node(arn, ROLE, roles[arn], {"effectiveAuthorization": "UNKNOWN"}, "Lambda ListFunctions Role")
            edge(function["resourceId"], arn, "ASSUMES_ROLE")
    cognito = client("cognito-idp") if cognito_enabled else None
    pool_cache = {}
    if cognito_enabled:
        coverage["AWS::Cognito::UserPool"] = "COMPLETE"
        states["JWT_ISSUER"] = "COMPLETE" if api_enabled else "UNSUPPORTED"
        for pool_id in sorted(scope.get("AWS::Cognito::UserPool", set())):
            try:
                pool = call(cognito, "describe_user_pool", UserPoolId=pool_id).get("UserPool", {})
                expected = f"arn:{partition}:cognito-idp:{region}:{account_id}:userpool/{pool_id}"
                if pool.get("Arn") != expected or pool.get("Id") != pool_id:
                    warn("cognito:userpool", "INVALID_POOL_SCOPE")
                    continue
                pool_cache[pool_id] = expected
                node(expected, "AWS::Cognito::UserPool", pool_id, {"status": pool.get("Status")}, "Cognito DescribeUserPool")
            except (ClientError, BotoCoreError) as exc:
                failure("cognito:userpool", exc)
    if api_enabled:
        for kind in (API, ROUTE, AUTHORIZER):
            coverage[kind] = "COMPLETE"
        for kind in ("API_ROUTE", "API_INTEGRATION", "JWT_AUTHORIZER"):
            states[kind] = "COMPLETE"
        try:
            api_client = client("apigatewayv2")
            for scoped_api_id in sorted(scope.get(API, set())):
                api = call(api_client, "get_api", ApiId=scoped_api_id)
                api_id = api.get("ApiId", "")
                if api_id != scoped_api_id or not re.fullmatch(r"[a-z0-9]+", api_id) or not account_id:
                    warn("apigatewayv2", "INVALID_API_SCOPE")
                    continue
                api_arn = f"arn:{partition}:apigateway:{region}::/apis/{api_id}"
                node(api_arn, API, api.get("Name", api_id), {"protocolType": api.get("ProtocolType"), "disableExecuteApiEndpoint": api.get("DisableExecuteApiEndpoint")}, "API Gateway GetApi")
                integrations = {x["IntegrationId"]: x for x in rows(api_client, "get_integrations", "Items", ApiId=api_id) if x.get("IntegrationId")}
                authors = {}
                for auth in rows(api_client, "get_authorizers", "Items", ApiId=api_id):
                    aid = auth.get("AuthorizerId")
                    if not aid:
                        continue
                    rid = api_arn + "/authorizers/" + aid
                    jwt = auth.get("JwtConfiguration", {})
                    node(rid, AUTHORIZER, auth.get("Name", aid), {"authorizerType": auth.get("AuthorizerType"), "issuer": jwt.get("Issuer"), "audience": jwt.get("Audience", [])}, "API Gateway GetAuthorizers")
                    authors[aid] = rid
                    issuer = jwt.get("Issuer", "")
                    pool_match = re.fullmatch(r"https://cognito-idp\." + re.escape(region) + r"\.amazonaws\.com/(" + re.escape(region) + r"_[A-Za-z0-9]+)", issuer)
                    if cognito is not None and pool_match and pool_match.group(1) in scope.get("AWS::Cognito::UserPool", set()) and len(pool_cache) < MAX_ITEMS:
                        pool_id = pool_match.group(1)
                        if pool_cache.get(pool_id):
                            edge(rid, pool_cache[pool_id], "JWT_ISSUER")

                for route in rows(api_client, "get_routes", "Items", ApiId=api_id):
                    rid = api_arn + "/routes/" + route["RouteId"]
                    node(rid, ROUTE, route.get("RouteKey", route["RouteId"]), {"authorizationType": route.get("AuthorizationType"), "authorizationScopes": route.get("AuthorizationScopes", [])}, "API Gateway GetRoutes")
                    edge(api_arn, rid, "API_ROUTE")
                    aid = route.get("AuthorizerId")
                    if aid in authors and route.get("AuthorizationType") == "JWT" and nodes[authors[aid]]["attributes"].get("authorizerType") == "JWT":
                        edge(rid, authors[aid], "JWT_AUTHORIZER")
                    elif route.get("AuthorizationType") == "JWT":
                        warn("apigatewayv2", "UNRESOLVED_AUTHORIZER")
                        states["JWT_AUTHORIZER"] = "PARTIAL"
                    target = route.get("Target", "")
                    integration = integrations.get(target.split("/", 1)[1], {}) if target.startswith("integrations/") else {}
                    uri = integration.get("IntegrationUri", "")
                    match = re.fullmatch(r"(arn:aws(?:-[a-z0-9]+)*:lambda:[^:/]+:\d{12}:function:[A-Za-z0-9_-]+)", uri)
                    if not match:
                        match = re.fullmatch(r"arn:aws(?:-[a-z0-9]+)*:apigateway:[^:]+:lambda:path/2015-03-31/functions/(arn:aws(?:-[a-z0-9]+)*:lambda:[^:/]+:\d{12}:function:[A-Za-z0-9_-]+)/invocations", uri)
                    function_arn = match.group(1) if match else None
                    if function_arn in nodes and nodes[function_arn].get("resourceType") == "AWS::Lambda::Function" and function_arn.rsplit(":", 1)[-1] in scope.get("AWS::Lambda::Function", set()):
                        edge(rid, function_arn, "API_INTEGRATION", integrationType=integration.get("IntegrationType"))
                    elif target:
                        warn("apigatewayv2", "UNRESOLVED_INTEGRATION")
                        states["API_INTEGRATION"] = "PARTIAL"
        except (ClientError, BotoCoreError) as exc:
            failure("apigatewayv2", exc)
            for kind in (API, ROUTE, AUTHORIZER):
                coverage[kind] = "PARTIAL"
            for kind in ("API_ROUTE", "API_INTEGRATION", "JWT_AUTHORIZER"):
                states[kind] = "PARTIAL"
    # Clients are shared across bounded threads; sessions and boto3 resources are not.
    # API/JWT metadata is collected first so policy reads cannot starve routing facts.
    if iam_enabled:
        iam = client("iam")
        managed_documents = {}
        def fetch_documents(role):
            arn, name = role
            documents = []
            try:
                for policy_name in rows(iam, "list_role_policies", "PolicyNames", RoleName=name):
                    documents.append(call(iam, "get_role_policy", RoleName=name, PolicyName=policy_name).get("PolicyDocument", {}))
                for attached in rows(iam, "list_attached_role_policies", "AttachedPolicies", RoleName=name):
                    policy_arn = attached.get("PolicyArn", "")
                    if not re.fullmatch(r"arn:aws(?:-[a-z0-9]+)*:iam::(?:aws|" + re.escape(account_id or "INVALID") + r"):policy/[\w+=,.@/-]+", policy_arn):
                        warn("iam:policies", "INVALID_POLICY_SCOPE")
                        continue
                    with policy_guard:
                        if policy_arn not in managed_documents:
                            version = call(iam, "get_policy", PolicyArn=policy_arn)["Policy"]["DefaultVersionId"]
                            managed_documents[policy_arn] = call(iam, "get_policy_version", PolicyArn=policy_arn, VersionId=version)["PolicyVersion"].get("Document", {})
                        documents.append(managed_documents[policy_arn])
            except (ClientError, BotoCoreError) as exc:
                failure("iam:policies", exc)
                coverage[ROLE] = "PARTIAL"
            return arn, documents
        with ThreadPoolExecutor(max_workers=6) as executor:
            role_documents = list(executor.map(fetch_documents, sorted(roles.items())))
        # Merge in sorted role order; concurrent completion order never changes output.
        for arn, documents in role_documents:
            declarations = []
            for document in documents:
                if isinstance(document, str):
                    try:
                        document = json.loads(unquote(document))
                    except (ValueError, TypeError):
                        warn("iam:policies", "INVALID_POLICY_DOCUMENT")
                        continue
                statements = document.get("Statement", []) if isinstance(document, dict) else []
                if isinstance(statements, dict):
                    statements = [statements]
                for statement in statements[:MAX_ITEMS]:
                    if not isinstance(statement, dict):
                        continue
                    actions, resources = statement.get("Action", []), statement.get("Resource", [])
                    actions = [actions] if isinstance(actions, str) else actions
                    resources = [resources] if isinstance(resources, str) else resources
                    if not isinstance(actions, list) or not isinstance(resources, list):
                        continue
                    declarations.append({"effect": statement.get("Effect"), "actions": actions[:MAX_ITEMS],
                                         "resources": resources[:MAX_ITEMS], "conditional": bool(statement.get("Condition")),
                                         "effectiveAuthorization": "UNKNOWN"})
                    if len(declarations) >= MAX_ITEMS:
                        break
                if len(declarations) >= MAX_ITEMS:
                    warn("iam:policies", "RESOURCE_CAP")
                    break
            nodes[arn]["attributes"]["policyDeclarations"] = declarations
            for table in list(nodes.values()):
                if table.get("resourceType") != "AWS::DynamoDB::Table" or table["resourceId"].rsplit("/", 1)[-1] not in scope.get("AWS::DynamoDB::Table", set()):
                    continue
                matches = [d for d in declarations if d["effect"] == "Allow" and any(isinstance(a, str) and (a.lower().startswith("dynamodb:") or a == "*") for a in d["actions"]) and any(isinstance(r, str) and fnmatchcase(table["resourceId"], r) for r in d["resources"])]
                if matches:
                    edge(arn, table["resourceId"], "IAM_DECLARED_PERMISSION", effectiveAuthorization="UNKNOWN", declarationCount=len(matches))

    if len(warnings) > initial_warning_count:
        states = {k: "PARTIAL" if v != "UNSUPPORTED" else v for k, v in states.items()}
        for kind in (API, ROUTE, AUTHORIZER, ROLE):
            if coverage[kind] != "UNSUPPORTED":
                coverage[kind] = "PARTIAL"
    if cognito_enabled and len(warnings) > initial_warning_count:
        coverage["AWS::Cognito::UserPool"] = "PARTIAL"
    return states


def simulate_declared_permission(client, role_arn, action, table_arn):
    """Return exact simulator evidence without promoting it to operational access.

    IAM simulation does not reproduce all resource policies or organization policy
    contexts. Consequently even an allowed result leaves effectiveAuthorization UNKNOWN.
    """
    role = re.fullmatch(r"arn:(aws(?:-[a-z0-9]+)*):iam::(\d{12}):role/[\w+=,.@/-]+", role_arn)
    table = re.fullmatch(r"arn:(aws(?:-[a-z0-9]+)*):dynamodb:[a-z0-9-]+:(\d{12}):table/[A-Za-z0-9_.-]+", table_arn)
    if not role or not table or role.group(1, 2) != table.group(1, 2) or not re.fullmatch(r"dynamodb:[A-Za-z]+", action):
        raise ValueError("Simulation requires an exact same-account role, DynamoDB action and table ARN.")
    evidence = {"roleArn": role_arn, "action": action, "resourceArn": table_arn,
                "effectiveAuthorization": "UNKNOWN", "source": "IAM SimulatePrincipalPolicy"}
    try:
        response = client.simulate_principal_policy(PolicySourceArn=role_arn, ActionNames=[action], ResourceArns=[table_arn])
        results = response.get("EvaluationResults", [])
        if len(results) != 1 or response.get("IsTruncated"):
            evidence["simulationDecision"] = "UNKNOWN"
            return evidence
        result = results[0]
        if result.get("EvalActionName") != action or result.get("EvalResourceName") != table_arn:
            evidence["simulationDecision"] = "UNKNOWN"
            return evidence
        evidence.update({"simulationDecision": result.get("EvalDecision", "UNKNOWN"),
                         "missingContextValues": result.get("MissingContextValues", []),
                         "permissionsBoundaryDecision": result.get("PermissionsBoundaryDecisionDetail"),
                         "organizationsDecision": result.get("OrganizationsDecisionDetail")})
    except (ClientError, BotoCoreError) as exc:
        evidence["simulationDecision"] = "UNKNOWN"
        evidence["errorCode"] = exc.response.get("Error", {}).get("Code", "AWS_ERROR") if isinstance(exc, ClientError) else type(exc).__name__
    return evidence
