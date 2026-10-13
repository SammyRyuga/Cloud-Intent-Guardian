# Frontend/backend integration status

The `frontend` branch has been incorporated alongside the existing backend. This joins source histories; it does not establish live end-to-end integration. No backend endpoint or persisted identifier was renamed to make the merge appear complete.

## Verified merge checks

Checked on 2026-10-13 using Node.js 22.19.0:

- Locked dependency installation (`npm ci`) completed.
- `npm test`: 12 checks passed (nine mock-fixture schema checks and three environment/configuration checks).
- `npm run test:contract`: nine fixture checks passed.
- `npm run build`: TypeScript and production Vite build passed; the mock service worker was absent from the final output.
- A build with `VITE_USE_MOCKS=true` failed with the intended configuration error.
- `npm run lint` completed with four warnings in imported code (two fast-refresh export warnings and two unused-variable warnings). The configured linter is Oxlint; it does not implement every boundary rule prescribed by the frontend instruction file.
- Emitted JavaScript files passed the documented gzip thresholds after route splitting. Vite reported the main chunk at 130.37 KB gzip and the architecture chunk at 83.86 KB gzip.
- A limited artifact check found no selected fixture identifiers/MSW markers, AWS access-key-shaped values, or private-key headers in generated JavaScript. This is not a comprehensive security audit.

See `backend/VALIDATION.md` for separate backend checks. No browser journeys, accessibility checks, live AWS discovery, Cognito login or real database persistence were verified by this merge.

## Contracts that still need alignment

| Area | Current backend | Current frontend expectation |
| --- | --- | --- |
| System status | `status`, `accountId`, `region`, `sources`, `checkedAt` | `backendReachable`, `awsSourcesConnected`, `evaluatedRegion`, `lastSyncAt`, `version` |
| Findings | `findingId`, `firstSeenAt`, `nextToken` at top level | `id`, `detectedAt`, `remediationAvailable`, `meta.nextCursor` |
| Intents | `intentId`, numeric `version`, `constraints`, `updatedAt`; detail `{item}` | `id`, `currentVersion`, `versions`, `resourceCount`, `lastUpdatedAt`; direct detail object |
| Evaluations | Synchronous `{evaluation, findings, inventory}` | Job submission with `jobId`, followed by `/v1/jobs/{jobId}` polling |
| Architecture | `/v1/resources` with observed items/edges | `/v1/architecture/graph` with diff nodes/edges and truncation |
| Authentication | Cognito pool/client and JWT authorizer; SRP/password flows | Managed-login domain and authorization-code OAuth callbacks |

The supplied implementation specification and actual frontend also differ in places (for example `/v1/architecture` in the specification versus `/v1/architecture/graph` in frontend endpoints, and recommended `data/meta` envelopes versus direct frontend objects). Resolve these explicitly with both owners before changing contracts. Do not silently fabricate conformance, graph diff states, historical versions or approval success.

Backend routes absent today: dashboard summary, finding detail/status mutation, job status, graph comparison, intent upload/ingestion, drift events, audit events, remediation requests/decisions and explanation generation. Existing approval is `/v1/intents/{intentId}/approve`; the UI does not yet implement that JSON-manifest flow.

## Safe development mode

Use explicit development mocks to inspect the full frontend. Copy `frontend/.env.example` to `.env.development.local`. The visible mock banner identifies fixture data. `VITE_USE_MOCKS=false` disables mocking; production rejects a true flag. API base URLs are origins without `/v1`, since endpoint paths include that prefix.

Setting an API URL alone does not close the contracts above. Keep unsupported live capabilities disabled. Do not remove Cognito authorization to connect the UI; the backend template needs managed-login domain/callback support before the frontend's real login can work.

## Next integration milestone

1. Prove the existing intent POST/list/detail flow with the backend persistence verifier.
2. Agree a compatible status, findings and JSON-intent transport contract, preserving backend identifiers or explicitly adapting them in `src/api/`.
3. Configure Cognito OAuth and exact frontend-origin CORS after deployment authorization.
4. Implement job-based evaluation/status and server-backed dashboard/graph data, with deterministic evidence and partial inventory handling.
5. Add history/audit and human-approved remediation only after detection and approval paths pass.

## Validation boundaries

The frontend instruction file specifies additional unit/component, accessibility, E2E, boundary-lint, bundle and live-contract gates. The imported branch did not provide implementations for all those gates. Fixture tests and the available lint/build scripts are checked during this merge; missing gates must be implemented before treating the application as production ready. Backend live integration and browser journeys remain separate unverified work.
