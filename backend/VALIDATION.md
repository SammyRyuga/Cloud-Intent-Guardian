# Validation of the local persistence patch

## Phase 1 validation - 2026-10-15

Implemented v2 manifests, deterministic relationship/path/boundary rules,
coverage-aware graph comparison and explicit local fixture observations. Existing
v1 envelopes and attribute finding IDs remain intact. Phase 2 async/version/audit,
Phase 3 scoring, Phase 4 Bedrock/corroboration and Phase 5 remediation are not
implemented by this phase.

Checks run against this phase:

- **75 backend tests passed** with Python 3.14.8, cached boto3 1.43.108 and Moto
  5.2.4. Tests include the original botocore Stubber contracts, Moto-backed handler
  workflows, pure topology/manifest rules, and fake SDK inventory clients. They
  cover legacy manifests, v2 approval round trips, complete/partial coverage,
  component cardinality, selector ambiguity, all five topology rules, missing
  attributes, stable finding IDs, conservative resolution and local-only fixtures.
- **DynamoDB Local workflow passed** against a newly isolated container
  `cig-phase-validation`, loopback port 18000. Tables were initialized with
  `scripts/local_db.py init`, then `scripts/verify_topology.py` called the real
  Lambda handlers and checked consistent reads and all graph views. Benign:
  SUCCEEDED/no finding; open SSH: SUCCEEDED/deterministic finding; Lambda DB bypass:
  SUCCEEDED/path findings including HIGH; unruled crossing and source-disagreement
  seeds: PARTIAL/no fabricated conformance. Intent ID:
  `6f586f63-9823-428f-a348-853d90309723`. Ignored evidence:
  `backend/local-evidence/phase1-topology.json`.
- **SAM lint/validation and build passed** using SAM CLI 1.168.0. Build targets
  Python 3.13/x86_64; dependencies were resolved from public wheels downloaded to
  `/private/tmp/cig-phase-wheels`, with `PIP_NO_INDEX=1`. No cloud API was used.
- **Frontend gates passed**: `npm run lint` (three existing warnings), `npm test`
  (20/20), `npm run test:contract` (10/10) and `npm run build`. Generated real
  handler responses validate in both languages. The architecture chunk is
  83,476 bytes gzip, within the documented 250 kB gzip budget. No new rendered
  browser journey was run in this phase; the earlier browser evidence remains dated.
- `git diff --check` and Python compilation passed. `local-env.json` remains
  ignored. No existing database/container was replaced.

Reproduction commands on this host (from repository root, except SAM build):

```bash
CIG_CONTRACT_OUTPUT=frontend/tests/fixtures/backend-contract.json \
CIG_TOPOLOGY_CONTRACT_OUTPUT=frontend/tests/fixtures/topology-contract.json \
PYTHONPATH=/private/tmp/cig-test-venv/lib/python3.14/site-packages \
python3.14 -S -m unittest discover -s backend/tests -v

cd backend
PYTHONPATH=/private/tmp/cig-test-venv/lib/python3.14/site-packages \
python3.14 -S scripts/local_db.py init --endpoint http://127.0.0.1:18000
PYTHONPATH=/private/tmp/cig-test-venv/lib/python3.14/site-packages \
python3.14 -S scripts/verify_topology.py --endpoint http://127.0.0.1:18000

PYTHONPATH=/private/tmp/cig-test-venv/lib/python3.14/site-packages \
SAM_CLI_TELEMETRY=0 AWS_EC2_METADATA_DISABLED=true \
python3.14 /private/tmp/cig-test-venv/bin/sam validate --lint
PIP_NO_INDEX=1 PIP_FIND_LINKS=/private/tmp/cig-phase-wheels \
PYTHONPATH=/private/tmp/cig-test-venv/lib/python3.14/site-packages \
SAM_CLI_TELEMETRY=0 AWS_EC2_METADATA_DISABLED=true \
python3.14 /private/tmp/cig-test-venv/bin/sam build
```

The cached virtualenv's original Python symlink is stale; the explicit interpreter
and `-S` avoid reliance on it and on unrelated host site packages. For a normal
checkout, install `requirements-dev.txt` into a working project virtualenv and
use its Python/SAM commands. PyPI DNS was unavailable inside the sandbox; public
build wheels were downloaded with the permitted network path. Docker Desktop was
started locally and Docker access required sandbox escalation.

Still unverified: deployed Cognito JWT/group enforcement, Academy IAM/region/service
availability, live AWS inventory/tag/Lambda permissions, real network reachability,
API Gateway integration for these new paths, independent-source cross-validation,
Bedrock and all modifying actions. The local verifier directly invokes handlers;
it does not prove deployed API authorization or persistence across an in-memory
container restart. The source-disagreement fixture is intentionally only an UNKNOWN
candidate until Phase 4 implements corroboration.

The original dated records below are retained as historical evidence.

Run date: 2026-10-13. Baseline inspected: `b479f32`.

Confirmed in this workspace:

- Seven `unittest` tests passed using cached Boto3 1.43.111 and botocore Stubber: local endpoint required; cloud endpoint rejected locally; local endpoint rejected outside local mode; production uses the default role/session; local client endpoint/timeouts/signing isolation; create/list/detail/approval response contracts; structured connection failure.
- Python AST parsing passed for backend Python files.
- `bash -n backend/scripts/diagnose-local.sh` passed.
- `git diff --check` passed.

The stubbed tests perform no service network calls and prove no DynamoDB persistence or SAM connectivity. Test responses are explicitly provided by botocore Stubber. The test code is committed and runs with `python -m unittest discover -s tests -v` after installing the existing requirements. In this workspace package installation failed because PyPI DNS resolution was unavailable; tests were run by adding already-cached package directories to Python's import path.

Not run/proven here:

- SAM validation/build/API emulation: SAM executable unavailable.
- Real DynamoDB Local writes/reads: Docker's daemon socket unavailable.
- The user's Windows network/container/environment state.
- Cognito authorization, live inventory/evaluation, Academy permissions, production deployment or resource costs.

The user's previously reported successful SAM validation/build, health calls and invalid-input calls remain user-reported evidence for their earlier code. They are not rerun results for this patch.

Use `LOCAL_TESTING.md` to run the runtime probe and the real four-part persistence verification on the machine with SAM and the existing database container. Only that verification can establish the immediate live milestone.

## Subsequent integration validation

The original limitations above describe the initial patch, not the current validation state. On 2026-10-13, SAM validation/build, real SAM-to-DynamoDB Local persistence, thirteen Python tests, seventeen frontend tests and two browser integration journeys passed. The database was isolated and temporary. See [current integration evidence](../INTEGRATION.md). Live AWS deployment and Cognito remain unverified.
