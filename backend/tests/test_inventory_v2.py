"""Stubbed read-only inventory contracts; no credentials or network are used."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from botocore.exceptions import ClientError
from common import inventory


class FakePaginator:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def paginate(self, **kwargs):
        self.calls.append(kwargs)
        def pages():
            for page in self.pages:
                if isinstance(page, Exception):
                    raise page
                yield page
        return pages()


class FakeClient:
    def __init__(self, **methods):
        self.methods = methods
        self.calls = []
        self.paginators = {}

    def __getattr__(self, name):
        if name == "get_paginator":
            return self._get_paginator
        if name not in self.methods:
            raise AssertionError(f"Unexpected SDK call: {name}")

        def call(**kwargs):
            self.calls.append((name, kwargs))
            result = self.methods[name]
            if isinstance(result, Exception):
                raise result
            return result(**kwargs) if callable(result) else result
        return call

    def _get_paginator(self, operation):
        self.calls.append(("get_paginator", {"operation": operation}))
        if operation not in self.paginators:
            raise AssertionError(f"Unexpected paginator: {operation}")
        return self.paginators[operation]


class FakeSession:
    region_name = "ap-south-1"

    def __init__(self, clients):
        self.clients = clients
        self.created = []

    def client(self, service, **kwargs):
        self.created.append((service, kwargs))
        if service not in self.clients:
            raise AssertionError(f"Unexpected service client: {service}")
        return self.clients[service]


def denied(operation):
    return ClientError({"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, operation)


def make_session(*, lambda_error=None, buckets=None, dbs=None, functions=None):
    clients = {
        "sts": FakeClient(get_caller_identity={"Account": "123456789012"}),
        "ec2": FakeClient(describe_vpcs={"Vpcs": [{"VpcId": "vpc-1", "Tags": [{"Key": "env", "Value": "dev"}]}]}),
        "rds": FakeClient(),
        "s3": FakeClient(),
    }
    ec2 = clients["ec2"]
    ec2.paginators["describe_subnets"] = FakePaginator([{"Subnets": [{
        "SubnetId": "subnet-1", "VpcId": "vpc-1", "Tags": [{"Key": "env", "Value": "dev"}],
    }]}])
    ec2.paginators["describe_security_groups"] = FakePaginator([{"SecurityGroups": [{
        "GroupId": "sg-1", "VpcId": "vpc-1", "Tags": [{"Key": "env", "Value": "dev"}],
        "IpPermissions": [], "IpPermissionsEgress": [],
    }]}])
    ec2.paginators["describe_instances"] = FakePaginator([{"Reservations": [{"Instances": [{
        "InstanceId": "i-1", "VpcId": "vpc-1", "SubnetId": "subnet-1",
        "Tags": [{"Key": "Name", "Value": "Web"}, {"Key": "env", "Value": "dev"}],
        "SecurityGroups": [{"GroupId": "sg-1"}], "State": {"Name": "running"},
    }]}]}])

    rds = clients["rds"]
    rds.paginators["describe_db_instances"] = FakePaginator([{"DBInstances": dbs if dbs is not None else [{
        "DBInstanceArn": "arn:aws:rds:ap-south-1:123456789012:db:db-1",
        "DBInstanceIdentifier": "db-1", "PubliclyAccessible": None,
        "VpcSecurityGroups": [{"VpcSecurityGroupId": "sg-1", "Status": "active"}],
    }]}])
    rds.methods["list_tags_for_resource"] = {"TagList": [{"Key": "env", "Value": "prod"}]}

    s3 = clients["s3"]
    s3.methods.update({
        "list_buckets": {"Buckets": buckets if buckets is not None else [{"Name": "bucket-1"}]},
        "get_bucket_location": {"LocationConstraint": "ap-south-1"},
        "get_public_access_block": {"PublicAccessBlockConfiguration": {
            "BlockPublicAcls": True, "IgnorePublicAcls": True,
            "BlockPublicPolicy": True, "RestrictPublicBuckets": True,
        }},
        "get_bucket_policy_status": {"PolicyStatus": {"IsPublic": False}},
        "get_bucket_tagging": {"TagSet": [{"Key": "env", "Value": "prod"}]},
    })

    if lambda_error is not None or functions is not None:
        lambda_client = FakeClient()
        lambda_client.paginators["list_functions"] = FakePaginator(
            [{"Functions": functions}] if lambda_error is None else []
        )
        if lambda_error is not None:
            lambda_client.paginators["list_functions"] = FakePaginator(lambda_error)
        clients["lambda"] = lambda_client
    return FakeSession(clients)


class InventoryV2Tests(unittest.TestCase):
    def collect(self, session, env=None):
        with patch("common.inventory.boto3.session.Session", return_value=session):
            with patch.dict("os.environ", env or {}, clear=True):
                return inventory.collect_inventory("ap-south-1")

    def test_tags_are_retained_from_existing_ec2_responses_and_edges_are_structural(self):
        session = make_session()
        result = self.collect(session)
        by_id = {item["resourceId"]: item for item in result["items"]}
        self.assertEqual(by_id["vpc-1"]["tags"], {"env": "dev"})
        self.assertEqual(by_id["subnet-1"]["tags"], {"env": "dev"})
        self.assertEqual(by_id["sg-1"]["tags"], {"env": "dev"})
        self.assertEqual(by_id["i-1"]["tags"], {"Name": "Web", "env": "dev"})
        self.assertTrue(result["edges"])
        self.assertTrue(all(edge["observationKind"] == "STRUCTURAL" for edge in result["edges"]))
        self.assertTrue(all(edge["evidence"][0]["kind"] == "STRUCTURAL" for edge in result["edges"]))
        self.assertEqual(result["meta"]["coverage"]["relationshipTypes"]["NETWORK_REACHABILITY"], "UNSUPPORTED")
        self.assertEqual(result["meta"]["coverage"]["relationshipTypes"]["NETWORK_PERMISSION"], "UNSUPPORTED")
        self.assertEqual(result["meta"]["coverage"]["resourceTypes"]["AWS::Lambda::Function"], "UNSUPPORTED")
        self.assertNotIn("lambda", [service for service, _ in session.created])

    def test_missing_rds_accessibility_stays_unknown_and_sg_attachment_is_recorded(self):
        result = self.collect(make_session())
        rds = next(item for item in result["items"] if item["resourceType"] == "AWS::RDS::DBInstance")
        self.assertIsNone(rds["attributes"]["publiclyAccessible"])
        self.assertIn("sg-1", rds["attributes"]["vpcSecurityGroupIds"])
        self.assertIn({"type": "USES_SECURITY_GROUP", "targetId": "sg-1"}, rds["relationships"])
        self.assertTrue(any(edge["sourceId"] == rds["resourceId"] and edge["targetId"] == "sg-1"
                            and edge["type"] == "USES_SECURITY_GROUP" for edge in result["edges"]))

    def test_rds_and_s3_tag_apis_are_off_by_default_and_opt_in(self):
        session = make_session()
        result = self.collect(session)
        self.assertFalse(any(name in {"list_tags_for_resource", "get_bucket_tagging"}
                             for client in (session.clients["rds"], session.clients["s3"])
                             for name, _ in client.calls))
        self.assertEqual(result["meta"]["coverage"]["relationshipTypes"]["TAGS"], "PARTIAL")
        self.assertTrue(all(item.get("tags") is None for item in result["items"]
                            if item["resourceType"] in {"AWS::RDS::DBInstance", "AWS::S3::Bucket"}))

        enabled = self.collect(make_session(), {"TAG_INVENTORY_ENABLED": "true"})
        by_type = {item["resourceType"]: item for item in enabled["items"]}
        self.assertEqual(by_type["AWS::RDS::DBInstance"]["tags"], {"env": "prod"})
        self.assertEqual(by_type["AWS::S3::Bucket"]["tags"], {"env": "prod"})
        self.assertEqual(enabled["meta"]["coverage"]["relationshipTypes"]["TAGS"], "COMPLETE")

    def test_lambda_is_only_called_when_enabled_and_access_denial_is_partial(self):
        disabled_session = make_session()
        disabled = self.collect(disabled_session)
        self.assertEqual(disabled["meta"]["coverage"]["resourceTypes"]["AWS::Lambda::Function"], "UNSUPPORTED")
        self.assertNotIn("lambda", [service for service, _ in disabled_session.created])

        denied_session = make_session(lambda_error=[denied("ListFunctions")])
        denied_result = self.collect(denied_session, {"LAMBDA_INVENTORY_ENABLED": "true"})
        self.assertEqual(denied_result["meta"]["coverage"]["resourceTypes"]["AWS::Lambda::Function"], "PARTIAL")
        self.assertTrue(any(row["source"] == "lambda:functions" for row in denied_result["meta"]["warnings"]))
        self.assertTrue(denied_result["meta"]["partial"])

    def test_lambda_metadata_and_attachments_are_collected_when_enabled(self):
        function = {"FunctionArn": "arn:aws:lambda:ap-south-1:123456789012:function:worker",
                    "FunctionName": "worker", "Runtime": "python3.14", "Role": "arn:aws:iam::123456789012:role/worker",
                    "VpcConfig": {"VpcId": "vpc-1", "SubnetIds": ["subnet-1"], "SecurityGroupIds": ["sg-1"]}}
        result = self.collect(make_session(functions=[function]), {"LAMBDA_INVENTORY_ENABLED": "true"})
        resource = next(item for item in result["items"] if item["resourceType"] == "AWS::Lambda::Function")
        self.assertEqual(resource["attributes"]["runtime"], "python3.14")
        self.assertEqual(resource["attributes"]["subnetIds"], ["subnet-1"])
        self.assertEqual(result["meta"]["coverage"]["resourceTypes"]["AWS::Lambda::Function"], "COMPLETE")

    def test_cap_reached_marks_source_and_structural_coverage_partial(self):
        session = make_session()
        with patch.object(inventory, "MAX_PER_KIND", 1):
            result = self.collect(session)
        self.assertTrue(result["meta"]["partial"])
        self.assertEqual(result["meta"]["coverage"]["resourceTypes"]["AWS::EC2::Instance"], "PARTIAL")
        self.assertEqual(result["meta"]["coverage"]["relationshipTypes"]["STRUCTURAL"], "PARTIAL")
        self.assertTrue(any(row["code"] == "RESOURCE_CAP" for row in result["meta"]["warnings"]))


if __name__ == "__main__":
    unittest.main()
