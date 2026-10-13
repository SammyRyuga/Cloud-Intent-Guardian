# Cloud Intent Guardian frontend

React 18, TypeScript, and Vite single-page application for the Cloud Intent Guardian project.

## Run locally

From this directory:

```bash
npm ci
test -f .env.development.local || cp .env.example .env.development.local
npm run dev
```

Use Node.js 22.19 or newer in a supported release line. The example explicitly enables the development mock API. The `Mock mode` banner identifies this state; mock responses are not production data. `VITE_USE_MOCKS=false` disables mocks even in development. Production builds reject `VITE_USE_MOCKS=true`; keep mock settings in `.env.development.local`, which is not loaded by a default production build. To build the app, run `npm run build`. To lint it, run `npm run lint`. Run `npm test` for configuration and mock-fixture schema checks, or `npm run test:contract` for fixture checks alone. These are not browser/component tests.

## Configuration

Create a local `.env` file for a deployed backend. Only public configuration belongs in `VITE_` variables. Never add AWS credentials, private keys, or other secrets.

| Variable | Purpose |
| --- | --- |
| `VITE_API_BASE_URL` | API origin without `/v1`; endpoint paths already include it |
| `VITE_USE_MOCKS` | Enable development mock responses (`true` or `false`) |
| `VITE_COGNITO_REGION` | Cognito region |
| `VITE_COGNITO_USER_POOL_ID` | Cognito user pool ID |
| `VITE_COGNITO_CLIENT_ID` | Public Cognito app client ID |
| `VITE_COGNITO_DOMAIN` | Cognito managed-login domain |
| `VITE_DEFAULT_REGION` | Region selected in the interface |
| `VITE_FEATURES` | Comma-separated enabled frontend capabilities |

The frontend follows the frontend PRD in `Cloud_Intent_Guardian_Frontend_PRD.md`. The current backend starter exposes a smaller API surface than that PRD; keep unsupported capabilities disabled in live configuration and use mock mode for the full UI until the API contracts are aligned.

Merging the frontend does not establish live integration: findings/intents identifiers and pagination differ, system-status fields differ, and evaluations expect jobs while the backend runs synchronously. Dashboard, graph, finding detail, jobs, upload, drift, remediation and audit endpoints are not yet implemented by the backend. The template also lacks the managed-login domain and OAuth callback configuration used by this frontend. See [integration gaps](../INTEGRATION.md).

## Project structure

- `src/app/` — providers and route composition
- `src/features/` — route-level screens
- `src/components/` — shared presentation components
- `src/hooks/` — API query and mutation bindings
- `src/api/` — API client, schemas, and development mocks
- `src/auth/` — Cognito authentication client and route protection
- `src/config/` — public runtime configuration and capability flags

See the repository-level backend guide in `../backend/README.md` for AWS deployment details.
