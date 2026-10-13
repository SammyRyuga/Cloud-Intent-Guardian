# Cloud Intent Guardian — AWS backend starter

This is the first deployable AWS backend slice for the Cloud Intent Guardian MVP. It uses AWS SAM/CloudFormation to create the infrastructure; no long-running local server is required.

## Included in this slice

- Amazon Cognito User Pool with **admin-only user creation**.
- API Gateway HTTP API with Cognito JWT authorization on application endpoints.
- Public `GET /v1/health` liveness endpoint (does not reveal AWS account information).
- Authenticated `GET /v1/system/status` account/source readiness endpoint.
- Authenticated `GET /v1/resources` read-only live inventory for EC2 instances, VPCs, subnets, security groups, RDS DB instances and S3 bucket metadata.
- `GET /v1/intents`, `POST /v1/intents`, `GET /v1/intents/{intentId}`, and `POST /v1/intents/{intentId}/approve` for JSON constraint manifests.
- `POST /v1/evaluations` to evaluate an approved intent against live inventory.
- `GET /v1/findings` for persisted findings.
- DynamoDB tables for intents, findings and evaluation history.
- A first deterministic constraint set: `S3_BLOCK_PUBLIC_ACCESS`, `EC2_NO_PUBLIC_IP`, `RDS_NOT_PUBLICLY_ACCESSIBLE`, `SECURITY_GROUP_NO_OPEN_SSH`.

This is an MVP, not the final system described in the case study. IaC/ADR file upload, AWS Config event ingestion, Step Functions, Bedrock explanations, RBAC and safe remediation are later phases. No remediation action is executed by this starter.

## Prerequisites on Windows

1. An AWS account with billing alerts enabled.
2. AWS CLI v2.
3. AWS SAM CLI.
4. Python 3.13 (recommended for local tests) and Docker Desktop if you want containerized SAM builds/local emulation.
5. An AWS identity authorized to create CloudFormation stacks, Lambda roles/functions, API Gateway, Cognito User Pools and DynamoDB tables. Use your organization's/student-lab rules; do not create long-lived access keys for the root user.

Install instructions: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html

## 1. Verify AWS credentials first (PowerShell)

```powershell
aws --version
sam --version
aws configure list
aws sts get-caller-identity
```

The final command must return the account ID and the identity you intend to deploy with. If it fails, stop and configure a named AWS CLI profile through your approved IAM/Identity Center flow. Do not paste credentials into chat or commit them to Git.

Set a profile and region for this terminal if needed:

```powershell
$env:AWS_PROFILE = "default"
$env:AWS_DEFAULT_REGION = "ap-south-1"
aws sts get-caller-identity
```

Mumbai (`ap-south-1`) is a reasonable default for an India-based student project, but use the region your team has chosen consistently.

## 2. Validate and build

From this directory:

```powershell
sam validate --lint
sam build
```

If SAM asks about a template or environment, run these commands from the folder containing `template.yaml`.

## 3. Deploy a development stack

```powershell
sam deploy --guided
```

Use these answers for the first deployment:

- Stack Name: `cloud-intent-guardian-dev`
- AWS Region: `ap-south-1` (or your selected region)
- StageName: `dev`
- AllowedOrigin: `http://localhost:5173`
- Confirm changes before deploy: `Y`
- Allow SAM CLI IAM role creation: `Y`
- Disable rollback: `N`
- Save arguments to configuration: `Y`

Review the CloudFormation change set before accepting it. The stack creates billable service usage and storage/API resources; no EC2 instance, RDS database, NAT Gateway, ALB or Fargate service is created by this starter.

## 4. Read the outputs

```powershell
aws cloudformation describe-stacks --stack-name cloud-intent-guardian-dev --query "Stacks[0].Outputs[*].[OutputKey,OutputValue]" --output table
```

Copy `ApiUrl`, `AwsRegion`, `CognitoUserPoolId`, and `CognitoUserPoolClientId` into a **local, uncommitted** frontend environment file later. The User Pool Client ID is public configuration, not a secret. Never put AWS access keys in the frontend.

