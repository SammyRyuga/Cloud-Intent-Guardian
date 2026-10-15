# Cloud Intent Guardian

Cloud Intent Guardian compares approved architecture constraints with live AWS configuration and stores findings with severity and evidence. The current backend uses AWS SAM, Python 3.13 Lambda, API Gateway, Cognito and DynamoDB.

**Start by proving local intent persistence. AWS Academy activation and deployment are separate steps requiring explicit authorization.** Local SAM/DynamoDB integration is verified; AWS deployment and Cognito authentication remain unverified. See [recorded validation](backend/VALIDATION.md).

## Files and current scope

```text
backend/
  template.yaml                 Infrastructure, routes, IAM and environment defaults
  local-env.example.json        Local SAM configuration example
  LOCAL_TESTING.md               Detailed timeout diagnosis
  VALIDATION.md                 Recorded checks and remaining verification
  events/                       Sample Lambda events
  scripts/local_db.py            Probe, initialize missing tables, verify persistence
  scripts/diagnose-local.sh      Runtime-container and SAM diagnostic
  tests/                        SDK-stubbed contract tests
  src/                          Eight handlers and shared helpers
```

The backend implements v2 architectural intent, four attribute checks plus relationship/path/boundary rules, immutable approved versions, rollback, async evaluation/history, audit and finding lifecycle. INTENT/DIFF graphs and a guarded local fixture worker are available. Server roles use Cognito groups. Live collected edges are structural; network reachability remains unknown without adequate evidence. Severity scoring, cross-validated Bedrock escalation and gated remediation remain later phases. See [current integration](INTEGRATION.md) and [validation](backend/VALIDATION.md).

The React frontend is in `frontend/`, together with its PRD and implementation specification. [Integration guide](INTEGRATION.md) documents the connected MVP, real local API mode and remaining AWS validation.

## Frontend setup on macOS

Use Node.js 22.19 or newer in a supported release line. From the repository root:

```bash
cd frontend
npm ci
test -f .env.development.local || cp .env.example .env.development.local
npm run dev
```

The example explicitly enables development mocks with a visible banner. This is a fixture preview, not live AWS data. `VITE_USE_MOCKS=false` disables mocks even during development. Endpoint paths include `/v1`, so `VITE_API_BASE_URL` must be an origin such as `http://127.0.0.1:3000`, without that suffix. For the real local backend, use `.env.local-api.example` instead of the mock example and follow [INTEGRATION.md](INTEGRATION.md). Production uses the deployed Cognito configuration.

```bash
npm run lint
npm test
npm run test:contract
npm run build
```

Production builds reject `VITE_USE_MOCKS=true`; `.env.development.local` is not loaded for a default production build. See [frontend README](frontend/README.md) for public configuration.

## 1. macOS tools

Use Terminal with zsh or bash. Check installed tools:

```bash
python3 --version
sam --version
docker --version
aws --version
```

Use Python 3.13, Docker Desktop, AWS SAM CLI and AWS CLI v2. If using Homebrew, install only missing tools:

```bash
brew install python@3.13 aws-sam-cli awscli
brew install --cask docker
```

Homebrew's SAM package is community maintained; AWS also provides [macOS installers](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html). If `python3` selects another version, use `python3.13` below.

```bash
open -a Docker
docker info --format '{{.ServerVersion}}'
```

Wait until Docker Desktop finishes starting and the second command succeeds.

## 2. Backend setup - Terminal 1

For a new checkout:

```bash
git clone https://github.com/SammyRyuga/Cloud-Intent-Guardian.git
cd Cloud-Intent-Guardian/backend
```

For the existing workspace, use this instead:

```bash
cd /Volumes/Seagate/cloud-project/Cloud-Intent-Guardian/backend
```

