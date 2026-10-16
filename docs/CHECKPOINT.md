# Remaining work checkpoint - 2026-10-16

The owner requested that tested work be pushed before usage limits. No new cloud
deployment or finding state change was performed for this checkpoint.

## Saved and tested

- Optional snapshot drift table, worker staging/publication, scoped paginated
  GET /v1/drift-events and GET /v1/drift-events/{id}, viewer UI and mock fixtures.
  First complete same-intent/version evaluation establishes a baseline. Partial
  data never proves deletion; immutable deterministic events stay hidden until
  successful publication. EnableDriftHistory defaults false.
- Disabled API routing/JWT/Cognito and Lambda-role/declared-policy collectors.
  Seven SDK tests pass. IAM simulation helper records a simulation result;
  effectiveAuthorization stays UNKNOWN. Collection is bounded, but Guardian-only
  stack filtering and SAM flag/permission wiring remain unfinished.
- Read-only scripts/verify_live_operations.py correlates one existing intent
  record with exact same-stream started/succeeded CloudWatch events, with source
  IDs required and one bounded log page. Four correlation tests pass. No general
  authorization or packet-path inference is made.

Final checks: 187 backend tests, 34 frontend tests, 14 contract tests, SAM lint,
SAM build, frontend lint/build. Two existing Fast Refresh warnings. New drift
persistence tests use Moto; a DynamoDB Local drift journey has not been run.

## Resume safely

1. Recheck git, deployment status and current feature flags. Last verified live
   implementation was 6545469, plus documentation 5c859c2. Guardian intent
   9af2782d-f80b-41f8-9bd7-eeefddeb672d version 1 is approved; live evaluation
   d9750c08-cc02-49ec-af1d-b1e387ef8fc2 passed its seven structural rules.
2. Run eight-table DynamoDB Local drift first-baseline/change/retry/partial tests,
   then deploy EnableDriftHistory=true only after those checks. Re-run unit/SAM
   and frontend gates; verify authenticated drift endpoints and UI on live data.
3. Finish exact CloudFormation stack-resource scoping for architecture collectors
   before enabling them. Function names can be truncated by CloudFormation;
   prefix guessing can exclude the evaluation worker. Use actual resource IDs.
   Add SAM API_ARCHITECTURE_INVENTORY_ENABLED, IAM_ARCHITECTURE_INVENTORY_ENABLED,
   COGNITO_ARCHITECTURE_INVENTORY_ENABLED and conditional read permissions.
   Review an expanded intent with the owner before approval.
4. Bedrock: prior synthetic in-region google.gemma-3-4b-it runtime calls succeeded
   but strict JSON parsing failed. Diagnose the raw response and validate a strict
   schema-compatible result before activation. No cross-region profile is
   authorized implicitly; no agreements or subscriptions were accepted.
5. Existing VPC Flow Logs and Reachability Analyzer paths were absent. Guardian
   is serverless; do not create NAT/EC2/RDS solely for packet evidence. Historical
   app-write evidence is in ignored backend/local-evidence/ and is not current
   network reachability proof.
6. Five earlier findings: two duplicate-by-intent findings refer to one real
   open-SSH SG (unrelated Guardian); three missing EC2 components belong to older
   approved baselines. Review intent retirement/suppression with the owner and
   preserve the real SSH issue. Do not auto-resolve or remediate them.

Remediation remains disabled/dry-run. Use profile ryan and ap-south-1 only for
previously authorized cloud work; never retrieve credential values or function
environment secrets. Exact resource inventories and live receipts remain ignored.

Cached local checks use PYTHONPATH=/private/tmp/cig-test-venv/lib/python3.14/site-packages
with python3.14 -S for unittest; SAM uses python3.14 /private/tmp/cig-test-venv/bin/sam.
Build wheels are /private/tmp/cig-phase-wheels (PIP_NO_INDEX=1). These temporary
paths may disappear; inspect before reuse.
