from common.http import response, utc_now


def lambda_handler(event, context):
    return response(200, {"ok": True, "service": "cloud-intent-guardian-api", "timestamp": utc_now(), "version": "0.1.0"})