All following backend commands run from the folder containing `template.yaml`.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r src/requirements.txt
test -f local-env.json || cp local-env.example.json local-env.json
```

The copy preserves an existing configuration. Check its effective values against the example; function-specific overrides take precedence over global `Parameters`.

| Variable | SAM local value |
| --- | --- |
| `CIG_LOCAL` | `true` |
| `DYNAMODB_ENDPOINT_URL` | `http://cig-dynamodb-local:8000` |
| `INTENTS_TABLE` | `cloud-intent-guardian-dev-intents` |
| `FINDINGS_TABLE` | `cloud-intent-guardian-dev-findings` |
| `EVALUATIONS_TABLE` | `cloud-intent-guardian-dev-evaluations` |

Local intent persistence uses fixed non-secret signing placeholders scoped to the DynamoDB helper. No real AWS keys or lab tokens are required. The local environment file, virtual environment, build artifacts and evidence directory are ignored by Git.

## 3. Preserve and inspect DynamoDB Local

```bash
docker inspect cig-dynamodb-local \
  --format 'State={{.State.Status}} Args={{json .Args}} Networks={{json .NetworkSettings.Networks}} Ports={{json .NetworkSettings.Ports}}'
docker network inspect cig-local --format '{{json .Containers}}'
```

Run only the correction matching the inspection result:

- Existing container stopped: `docker start cig-dynamodb-local`.
- Network missing: `docker network create cig-local`.
- Container absent from the network: `docker network connect cig-local cig-dynamodb-local`.

Do not delete or replace the existing container. With `-inMemory`, stopping its process loses tables/data. Without `-sharedDb`, DynamoDB Local separates databases by signing key and region; the helper uses local placeholder `CIGLOCAL` and region `ap-south-1`. Older tables under different values may therefore be invisible. [DynamoDB Local usage notes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.UsageNotes.html).

For a **fresh checkout only**, if inspection confirms no existing container, create a persistent local database:

```bash
docker network inspect cig-local >/dev/null 2>&1 || docker network create cig-local
docker volume create cig-dynamodb-data
docker run -d --name cig-dynamodb-local \
  --network cig-local \
  -p 127.0.0.1:8000:8000 \
  -v cig-dynamodb-data:/home/dynamodblocal/data \
  amazon/dynamodb-local:latest \
  -jar DynamoDBLocal.jar -sharedDb -dbPath /home/dynamodblocal/data
```

This may pull the image. The named volume persists files, and the host port binds to loopback. Containers use `cig-dynamodb-local:8000`; your Mac uses `127.0.0.1:8000`.

## 4. Probe and initialize missing tables

```bash
.venv/bin/python scripts/local_db.py probe \
  --env-file local-env.json --endpoint http://127.0.0.1:8000
```

The probe checks endpoint selection, DNS, TCP and schemas. If it reports missing tables, explicitly create only those missing:

```bash
.venv/bin/python scripts/local_db.py init \
  --env-file local-env.json --endpoint http://127.0.0.1:8000
```

| Table | String partition key |
| --- | --- |
| `cloud-intent-guardian-dev-intents` | `intentId` |
| `cloud-intent-guardian-dev-findings` | `findingId` |
| `cloud-intent-guardian-dev-evaluations` | `evaluationId` |

Incorrect existing schemas produce an error; the script does not replace tables.

## 5. Build and start SAM - Terminal 1

```bash
sam validate --lint
sam build
sam local start-api \
  --template .aws-sam/build/template.yaml \
  --env-vars ./local-env.json \
  --docker-network cig-local \
  --region ap-south-1 \
  --skip-pull-image
```

Keep this terminal open. The API uses `http://127.0.0.1:3000`. Skipping image pulls requires a usable local runtime image. After source/template edits, stop SAM with Ctrl-C, rebuild and restart it.

## 6. Verify persistence - Terminal 2

Open another terminal in the same backend directory:

```bash
cd /Volumes/Seagate/cloud-project/Cloud-Intent-Guardian/backend
curl --fail-with-body http://127.0.0.1:3000/v1/health
.venv/bin/python scripts/local_db.py verify \
  --env-file local-env.json --endpoint http://127.0.0.1:8000
```

