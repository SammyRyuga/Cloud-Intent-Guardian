# Cloud Intent Guardian frontend

React 18, TypeScript, and Vite single-page application for the Cloud Intent Guardian project.

## Run locally

From this directory:

```powershell
npm ci
npm run dev
```

Development uses the in-browser mock API by default. The `Mock mode` banner identifies this state; mock responses are not production data. To build the app, run `npm run build`. To lint it, run `npm run lint`.

## Configuration

Create a local `.env` file for a deployed backend. Only public configuration belongs in `VITE_` variables. Never add AWS credentials, private keys, or other secrets.

| Variable | Purpose |
| --- | --- |
| `VITE_API_BASE_URL` | API origin or base path |
| `VITE_USE_MOCKS` | Enable development mock responses (`true` or `false`) |
| `VITE_COGNITO_REGION` | Cognito region |
| `VITE_COGNITO_USER_POOL_ID` | Cognito user pool ID |
| `VITE_COGNITO_CLIENT_ID` | Public Cognito app client ID |
| `VITE_COGNITO_DOMAIN` | Cognito managed-login domain |
| `VITE_DEFAULT_REGION` | Region selected in the interface |
| `VITE_FEATURES` | Comma-separated enabled frontend capabilities |

The frontend follows the frontend PRD in `Cloud_Intent_Guardian_Frontend_PRD.md`. The current backend starter exposes a smaller API surface than that PRD; keep unsupported capabilities disabled in live configuration and use mock mode for the full UI until the API contracts are aligned.

## Project structure

- `src/app/` — providers and route composition
- `src/features/` — route-level screens
- `src/components/` — shared presentation components
- `src/hooks/` — API query and mutation bindings
- `src/api/` — API client, schemas, and development mocks
- `src/auth/` — Cognito authentication client and route protection
- `src/config/` — public runtime configuration and capability flags

See the repository-level backend guide in `../backend/README.md` for AWS deployment details.
