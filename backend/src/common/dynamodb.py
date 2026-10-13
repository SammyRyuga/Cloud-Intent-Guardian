"""Use DynamoDB Local only in an explicitly local execution environment."""
import json
import os
from urllib.parse import urlsplit

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError


class DynamoDBConfigurationError(BotoCoreError):
    fmt = "{message}"


def dynamodb_resource():
    local = any(os.environ.get(key, "").lower() == "true"
                for key in ("AWS_SAM_LOCAL", "CIG_LOCAL"))
    endpoint = os.environ.get("DYNAMODB_ENDPOINT_URL", "").strip()
    if local and not endpoint:
        raise DynamoDBConfigurationError(message="Local execution requires DYNAMODB_ENDPOINT_URL; refusing to use AWS DynamoDB.")
    if endpoint and not local:
        raise DynamoDBConfigurationError(message="DYNAMODB_ENDPOINT_URL requires AWS_SAM_LOCAL=true or CIG_LOCAL=true.")
    if not local:
        return boto3.resource("dynamodb")

    parsed = urlsplit(endpoint)
    if (parsed.scheme != "http" or parsed.hostname not in {
        "localhost", "127.0.0.1", "::1", "cig-dynamodb-local", "host.docker.internal"
    } or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"}):
        raise DynamoDBConfigurationError(message="Use an HTTP DynamoDB Local endpoint on localhost, host.docker.internal or cig-dynamodb-local.")
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "ap-south-1"
    # Non-secret, fixed local signing values. Never use these for other AWS services.
    session = boto3.Session(aws_access_key_id="CIGLOCAL", aws_secret_access_key="CIGLOCAL", region_name=region)
    resource = session.resource("dynamodb", endpoint_url=endpoint, config=Config(
        connect_timeout=2, read_timeout=3,
        retries={"mode": "standard", "total_max_attempts": 1}, proxies={},
    ))
    print(json.dumps({"event": "dynamodb_configured", "mode": "local", "endpoint": endpoint,
                      "region": region, "signing": "fixed-local-placeholder"}), flush=True)
    return resource
