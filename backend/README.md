# Cloud Intent Guardian backend

The main [project README](../README.md) contains macOS instructions for tool setup, DynamoDB Local, environment configuration, SAM, intent persistence verification, the API contract and authorized AWS Academy deployment.

Run backend commands from this directory, which contains `template.yaml`.

- [Detailed local diagnostics](LOCAL_TESTING.md): request tracing, runtime connectivity checks and timeout interpretation.
- [Validation record](VALIDATION.md): checks actually run and work still unverified.
- [Environment example](local-env.example.json): copy to an uncommitted `local-env.json` only if no configuration file exists.

Start with local intent creation and retrieval. Live inventory and evaluation require separate AWS access. Cognito authorization remains in the deployment template; local SAM requests do not verify it. No AWS deployment is implied by these instructions.
