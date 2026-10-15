# Local intent persistence on macOS

Phase 2 now requires six tables and their declared indexes. Use
`scripts/local_db.py init`, then explicitly `migrate` for earlier local records,
then `probe`. Local API mutations require the fixture provider's synthetic actor;
live AWS discovery remains blocked locally. Evaluation now queues work with 202;
run `scripts/run_evaluations.py` against the same local database to process it.
See [the current contract and commands](../INTEGRATION.md#phase-2-additions-2026-10-15).
The older sections below retain the original timeout investigation.

Run commands from `Cloud-Intent-Guardian/backend` (the directory containing `template.yaml`). No AWS deployment or Academy activation is needed. Keep the existing DynamoDB container. No command below removes it or deletes existing tables/items.

## What was actually inspected

The checkout at initial commit `b479f32` contains `README.md`, `template.yaml`, `src/requirements.txt`, eight handler packages, `src/common/http.py`, `src/common/inventory.py`, and two sample event files. There is no ZIP, implementation specification, frontend code, `local-env.json`, or `src/common/dynamodb.py` in that baseline. The user confirmed the frontend will be added later. This patch adds the shared helper and an environment example; it does not claim to inspect the absent Windows modifications.

## Evidence and failure path

`POST /v1/intents` maps to `IntentsFunction`, handler `intents.app.lambda_handler`, built from `src/`. The original handler constructs a DynamoDB resource and a table before parsing the request, validates the manifest, constructs a DRAFT record, calls conditional `PutItem`, then returns `201 {item}`. Creating a `Table` object is not a table existence check; the service call happens at `PutItem`.

The original five persistence handlers ignore `DYNAMODB_ENDPOINT_URL`: they call `boto3.resource("dynamodb")` directly. The template does not declare that variable. For this checkout, those are confirmed defects in local configuration. A stale SAM build could retain them after editing source.

The user's timeout log includes runtime `START RequestId`, so it supports runtime startup, but does not establish Python handler entry or which call blocked. `Invalid lambda response` follows the timeout and is not evidence of malformed handler JSON. The earlier structured `UnrecognizedClientException` establishes that an AWS-style request reached a service and was rejected, but does not independently prove which endpoint was used. Endpoint omission, stale build, missing environment override, Docker DNS/TCP failure, and SDK retries/timeouts are hypotheses for the Windows run until the diagnostics establish the actual endpoint and operation stage. `host.docker.internal` can be valid when the port is published; its use alone does not establish the cause.

## Small correction

- Shared `dynamodb_resource()` for all five persistence handlers, reusing one resource in the evaluation handler.
- Declare `DYNAMODB_ENDPOINT_URL` (empty) and `CIG_LOCAL` (`false`) in the SAM template, so local overrides have declared targets. Deployed defaults still use the normal Lambda role/session.
- Require an explicit local endpoint when running locally; refuse local endpoint overrides outside local mode. Only the documented local hostnames are accepted.
- Use fixed non-secret local signing placeholders, region `ap-south-1`, no inherited session token, no proxy, 2-second connection timeout, 3-second read timeout, and one SDK attempt for local DynamoDB. These settings are scoped to this helper, not live AWS inventory clients. DNS timing is independently diagnosed; socket timeouts cannot guarantee an upper bound on the operating system's DNS resolver.
- Log handler start, endpoint selection, and intent write start/success, without request bodies, passwords, authorization headers or credentials.
- Preserve numeric JSON fields when DynamoDB returns `Decimal` (e.g. `version` previously changed from JSON number to string after reading it).

## Terminal 1: inspect and build

```bash
cd /Volumes/Seagate/cloud-project/Cloud-Intent-Guardian/backend
python3 -m venv .venv
.venv/bin/python -m pip install -r src/requirements.txt
test -f local-env.json || cp local-env.example.json local-env.json
docker info --format '{{.ServerVersion}}'
docker inspect cig-dynamodb-local --format 'State={{.State.Status}} Args={{json .Args}} Networks={{json .NetworkSettings.Networks}} Ports={{json .NetworkSettings.Ports}}'
docker network inspect cig-local --format '{{json .Containers}}'
sam validate --lint
sam build
```

If Docker reports its socket unavailable, launch Docker Desktop with `open -a Docker` and wait until `docker info` succeeds. If SAM is absent, install with `brew install aws-sam-cli`. These install/start steps were not performed by this patch.

If the existing container is stopped, `docker start cig-dynamodb-local` starts it without replacing it, but `-inMemory` tables from the previous run are already gone. If the network is absent, `docker network create cig-local` creates it. If the inspected network list excludes this container, run `docker network connect cig-local cig-dynamodb-local` once. Do not repeat it when already connected. If the container itself is absent, stop and determine where the original container was created; this workflow does not recreate it automatically.

Do not overwrite an existing `local-env.json` blindly. Its effective IntentsFunction settings must match the example. `Parameters` provides global overrides; function-specific objects override it. The scripts display only the non-secret settings they use.

Check the host endpoint and all three schemas:

```bash
.venv/bin/python scripts/local_db.py probe --env-file local-env.json --endpoint http://127.0.0.1:8000
```

If it reports missing tables, explicitly create only those missing tables:

```bash
.venv/bin/python scripts/local_db.py init --env-file local-env.json --endpoint http://127.0.0.1:8000
```

This uses `CIGLOCAL` local signing and the same region as the helper. DynamoDB Local normally partitions databases by access key and region unless started with `-sharedDb`. An older CLI-created table may therefore be invisible under these values. The init step creates missing tables in the namespace used by the application; it does not delete another namespace. In-memory data survives only while that container process runs. Do not change its startup arguments or restart it just to add `-sharedDb`.

References: [SAM environment overrides](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-using-start-api.html), [DynamoDB Local usage notes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.UsageNotes.html).

## One focused runtime diagnostic

List cached images; pick the Python 3.13 runtime image used by SAM:

```bash
docker image ls --format '{{.Repository}}:{{.Tag}}'
bash scripts/diagnose-local.sh '<cached-python-3.13-runtime-image:tag>'
```

Replace the angle-bracket placeholder with the actual local image name. The script uses `--pull=never`, joins `cig-local`, mounts the existing build, and runs the same shared helper in a runtime container. It checks DNS, TCP connectivity, and the three table schemas in that order. It then invokes the actual `IntentsFunction` through SAM with your environment file and sample event. That invocation creates one draft intent if successful. The independent Docker probe uses the JSON file directly; only the SAM invocation verifies SAM's environment injection. This diagnostic container is disposable; the DynamoDB container remains intact.

Interpret the first failure:

| Evidence | Meaning / next correction |
| --- | --- |
| No runtime START | SAM/runtime startup is still failing; inspect preceding runtime error |
| START but no `intent_handler_started` | Handler import/startup did not reach its first line; inspect import exceptions and built files |
| `DYNAMODB_CONFIGURATION_FAILED` with missing endpoint | SAM overrides absent or build stale; verify declared variable, JSON precedence and rebuild |
| `dns_ok` absent | Docker hostname cannot resolve; inspect the shared network |
| DNS succeeds, TCP fails | Host resolved, but port/service not reachable; inspect container state and port |
| TCP succeeds, table missing | Local namespace/table state mismatch; use matching region/signing and explicit init |
| `intent_put_started` then structured error | Handler reached PutItem; error identifies endpoint/SDK/service failure |
| `intent_put_succeeded` and HTTP 201 | Write completed; still perform the separate persistence verification below |

An endpoint log pointing at AWS must not appear in a local run of this patch. A 25-second timeout after `intent_put_started` despite the local timeout config warrants checking that SAM is mounting the new build and whether another exception/call is involved.

## Terminal 1: start SAM

Stop an existing SAM server with Ctrl-C, rebuild after edits, then start it:

```bash
sam local start-api \
  --template .aws-sam/build/template.yaml \
  --env-vars ./local-env.json \
  --docker-network cig-local \
  --region ap-south-1 \
  --skip-pull-image
```

Bind locally (the default loopback address); keep the server terminal open.

## Terminal 2: prove the immediate milestone

```bash
cd /Volumes/Seagate/cloud-project/Cloud-Intent-Guardian/backend
.venv/bin/python scripts/local_db.py verify \
  --env-file local-env.json \
  --endpoint http://127.0.0.1:8000
```

This checks HTTP 201 and `item.intentId`, directly reads that item from DynamoDB Local with `ConsistentRead`, follows list pagination until it finds the same ID, and checks the detail response matches the created record. Only after all four checks pass does it write `local-evidence/intent-persistence.json` and print `milestone_passed`. The script intentionally leaves the test intent in your database. Evidence is ignored by Git. A missing/older evidence file is not evidence of success on the current run; use the exit code and current console output.

After that passes, approval can be tested separately using the actual returned ID:

```bash
curl --fail-with-body -X POST "http://127.0.0.1:3000/v1/intents/<intentId>/approve"
curl --fail-with-body "http://127.0.0.1:3000/v1/intents/<intentId>"
curl --fail-with-body "http://127.0.0.1:3000/v1/findings"
```

These are commands to run, not reported passes. Do not launch live inventory/evaluations until their AWS discovery dependencies have an approved test strategy; DynamoDB Local does not emulate EC2, RDS, S3 or STS.

## Authentication and remaining backend work

The template declares a Cognito JWT authorizer as the default on `AWS::Serverless::HttpApi`. Only `/v1/health` sets `Authorizer: NONE`. SAM's local JWT emulation is unsupported in the reported behavior; the warning is not fixed by removing authorization. [AWS SAM JWT authorizer issue](https://github.com/aws/aws-sam-cli/issues/6550). Local route tests do not prove authorization. Once explicitly authorized to deploy, require anonymous protected requests to fail, invalid/expired JWTs to fail, valid JWTs to succeed, and public health to remain accessible.

Existing capabilities are inventory metadata and observed graph edges, draft/approve intent manifests, four deterministic rules, stored findings, and synchronous evaluation storage. Missing capabilities include finding details, dashboard aggregation, evaluation history/detail/status reads, intent version management, audit events, architectural relationship constraints, account/role isolation, remediation requests/approvals and Bedrock explanations. Paths/schemas for new capabilities must be agreed when the frontend specification arrives; this patch invents none.

Follow-up correctness issues visible in the existing code: resource caps do not mark inventory partial (old findings can be incorrectly resolved), scans select/reconcile only a first page, SSH checking does not restrict TCP protocol, evaluation finding writes can raise uncaught SDK errors, approval lacks conditional state transition, and evaluation runs live discovery serially within a short Lambda timeout. Resolve and test these after persistence; do not treat this patch as full backend readiness.

No resources have been deployed. Before Academy deployment, inspect the lab's actual allowed operations and whether SAM can create roles or must reference an existing lab role. Review a SAM change set; verify permission to package artifacts and create CloudFormation, Lambda, API Gateway, Cognito and DynamoDB resources plus necessary read-only discovery/logging permissions. Set the agreed region and exact frontend origin; review IAM and indexes for the agreed access patterns. Cost review must cover Lambda, API Gateway, DynamoDB, logs, packaging S3, Cognito and any optional AWS Config usage with current pricing and lab restrictions. Bedrock and automatic remediation remain later phases. Deployment requires explicit authorization.

## Repeatable code checks

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -v
bash -n scripts/diagnose-local.sh
sam validate --lint
```

Tests use real Boto3 resource serialization with botocore Stubber responses; they test local isolation, timeout config, error shape and create/list/detail/approval contracts. They do not connect to DynamoDB Local, run SAM or verify Cognito. The subsequent integration tests require the development dependencies in `requirements-dev.txt`; runtime Lambda dependencies remain in `src/requirements.txt`. See [current integration status](../INTEGRATION.md).
