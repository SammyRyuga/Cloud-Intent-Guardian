import os
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from common.http import response, utc_now


def lambda_handler(event, context):
    region = os.environ.get("AWS_REGION", "unknown")
    account_id = None
    sts_status = "CONNECTED"
    config_status = "NOT_CONFIGURED"
    warnings = []
    session = boto3.session.Session(region_name=region)
    try:
        account_id = session.client("sts").get_caller_identity().get("Account")
    except (ClientError, BotoCoreError) as exc:
        sts_status = "ERROR"
        warnings.append({"source": "sts", "message": str(exc)[:250]})
    try:
        config = session.client("config")
        recorders = config.describe_configuration_recorders().get("ConfigurationRecorders", [])
        if not recorders:
            config_status = "NOT_CONFIGURED"
        else:
            statuses = config.describe_configuration_recorder_status().get("ConfigurationRecordersStatus", [])
            config_status = "CONNECTED" if any(x.get("recording") for x in statuses) else "STOPPED"
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"NoSuchConfigurationRecorderException", "NoAvailableConfigurationRecorderException"}:
            config_status = "NOT_CONFIGURED"
        else:
            config_status = "ERROR"
            warnings.append({"source": "aws_config", "message": exc.response.get("Error", {}).get("Message", str(exc))[:250]})
    except BotoCoreError as exc:
        config_status = "ERROR"
        warnings.append({"source": "aws_config", "message": str(exc)[:250]})
    status = "CONNECTED" if sts_status == "CONNECTED" else "DEGRADED"
    return response(200, {
        "status": status,
        "accountId": account_id,
        "region": region,
        "stage": os.environ.get("STAGE_NAME", "unknown"),
        "checkedAt": utc_now(),
        "sources": {
            "awsIdentity": {"status": sts_status},
            "awsConfig": {"status": config_status, "note": "AWS Config is optional for this first inventory implementation."},
            "liveInventory": {"status": "AVAILABLE" if sts_status == "CONNECTED" else "DEGRADED"},
        },
        "warnings": warnings,
    })