Substitute your actual backend path for a checkout elsewhere. The verifier checks POST HTTP 201 with an ID, a direct consistent DynamoDB read, paginated list retrieval of the same ID, and a matching detail response. Only after all four pass does it print `milestone_passed` and write `local-evidence/intent-persistence.json`. It leaves the test record in the database. Use current output/exit status; old evidence is not proof of a new run.

After this passes, replace the ID placeholder to check approval and findings:

```bash
intent_id='YOUR_RETURNED_INTENT_ID'
curl --fail-with-body -X POST "http://127.0.0.1:3000/v1/intents/$intent_id/approve"
curl --fail-with-body "http://127.0.0.1:3000/v1/intents/$intent_id"
curl --fail-with-body 'http://127.0.0.1:3000/v1/findings?limit=25'
```

Expect the approval/detail item to have `status: APPROVED`. These commands are instructions, not recorded test passes. Live inventory/evaluation calls need AWS access and an agreed test plan; DynamoDB Local does not emulate STS, EC2, RDS or S3.

## 7. Diagnose a timeout

```bash
docker image ls --format '{{.Repository}}:{{.Tag}}'
bash scripts/diagnose-local.sh 'YOUR_CACHED_PYTHON_3_13_RUNTIME_IMAGE:TAG'
```

Use the actual cached SAM image name. The diagnostic preserves the database container, probes DNS/TCP/tables from a runtime container using the built helper, then invokes `IntentsFunction` through SAM to check environment injection. That invocation creates a draft if successful.

| Evidence | Interpretation |
| --- | --- |
| No runtime START | Runtime invocation not established |
| START, no `intent_handler_started` | Inspect handler import/startup and build |
| `DYNAMODB_CONFIGURATION_FAILED` | Missing/invalid endpoint or configuration |
| DNS fails | Docker hostname/network resolution issue |
| DNS succeeds, TCP fails | Service or port unreachable |
| Table absent/schema wrong | Database namespace/table-state issue |
| `intent_put_started` then error | PutItem was reached; inspect the structured error |
| `intent_put_succeeded` | Write completed; still run persistence verification |

The original checkout ignored `DYNAMODB_ENDPOINT_URL`; the shared helper fixes that defect. The exact cause of the earlier Windows timeout remains unproven. SAM's invalid-response message followed the timeout and does not establish malformed handler JSON. [Detailed diagnosis](backend/LOCAL_TESTING.md).

## API contract

| Method and path | Request / response |
| --- | --- |
| `GET /v1/health` | Public `{ok, service, timestamp, version}` |
| `GET /v1/system/status` | Live AWS `{status, accountId, region, stage, checkedAt, sources, warnings}` |
| `GET /v1/resources` | Live inventory `{items, edges, meta}` |
| `GET /v1/architecture/graph?view=ACTUAL` | Observed graph; INTENT and DIFF also accept optional intentId/version, with evidence-based comparison states |
| `GET /v1/dashboard/summary` | Stored counts and latest evaluation conformance; unavailable features are null |
| `GET /v1/findings/{findingId}` | `{item}` with persisted evidence |
| `GET /v1/intents` | Optional `limit`, `nextToken`; `{items, count, nextToken, limit}` |
| `POST /v1/intents` | Manifest; HTTP 201 `{item}` containing `intentId` and DRAFT status |
| `GET /v1/intents/{intentId}` | `{item}` |
| `POST /v1/intents/{intentId}/approve` | `{item}`; repeated approval also includes a message |
| `POST /v1/evaluations` | `{intentId}` or `{}`; 202 `{evaluation,statusUrl}` with queued ID |
| `GET /v1/evaluations` / `GET /v1/evaluations/{id}` | Paginated history / `{item}` status polling |
| `GET /v1/audit` | Scope-bound paginated audit history |
| `PATCH /v1/findings/{findingId}` | Explicit lifecycle action/revision; suppression requires a reason |
| `GET /v1/findings` | Optional `limit`, `nextToken`, `status`; `{items, nextToken, count, limit}` |

