"""Attribute rules retain legacy known-value decisions, with explicit missing evidence."""
from common.manifest import ATTRIBUTE_TYPES


def _violates(constraint, resource):
    ctype = constraint["type"]
    attrs = resource.get("attributes") or {}
    if ctype == "S3_BLOCK_PUBLIC_ACCESS" and resource["resourceType"] == "AWS::S3::Bucket":
        value = attrs.get("publicAccessBlockEnabled")
        return value is False, {"publicAccessBlockEnabled": value, "bucketPolicyPublic": attrs.get("bucketPolicyPublic"), "publicAccessBlock": attrs.get("publicAccessBlock"), "publicAccessBlockMissing": attrs.get("publicAccessBlockMissing", False)}, "All four S3 Block Public Access settings must be enabled."
    if ctype == "EC2_NO_PUBLIC_IP" and resource["resourceType"] == "AWS::EC2::Instance":
        value = attrs.get("publicIpAddress")
        return bool(value), {"publicIpAddress": value}, "The EC2 instance has a public IPv4 address."
    if ctype == "RDS_NOT_PUBLICLY_ACCESSIBLE" and resource["resourceType"] == "AWS::RDS::DBInstance":
        value = attrs.get("publiclyAccessible")
        return value is True, {"publiclyAccessible": value}, "The RDS instance is configured as publicly accessible."
    if ctype == "SECURITY_GROUP_NO_OPEN_SSH" and resource["resourceType"] == "AWS::EC2::SecurityGroup":
        matching = []
        for rule in attrs.get("ingressRules", []):
            protocol = str(rule.get("protocol", ""))
            first, last, cidr = rule.get("fromPort"), rule.get("toPort"), str(rule.get("cidr", ""))
            port_covers_ssh = protocol == "-1" or (protocol in {'tcp', '6'} and first is not None and last is not None and first <= 22 <= last)
            public_source = cidr in {"0.0.0.0/0", "::/0"}
            if port_covers_ssh and public_source:
                matching.append(rule)
        return bool(matching), {"matchingIngressRules": matching, **({"attachmentImpact": {**attrs["attachmentImpact"], "observedAt": resource.get("lastObservedAt")}} if "attachmentImpact" in attrs else {})}, "The security group permits SSH (TCP/22) from the public internet."
    return False, {}, "Constraint does not apply to this resource type."



def attribute_outcome(constraint, resource):
    if resource.get('resourceType') != ATTRIBUTE_TYPES.get(constraint['type']):
        return 'NOT_APPLICABLE', {}, 'Rule does not apply to this resource type.'
    attrs = resource.get('attributes') or {}
    field = {'EC2_NO_PUBLIC_IP': 'publicIpAddress', 'RDS_NOT_PUBLICLY_ACCESSIBLE': 'publiclyAccessible',
             'S3_BLOCK_PUBLIC_ACCESS': 'publicAccessBlockEnabled', 'SECURITY_GROUP_NO_OPEN_SSH': 'ingressRules'}[constraint['type']]
    value = attrs.get(field)
    known = field in attrs
    if constraint['type'] in {'RDS_NOT_PUBLICLY_ACCESSIBLE', 'S3_BLOCK_PUBLIC_ACCESS'}:
        known = isinstance(value, bool)
    if constraint['type'] == 'SECURITY_GROUP_NO_OPEN_SSH':
        known = isinstance(value, list) and all(isinstance(row, dict) and row.get('protocol') is not None for row in value)
    if constraint['type'] == 'SECURITY_GROUP_NO_OPEN_SSH' and known:
        # A known public SSH witness still violates even if another source is unresolved.
        violated, observed, explanation = _violates(constraint, resource)
        if violated:
            return 'VIOLATION', observed, explanation
        for row in value:
            if row.get('publicSourceUnknown'):
                known = False
            if row.get('cidr') in {'0.0.0.0/0', '::/0'} and str(row.get('protocol')) in {'tcp', '6'}:
                if row.get('fromPort') is None or row.get('toPort') is None:
                    known = False
    if not known:
        return 'UNKNOWN', {field: value}, 'Required attribute was not collected; absence is not a passing result.'
    violated, observed, explanation = _violates(constraint, resource)
    return 'VIOLATION' if violated else 'PASS', observed, explanation if violated else 'Observed attribute satisfies the rule.'
