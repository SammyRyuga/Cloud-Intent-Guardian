from common.auth import require_role
import os
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from common.http import response, utc_now
from common.contracts import is_local, local_status
from botocore.config import Config


@require_role('viewer')
def lambda_handler(event, context):
    region = os.environ.get("AWS_REGION", "unknown")
    if is_local():
        state = local_status(region, os.environ.get('STAGE_NAME', 'dev'))
        state['features'] = {'fixtureInventory': os.environ.get('INVENTORY_PROVIDER') == 'fixture',
                             'topology': os.environ.get('TOPOLOGY_ENABLED', 'true').lower() == 'true',
                             'remediationProposals': os.environ.get('INVENTORY_PROVIDER') == 'fixture',
                             'evaluations': os.environ.get('INVENTORY_PROVIDER') == 'fixture',
                             'remediationExecution': False,
                             'driftEvents': os.environ.get('DRIFT_HISTORY_ENABLED', 'false').lower() == 'true'}
        return response(200, state)
    account_id = None
    sts_status = "CONNECTED"
    config_status = "NOT_CONFIGURED"
    warnings = []
    session = boto3.session.Session(region_name=region)
    config_options = Config(connect_timeout=2, read_timeout=3, retries={'total_max_attempts': 1, 'mode': 'standard'})
    try:
        account_id = session.client("sts", config=config_options).get_caller_identity().get("Account")
    except (ClientError, BotoCoreError) as exc:
        sts_status = "ERROR"
        warnings.append({"source": "sts", "message": str(exc)[:250]})
    if os.environ.get('CONFIG_ENABLED', 'false').lower() != 'true':
        config_status = 'NOT_ENABLED'
    else:
        try:
            config = session.client("config", config=config_options)
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
    discovery_ok = sts_status == 'CONNECTED'
    for service, operation, options in [('ec2', 'describe_instances', {'MaxResults': 5}),
                                        ('rds', 'describe_db_instances', {'MaxRecords': 20}),
                                        ('s3', 'list_buckets', {})]:
        try:
            getattr(session.client(service, config=config_options), operation)(**options)
        except (ClientError, BotoCoreError) as exc:
            discovery_ok = False
            warnings.append({'source': service, 'message': f'Readiness probe failed: {type(exc).__name__}'})
    status = "CONNECTED" if discovery_ok else "DEGRADED"
    checked_at = utc_now()
    return response(200, {
        "status": status,
        "accountId": account_id,
        "region": region,
        "stage": os.environ.get("STAGE_NAME", "unknown"),
        "checkedAt": checked_at,
        "backendReachable": True,
        "awsSourcesConnected": discovery_ok,
        "evaluatedRegion": region,
        "lastSyncAt": checked_at,
        "version": "0.2.0",
        "sources": {
            "awsIdentity": {"status": sts_status},
            "awsConfig": {"status": config_status, "note": "AWS Config is optional for this first inventory implementation."},
            "liveInventory": {"status": "AVAILABLE" if discovery_ok else "DEGRADED", "note": "STS and EC2/RDS/S3 list probes succeeded; individual resource security metadata is checked during inventory."},
        },
        "features": {"driftEvents": os.environ.get("DRIFT_HISTORY_ENABLED", "false").lower() == "true", "remediationProposals": True, "remediationExecution": os.environ.get("REMEDIATION_ENABLED", "false").lower() == "true" and os.environ.get("REMEDIATION_DRY_RUN", "true").lower() == "false"},
        "warnings": warnings,
    })