Prefer an explicit approved ID for evaluation: default selection has a bounded scan and refuses incomplete selection. Evaluation responses include at most 100 findings. List ordering applies within each scan page, not globally.

Example manifest:

```json
{
  "name": "Local AWS Baseline",
  "description": "Integration test for Cloud Intent Guardian",
  "constraints": [{
    "id": "s3-public-access",
    "type": "S3_BLOCK_PUBLIC_ACCESS",
    "severity": "HIGH",
    "description": "S3 buckets must block public access"
  }]
}
```

Supported types: `EC2_NO_PUBLIC_IP`, `RDS_NOT_PUBLICLY_ACCESSIBLE`, `S3_BLOCK_PUBLIC_ACCESS`, `SECURITY_GROUP_NO_OPEN_SSH`. Severities: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`.

Application errors use `{ "error": { "code": "...", "message": "...", "details": "optional" } }`. Handle 400 input errors, 404 missing items, 409 workflow conflicts and 502 backend failures. Gateway authentication errors may use a different body. Frontend requests go through the API, never directly to DynamoDB, Config, CloudTrail or Bedrock.

## Authentication and validation

The template retains Cognito JWT authorization for all application routes except health. It now provisions a hosted login domain and configurable OAuth callback/logout URLs. Local SAM's JWT limitation explains authorizer warnings; local success does not prove deployed authentication. [AWS SAM issue](https://github.com/aws/aws-sam-cli/issues/6550). Deployed tests must confirm public health succeeds, anonymous/invalid/expired-token protected requests fail, and a valid JWT succeeds. The Cognito user pool allows admin-only user creation.

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -v
bash -n scripts/diagnose-local.sh
sam validate --lint
```

The earlier persistence patch passed seven SDK-stubbed tests. The integration work additionally passed thirteen Python tests, seventeen frontend tests, SAM validation/build, real local persistence and two browser journeys. Cognito and live AWS discovery remain unverified; see [INTEGRATION.md](INTEGRATION.md). [Validation record](backend/VALIDATION.md).

Inventory cap handling, bounded evaluation scans, TCP-specific SSH checking, finding-write error handling and conditional approval were corrected during integration. Next add async evaluation/history and audit contracts. Bedrock and remediation remain later phases.

## AWS Academy deployment - requires explicit authorization

Do not run deployment as part of local setup. Review the lab-approved region and permissions, whether it permits IAM role creation or requires an existing role, the frontend origin and the SAM change set. The current template creates roles and is not yet verified against Academy restrictions.

Permission review covers packaging S3, CloudFormation, Lambda, IAM, API Gateway, Cognito, DynamoDB, CloudWatch logs and read-only inventory. Review least privilege and indexes against agreed access patterns. Cost review covers Lambda, API Gateway, on-demand DynamoDB, Cognito, logs, packaging S3 and any optional Config recording. No fixed cost or lab entitlement is asserted.

Only after authorization and lab identity setup:

```bash
aws sts get-caller-identity
sam validate --lint
sam build
sam deploy --guided
```

Use stack `cloud-intent-guardian-dev`, the lab-approved region, `StageName=dev`, `AllowedOrigin` equal to the actual frontend origin, and matching `CognitoCallbackUrl`/`CognitoLogoutUrl`. Enable change-set confirmation and rollback; review before executing. Allow role creation only if the lab permits it. Do not deploy `local-env.json`: production defaults use `CIG_LOCAL=false`, an empty local endpoint and the Lambda execution role.

After deployment, inspect the API URL, region, Cognito pool/client and table outputs; verify health, authorization and persistence before reporting success. Keep credentials, passwords and tokens out of Git/chat.

## Push source changes

From the repository root after committing reviewed changes:

```bash
git push https://github.com/SammyRyuga/Cloud-Intent-Guardian.git main
```

A source push does not deploy AWS resources. Network/DNS/authentication failure means the push did not complete.
