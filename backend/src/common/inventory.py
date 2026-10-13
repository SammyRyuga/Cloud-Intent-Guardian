"""Read-only, bounded AWS inventory for the first Cloud Intent Guardian MVP."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

MAX_PER_KIND = 250


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _name(tags: list[dict[str, str]] | None, fallback: str) -> str:
    for tag in tags or []:
        if tag.get("Key") == "Name" and tag.get("Value"):
            return tag["Value"]
    return fallback


def _warn(warnings: list[dict[str, str]], source: str, exc: Exception) -> None:
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "AWS_ERROR")
        msg = exc.response.get("Error", {}).get("Message", str(exc))
    else:
        code = type(exc).__name__
        msg = str(exc)
    warnings.append({"source": source, "code": code, "message": msg[:300]})


def collect_inventory(region: str | None = None) -> dict[str, Any]:
    region = region or boto3.session.Session().region_name or "us-east-1"
    session = boto3.session.Session(region_name=region)
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []
    account_id = None
    try:
        account_id = session.client("sts").get_caller_identity().get("Account")
    except (ClientError, BotoCoreError) as exc:
        _warn(warnings, "sts", exc)

    # VPCs, subnets, security groups are collected separately so their nodes can be selected in the graph.
    ec2 = session.client("ec2")
    try:
        result = ec2.describe_vpcs(MaxResults=1000)
        for vpc in result.get("Vpcs", [])[:MAX_PER_KIND]:
            rid = vpc["VpcId"]
            nodes[rid] = {
                "resourceId": rid, "resourceType": "AWS::EC2::VPC", "name": rid,
                "region": region, "accountId": account_id,
                "attributes": {"isDefault": bool(vpc.get("IsDefault")), "state": vpc.get("State"), "cidrBlock": vpc.get("CidrBlock")},
                "relationships": [], "source": "EC2 DescribeVpcs", "lastObservedAt": _now(),
            }
    except (ClientError, BotoCoreError) as exc:
        _warn(warnings, "ec2:vpcs", exc)

    try:
        paginator = ec2.get_paginator("describe_subnets")
        count = 0
        for page in paginator.paginate():
            for subnet in page.get("Subnets", []):
                if count >= MAX_PER_KIND:
                    break
                rid = subnet["SubnetId"]
                vpc_id = subnet.get("VpcId")
                rels = []
                if vpc_id:
                    rels.append({"type": "BELONGS_TO_VPC", "targetId": vpc_id})
                    edges.append({"sourceId": rid, "targetId": vpc_id, "type": "BELONGS_TO_VPC", "status": "OBSERVED"})
                nodes[rid] = {
                    "resourceId": rid, "resourceType": "AWS::EC2::Subnet", "name": rid,
                    "region": region, "accountId": account_id,
                    "attributes": {"vpcId": vpc_id, "cidrBlock": subnet.get("CidrBlock"), "availabilityZone": subnet.get("AvailabilityZone"), "availableIpAddressCount": subnet.get("AvailableIpAddressCount")},
                    "relationships": rels, "source": "EC2 DescribeSubnets", "lastObservedAt": _now(),
                }
                count += 1
            if count >= MAX_PER_KIND:
                break
    except (ClientError, BotoCoreError) as exc:
        _warn(warnings, "ec2:subnets", exc)

    try:
        paginator = ec2.get_paginator("describe_security_groups")
        count = 0
        for page in paginator.paginate():
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
                    for group_pair in perm.get("UserIdGroupPairs", []):
                        ingress.append({"protocol": perm.get("IpProtocol"), "fromPort": perm.get("FromPort"), "toPort": perm.get("ToPort"), "sourceSecurityGroupId": group_pair.get("GroupId"), "description": group_pair.get("Description")})
                vpc_id = sg.get("VpcId")
                rels = []
                if vpc_id:
                    rels.append({"type": "BELONGS_TO_VPC", "targetId": vpc_id})
                    edges.append({"sourceId": rid, "targetId": vpc_id, "type": "BELONGS_TO_VPC", "status": "OBSERVED"})
                nodes[rid] = {
                    "resourceId": rid, "resourceType": "AWS::EC2::SecurityGroup", "name": sg.get("GroupName") or rid,
                    "region": region, "accountId": account_id,
                    "attributes": {"description": sg.get("Description"), "vpcId": vpc_id, "ingressRules": ingress},
                    "relationships": rels, "source": "EC2 DescribeSecurityGroups", "lastObservedAt": _now(),
                }
                count += 1
            if count >= MAX_PER_KIND:
                break
    except (ClientError, BotoCoreError) as exc:
        _warn(warnings, "ec2:security-groups", exc)

    try:
        paginator = ec2.get_paginator("describe_instances")
        count = 0
        for page in paginator.paginate(PaginationConfig={"MaxItems": MAX_PER_KIND}):
            for reservation in page.get("Reservations", []):
                for inst in reservation.get("Instances", []):
                    rid = inst["InstanceId"]
                    rels = []
                    subnet_id, vpc_id = inst.get("SubnetId"), inst.get("VpcId")
                    if subnet_id:
                        rels.append({"type": "IN_SUBNET", "targetId": subnet_id})
                        edges.append({"sourceId": rid, "targetId": subnet_id, "type": "IN_SUBNET", "status": "OBSERVED"})
                    if vpc_id:
                        rels.append({"type": "IN_VPC", "targetId": vpc_id})
                    sg_ids = []
                    for group in inst.get("SecurityGroups", []):
                        gid = group.get("GroupId")
                        if gid:
                            sg_ids.append(gid)
                            rels.append({"type": "USES_SECURITY_GROUP", "targetId": gid})
                            edges.append({"sourceId": rid, "targetId": gid, "type": "USES_SECURITY_GROUP", "status": "OBSERVED"})
                    nodes[rid] = {
                        "resourceId": rid, "resourceType": "AWS::EC2::Instance", "name": _name(inst.get("Tags"), rid),
                        "region": region, "accountId": account_id,
                        "attributes": {"state": inst.get("State", {}).get("Name"), "instanceType": inst.get("InstanceType"), "vpcId": vpc_id, "subnetId": subnet_id, "securityGroupIds": sg_ids, "publicIpAddress": inst.get("PublicIpAddress"), "privateIpAddress": inst.get("PrivateIpAddress")},
                        "relationships": rels, "source": "EC2 DescribeInstances", "lastObservedAt": _now(),
                    }
                    count += 1
    except (ClientError, BotoCoreError) as exc:
        _warn(warnings, "ec2:instances", exc)

    # RDS may not exist in a student account; an empty result is a normal state.
    try:
        rds = session.client("rds")
        paginator = rds.get_paginator("describe_db_instances")
        count = 0
        for page in paginator.paginate(PaginationConfig={"MaxItems": MAX_PER_KIND}):
            for db in page.get("DBInstances", []):
                rid = db["DBInstanceArn"]
                dbid = db.get("DBInstanceIdentifier", rid)
                subnet_group = db.get("DBSubnetGroup", {})
                vpc_id = subnet_group.get("VpcId")
                rels = []
                if vpc_id:
                    rels.append({"type": "IN_VPC", "targetId": vpc_id})
                    edges.append({"sourceId": rid, "targetId": vpc_id, "type": "IN_VPC", "status": "OBSERVED"})
                nodes[rid] = {
                    "resourceId": rid, "resourceType": "AWS::RDS::DBInstance", "name": dbid,
                    "region": region, "accountId": account_id,
                    "attributes": {"publiclyAccessible": bool(db.get("PubliclyAccessible")), "engine": db.get("Engine"), "status": db.get("DBInstanceStatus"), "vpcId": vpc_id, "dbSubnetGroup": subnet_group.get("DBSubnetGroupName"), "endpointAddress": (db.get("Endpoint") or {}).get("Address")},
                    "relationships": rels, "source": "RDS DescribeDBInstances", "lastObservedAt": _now(),
                }
                count += 1
    except (ClientError, BotoCoreError) as exc:
        _warn(warnings, "rds:instances", exc)

    # S3 is global; inventory is metadata-only and never reads bucket objects.
    try:
        s3 = session.client("s3")
        bucket_list = s3.list_buckets().get("Buckets", [])[:MAX_PER_KIND]
        for bucket in bucket_list:
            name = bucket["Name"]
            bucket_region = None
            public_access_block_enabled = None
            bucket_policy_public = None
            try:
                loc = s3.get_bucket_location(Bucket=name).get("LocationConstraint")
                bucket_region = loc or "us-east-1"
            except (ClientError, BotoCoreError) as exc:
                _warn(warnings, f"s3:location:{name}", exc)
            # Bucket-level S3 API calls should target the bucket's actual Region.
            bucket_s3 = session.client("s3", region_name=bucket_region or "us-east-1")
            try:
                pab = bucket_s3.get_public_access_block(Bucket=name).get("PublicAccessBlockConfiguration", {})
                required = ["BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets"]
                public_access_block_enabled = all(pab.get(k) is True for k in required)
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code in {"NoSuchPublicAccessBlockConfiguration", "NoSuchConfiguration"}:
                    public_access_block_enabled = False
                else:
                    _warn(warnings, f"s3:public-access-block:{name}", exc)
            except BotoCoreError as exc:
                _warn(warnings, f"s3:public-access-block:{name}", exc)
            try:
                bucket_policy_public = bool(bucket_s3.get_bucket_policy_status(Bucket=name).get("PolicyStatus", {}).get("IsPublic"))
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code in {"NoSuchBucketPolicy", "NoSuchPolicy"}:
                    bucket_policy_public = False
                else:
                    _warn(warnings, f"s3:policy-status:{name}", exc)
            except BotoCoreError as exc:
                _warn(warnings, f"s3:policy-status:{name}", exc)
            arn = f"arn:aws:s3:::{name}"
            nodes[arn] = {
                "resourceId": arn, "resourceType": "AWS::S3::Bucket", "name": name,
                "region": bucket_region or region, "accountId": account_id,
                "attributes": {"createdAt": bucket.get("CreationDate"), "publicAccessBlockEnabled": public_access_block_enabled, "bucketPolicyPublic": bucket_policy_public},
                "relationships": [], "source": "S3 ListBuckets + bucket security metadata", "lastObservedAt": _now(),
            }
    except (ClientError, BotoCoreError) as exc:
        _warn(warnings, "s3:buckets", exc)

    # Attach inverse references only when both endpoints were actually collected.
    for node in nodes.values():
        for rel in node.get("relationships", []):
            target = rel.get("targetId")
            if target in nodes:
                nodes[target].setdefault("relationships", []).append({"type": f"HAS_{rel['type']}", "targetId": node["resourceId"]})

    items = list(nodes.values())
    return {
        "items": items,
        "edges": edges,
        "meta": {
            "region": region,
            "accountId": account_id,
            "collectedAt": _now(),
            "totalResources": len(items),
            "partial": bool(warnings),
            "warnings": warnings,
            "resourceCapPerType": MAX_PER_KIND,
        },
    }
