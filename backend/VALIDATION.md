# Validation of the local persistence patch

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
