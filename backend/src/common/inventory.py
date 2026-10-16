"""Read-only, bounded AWS inventory with explicit resource and edge coverage."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import boto3
from common.contracts import is_local
from common.observations import ObservationUnavailable
from common.serverless_inventory import collect_serverless, STREAM_EDGE, TABLE_TYPE
from botocore.exceptions import BotoCoreError, ClientError

MAX_PER_KIND = 250
RESOURCE_TYPES = {
    "vpcs": "AWS::EC2::VPC",
    "subnets": "AWS::EC2::Subnet",
    "security-groups": "AWS::EC2::SecurityGroup",
    "instances": "AWS::EC2::Instance",
    "rds": "AWS::RDS::DBInstance",
    "s3": "AWS::S3::Bucket",
    "lambda": "AWS::Lambda::Function",
    "dynamodb": TABLE_TYPE,
}
STRUCTURAL_EDGE_TYPES = {"BELONGS_TO_VPC", "IN_SUBNET", "USES_SECURITY_GROUP", "IN_VPC"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _tag_map(tags: list[dict[str, Any]] | None) -> dict[str, str]:
    return {str(tag["Key"]): str(tag["Value"]) for tag in tags or []
            if isinstance(tag, dict) and tag.get("Key") is not None and tag.get("Value") is not None}


def _name(tags: list[dict[str, Any]] | None, fallback: str) -> str:
    for tag in tags or []:
        if isinstance(tag, dict) and tag.get("Key") == "Name" and tag.get("Value"):
            return str(tag["Value"])
    return fallback


def _warn(warnings: list[dict[str, str]], source: str, exc: Exception) -> None:
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "AWS_ERROR")
        msg = exc.response.get("Error", {}).get("Message", str(exc))
    else:
        code = type(exc).__name__
        msg = str(exc)
    warnings.append({"source": source, "code": code, "message": str(msg)[:300]})


def _edge(source: str, target: str, relationship: str, observed_at: str) -> dict[str, Any]:
    return {
        "sourceId": source,
        "targetId": target,
        "type": relationship,
        "status": "OBSERVED",
        "observationKind": "STRUCTURAL",
        "evidence": [{"kind": "STRUCTURAL", "source": "AWS inventory", "observedAt": observed_at}],
    }


def _coverage_state(warnings: list[dict[str, str]], source_names: set[str], count: int) -> str:
    if any(row.get("source") in source_names for row in warnings):
        return "PARTIAL"
    if count >= MAX_PER_KIND:
        return "PARTIAL"
    return "COMPLETE"


def _api_error(exc: Exception, warnings: list[dict[str, str]], source: str,
               coverage: dict[str, str], resource_type: str) -> None:
    _warn(warnings, source, exc)
    coverage[resource_type] = "PARTIAL"


def collect_inventory(region: str | None = None) -> dict[str, Any]:
    if is_local():
        raise ObservationUnavailable("Live AWS inventory is disabled in local execution. Use the fixture provider.")
    region = region or boto3.session.Session().region_name or "us-east-1"
    session = boto3.session.Session(region_name=region)
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []
    resource_coverage: dict[str, str] = {value: "COMPLETE" for value in RESOURCE_TYPES.values()}
    account_id = None
    collected_at = _now()
    tag_enabled = os.environ.get("TAG_INVENTORY_ENABLED", "false").lower() == "true"
    lambda_enabled = os.environ.get("LAMBDA_INVENTORY_ENABLED", "false").lower() == "true"

    try:
        account_id = session.client("sts").get_caller_identity().get("Account")
    except (ClientError, BotoCoreError) as exc:
        _warn(warnings, "sts", exc)

    ec2 = session.client("ec2")
    try:
        result = ec2.describe_vpcs(MaxResults=1000)
        if result.get("NextToken"):
            warnings.append({"source": "ec2:vpcs", "code": "TRUNCATED", "message": "Additional VPC pages were not collected."})
        for vpc in result.get("Vpcs", [])[:MAX_PER_KIND]:
            rid = vpc["VpcId"]
            tags = _tag_map(vpc.get("Tags"))
            nodes[rid] = {
                "resourceId": rid, "resourceType": RESOURCE_TYPES["vpcs"], "name": _name(vpc.get("Tags"), rid),
                "region": region, "accountId": account_id, "tags": tags,
                "attributes": {"isDefault": bool(vpc.get("IsDefault")), "state": vpc.get("State"), "cidrBlock": vpc.get("CidrBlock")},
                "relationships": [], "source": "EC2 DescribeVpcs", "lastObservedAt": collected_at,
            }
        resource_coverage[RESOURCE_TYPES["vpcs"]] = _coverage_state(warnings, {"ec2:vpcs"}, len(result.get("Vpcs", [])))
    except (ClientError, BotoCoreError) as exc:
        _api_error(exc, warnings, "ec2:vpcs", resource_coverage, RESOURCE_TYPES["vpcs"])

    try:
        count = 0
        for page in ec2.get_paginator("describe_subnets").paginate():
            for subnet in page.get("Subnets", []):
                if count >= MAX_PER_KIND:
                    break
                rid = subnet["SubnetId"]
                vpc_id = subnet.get("VpcId")
                rels = []
                if vpc_id:
                    rels.append({"type": "BELONGS_TO_VPC", "targetId": vpc_id})
                    edges.append(_edge(rid, vpc_id, "BELONGS_TO_VPC", collected_at))
                tags = _tag_map(subnet.get("Tags"))
                nodes[rid] = {
                    "resourceId": rid, "resourceType": RESOURCE_TYPES["subnets"], "name": _name(subnet.get("Tags"), rid),
                    "region": region, "accountId": account_id, "tags": tags,
                    "attributes": {"vpcId": vpc_id, "cidrBlock": subnet.get("CidrBlock"), "availabilityZone": subnet.get("AvailabilityZone"), "availableIpAddressCount": subnet.get("AvailableIpAddressCount")},
                    "relationships": rels, "source": "EC2 DescribeSubnets", "lastObservedAt": collected_at,
                }
                count += 1
            if count >= MAX_PER_KIND:
                break
        resource_coverage[RESOURCE_TYPES["subnets"]] = _coverage_state(warnings, {"ec2:subnets"}, count)
    except (ClientError, BotoCoreError) as exc:
        _api_error(exc, warnings, "ec2:subnets", resource_coverage, RESOURCE_TYPES["subnets"])

    try:
        count = 0
        for page in ec2.get_paginator("describe_security_groups").paginate():
            for sg in page.get("SecurityGroups", []):
                if count >= MAX_PER_KIND:
                    break
                rid = sg["GroupId"]
                ingress = []
                for perm in sg.get("IpPermissions", []):
                    for ip_range in perm.get("IpRanges", []):
                        ingress.append({"protocol": perm.get("IpProtocol"), "fromPort": perm.get("FromPort"), "toPort": perm.get("ToPort"), "cidr": ip_range.get("CidrIp"), "description": ip_range.get("Description")})
                    for ip_range in perm.get("Ipv6Ranges", []):
                        ingress.append({"protocol": perm.get("IpProtocol"), "fromPort": perm.get("FromPort"), "toPort": perm.get("ToPort"), "cidr": ip_range.get("CidrIpv6"), "description": ip_range.get("Description")})
                    for prefix in perm.get("PrefixListIds", []):
                        ingress.append({"protocol": perm.get("IpProtocol"), "fromPort": perm.get("FromPort"),
                                        "toPort": perm.get("ToPort"), "prefixListId": prefix.get("PrefixListId"),
                                        "publicSourceUnknown": True})
                    for group_pair in perm.get("UserIdGroupPairs", []):
                        ingress.append({"protocol": perm.get("IpProtocol"), "fromPort": perm.get("FromPort"), "toPort": perm.get("ToPort"), "sourceSecurityGroupId": group_pair.get("GroupId"), "description": group_pair.get("Description")})
                egress = []
                for perm in sg.get("IpPermissionsEgress", []):
                    for ip_range in perm.get("IpRanges", []):
                        egress.append({"protocol": perm.get("IpProtocol"), "fromPort": perm.get("FromPort"), "toPort": perm.get("ToPort"), "cidr": ip_range.get("CidrIp"), "description": ip_range.get("Description")})
                    for ip_range in perm.get("Ipv6Ranges", []):
                        egress.append({"protocol": perm.get("IpProtocol"), "fromPort": perm.get("FromPort"), "toPort": perm.get("ToPort"), "cidr": ip_range.get("CidrIpv6"), "description": ip_range.get("Description")})
                    for group_pair in perm.get("UserIdGroupPairs", []):
                        egress.append({"protocol": perm.get("IpProtocol"), "fromPort": perm.get("FromPort"), "toPort": perm.get("ToPort"), "destinationSecurityGroupId": group_pair.get("GroupId"), "description": group_pair.get("Description")})
                vpc_id = sg.get("VpcId")
                rels = []
                if vpc_id:
                    rels.append({"type": "BELONGS_TO_VPC", "targetId": vpc_id})
                    edges.append(_edge(rid, vpc_id, "BELONGS_TO_VPC", collected_at))
                tags = _tag_map(sg.get("Tags"))
                nodes[rid] = {
                    "resourceId": rid, "resourceType": RESOURCE_TYPES["security-groups"], "name": sg.get("GroupName") or rid,
                    "region": region, "accountId": account_id, "tags": tags,
                    "attributes": {"description": sg.get("Description"), "vpcId": vpc_id, "ingressRules": ingress, "egressRules": egress},
                    "relationships": rels, "source": "EC2 DescribeSecurityGroups", "lastObservedAt": collected_at,
                }
                count += 1
            if count >= MAX_PER_KIND:
                break
        resource_coverage[RESOURCE_TYPES["security-groups"]] = _coverage_state(warnings, {"ec2:security-groups"}, count)
    except (ClientError, BotoCoreError) as exc:
        _api_error(exc, warnings, "ec2:security-groups", resource_coverage, RESOURCE_TYPES["security-groups"])

    try:
        count = 0
        for page in ec2.get_paginator("describe_instances").paginate(PaginationConfig={"MaxItems": MAX_PER_KIND}):
            for reservation in page.get("Reservations", []):
                for inst in reservation.get("Instances", []):
                    if count >= MAX_PER_KIND:
                        break
                    rid = inst["InstanceId"]
                    rels = []
                    subnet_id, vpc_id = inst.get("SubnetId"), inst.get("VpcId")
                    if subnet_id:
                        rels.append({"type": "IN_SUBNET", "targetId": subnet_id})
                        edges.append(_edge(rid, subnet_id, "IN_SUBNET", collected_at))
                    if vpc_id:
                        rels.append({"type": "IN_VPC", "targetId": vpc_id})
                    sg_ids = []
                    for group in inst.get("SecurityGroups", []):
                        gid = group.get("GroupId")
                        if gid:
                            sg_ids.append(gid)
                            rels.append({"type": "USES_SECURITY_GROUP", "targetId": gid})
                            edges.append(_edge(rid, gid, "USES_SECURITY_GROUP", collected_at))
                    tags = _tag_map(inst.get("Tags"))
                    nodes[rid] = {
                        "resourceId": rid, "resourceType": RESOURCE_TYPES["instances"], "name": _name(inst.get("Tags"), rid),
                        "region": region, "accountId": account_id, "tags": tags,
                        "attributes": {"state": inst.get("State", {}).get("Name"), "instanceType": inst.get("InstanceType"), "vpcId": vpc_id, "subnetId": subnet_id, "securityGroupIds": sg_ids, "publicIpAddress": inst.get("PublicIpAddress"), "privateIpAddress": inst.get("PrivateIpAddress")},
                        "relationships": rels, "source": "EC2 DescribeInstances", "lastObservedAt": collected_at,
                    }
                    count += 1
        resource_coverage[RESOURCE_TYPES["instances"]] = _coverage_state(warnings, {"ec2:instances"}, count)
    except (ClientError, BotoCoreError) as exc:
        _api_error(exc, warnings, "ec2:instances", resource_coverage, RESOURCE_TYPES["instances"])

    rds_items = []
    try:
        count = 0
        rds = session.client("rds")
        for page in rds.get_paginator("describe_db_instances").paginate(PaginationConfig={"MaxItems": MAX_PER_KIND}):
            for db in page.get("DBInstances", []):
                if count >= MAX_PER_KIND:
                    break
                rds_items.append(db)
                count += 1
        resource_coverage[RESOURCE_TYPES["rds"]] = _coverage_state(warnings, {"rds:instances"}, count)
    except (ClientError, BotoCoreError) as exc:
        rds = None
        _api_error(exc, warnings, "rds:instances", resource_coverage, RESOURCE_TYPES["rds"])

    for db in rds_items:
        rid = db["DBInstanceArn"]
        dbid = db.get("DBInstanceIdentifier", rid)
        subnet_group = db.get("DBSubnetGroup", {})
        vpc_id = subnet_group.get("VpcId")
        rels = []
        if vpc_id:
            rels.append({"type": "IN_VPC", "targetId": vpc_id})
            edges.append(_edge(rid, vpc_id, "IN_VPC", collected_at))
        vpc_security_groups = []
        for attachment in db.get("VpcSecurityGroups", []):
            group_id = attachment.get("VpcSecurityGroupId")
            if group_id:
                vpc_security_groups.append(group_id)
                rels.append({"type": "USES_SECURITY_GROUP", "targetId": group_id})
                edges.append(_edge(rid, group_id, "USES_SECURITY_GROUP", collected_at))
        tags = None
        if tag_enabled:
            try:
                tag_result = rds.list_tags_for_resource(ResourceName=rid)
                tags = _tag_map(tag_result.get("TagList"))
            except (ClientError, BotoCoreError) as exc:
                _warn(warnings, "rds:tags", exc)
                resource_coverage[RESOURCE_TYPES["rds"]] = "PARTIAL"
        nodes[rid] = {
            "resourceId": rid, "resourceType": RESOURCE_TYPES["rds"], "name": dbid,
            "region": region, "accountId": account_id, "tags": tags,
            "attributes": {"publiclyAccessible": db.get("PubliclyAccessible"), "engine": db.get("Engine"), "status": db.get("DBInstanceStatus"), "vpcId": vpc_id, "dbSubnetGroup": subnet_group.get("DBSubnetGroupName"), "endpointAddress": (db.get("Endpoint") or {}).get("Address"), "vpcSecurityGroupIds": vpc_security_groups},
            "relationships": rels, "source": "RDS DescribeDBInstances", "lastObservedAt": collected_at,
        }

    # S3 is global; inventory is metadata-only and never reads bucket objects.
    bucket_list = []
    s3_clients: dict[str, Any] = {}
    try:
        s3 = session.client("s3")
        bucket_list = s3.list_buckets().get("Buckets", [])[:MAX_PER_KIND]
        resource_coverage[RESOURCE_TYPES["s3"]] = _coverage_state(warnings, {"s3:buckets"}, len(bucket_list))
    except (ClientError, BotoCoreError) as exc:
        s3 = None
        _api_error(exc, warnings, "s3:buckets", resource_coverage, RESOURCE_TYPES["s3"])
    for bucket in bucket_list:
        name = bucket["Name"]
        bucket_region = None
        pab = None
        pab_missing = False
        public_access_block_enabled = None
        bucket_policy_public = None
        try:
            loc = s3.get_bucket_location(Bucket=name).get("LocationConstraint")
            bucket_region = loc or "us-east-1"
        except (ClientError, BotoCoreError) as exc:
            _warn(warnings, f"s3:location:{name}", exc)
            resource_coverage[RESOURCE_TYPES["s3"]] = "PARTIAL"
        client_region = bucket_region or "us-east-1"
        if client_region not in s3_clients:
            s3_clients[client_region] = session.client("s3", region_name=client_region)
        bucket_s3 = s3_clients[client_region]
        try:
            pab = bucket_s3.get_public_access_block(Bucket=name).get("PublicAccessBlockConfiguration", {})
            required = ["BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets"]
            public_access_block_enabled = all(pab.get(key) is True for key in required)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"NoSuchPublicAccessBlockConfiguration", "NoSuchConfiguration"}:
                pab_missing = True
                public_access_block_enabled = False
            else:
                _warn(warnings, f"s3:public-access-block:{name}", exc)
                resource_coverage[RESOURCE_TYPES["s3"]] = "PARTIAL"
        except BotoCoreError as exc:
            _warn(warnings, f"s3:public-access-block:{name}", exc)
            resource_coverage[RESOURCE_TYPES["s3"]] = "PARTIAL"
        try:
            bucket_policy_public = bool(bucket_s3.get_bucket_policy_status(Bucket=name).get("PolicyStatus", {}).get("IsPublic"))
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"NoSuchBucketPolicy", "NoSuchPolicy"}:
                bucket_policy_public = False
            else:
                _warn(warnings, f"s3:policy-status:{name}", exc)
                resource_coverage[RESOURCE_TYPES["s3"]] = "PARTIAL"
        except BotoCoreError as exc:
            _warn(warnings, f"s3:policy-status:{name}", exc)
            resource_coverage[RESOURCE_TYPES["s3"]] = "PARTIAL"
        tags = None
        if tag_enabled:
            try:
                tags = _tag_map(bucket_s3.get_bucket_tagging(Bucket=name).get("TagSet"))
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code in {"NoSuchTagSet", "NoSuchTagSetError"}:
                    tags = {}
                else:
                    _warn(warnings, f"s3:tags:{name}", exc)
                    resource_coverage[RESOURCE_TYPES["s3"]] = "PARTIAL"
            except BotoCoreError as exc:
                _warn(warnings, f"s3:tags:{name}", exc)
                resource_coverage[RESOURCE_TYPES["s3"]] = "PARTIAL"
        arn = f"arn:aws:s3:::{name}"
        nodes[arn] = {
            "resourceId": arn, "resourceType": RESOURCE_TYPES["s3"], "name": name,
            "region": bucket_region or region, "accountId": account_id, "tags": tags,
            "attributes": {"createdAt": bucket.get("CreationDate"), "publicAccessBlockEnabled": public_access_block_enabled, "publicAccessBlock": pab, "publicAccessBlockMissing": pab_missing, "bucketPolicyPublic": bucket_policy_public},
            "relationships": [], "source": "S3 ListBuckets + bucket security metadata", "lastObservedAt": collected_at,
        }

    # Lambda enumeration is deliberately off by default and never implies reachability.
    lambda_count = 0
    if lambda_enabled:
        try:
            lambda_client = session.client("lambda")
            for page in lambda_client.get_paginator("list_functions").paginate(PaginationConfig={"MaxItems": MAX_PER_KIND}):
                for function in page.get("Functions", []):
                    if lambda_count >= MAX_PER_KIND:
                        break
                    arn = function.get("FunctionArn")
                    if not arn:
                        continue
                    vpc_config = function.get("VpcConfig", {}) or {}
                    subnets = vpc_config.get("SubnetIds", [])
                    groups = vpc_config.get("SecurityGroupIds", [])
                    relationships = []
                    for subnet_id in subnets:
                        relationships.append({"type": "IN_SUBNET", "targetId": subnet_id})
                        edges.append(_edge(arn, subnet_id, "IN_SUBNET", collected_at))
                    for group_id in groups:
                        relationships.append({"type": "USES_SECURITY_GROUP", "targetId": group_id})
                        edges.append(_edge(arn, group_id, "USES_SECURITY_GROUP", collected_at))
                    nodes[arn] = {
                        "resourceId": arn, "resourceType": RESOURCE_TYPES["lambda"], "name": function.get("FunctionName", arn),
                        "region": region, "accountId": account_id, "tags": None,
                        "attributes": {"runtime": function.get("Runtime"), "packageType": function.get("PackageType"), "role": function.get("Role"), "state": function.get("State"), "timeout": function.get("Timeout"), "memorySize": function.get("MemorySize"), "vpcId": vpc_config.get("VpcId"), "subnetIds": subnets, "securityGroupIds": groups},
                        "relationships": relationships, "source": "Lambda ListFunctions", "lastObservedAt": collected_at,
                    }
                    lambda_count += 1
            resource_coverage[RESOURCE_TYPES["lambda"]] = "PARTIAL" if lambda_count >= MAX_PER_KIND else "COMPLETE"
        except (ClientError, BotoCoreError) as exc:
            _api_error(exc, warnings, "lambda:functions", resource_coverage, RESOURCE_TYPES["lambda"])
    else:
        resource_coverage[RESOURCE_TYPES["lambda"]] = "UNSUPPORTED"

    stream_coverage = collect_serverless(
        session, nodes, edges, warnings, resource_coverage, region, account_id, collected_at,
        tables_enabled=os.environ.get("DYNAMODB_INVENTORY_ENABLED", "false").lower() == "true",
        mappings_enabled=os.environ.get("SERVERLESS_RELATIONSHIPS_ENABLED", "false").lower() == "true",
        lambda_enabled=lambda_enabled,
    )

    # Snapshot direct relationships so inverse links never create new inverse-of-inverse links.
    direct = [(node["resourceId"], rel) for node in nodes.values() for rel in list(node.get("relationships", []))]
    for source, rel in direct:
        target = rel.get("targetId")
        if target in nodes:
            nodes[target].setdefault("relationships", []).append({"type": f"HAS_{rel['type']}", "targetId": source})

    counts: dict[str, int] = {}
    for node in nodes.values():
        kind = node["resourceType"]
        counts[kind] = counts.get(kind, 0) + 1
    for kind, count in counts.items():
        if count >= MAX_PER_KIND:
            warnings.append({"source": kind, "code": "RESOURCE_CAP", "message": "Resource cap reached; completeness is not established."})
            resource_coverage[kind] = "PARTIAL"

    tag_coverage = "COMPLETE"
    if not tag_enabled and (rds_items or bucket_list):
        tag_coverage = "PARTIAL"
    if lambda_count or any(node["resourceType"] == TABLE_TYPE for node in nodes.values()):
        tag_coverage = "PARTIAL"
    if any(row.get("source", "").startswith(("rds:tags", "s3:tags:")) for row in warnings):
        tag_coverage = "PARTIAL"

    structural_status = "PARTIAL" if any(state != "COMPLETE" for state in resource_coverage.values()
                                           if state != "UNSUPPORTED") else "COMPLETE"
    relationship_coverage = {kind: structural_status for kind in sorted(STRUCTURAL_EDGE_TYPES)}
    relationship_coverage[STREAM_EDGE] = stream_coverage
    relationship_coverage["STRUCTURAL"] = ("PARTIAL" if os.environ.get("SERVERLESS_RELATIONSHIPS_ENABLED", "false").lower() == "true"
                                             and stream_coverage != "COMPLETE" else structural_status)
    relationship_coverage["NETWORK_PERMISSION"] = "UNSUPPORTED"
    relationship_coverage["NETWORK_REACHABILITY"] = "UNSUPPORTED"
    relationship_coverage["TAGS"] = tag_coverage
    items = list(nodes.values())
    return {
        "items": items,
        "edges": edges,
        "meta": {
            "region": region,
            "accountId": account_id,
            "collectedAt": collected_at,
            "totalResources": len(items),
            "partial": bool(warnings),
            "warnings": warnings,
            "resourceCapPerType": MAX_PER_KIND,
            "coverage": {"resourceTypes": resource_coverage, "relationshipTypes": relationship_coverage},
        },
    }
