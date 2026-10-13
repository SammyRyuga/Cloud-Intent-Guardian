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
| `VITE_LOCAL_API` | Explicit development-only local backend mode; production rejects true |
| `VITE_COGNITO_REDIRECT_SIGN_IN` | Exact configured OAuth callback URL |
| `VITE_COGNITO_REDIRECT_SIGN_OUT` | Exact configured sign-out URL |
| `VITE_COGNITO_REGION` | Cognito region |
| `VITE_COGNITO_USER_POOL_ID` | Cognito user pool ID |
| `VITE_COGNITO_CLIENT_ID` | Public Cognito app client ID |
| `VITE_COGNITO_DOMAIN` | Cognito managed-login domain |
| `VITE_DEFAULT_REGION` | Region selected in the interface |
| `VITE_FEATURES` | Comma-separated enabled frontend capabilities |

The frontend follows the frontend PRD in `Cloud_Intent_Guardian_Frontend_PRD.md`. The connected MVP implements JSON intent creation/detail/approval, findings list/detail, stored dashboard data, system readiness, observed topology and synchronous evaluation. Unsupported later workflows remain disabled in live mode.

For real local integration, copy `.env.local-api.example` to `.env.development.local` (preserve and edit an existing configuration), start the local SAM backend, and use `npm run dev -- --host localhost --port 5173 --strictPort`. This is explicit loopback-only local API mode, not Cognito authentication. See [integration instructions and evidence](../INTEGRATION.md).

## Project structure

- `src/app/` — providers and route composition
- `src/features/` — route-level screens
- `src/components/` — shared presentation components
- `src/hooks/` — API query and mutation bindings
- `src/api/` — API client, schemas, and development mocks
- `src/auth/` — Cognito authentication client and route protection
- `src/config/` — public runtime configuration and capability flags

See the repository-level backend guide in `../backend/README.md` for AWS deployment details.
