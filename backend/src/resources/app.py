import os
from common.http import response, error
from common.inventory import collect_inventory
from botocore.exceptions import BotoCoreError, ClientError


def lambda_handler(event, context):
    region = os.environ.get("AWS_REGION")
    try:
        inventory = collect_inventory(region)
    except (ClientError, BotoCoreError) as exc:
        return error(502, "INVENTORY_FAILED", "The backend could not read the AWS inventory.", {"reason": str(exc)[:300]})
    if not inventory["meta"].get("accountId"):
        return error(502, "AWS_IDENTITY_UNAVAILABLE", "AWS account identity could not be confirmed. Check the Lambda execution role.")
    return response(200, inventory)