Test the unauthenticated health endpoint:

```powershell
$api = (aws cloudformation describe-stacks --stack-name cloud-intent-guardian-dev --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)
Invoke-RestMethod -Method Get -Uri "$api/v1/health"
```

Expect `ok: true`.

## 5. Create users (admin only)

The User Pool does not allow public sign-up. In the AWS Console:

1. Open Amazon Cognito → User pools → the `cloud-intent-guardian-dev-users` pool.
2. Create a user for each teammate using their email address.
3. Use the temporary-password flow and complete the required password reset at first sign-in.
4. Never share a password or token in source control or chat.

Your frontend teammate will configure Cognito login with the User Pool ID and Client ID; application API requests must send `Authorization: Bearer <Cognito JWT>`.

## API contract summary

- `GET /v1/health` — public liveness check.
- `GET /v1/system/status` — account ID, selected region, AWS Config recorder status.
- `GET /v1/resources` — live inventory JSON with `items`, observed `edges`, and `meta` including warnings/partial state.
- `GET /v1/intents` — `{ items, count, nextToken }`.
- `POST /v1/intents` — creates a `DRAFT` intent from a JSON manifest.
- `GET /v1/intents/{intentId}` — returns `{ item }`.
- `POST /v1/intents/{intentId}/approve` — explicitly approves a draft.
- `POST /v1/evaluations` — body `{ "intentId": "optional-id" }`; if omitted, uses the most recently updated approved intent.
- `GET /v1/findings` — `{ items, nextToken, count, limit }`; supports `?limit=25&status=OPEN`.

### Supported intent example

```json
{
  "name": "Initial AWS baseline",
  "description": "Demo constraints approved by the team",
  "constraints": [
    {
      "id": "no-open-ssh",
      "type": "SECURITY_GROUP_NO_OPEN_SSH",
      "severity": "HIGH",
      "description": "SSH must not be open to the public internet"
    },
    {
      "id": "s3-block-public-access",
      "type": "S3_BLOCK_PUBLIC_ACCESS",
      "severity": "HIGH",
      "description": "All S3 buckets must enable all Block Public Access settings"
    },
    {
      "id": "no-public-rds",
      "type": "RDS_NOT_PUBLICLY_ACCESSIBLE",
      "severity": "CRITICAL",
      "description": "RDS instances must not be publicly accessible"
    },
    {
      "id": "no-public-ec2-ip",
      "type": "EC2_NO_PUBLIC_IP",
      "severity": "MEDIUM",
      "description": "EC2 instances must not have public IPv4 addresses"
    }
  ]
}
```

## Error response contract

Errors use this shape:

```json
{"error":{"code":"NO_APPROVED_INTENT","message":"Create an intent and approve it before running an evaluation."}}
```

The frontend should handle `401/403` (auth/session), `400` (invalid input), `404` (unknown intent), `409` (workflow state), and `502` (AWS source/backend error) as distinct states.

## Security/cost guardrails

- Keep account/root credentials out of code and chat.
- Use Cognito JWT authorization for all API routes except the low-information health endpoint.
- Inventory IAM actions are read-only. No public API route can change EC2, S3, security groups or RDS configurations.
- Never store AWS secrets in DynamoDB or browser storage.
- Add AWS Budgets billing alerts before deploying. Check current pricing for each service and delete the stack when the demo is no longer needed.
- AWS Config is optional for this first pass; status reports whether a recorder appears configured. The inventory itself uses read-only AWS service APIs.
- The scanner caps results at 250 resources per kind in this starter. A warning is returned if an AWS data source could not be read, and incomplete inventory does not auto-resolve old findings.
- Do not expose this API to a broad audience until user-level authorization/RBAC and tenant/account isolation have been implemented.

## Delete development resources

When ready to remove the stack:

```powershell
sam delete --stack-name cloud-intent-guardian-dev --region ap-south-1
```

Review the target stack name and region before confirming. If any S3 bucket was created outside this template by SAM's deployment packaging, SAM may need separate cleanup depending on the CLI prompt and configuration.
