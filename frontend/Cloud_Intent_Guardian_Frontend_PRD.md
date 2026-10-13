# Cloud Intent Guardian: Frontend Product Requirements Document

| | |
|---|---|
| **Product** | Cloud Intent Guardian (CIG), an AWS architecture-conformance platform |
| **Document** | Frontend PRD (React single-page application only) |
| **Version** | 1.0, draft for backend alignment |
| **Date** | 2026-10-11 |
| **Frontend owner** | Aritra |
| **Source of truth** | `Cloud_Intent_Guardian_Implementation_Spec.md`, referred to below as **the Spec** |
| **Precedence rule** | Where this PRD and the Spec differ, the Spec wins until the change is agreed through the contract process in §10.3 |

---

## 0. Conventions

### 0.1 Provenance tags

Every requirement or contract detail carries one of these tags so nobody mistakes an assumption for an agreed fact.

| Tag | Meaning |
|---|---|
| **[SPEC]** | Stated by the Spec. Copy, field names and numbers are taken from it verbatim. |
| **[DERIVED]** | A direct consequence of combining Spec statements. No new decision was needed. |
| **[DESIGN]** | A frontend decision inside freedom the Spec leaves open. |
| **[PROPOSED]** | Not in the Spec. The frontend needs it, and it is registered in §16 as an Open Contract Item (OCI) for the backend to confirm or change. Until confirmed, the frontend follows the stated fallback. |

### 0.2 Priorities and identifiers

| Item | Meaning |
|---|---|
| **P0** | Needed for the Milestone 1 to 3 demo (Spec §14) |
| **P1** | Needed for Milestones 4 and 5 |
| **P2** | Milestone 6 hardening, or polish not required by the Spec |
| `INV-xx` | Frontend invariant, never violated (§3) |
| `CC-xx` | Spec cross-check finding (§2) |
| `OCI-xx` | Open Contract Item for the backend (§16) |
| `AC-xxx-nn` | Acceptance criterion for a page or component (§8) |

"Spec §n" always uses the Spec's own section numbers.

### 0.3 Reading order

- **Backend developers:** §9 (integration layer), §10 (connection plan), §16 (open items), Appendix C (contract types).
- **Frontend developers:** all of it, in order.
- **Reviewers:** §2 (what was checked), §3 (the rules), §12 (how it is verified).

---

## 1. Product context and frontend scope

### 1.1 What the product is [SPEC §0]

CIG represents an approved AWS architecture as versioned intent, gathers a supported subset of live AWS resources and relationships, detects violations of explicit architecture constraints, explains the evidence, and routes risky remediation through human approval. The frontend is the investigation and approval surface for that loop.

### 1.2 Primary user [SPEC §1]

A cloud engineer or security analyst reviewing an AWS environment and investigating why it no longer conforms to approved architecture. The product is an operations dashboard. It is not a marketing page.

### 1.3 Frontend ownership [SPEC §15]

| Area | Frontend role |
|---|---|
| Visual system, routes, responsive shell | Owner |
| Overview, findings table, finding detail UI | Owner (backend supplies payloads and query filters) |
| Architecture graph visualization | Owner (backend defines node/edge schema and computes diff state) |
| Intent upload/review UI | Owner (backend does presigned upload, parsing, versioning, constraint approval) |
| Cognito login integration | Owner, jointly reviewed (backend configures pool, client, authorizer) |
| Remediation approval UI | Owner (backend enforces authorization and workflow) |
| Build and deploy configuration | Owner of frontend build/deploy config; collaborates on the rest |
| Endpoint handlers, ingestion, evaluation engine, Bedrock | Consumes the contract and displays results only |

### 1.4 Goals

| ID | Goal |
|---|---|
| G1 | Every screen is data-driven through the deployed API. No page contains hard-coded operational data. |
| G2 | Every page has loading, empty, partial, error and success states (Spec §4, §17). |
| G3 | The Architecture Explorer clearly distinguishes approved architecture from what was observed, and renders backend-provided diff states without computing any. |
| G4 | The Finding detail page is the best investigation tool in the product: expected versus observed, violation path, evidence, lifecycle. |
| G5 | The frontend and backend share one contract (types, schemas, fixtures) so the backend developer can connect to the frontend by following this plan. |
| G6 | The interface has a deliberate, subject-specific visual identity and does not look generated or templated (§6). |
| G7 | The application is fast, accessible (WCAG 2.2 AA) and safe: no secrets in the bundle, no browser-side AWS access, no invented data. |

### 1.5 Non-goals

- No AWS SDK calls from the browser except the Cognito authentication library. No IAM credentials, access keys or Bedrock keys anywhere in the client [SPEC §5, §10].
- No diff, conformance, severity or path logic in React [SPEC §3.2, §12].
- No dark theme and no theme toggle. The Spec requires one theme globally [SPEC §1]. This PRD picks the light theme.
- No multi-account onboarding, no bulk remediation, no automatic-remediation toggle [SPEC §3.3, §3.9].
- No marketing landing page.
- No internationalisation framework in the MVP. All copy is English, kept in one vocabulary module so it can be extracted later.

### 1.6 "AWS-connected" from the frontend side [DERIVED from SPEC §0]

The frontend meets the Spec's definition when all of these hold:

1. All data arrives through the deployed API (`VITE_USE_MOCKS` is off).
2. Nothing visible is hard-coded, including the "Connected" indicator, which comes only from `/v1/system/status`.
3. A controlled change in the AWS account produces, and later resolves, a finding that appears in Findings and in the Architecture Explorer without any frontend code change.

---

## 2. Requirements cross-check against the Spec

### 2.1 Method

All 1,086 lines of the Spec were read and each requirement was checked four ways:

1. Against the page text in Part A.
2. Against the JSON examples and TypeScript in Parts B and D (can the screen actually be built from the payload?).
3. Against the ownership table (§15), milestone exit criteria (§14), and the test checklist (§17).
4. Against the Spec's own rules (§16 PR rules, §4 shared behaviour).

### 2.2 Result

The Spec is consistent about structure, routes, states, safety rules and ownership. The checks found **28 items** that needed a decision before building. They are listed below with the PRD's resolution. None blocks Milestone 1 (UI on fixtures). Items marked **Backend** need an answer from the backend developers and are tracked in §16.

Categories: **Conflict** (two Spec statements disagree), **Gap** (the screen needs something the contract does not carry), **Ambiguity** (more than one reading), **Risk** (works but fails a quality bar), **Tension** (two Spec goals pull against each other).

### 2.3 Findings

| ID | Type | Spec reference | Observation | PRD resolution | Backend? |
|---|---|---|---|---|---|
| CC-01 | Ambiguity | §5 step 4 | "Bearer `<JWT>`" does not say whether the ID token or the access token is sent. A Cognito JWT authorizer validates them differently (`aud` vs `client_id`). | Send the **access token** by default. Read display claims (name, email) from the ID token client-side only. Make the choice a single line in `authClient.ts`. | Yes, OCI-01 |
| CC-02 | Gap | §5 env example, §14 M2 | The example env file has no Cognito domain or redirect URLs, which managed login needs. `VITE_USE_MOCKS` appears in §14 only. The sidebar chip needs a `DEMO`/`LIVE` source, but `VITE_APP_ENV` carries `development`. | Add `VITE_COGNITO_DOMAIN`, `VITE_COGNITO_REDIRECT_SIGN_IN`, `VITE_COGNITO_REDIRECT_SIGN_OUT`, `VITE_USE_MOCKS`, `VITE_DEPLOYMENT_MODE` (`demo`\|`live`), `VITE_FEATURES`. See §13.1. All are public, non-secret values. | Yes, OCI-02 |
| CC-03 | Conflict | §6.8 vs §6.9, §13 | `POST /v1/intents/ingest` returns `status: "PROCESSING"`, then says to poll `/v1/jobs/{jobId}`. The `JobStatus` type and §6.9 list `QUEUED`, `RUNNING`, `SUCCEEDED`, `PARTIAL`, `FAILED` only. | Treat only `SUCCEEDED`, `PARTIAL`, `FAILED` as terminal. Any other string is non-terminal and shown humanised. A maximum polling window prevents endless polling (§9.5). | Yes, OCI-04 |
| CC-04 | Gap | §6.9, §6.12 | `/v1/jobs/{jobId}` and `/v1/system/status` list field names but give no payload. | Proposed payloads in OCI-03 and OCI-04. Frontend schemas are tolerant of extra fields. | Yes |
| CC-05 | Gap | §3.1 vs §2 | The overview shows a `View job` link, but the route table has no job route. | Open a global **Job drawer** from any page with `?job=<jobId>`. Route names stay stable. | No |
| CC-06 | Gap | §3.5, §8, §14 M4 | The Spec calls for approving an intent version, a version diff, a version list and constraint review. §6.7 defines only list, detail, upload-url and ingest. | Proposed endpoints in OCI-09. Until confirmed, `Review and approve` and the diff tab render as `Not enabled` (INV-14). | Yes |
| CC-07 | Gap | §3.7 vs §6.11 | The approval detail needs parameters, risk note, dry-run output and audit timeline. `Cancel request` is mentioned. §6.11 has list, create and decision only, with no list-item or detail payload. | Proposed in OCI-10. `Cancel request` is hidden until its endpoint exists. | Yes |
| CC-08 | Gap | §3.2 vs §6.6 | The Explorer needs outline colour by finding severity, ARN, tags, last observed time, intended and live status for edges, explanation text, "Not collected" relationship types, and an empty-state explanation. The §6.6 node/edge carries none of these. | Proposed additions in OCI-08. Fallbacks are listed there, and none of them infer security meaning in React. | Yes |
| CC-09 | Gap | §3.4 vs §6.4 | The detail page needs relation labels between path steps, a "Why it matters" text, related findings, a confidence value with its definition, a rule ID and a console link. §6.4 has `path` (nodes only), `description`, `intent.constraintId`. | Map `description` to "Why it matters" and `intent.constraintId` to the rule ID. Hide the confidence card when absent (the Spec allows this). Rest in OCI-07. | Yes |
| CC-10 | Gap | §3.3 vs §6.3 | The page needs search text, first/last-seen date ranges and sort. §6.3 supports `severity`, `status`, `category`, `resourceType`, `limit`, `cursor` only. | Proposed parameters in OCI-06. Until confirmed, text search filters only the loaded results and says so in a caption, while date-range and sort controls render as `Not enabled` (sorting or date-filtering one page would mislead). | Yes |
| CC-11 | Gap | §3.1 vs §6.2 | The System health panel shows `Connected`, `Needs setup`, `Error`, `Not enabled`, plus evaluator, last inventory and latest error. §6.2 shows only `CONNECTED` and `NOT_ENABLED`, and its `sourceStatus` omits the evaluator and latest error. | Codes `NEEDS_SETUP` and `ERROR` are assumed. Evaluator and latest error come from `/v1/system/status`. | Yes, OCI-05 |
| CC-12 | Gap | §3.9 | Settings lists an evaluation-settings section (constraint set, threshold, schedule) with no endpoint. | Render it read-only: show `Not enabled` for each unsupported item. Everything else is built from `/v1/dashboard/summary`, `/v1/system/status` and the session. | Yes, OCI-17 |
| CC-13 | Gap | §1 vs §0 | The top bar lists notifications, but no endpoint exists and SNS is "a later phase". | The bell is a client-derived activity menu: evaluations the user started, pending-approval count, system degradation. It never fabricates server notifications (§7.6). | No, OCI-19 |
| CC-14 | Risk | §1 colours | Secondary text `#68758A` on the page background `#F6F8FB` is about 4.4:1, below the AA threshold of 4.5:1. On white it is about 4.7:1. | Use `#68758A` on white surfaces only, and the slightly darker `#5A677B` on the page background. Verify with a contrast checker at token sign-off (§6.3). | No |
| CC-15 | Gap | §2 | The route table has no `/` entry. `/login` doubles as the OAuth return URL. | `/` redirects to `/overview`. `/login` handles sign-in, the OAuth callback status and failures (§8.1). | No |
| CC-16 | Inconsistency | §4 vs §6.2 | The query key `['dashboard-summary', region]` includes a region, but `GET /v1/dashboard/summary` has no region parameter. | Keep the key for forward compatibility. Send `region` only after the backend adds it. | Yes, OCI-05 |
| CC-17 | Gap | §3.4, §3.7 | The UI cannot know whether the caller may suppress, approve or reject. The Spec forbids sending `isAdmin` from the browser. | Show actions to authenticated users, handle `403` with a clear message, and consume server-computed `allowedActions` once provided. | Yes, OCI-14 |
| CC-18 | Tension | §12 vs §6.8 | "No page calls `fetch()` directly" and "all calls go through `apiClient.ts`", yet the presigned S3 `PUT` must not carry the bearer token (it would break the signature) and the upload needs progress. | Add `api/uploadClient.ts` inside the api layer (XMLHttpRequest for progress and abort). It is the only other network code, still isolated in `api/`. The S3 bucket needs CORS for `PUT`. | Yes, OCI-16 |
| CC-19 | Interpretation | §1 | "Region selector/display" with one Region in the MVP. | Read-only Region display. The component is built so a selector can be enabled by a flag later. | No |
| CC-20 | Ambiguity | §3.1 | "Open findings" uses "backend-defined open states". Severity metric cards link to Findings with the severity preselected, but the findings list needs to know which statuses to include. | The link sends `severity=<X>` plus the open states returned by the backend. Until the backend supplies them, the link sends `status=OPEN`. | Yes, OCI-06 |
| CC-21 | Ambiguity | §3.7 | "Optional required reason" for the approval dialog. | Reason field is always shown. It is required (min. 3 characters) for **Reject** and optional for **Approve**. The server's `400 VALIDATION_ERROR` always wins and is mapped to the field. | No |
| CC-22 | Gap | §17, §6 | The Spec requires stable error codes and a 429 retry hint but defines only `VALIDATION_ERROR` and `STATE_CONFLICT`. API Gateway's own 401/403/429 responses are not in the error envelope, and `Retry-After` is hidden from browsers unless CORS exposes it. | `apiClient` tolerates non-envelope bodies and derives the error code from the HTTP status. Proposed code registry in OCI-15. | Yes |
| CC-23 | Interpretation | §6.2 | `findingTrend[].date` is a date such as `2026-10-09`, not a timestamp. Converting it to local time could shift it by a day. | Display buckets exactly as returned, labelled "UTC days". No timezone conversion. | Yes, OCI-20 |
| CC-24 | Tension | §1 vs product brief | The Spec's visual recommendations (white cards, 10 to 14 px radius, soft shadow, deep-blue accent) are the standard "SaaS card" look. The product brief asks for an identity that does not look generated. | Keep every numeric and structural constraint. Create identity through type, shape language, the graph, microcopy and layout details (§6.2). | No |
| CC-25 | Ambiguity | §1 | "Global connection banner" could mean an always-visible strip or a status label. | A status pill is always visible in the top bar (clickable, opens detail). A full-width banner appears below the top bar only when the state is `DEGRADED` or `DISCONNECTED`. A permanent green banner would be noise and would encourage false confidence. | No |
| CC-26 | Gap | §3.5, §6.8 | The upload flow needs source-type codes beyond `ADR`, allowed file types, a size limit, a place for "rationale", and the no-secrets confirmation. Only `name`, `objectKeys` and `sourceType` are in the ingest request. | Assumed codes and limits in OCI-09 and OCI-16. The consent checkbox is client-side only. Rationale is hidden until a field exists. | Yes |
| CC-27 | Ambiguity | §3.2, §6.6 | `state` is defined for the DIFF view. Its meaning in INTENDED and LIVE views is not stated. | In INTENDED and LIVE views, nodes render with neutral styling except `UNKNOWN`. The full state language applies in DIFF only. | Yes, OCI-08 |
| CC-28 | Gap | §3.6, §3.8 | Drift `processingStatus` values and the audit-event row shape are not defined. Remediation statuses other than `PENDING_APPROVAL` are not defined. | Unknown strings render humanised. Proposed shapes in OCI-10, OCI-12, OCI-13. | Yes |

---

## 3. Frontend invariants

These rules are never traded away for schedule or polish. Each comes from the Spec. Reviewers check them in every pull request (§12.5).

| ID | Invariant | Source |
|---|---|---|
| INV-01 | No page, component or hook calls `fetch`, `XMLHttpRequest` or any HTTP library. Only `src/api/` does, and ESLint enforces it. | §12, §16.2 |
| INV-02 | The frontend never invents successful data. If an API call fails, the UI shows an error or partial state, never a plausible value. Mock data exists only in development, behind `VITE_USE_MOCKS`, with a visible banner. | §16.2 |
| INV-03 | "Connected" appears only when `/v1/system/status` confirms the backend can read the configured AWS sources. API reachability alone is never shown as healthy. | §1 |
| INV-04 | The UI never shows `100%` or "compliant" without a successful evaluation. With none, it shows `—` and `Not evaluated yet`. | §3.1, §17 |
| INV-05 | Severity is never expressed by colour alone. Every severity mark has a shape and a text label. | §1, §4 |
| INV-06 | No diff, conformance, severity-derivation or path logic in React. The frontend renders `MATCHED`, `ADDED`, `MISSING`, `CHANGED`, `UNKNOWN` exactly as received. | §3.2, §12 |
| INV-07 | An edge is drawn only if the backend returned it. No edges or flows are guessed from names. `UNKNOWN` is never painted as a confirmed violation. | §3.2, §6.6 |
| INV-08 | A before-state is never fabricated. Drift events and evidence show only the fields the source provided. | §3.6 |
| INV-09 | No secret reaches the browser or the logs: no AWS keys, no Bedrock keys, no Step Functions task tokens, no raw JWTs, no presigned URLs, no uploaded file contents. `VITE_` variables hold only public configuration. | §5, §10 |
| INV-10 | Tokens are handled by one strategy (Amplify Auth with Cognito managed login). Nothing else reads, stores or decodes them. | §0 |
| INV-11 | A success toast appears only after the backend responds successfully. Durable status on the page is the source of truth. | §4 |
| INV-12 | Mutating buttons are disabled while a request is pending, and double submission is prevented. Stale or duplicate decisions surface the server's `409` as a conflict message. | §3.7, §17 |
| INV-13 | Authorization is decided by the server. The browser never sends or trusts an `isAdmin`-style flag. | §3.7 |
| INV-14 | A button that advertises an action exists only when the endpoint and behaviour exist. Otherwise it is hidden or labelled `Not enabled`. | §16.7 |
| INV-15 | Remediation is dry-run or approval-gated, and always labelled as such. A dry-run result is never worded as a real fix. There is no client-side switch for automatic remediation. | §0, §3.7, §3.9 |
| INV-16 | Bedrock output is labelled `AI-assisted explanation`, shown with its cited evidence and an advisory disclaimer. It is never the authority for an AWS fact. | §0, §3.4 |
| INV-17 | Audit entries are created by the backend only. The client has no way to create one. | §3.8 |
| INV-18 | Timestamps are ISO 8601 UTC from the API, shown in local time, with the timezone explicit in detailed evidence. | §4 |
| INV-19 | Lists are paginated with the opaque cursor from the API. The client never assumes the first page is complete and never fetches all records. | §3.3 |
| INV-20 | The graph renders only the current, server-limited result set, shows the resource count, and warns when `truncated` is true. A node click never triggers a full-account fetch. | §3.2 |
| INV-21 | Users are never asked for AWS credentials. Upload warns against secrets and file contents are never rendered into logs. | §3.5, §3.9 |
| INV-22 | A breaking contract change updates types, schemas, fixtures and backend tests in the same pull request. | §16.1 |

---

## 4. Technology stack

### 4.1 Required by the Spec

| Concern | Choice | Notes |
|---|---|---|
| Framework | React + Vite + TypeScript (`strict: true`) | [SPEC §0] |
| Styling | Tailwind CSS | [SPEC §0]. Tokens are defined once in `styles/index.css` (§6.3). With Tailwind v4 this is the CSS-first `@theme` block. If the team pins v3, the same tokens move to `tailwind.config`. |
| Components | shadcn/ui (Radix primitives) | [SPEC §0]. Primitives are copied into `components/ui/` and restyled to this PRD's tokens, so they do not ship with the library's default look. |
| Icons | Lucide | [SPEC §0]. Stroke 1.5 px. Custom SVG only for the logomark, severity shapes and graph silhouettes (§6.6). |
| Routing | React Router, data router (`createBrowserRouter`) | [SPEC §0] |
| Server state | TanStack Query | [SPEC §0, §4] |
| Graph | React Flow (`@xyflow/react`) | [SPEC §0] |
| Charts | Recharts | [SPEC §0] |
| Authentication | Amazon Cognito User Pool | [SPEC §0] |

### 4.2 Decisions the Spec leaves open

| Concern | Choice | Reason |
|---|---|---|
| Auth library | **Amplify Auth** (`aws-amplify`) with Cognito managed login (Authorization Code + PKCE, public app client, no client secret) [DESIGN] | The Spec says to pick one and not mix token strategies [§0]. Amplify handles redirect, refresh and sign-out, and keeps the token code out of the app. Imported **only** in `auth/authClient.ts`. Confirm with backend, OCI-01 and OCI-02. |
| Runtime contract validation | `zod` [DESIGN] | Turns the shared contract into code. Drift between frontend and backend is caught at the boundary with a precise error rather than as a blank screen (§9.6). |
| Graph layout | `@dagrejs/dagre` [DESIGN] | React Flow does not lay out graphs. Dagre is small and deterministic. Layout is presentation only and is not diff logic. |
| Class utilities | `clsx`, `tailwind-merge`, `class-variance-authority` | shadcn/ui standard |
| Fonts | `@fontsource` packages, self-hosted (§6.4) | No third-party font CDN: faster, private, and compatible with a strict CSP (§13.4) |
| Dev mocks | MSW (Mock Service Worker) [DESIGN] | Mocks at the network edge, so `apiClient` runs the same code in mock and live mode (§5.6) |
| Tests | Vitest, Testing Library, Playwright, `axe-core` | §12 |
| Lint and boundaries | ESLint, `eslint-plugin-boundaries` (or `import/no-restricted-paths`), Prettier | Enforces the separation of concerns in §5.2 |
| Dates | Native `Intl.DateTimeFormat` and `Intl.RelativeTimeFormat` | No date library |

### 4.3 Deliberately not used

Redux or Zustand (server state lives in TanStack Query, URL state in the router), axios, moment/dayjs, CSS-in-JS, icon fonts, external font CDNs, UI kits that bring their own theme (MUI, Ant Design), and any AWS SDK package other than the Cognito auth library.

### 4.4 Versions

Use the current stable major of each package when the repository is created, and pin them in the lockfile. Verify every package name at install time. In particular check that the Fontsource packages named in §6.4 exist, and use the listed fallbacks if one does not.

---

## 5. Architecture: separation of concerns

### 5.1 Layers

```
                    app/            composition root: providers, router, bootstrap
                     │
                     ▼
                  features/         one folder per route: page container + URL state
                  │       │
         ┌────────┘       └─────────┐
         ▼                          ▼
      hooks/                   components/           presentational only
   (TanStack Query                 │
    bindings)                      │
         │                         │
         ▼                         ▼
       api/  ──▶  auth/        utils/   types/       pure, no I/O
         │
         ▼
      config/
```

The arrows are the **only** allowed import directions. Anything not drawn is forbidden.

### 5.2 Layer responsibilities and rules

| Layer | Owns | May import | Must not |
|---|---|---|---|
| `types/` | Domain types independent of React and transport | nothing | contain runtime code that touches the network or DOM |
| `config/` | Validated environment (`env.ts`), feature flags (`capabilities.ts`), constants (page sizes, poll intervals, upload limits) | `types/` | be read by raw `import.meta.env` anywhere else |
| `utils/` | Pure functions: dates, severity ordering, labels, resource-type categories, graph layout transform, redaction, URL helpers | `types/`, `config/` | import React, `api/`, or perform I/O |
| `auth/` | `authClient.ts` (the only file importing `aws-amplify`), `AuthProvider`, `ProtectedRoute` | `config/`, `types/` | be imported by `components/` |
| `api/` | `apiClient`, `endpoints`, `schemas` (zod), `queryKeys`, `errors`, `uploadClient`, dev-only `mocks/` | `auth/`, `config/`, `types/`, `utils/` | import React or any UI code |
| `hooks/` | TanStack Query bindings: one hook per endpoint or mutation, cache policy, polling, invalidation | `api/`, `types/`, `utils/`, `config/` | render UI or read the router |
| `components/` | Presentational components: props in, events out | `utils/`, `types/`, other `components/` | fetch, use query hooks, read the router, or know about endpoints |
| `features/` | Route-level containers: read URL state, call hooks, map results to component props, choose which state to show | `hooks/`, `components/`, `utils/`, `types/`, `config/` | import another feature or call `api/` directly |
| `app/` | Providers, route table, bootstrap | everything | contain page logic |

Two clarifications keep this honest:

- **Connected shell pieces.** The Spec lists `AppShell`, `Sidebar`, `TopBar` and `ConnectionStatus` under `components/layout/`. They stay there as presentational components (state in via props). Their data-bound wrappers live in `features/shell/` (§5.4).
- **Shared code between features.** If two features need the same thing, it moves down into `components/`, `hooks/` or `utils/`. Features never import each other.

### 5.3 Enforcement

- ESLint `no-restricted-globals` and `no-restricted-imports` ban `fetch`, `XMLHttpRequest`, `axios` and `aws-amplify` outside the permitted folders (INV-01, INV-10).
- `eslint-plugin-boundaries` encodes the import matrix above. A violation fails CI.
- A build check fails the production build if `VITE_USE_MOCKS=true` (INV-02), and a post-build grep fails if mock fixtures or MSW appear in `dist/`.
- A post-build scan fails if `dist/` contains strings that look like AWS access keys or private keys (INV-09).

### 5.4 Folder structure

Based on Spec §12. Entries marked `+` are additions explained in §5.5. Nothing from the Spec's tree is removed or renamed.

```text
cloud-intent-guardian-frontend/
  src/
    app/
      App.tsx
      router.tsx                  # route table from Spec §2, lazy route boundaries
      providers.tsx               # QueryClient, Auth, Capabilities, Toasts, ErrorBoundary
      bootstrap.ts            +   # env check -> Amplify config -> (dev) MSW -> render
    config/                   +
      env.ts                      # zod-validated import.meta.env; the single read point
      capabilities.ts             # which backend capabilities are switched on
      constants.ts                # page sizes, poll intervals, upload limits
    auth/
      AuthProvider.tsx
      ProtectedRoute.tsx
      authClient.ts               # the only importer of aws-amplify
    api/
      apiClient.ts
      apiTypes.ts                 # types inferred from schemas.ts; names match Spec §13
      schemas.ts              +   # zod schemas: the runtime contract
      endpoints.ts
      queryKeys.ts            +   # key factory (Spec §4 keys plus additions)
      errors.ts
      uploadClient.ts         +   # presigned PUT: no bearer, progress, abort
      mocks/                  +   # dev-only: MSW handlers, scenarios, fixtures/*.json
    components/
      ui/                     +   # shadcn primitives restyled to tokens
      layout/
        AppShell.tsx
        Sidebar.tsx
        TopBar.tsx
        ConnectionStatus.tsx
        ConnectionBanner.tsx  +
        AccountChip.tsx       +
        NotificationsMenu.tsx +
        UserMenu.tsx          +
        SystemStatusDrawer.tsx +
        MockModeBanner.tsx    +
      common/
        PageHeader.tsx
        MetricCard.tsx
        SeverityBadge.tsx
        StatusBadge.tsx
        EmptyState.tsx
        ErrorState.tsx
        LoadingSkeleton.tsx
        ConfirmDialog.tsx
        CursorPagination.tsx
        StateBoundary.tsx     +   # picks loading / empty / error / partial / content
        DataTable.tsx         +
        TimeStamp.tsx         +
        ResourceRef.tsx       +
        CopyableId.tsx        +
        KeyValueList.tsx      +
        FilterBar.tsx         +
        JobProgress.tsx       +
        JobDrawer.tsx         +
        SourceStatusRow.tsx   +
        NotEnabled.tsx        +   # standard "Not enabled" label for INV-14
      charts/                 +
        FindingsTrendChart.tsx
        SeverityChart.tsx
        ConformanceReadout.tsx
      findings/
        FindingsTable.tsx
        FindingFilters.tsx
        EvidencePanel.tsx
        ViolationPath.tsx
        ExplanationPanel.tsx  +
        ExpectedObserved.tsx  +
        LifecycleTimeline.tsx +
      architecture/
        ArchitectureGraph.tsx
        ArchitectureNode.tsx
        ArchitectureEdge.tsx
        GraphLegend.tsx
        ResourceDetailsDrawer.tsx
        GraphToolbar.tsx      +
        GraphFilters.tsx      +
        GraphTitleBlock.tsx   +
        ResourceList.tsx      +   # keyboard/screen-reader alternative to the canvas
      intents/
        UploadIntentDialog.tsx
        ConstraintCard.tsx
        IntentVersionHistory.tsx
        IntentsTable.tsx      +
        ConstraintDiff.tsx    +
        ApproveVersionDialog.tsx +
      drift/                  +
        DriftEventsTable.tsx
        DriftEventDrawer.tsx
      remediation/
        RemediationTable.tsx
        ApprovalDialog.tsx
        RemediationDetail.tsx +
      audit/                  +
        AuditTable.tsx
        AuditEventDrawer.tsx
    features/
      overview/
      architecture/
      findings/                   # list + detail
      intents/                    # list + detail + upload
      drift-events/
      remediation/
      audit-trail/
      settings/
      login/                  +
      shell/                  +   # data-bound wrappers for the layout components
      not-found/              +
      # each folder: <Name>Page.tsx, containers, use<Name>UrlState.ts, index.ts
    hooks/
      useDashboardSummary.ts
      useFindings.ts
      useArchitecture.ts
      useJobs.ts
      useFinding.ts           +
      useFindingActions.ts    +   # acknowledge / suppress / reopen / request remediation
      useIntents.ts           +
      useIntent.ts            +
      useIntentUpload.ts      +
      useDriftEvents.ts       +
      useRemediations.ts      +
      useRemediationDecision.ts +
      useAuditEvents.ts       +
      useSystemStatus.ts      +
      useApiHealth.ts         +
      useUrlState.ts          +
    types/
      domain.ts
    utils/
      dates.ts
      severity.ts
      graph.ts                    # layout transform only; no diff logic
      labels.ts               +   # code -> display text maps
      resourceTypes.ts        +   # AWS resource type -> category, short name
      format.ts               +
      redact.ts               +
      url.ts                  +   # safe link validation
    styles/
      index.css                   # tokens and base
      fonts.css               +
    main.tsx
  e2e/                        +   # Playwright journeys
  public/
  docs/                       +
    CONTRACT.md                   # how types, schemas, fixtures and backend tests stay in sync
  .env.example
  package.json
  README.md
```

### 5.5 Why each addition exists

| Addition | Reason |
|---|---|
| `config/` | One validated read point for environment and feature flags. Without it `import.meta.env` leaks everywhere. |
| `api/schemas.ts`, `queryKeys.ts` | Runtime contract and one place for the Spec §4 cache keys (so invalidation cannot drift). |
| `api/uploadClient.ts` | Resolves CC-18 without breaking INV-01. |
| `api/mocks/` | Implements the Spec's "explicit mock mode only in development" [§16.2]. |
| `components/ui/` | shadcn primitives, restyled. |
| `components/layout/*` extras | Needed by the top-bar and status requirements in Spec §1. |
| `components/common/*` extras | Remove duplication across the eight pages and enforce one pattern for loading, empty, error and partial states (Spec §4). |
| `charts/`, `drift/`, `audit/` | Spec pages 3.1, 3.6 and 3.8 have no component folders in §12. |
| `features/login`, `shell`, `not-found` | The Spec requires `/login` and `*` routes and a shell with live data. |
| `hooks/*` extras | §12 lists four hooks. Every endpoint needs one. |
| `utils/*` extras | Keeps label maps, safe URL checks and redaction out of components. |
| `e2e/`, `docs/CONTRACT.md` | Tests per Spec §17 and the contract process per Spec §16.1. |

### 5.6 State management policy

| Kind of state | Where it lives | Examples |
|---|---|---|
| Server state | TanStack Query | Summary, findings, graph, intents, jobs |
| Shareable UI state | URL search parameters | Filters, sort, cursor, selected node/edge, tab, open drawer, `?job=`, `?version=` |
| Ephemeral UI state | `useState` / `useReducer` in the component or feature | Dialog open, form fields, hover |
| Cross-cutting client state | React context | Auth session, validated env, capabilities |
| Persisted client state | `sessionStorage` or `localStorage`, non-sensitive only | Graph node positions per intent version, preferred page size, `returnTo` path, ids of jobs the user started |

Never persisted: tokens (owned by Amplify), presigned URLs, uploaded content, evidence payloads.

### 5.7 One request, end to end (the pattern every page follows)

1. The URL carries the filters (`/findings?severity=HIGH&status=OPEN`).
2. `features/findings/useFindingsUrlState` parses and validates them. Unknown values are ignored.
3. `hooks/useFindings(filters)` calls `api/endpoints.getFindings`, keyed `['findings', filters]`.
4. `apiClient` attaches the bearer token, sends the request, and parses the body with the zod schema.
5. A typed `ApiError` (status, code, message, requestId) is thrown on failure.
6. The feature container maps the hook result to props and passes it through `StateBoundary` (loading, empty, error, partial, content).
7. Presentational components render. They never see a query object.
8. A mutation invalidates only the keys listed in §9.3.

### 5.8 Boot sequence (`app/bootstrap.ts`)

1. Parse and validate the environment with zod. On failure render a dependency-free `ConfigErrorScreen` that lists the **names** of missing or invalid variables, never their values.
2. Configure Amplify Auth (skipped in mock mode).
3. In development with `VITE_USE_MOCKS=true` only: dynamically import and start MSW. The import sits behind `import.meta.env.DEV`, so production builds cannot contain it.
4. Render `<App />` inside the providers.

---

## 6. Design system

### 6.1 Concept: the plan check

The product compares an **as-designed** architecture with an **as-built** one. That is the job of a plan checker in architecture and engineering: lay the approved drawing over the survey and mark every difference. The interface borrows the quiet conventions of that world instead of the usual dashboard kit:

- **A drawing sheet.** Fine 1 px rules, flat paper-like surfaces, and a **title block** on the architecture canvas that states what is being shown (intent version, generation time, resource count, legend).
- **Survey symbols.** Severity and resource categories are drawn as distinct shapes, the way point symbols are on a survey. Shape carries meaning, so colour never has to.
- **Revision marks.** A changed resource carries a small revision triangle, the drafting convention for "this differs from the approved issue".
- **Plain engineering lettering.** An engineering-grade, highly legible type family, with a semi-condensed display face for titles and figures.

**Restraint rule.** The boldness is spent in one place: the Architecture Explorer. Every other screen is calm, dense and exact, because the user is investigating.

### 6.2 What the Spec fixes and what it leaves free [CC-24]

| Fixed by the Spec (kept exactly) | Free (where identity is created) |
|---|---|
| Light theme, one theme globally, no mixing of dark panels [§1] | Typefaces |
| Neutrals: page `#F6F8FB`, card white, text `#172033`, secondary `#68758A`, border `#E2E8F0` [§1, "suggested"] (secondary text adjusted on the page background, CC-14) | Exact hue of the deep-blue accent |
| Deep-blue primary accent; green connected; amber warning; red critical [§1] | Severity palette beyond critical red |
| Sidebar 240 to 256 px fixed, top bar 64 to 72 px, content padding 24 px, max width about 1600 px [§1] | Navigation active-state treatment |
| Cards: restrained borders, 10 to 14 px radius, minimal shadow, 16 to 24 px padding [§1] | Shape language: severity symbols, node silhouettes, revision marks |
| One spacing scale, one type scale; page heading 24 to 28 px, section heading 16 to 18 px, table body 13 to 14 px [§1] | Chart styling, table styling, forms, empty and error layouts |
| Severity never colour alone [§1] | Motion personality (within "short and subtle") |
| Short, subtle animation; do not animate every metric, node or card [§1] | Copy and voice |
| Sidebar order, route names, page copy quoted in §8 [§1, §2, §3] | Logomark |

### 6.3 Tokens

All tokens are defined once in `styles/index.css`. Components use token names, never raw hex.

**Colour**

| Token | Hex | Role |
|---|---|---|
| `film` | `#F6F8FB` | Page background [SPEC] |
| `sheet` | `#FFFFFF` | Card and surface [SPEC] |
| `ink` | `#172033` | Primary text [SPEC] |
| `graphite` | `#5A677B` | Secondary text on `film` (about 5.4:1) [CC-14] |
| `pencil` | `#68758A` | Secondary text on `sheet` only (about 4.7:1) [SPEC] |
| `rule` | `#E2E8F0` | Borders and dividers [SPEC] |
| `rule-strong` | `#C5CFDC` | Input borders, matched-node outline |
| `prussian` / `-700` / `-50` | `#183B87` / `#12306D` / `#E8EEF9` | Primary accent, pressed, tint [SPEC: deep blue] |
| `survey` / `-50` | `#1B7A4B` / `#E6F4EC` | Good and connected [SPEC] |
| `sev-critical` / `-50` | `#B42318` / `#FDECEA` | Critical [SPEC: red] |
| `sev-high` / `-50` | `#C2410C` / `#FFEDE0` | High |
| `sev-medium` / `-50` | `#8A5A00` / `#FFF3D6` | Medium and warning text. Graph stroke for amber states: `#D98E04`. [SPEC: amber] |
| `sev-low` / `-50` | `#1F6C8C` / `#E3F0F6` | Low |
| `sev-info` / `-50` | `#5A677B` / `#EDF1F6` | Info |

Text colours were chosen to reach at least 4.5:1 on their tint. Re-verify with a contrast checker at sign-off.

**Other tokens**

| Group | Values |
|---|---|
| Spacing (4 px base) | 4, 8, 12, 16, 24, 32, 48, 64. Card padding 16 (dense) or 24 (feature). Grid gap 16 or 24. [SPEC: 16 to 24] |
| Radius | Card 12, dialog 14, control 8, badge 6, canvas title block 4. Docked drawers have no radius on the docked edge. [SPEC: cards 10 to 14] |
| Elevation | **None on cards** (border only). Overlays (popover, dialog, floating drawer) use an ink-tinted shadow: `0 12px 32px -8px rgb(23 32 51 / 0.18)`. The docked details drawer is separated by a 1 px rule. [SPEC: minimal] |
| Focus | 2 px `prussian` ring with 2 px `sheet` offset, on every interactive element |
| Motion | 120 ms fade, 150 ms dialog, 180 ms drawer. Easing `cubic-bezier(0.2, 0, 0, 1)` |

**Layout**

| Element | Value |
|---|---|
| Sidebar | 248 px fixed [SPEC 240 to 256] |
| Top bar | 68 px [SPEC 64 to 72] |
| Content padding | 24 px [SPEC] |
| Max content width | 1600 px, centred [SPEC] |
| Breakpoints | `sm` 640, `md` 768, `lg` 1024, `xl` 1280, `2xl` 1600 |

### 6.4 Typography

| Role | Family | Notes |
|---|---|---|
| Interface and body | **Atkinson Hyperlegible Next** | Designed for character distinction (`I`, `l`, `1`, `O`, `0`), which matters when the reader compares resource IDs all day. Weights 400, 500, 600, 700. |
| Identifiers (ARNs, IDs, CIDRs, ports, rule IDs) | **Atkinson Hyperlegible Mono** | Used for literal identifiers only, never as a decorative label font |
| Titles and large figures | **Archivo** (variable, width axis around 85) | Semi-condensed engineering lettering. Weight 600. |

Packages: `@fontsource/atkinson-hyperlegible-next`, `@fontsource/atkinson-hyperlegible-mono`, `@fontsource-variable/archivo` (use its `wdth` axis file if present, otherwise static Archivo SemiCondensed). If any package is unavailable at install, use IBM Plex Sans and IBM Plex Mono in place of the Atkinson pair and keep Archivo. Fallback stack ends in `system-ui, sans-serif`, with `size-adjust` metrics tuned to avoid layout shift. Fonts are self-hosted, Latin subset, `font-display: swap`, and the two most used files are preloaded.

| Token | Size / line height | Face and weight | Use |
|---|---|---|---|
| `figure` | 36 / 40 | Archivo 600 | Metric numerals |
| `page-title` | 26 / 32 | Archivo 600 | Page heading [SPEC 24 to 28] |
| `section` | 17 / 24 | Interface 600 | Section and card headings [SPEC 16 to 18] |
| `body` | 14 / 22 | Interface 400 | Body text, form text |
| `table` | 13 / 20 | Interface 400 | Table body [SPEC 13 to 14] |
| `table-head` | 12 / 16 | Interface 600, sentence case | Column headings (no all-caps) |
| `caption` | 12 / 16 | Interface 400 | Helper text, timestamps |
| `id` | 12.5 / 18 | Mono 400 | Identifiers |

Rules: tabular figures wherever the family provides them; body line length under 80 characters; sentence case everywhere; no letter-spaced all-caps labels; no single accented word in a heading; minimum text size 12 px.

### 6.5 Meaning systems

#### Severity (INV-05)

Each level has a **shape**, a **colour** and a **text label**. The shapes are inline SVG drawn on a 12 px grid.

| Level | Label | Shape | Colour |
|---|---|---|---|
| `CRITICAL` | Critical | Filled octagon | `sev-critical` |
| `HIGH` | High | Filled triangle | `sev-high` |
| `MEDIUM` | Medium | Filled diamond | `sev-medium` |
| `LOW` | Low | Open circle (ring) | `sev-low` |
| `INFO` | Info | Open square | `sev-info` |

`SeverityBadge` always renders shape plus label. A compact variant (shape only) exists for dense places such as graph legends and chart keys, and always carries an accessible name and a tooltip. Order for sorting and display: Critical, High, Medium, Low, Info (`utils/severity.ts`).

#### Finding status

`OPEN`, `ACKNOWLEDGED`, `IN_PROGRESS`, `RESOLVED`, `SUPPRESSED` render as text badges (Open, Acknowledged, In progress, Resolved, Suppressed) with a distinct leading mark, and never share severity shapes. Resolved uses `survey`, Suppressed uses `graphite`, the others use `prussian` tints.

#### Diff state (graph, edges, lists)

The frontend renders the backend's state exactly (INV-06).

| State | Text shown | Node treatment | Edge treatment |
|---|---|---|---|
| `MATCHED` | none on canvas (`Matched` in the drawer) | 1 px `rule-strong` outline, white fill | Solid 1.5 px, neutral |
| `ADDED` (live only) | `Unmatched` | 2 px amber outline | Solid, amber |
| `MISSING` (intended only) | `Missing` | 1.5 px **dashed** `ink` outline, white fill | Dashed, `ink` |
| `CHANGED` | `Changed` plus finding count | 2 px outline in the colour of the highest finding severity, plus the **revision triangle** | Solid, same severity colour |
| `UNKNOWN` | `Unknown` | 1.5 px dotted `graphite` outline, light diagonal hatch fill | Dotted, `graphite` |

"Highest finding severity" comes from the backend (OCI-08). Until it is provided, `CHANGED` uses the `sev-high` outline, and the label states `Changed` rather than a severity.

`UNKNOWN` is never red or amber, and no text on the canvas calls an unmatched node insecure. The label states the comparison result only [SPEC §3.2].

### 6.6 Graph visual language

**Nodes.** Each node is a custom React Flow node whose frame is an SVG path chosen by resource category. Using SVG paths means dashed, dotted and hatched outlines work exactly, at any zoom.

| Category (frontend presentation map only) | Silhouette | Example types |
|---|---|---|
| Compute | Chamfered rectangle (package outline) | `AWS::Lambda::Function`, `AWS::EC2::Instance` |
| Network and edge | Elongated hexagon | `AWS::EC2::VPC`, `AWS::EC2::Subnet`, `AWS::EC2::SecurityGroup`, `AWS::CloudFront::Distribution`, API gateways, load balancers |
| Data | Stacked plate (two parallel lower edges) | `AWS::RDS::DBInstance`, `AWS::S3::Bucket`, `AWS::DynamoDB::Table` |
| Identity and access | Pill | `AWS::IAM::Role`, `AWS::IAM::Policy` |
| Other or unrecognised | Plain square-cornered rectangle | Anything else. The raw type is shown, never a guessed one. |

The category map lives in `utils/resourceTypes.ts`. It is presentation only. An unrecognised type is never an error, and a new type needs no deploy to appear.

**Node anatomy** (216 × 60 px): category glyph (Lucide, 16 px) at left; short name (`label`, one line, ellipsis, full text in tooltip and drawer); short type under it (for example "Lambda function" from the type map, falling back to the raw type); a state label at the right when the state is not `MATCHED`; the revision triangle at the top right when `CHANGED`. ARNs never appear on the node.

**Selected node:** 2 px `prussian` ring with 3 px offset, independent of state outline, plus the open drawer. **Hover:** the node's edges and neighbours stay at full strength and the rest drop to 55 % opacity. **Focus:** same ring as selected, plus the standard focus ring.

**Edges:** right-angled routed lines with a small arrowhead showing direction. Each edge has a text label pill (`label` from the API, 12 px, ellipsis at 24 characters with a tooltip). An edge selected by the user is drawn 2.5 px with the `prussian` ring colour. Unknown `relationshipType` values render using their `label` unchanged.

**Canvas:** `film` background with a 24 px line grid at 4 % ink opacity. Zoom range 0.25 to 2. Pan by drag, zoom with the controls or ctrl/cmd + wheel. `onlyRenderVisibleElements` is on.

**Title block** (bottom-right overlay, collapsible): intent version, generated time (local, with UTC in the tooltip), `n resources shown`, a visible `Truncated` warning when `truncated` is true, the Region, and the **legend** with a sample of each state. It is the only place the legend lives, so the legend is always in view when the graph is.

**Layout stability:** node positions are computed once per dataset with dagre and cached by node id. Switching between `Intended`, `Live` and `Differences` keeps nodes that exist in both views in place. A user-dragged position is kept per intent version in `sessionStorage` until `Reset layout`.

### 6.7 Shell visuals

- **Logomark.** Two 20 px outlined squares, one solid and one dashed, offset by 4 px: the approved plan over the observed one. Wordmark "Cloud Intent Guardian" in Archivo 600, 16 px.
- **Sidebar.** `sheet` background, 1 px `rule` on the right. Items are 40 px tall, Lucide icon 18 px, label 14 px. Active item: `prussian` text, `prussian-50` fill, 2 px `prussian` inset rule on the left. Counts (open findings, pending approvals) appear as plain numerals only when loaded and above zero.
- **Sidebar footer.** `DEMO` or `LIVE` chip [SPEC], app version, and the AWS-connected indicator (a shape and a text label, never colour alone).
- **Top bar.** `sheet` background, 1 px `rule` below. Content details in §7.2.

### 6.8 Component visual rules

| Component | Rule |
|---|---|
| Cards | `sheet`, 1 px `rule`, 12 px radius, no shadow, 16 or 24 px padding. Not every block is a card: lists and tables sit on the page with rules between rows. |
| `MetricCard` | Label (`caption`, `graphite` or `pencil` by surface), figure (`figure`), one line of supporting text. No delta chips, sparklines or icons in a coloured circle. The Spec provides no trend data per metric, so none is shown. |
| `ConformanceReadout` | See §8.2. A row of ticks that is literally the numerator and denominator. |
| Tables | Row height 44 px (36 px dense). 1 px `rule` between rows, no zebra stripes. Sticky header with `table-head`. Hover state is a `film` tint. The whole row is a link, with the title as the semantic anchor. Numerals tabular. |
| Buttons | Primary: `prussian` fill, white text, 36 px high (40 px in dialogs), radius 8. Secondary: `sheet`, 1 px `rule-strong`. Danger-secondary (for `Reject`): outlined with `sev-critical` text. Ghost for icon buttons. While submitting the label stays and a spinner is added to the left, so the width does not jump. No trailing arrows. |
| Inputs | 36 px high, radius 8, 1 px `rule-strong`, label above (13 px, 600), helper text under (12 px), error text with an icon and a message. |
| Drawers | Docked (graph details) or overlay (everything else). 180 ms slide. Focus moves in on open and returns to the trigger on close. `Esc` closes. |
| Dialogs | 14 px radius, 150 ms fade and 4 px rise. Focus trapped, `Esc` closes unless a submission is pending. |
| Skeletons | Shaped like the final layout (same row heights and column widths). A slow 1.4 s opacity pulse, static when reduced motion is requested. |
| Empty states | Left-aligned in the content area. One heading (what is missing), one sentence (why), one valid next action. No illustrations. |
| Error states | Heading says what failed, body says what to do, `Retry` button, and the request ID in mono `caption`, with a copy control. No apology, no "Oops". |
| Charts | Flat fills at 18 % opacity with a 1.5 px stroke in the series colour. Only horizontal hairline gridlines. Axis text 12 px `graphite`. No gradients, no 3D, no donut. Tooltips list severity as shape plus label plus count. Each chart has a visually hidden data table. |
| Toasts | Top right, below the top bar, 4 s, `aria-live="polite"`. Success toasts appear only after a successful response (INV-11). Errors that belong to a dialog are shown in the dialog, not as a toast. |

### 6.9 Motion inventory

Only these motions exist. Anything else needs a design review.

| Motion | Spec |
|---|---|
| Route content | 120 ms opacity cross-fade. No slide. |
| Drawer | 180 ms slide from the right edge. |
| Dialog | 150 ms fade plus 4 px rise. |
| Toast | 150 ms fade. |
| Skeleton | 1.4 s opacity pulse. |
| **One orchestrated moment** | When the Architecture Explorer first renders a `DIFF` dataset, the outlines of `CHANGED` and `ADDED` nodes draw in over 400 ms (stroke-dashoffset), once per dataset load. Nothing else on that screen moves on load. |

No count-up numbers, no hover lift, no staggered entrances, no parallax, no animated backgrounds. With `prefers-reduced-motion: reduce`, every motion above is removed except an instant state change.

### 6.10 Voice and copy rules

- Sentence case. Plain verbs. Active voice. Name things the way the user thinks of them.
- A button states exactly what happens (`Run evaluation`, `Acknowledge`, `Approve`). The toast that follows uses the same verb (`Evaluation queued`, `Finding acknowledged`). The vocabulary is fixed in Appendix A.
- Errors say what failed, why if known, and the next step. They do not apologise or joke.
- Empty states are directions: what is missing and the next action.
- Page copy that the Spec quotes is used word for word (§8).
- Fixture data uses fictional but realistic AWS names. No "Acme", no lorem ipsum.

### 6.11 Blocklist (checked at design review and in pull requests)

A pull request that introduces any of these is rejected.

| Not allowed | Why |
|---|---|
| Gradients (backgrounds, text, buttons, chart fills), glass or blur effects, neumorphism | Generic decoration |
| Emoji or sparkle iconography, "magic" wording for Bedrock output | The AI explanation is labelled plainly (INV-16) |
| Identical shadowed cards in a uniform grid; shadows on cards | Spec asks for minimal shadow; hierarchy comes from layout |
| Hover lift or scale on cards, fade-up on every section, count-up figures | Spec: do not animate every metric, node or card |
| Tracked-out all-caps eyebrow labels above headings | Template chrome. The Spec's `DEMO`/`LIVE` chip is the only exception. |
| Meta strings joined with middle dots, spaced em-dash labels, trailing `→` on buttons or links | Template chrome |
| Centred hero-style empty states or stock illustrations | Directions, not mood |
| "Oops", "Something went wrong", "Welcome back!", exclamation marks | Voice rules |
| Purple-to-blue gradient palettes, neon-on-black palettes, cream and terracotta palettes | The three most common generated looks |
| Inter, Roboto or Arial as the visible face | Default, not chosen |
| Mixed icon families or stroke widths | Consistency |

### 6.12 Design review log

The design plan was reviewed against the brief before being committed to this PRD. First instincts that read as defaults were replaced.

| First instinct | Why it was rejected | Chosen instead |
|---|---|---|
| Inter or Geist, white cards, blue gradient accent | The default dashboard kit | Atkinson Hyperlegible plus Archivo; flat colour; no gradients |
| Five identical metric cards, each with a big number and a delta chip | Template; no per-metric trend data exists in the contract | Plain figures, and a conformance readout that draws numerator and denominator literally |
| Dark SOC theme with a neon accent | A cliché, and the Spec asks for one theme chosen deliberately | Light drafting-sheet theme using the Spec's neutrals |
| Severity as coloured pills | Violates INV-05 and looks generic | Shape plus label plus colour system (§6.5) |
| Generic rounded-rectangle graph nodes with icons in a coloured circle | The Spec asks for nodes by category; this reads as a stock diagram | SVG silhouettes per category, revision triangle, title block (§6.6) |
| Fade-up entrances and hover lift | Reads as generated | One orchestrated moment on the graph, nothing else (§6.9) |
| Donut chart for severity | Hard to read exact counts; generic | Horizontal bars with shape, label and count |

---

## 7. Application shell and global behaviour

### 7.1 Routes and guards [SPEC §2]

Route names are stable. All routes except `/login` and `*` require a session.

| Route | Page | Auth | First live in |
|---|---|---|---|
| `/` | Redirects to `/overview` [CC-15] | n/a | M1 |
| `/login` | Sign-in and Cognito redirect status | Public | M2 |
| `/overview` | Operational overview | Required | M2 |
| `/architecture` | Intended / Live / Differences graph explorer | Required | M3 |
| `/findings` | Filterable findings list | Required | M2 |
| `/findings/:findingId` | Finding details and evidence | Required | M3 |
| `/intents` | Versioned intent documents and policies | Required | M4 |
| `/intents/:intentId` | Intent detail, constraints, versions | Required | M4 |
| `/drift-events` | Timeline of observed configuration changes | Required | M4 |
| `/remediation` | Remediation requests and approvals | Required | M5 |
| `/audit-trail` | Searchable action and evaluation history | Required | M5 |
| `/settings` | Account, data source and application settings | Required | M2 |
| `*` | Not-found page with link to Overview | Public | M1 |

Rules:

- Each route's page code is lazy-loaded (`React.lazy`). React Flow and Recharts must not be in the initial bundle.
- Direct navigation to a protected URL works after login. `ProtectedRoute` saves the requested path (path and query only, never tokens) as `returnTo` and restores it after sign-in. Only same-origin relative paths are accepted as `returnTo`, to prevent open redirects.
- A refresh on `/findings/abc` must work. The static host serves `index.html` for client routes (§13.3).
- Pages whose backend is not yet enabled (§10.4) still render, in a clear `Not enabled` state rather than a broken one.

### 7.2 Top bar [SPEC §1]

Left to right:

| Element | Behaviour |
|---|---|
| Breadcrumb or page title | Detail pages show `Findings / [finding title]`. Titles truncate with a tooltip. |
| Account chip | `AccountChip` shows account alias and account ID from `/v1/dashboard/summary` (`account`). If alias is null show the ID only. The ID is in the `id` mono face with a copy control. |
| Region | Read-only text from `region` [CC-19]. |
| Last successful sync | `Last synced 4 min ago` from `lastInventoryAt`, absolute local and UTC time in a tooltip. `Not synced yet` when null. |
| Refresh | Icon button labelled `Refresh`. Invalidates the current page's queries plus `['system-status']` and `['dashboard-summary']`. Shows a spinner while any of those is fetching. |
| Notifications | See §7.6. |
| User menu | Name and email (from the ID token claims, display only), `Sign out`. |

The connection pill sits between the sync time and the refresh button, as described next.

### 7.3 Connection status [SPEC §1, CC-25]

Source of truth: `GET /v1/system/status` (`['system-status']`), refetched every 30 s and on window focus.

| Situation | Pill | Banner under top bar |
|---|---|---|
| Status `CONNECTED` | `Connected` (check-shape mark) | None |
| Status `DEGRADED` | `Degraded` (triangle mark) | Yes: safe error summary, `View details` |
| Status `DISCONNECTED` | `Disconnected` (octagon mark) | Yes: summary and `Retry` |
| The status request itself fails (network, 5xx) | `Disconnected` with the detail "Could not reach the API" | Yes, with `Retry` |
| Status request still loading on first load | `Checking` (neutral) | None |
| Mock mode | `Mock data` (neutral) | Mock banner (§7.8) |

The pill is clickable and opens the **System status drawer** (`SystemStatusDrawer`):

- Overall state and the time it was generated.
- A row per data source (Config, CloudTrail, Bedrock, optional flow logs): status label (`Connected`, `Needs setup`, `Error`, `Not enabled`), last success time, message.
- Evaluator status, `lastInventoryAt`, `lastEvaluationAt`, `lastErrorAt`, and the safe error summary.
- A line `API reachable` from `GET /v1/health` (public). It is shown as a fact only and never contributes to the overall state (INV-03).
- `Retry check`.

The sidebar footer indicator shows the same state as a shape plus a short text.

### 7.4 Authentication flow [SPEC §5]

Library: Amplify Auth with Cognito managed login (Authorization Code + PKCE, public client). Only `auth/authClient.ts` imports it.

| Step | Behaviour |
|---|---|
| First visit, no session | `ProtectedRoute` navigates to `/login?returnTo=…`. |
| `/login` | Starts the managed-login redirect once. The Cognito callback URL is the app's own `/login` (and logout URL `/login`). Both localhost and the CloudFront URL are registered (OCI-02). |
| Callback | `/login` shows `Completing sign-in`, Amplify exchanges the code, then navigates to `returnTo` or `/overview`. |
| Token for API calls | `apiClient` asks `authClient.getAccessToken()` before every request. Amplify refreshes silently. |
| `401` from API | `apiClient` forces one token refresh and retries the request **once**. If it fails again, the session is cleared and the user lands on `/login` with the message `Your session expired. Sign in again to continue.` |
| Loop guard | The auto-redirect is skipped when `/login` has an `error` parameter, or when a sign-in attempt was made in the last 60 s. In those cases the page shows the failure and a `Sign in` button. |
| `403` | Not a sign-out. The user sees a permission message in place (§9.4). |
| Sign out | User menu `Sign out` calls Cognito sign-out and returns to `/login`. Query cache is cleared. |
| Multiple tabs | A sign-out in one tab is detected through the auth library's event hub and routes the other tabs to `/login`. |

There is no code path that stores, decodes for authorization, logs or displays a raw JWT (INV-09, INV-10).

### 7.5 Jobs: evaluation and ingestion [SPEC §3.1, §6.8, §6.9]

Long work never blocks the browser. `useJobs` provides `useJob(jobId)`, which polls `GET /v1/jobs/{jobId}` (§9.5).

- A started job's id goes into the URL (`?job=<jobId>`) and into `sessionStorage` (list of jobs the user started in this session), so a refresh does not lose it.
- The **Job drawer** (`JobDrawer`, opened by `?job=` on any page) shows: status, `progressStage`, `startedAt`, `completedAt`, `resultSummary`, and the safe `errorMessage` when failed. It never shows stack traces.
- On a terminal status the hook invalidates the keys in §9.3, and a toast reports the result: `Evaluation finished`, `Evaluation finished with partial results`, or `Evaluation failed`.
- `PARTIAL` is shown as success with a warning, and the warning text comes from `resultSummary`.

### 7.6 Notifications menu [CC-13]

There is no notification endpoint. The bell opens a menu built only from data the frontend already holds, labelled `Activity in this session`:

- Evaluations and uploads the user started, with their current or final status, each linking to the Job drawer.
- `Pending approvals` count (from `/v1/dashboard/summary`) linking to Remediation.
- A system degradation notice when status is not `CONNECTED`.

It shows an unread dot for terminal job results not yet opened. Empty text: `No activity yet in this session.` Server-sent notifications arrive with the later SNS phase and need a new contract.

### 7.7 Errors, toasts, boundaries

- A route-level `ErrorBoundary` catches render errors and shows an `ErrorState` with `Reload page`. A widget-level boundary around each chart, graph and drawer keeps one failure from taking down the page.
- Contract mismatches (zod parse failure) render the standard error state with the code `CONTRACT_MISMATCH` and the request ID (§9.6).
- Toasts follow INV-11. Dialog errors are shown in the dialog.

### 7.8 Mock mode [SPEC §16.2, §14 M1, M2]

Available only in development with `VITE_USE_MOCKS=true`.

- A fixed `MockModeBanner` above the top bar: `Mock data: this screen is not connected to AWS.`
- The connection pill reads `Mock data` and never `Connected`.
- A development-only scenario switcher (in the user menu) selects: `normal`, `empty account`, `not evaluated`, `partial source failure`, `api error`, `unauthenticated (401)`, `forbidden (403)`, `not found (404)`, `conflict (409)`, `rate limited (429)`, `slow`. These exist so every state in Spec §17 can be seen and tested without AWS.
- The production build refuses to start with the mock flag on (§5.3).

### 7.9 Responsive behaviour [SPEC §4]

| Width | Behaviour |
|---|---|
| 1280 and up | Full layout. Graph details drawer docked at 320 to 380 px. |
| 1024 to 1279 | Content full width. Graph details drawer overlays the canvas instead of docking. |
| 768 to 1023 | Sidebar becomes an off-canvas drawer opened from a top-bar menu button. Tables scroll horizontally inside their own container. |
| Below 768 | Review use is supported. Tables become stacked rows (title, severity, status, resource, time). The graph opens in `ResourceList` mode, with the canvas available on request. Dialogs and drawers become full-height sheets. |

The page body never scrolls sideways. Wide content scrolls in its own container.

### 7.10 Accessibility [SPEC §4]

Target WCAG 2.2 AA.

- Semantic landmarks (`header`, `nav`, `main`), one `h1` per page, a skip link to `main`, visible focus everywhere.
- Every icon-only button has an accessible name and a tooltip.
- Severity and diff state are always text plus shape (INV-05). Status changes are announced through an `aria-live` region.
- The graph canvas is not the only way in. `ResourceList` is a keyboard- and screen-reader-usable table of the same nodes and edges, with the same selection and the same details drawer. Search works in both.
- Dialogs trap focus and restore it. Drawers move focus in and return it.
- Each chart has a visually hidden data table and a text summary.
- `prefers-reduced-motion` is honoured (§6.9). Target size for touch is at least 24 px, and 40 px for primary controls.

---

## 8. Page specifications

Quoted strings are from the Spec and are used verbatim [SPEC]. Each page lists data dependencies, layout, interactions, required states, and acceptance criteria (AC). All pages use the `StateBoundary` pattern for loading, empty, error, partial and not-enabled states.

### 8.1 Login (`/login`) [P0, M2]

**Purpose:** sign in, show the redirect status, and recover from failure without looping.

| State | Content |
|---|---|
| Checking session | `Checking your session` with a skeleton of the sign-in panel |
| Redirecting | `Redirecting to sign-in` |
| Completing callback | `Completing sign-in` |
| Signed out (first visit or after sign-out) | `Sign in` button |
| Session expired | `Your session expired. Sign in again to continue.` plus `Sign in` |
| Sign-in failed | A short, sanitised reason from the callback `error` parameter if present, otherwise `Sign-in did not complete.` plus `Try again`. No automatic redirect. |
| API unreachable | `The API could not be reached.` shown when `GET /v1/health` fails, plus `Retry` |

**Acceptance**

- AC-LOG-01 An unauthenticated visit to `/findings/abc` ends on `/findings/abc` after login.
- AC-LOG-02 After a failed sign-in or an expired session, the page never redirects automatically more than once per minute (no loop).
- AC-LOG-03 `returnTo` accepts only same-origin relative paths.
- AC-LOG-04 No token appears in the URL after the callback completes, in console output, or in any storage the app wrote itself.

### 8.2 Overview (`/overview`) [P0, M2]

**Goal [SPEC]:** a truthful snapshot of the configured AWS environment and the most important risks.

**Data**

| Region of the page | Endpoint | Query key |
|---|---|---|
| Metrics, charts, source rows | `GET /v1/dashboard/summary` | `['dashboard-summary', region]` |
| System health extras (evaluator, latest error) | `GET /v1/system/status` | `['system-status']` |
| Recent findings | `GET /v1/findings?limit=8` (newest first, OCI-06; until then the page sorts the returned page by `lastSeenAt`) | `['findings', {limit: 8, recent: true}]` |
| Recent activity (optional, M5) | `GET /v1/audit-events?limit=8` | `['audit-events', {limit: 8}]` |
| Run evaluation | `POST /v1/evaluations`, then `GET /v1/jobs/{jobId}` | `['job', jobId]` |

**Header [SPEC]:** title `Overview`; subtitle `Architecture conformance for your AWS environment`; account and Region context; primary button `Run evaluation`; secondary action `View architecture`.

**Wireframe (desktop)**

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ Overview                                      [View architecture] [Run evaluation]│
│ Architecture conformance for your AWS environment                                │
├──────────────┬───────────────────────┬────────────┬────────────┬────────────────┤
│ Resources    │ Conformance           │ Open       │ Critical / │ Pending        │
│ observed     │ 87.5%                 │ findings   │ High       │ approvals      │
│ 24           │ ▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▯▯▯ │ 5          │ ● 1  ▲ 2   │ 1              │
│              │ 21 of 24 evaluated    │            │            │                │
├──────────────┴───────────────────────┴────────────┴────────────┴────────────────┤
│ [evaluation in progress: stage name                              View job]       │ (only while running)
├───────────────────────────────────────────────┬────────────────────────────────┤
│ Findings over time                            │ Finding severity               │
│ stacked area by day and severity   (2/3)      │ bars with shape, label, count  │
│                                               │                          (1/3) │
├───────────────────────────────────────────────┼────────────────────────────────┤
│ Recent findings (latest 5 to 8)               │ System health                  │
├───────────────────────────────────────────────┴────────────────────────────────┤
│ Recent activity (optional)                                                      │
└────────────────────────────────────────────────────────────────────────────────┘
```

**Metric cards [SPEC §3.1]**, in this order:

| Card | Value | Supporting line | Click |
|---|---|---|---|
| `Resources observed` | `resourcesObserved` | `Supported resources in the latest inventory` | `/architecture?view=LIVE` [DESIGN] |
| `Conformance` | `conformance.percent` (one decimal if not whole), or `—` when null | `{passing} of {evaluated} evaluated` or `Not evaluated yet` | none |
| `Open findings` | `openFindings` | open states are backend-defined | `/findings` with the open-state filter |
| `Critical / High` | Two figures, each with its severity mark and label: `Critical` and `High` counts from `severityCounts` | counts open findings | Each figure links to `/findings?severity=CRITICAL` or `?severity=HIGH` [SPEC: severity metric opens Findings with that filter] |
| `Pending approvals` | `pendingApprovals` | `Waiting for a person` | `/remediation` (Pending approval tab) [DESIGN] |

**Conformance readout.** The Conformance card is visually wider than the others. Beneath the percentage is a row of ticks. Each tick is one evaluated resource, filled for passing and empty for not passing, so the row literally draws `passing` of `evaluated`. If `evaluated` exceeds 48, 48 ticks are drawn proportionally and a caption states `1 tick = n resources`. With no evaluation the row is not drawn. A tooltip carries the backend's definition of the denominator when provided (OCI-05). Ticks render immediately and do not animate.

**Charts**

- `Findings over time`: stacked area by day and severity from `findingTrend`. Days are shown exactly as returned and labelled `UTC days` (CC-23). `INFO` is optional in the payload and is drawn only if present.
- `Finding severity`: one horizontal bar per severity, always all five, each row with shape, label, count and bar. A text legend is inherent in the rows [SPEC: with text legend].
- Both show an empty state when there are no history records: `No history yet. Run an evaluation to start the trend.`

**Recent findings:** compact table, 5 to 8 rows (severity, title, resource, status, last seen). A row opens its detail page.

**System health [SPEC]:** rows for Config, CloudTrail, last inventory, evaluator, Bedrock (optional) and the latest error. Each source shows `Connected`, `Needs setup`, `Error` or `Not enabled` with a shape and a text label. Unsupported sources are never shown as connected.

**Run evaluation [SPEC]:** calls `POST /v1/evaluations` with `{ "scope": "SUPPORTED_RESOURCES", "reason": "Manual evaluation" }`. It immediately shows a queued or running state, an inline `JobProgress` panel with the `progressStage` and a `View job` link, and polls the returned job. The button is disabled while the user's own job is active, and during submission. A `409` is shown as a conflict message. `429` shows retry guidance.

**States [SPEC]**

| State | Treatment |
|---|---|
| Loading | Skeleton with the final grid, card heights and chart areas |
| No evaluation yet | `Conformance` shows `—` and `Not evaluated yet`. The page offers `Run evaluation`. No `100%` anywhere (INV-04). |
| Normal | As above |
| Partial data | A warning bar names the part that failed (for example `System health could not be loaded`) with `Retry`. The rest renders. |
| API error | `ErrorState` for the page with `Retry` and the request ID |
| Evaluation in progress | `JobProgress` panel with stage and `View job` |

**Acceptance**

- AC-OVR-01 Every number on the page comes from the API response. A grep for numeric literals in `features/overview` and its components finds none that are data.
- AC-OVR-02 With `conformance.percent === null` the page shows `—` and `Not evaluated yet`, and never `100%`.
- AC-OVR-03 Clicking `Critical` opens `/findings?severity=CRITICAL` with the filter shown as selected.
- AC-OVR-04 `Run evaluation` shows a queued state within one render of the `202`, never blocks the browser, and stops polling at a terminal status.
- AC-OVR-05 When `sourceStatus` lacks a source or reports `NOT_ENABLED`, the source is not labelled `Connected`.
- AC-OVR-06 With one failed request among several, the rest of the page renders and the failed region shows a retry control.
- AC-OVR-07 The severity chart and the trend chart each have a text equivalent for screen readers.

### 8.3 Architecture Explorer (`/architecture`) [P0, M3; diff mode and intent data M4]

**Goal [SPEC]:** make the difference between the approved architecture and what was observed in AWS visible at a glance.

**Data**

| Need | Endpoint | Query key |
|---|---|---|
| Graph | `GET /v1/architecture?view=&region=&resourceType=&findingOnly=` | `['architecture', view, filters]` |
| Findings for a selected node (Conformance tab, loaded only when that tab is open) | `GET /v1/findings/{id}` for the node's `findingIds` (at most 10) | `['finding', id]` |

**Header controls [SPEC]**

- Title `Architecture Explorer`.
- Segmented switch: `Intended`, `Live`, `Differences`. Default is `Differences` once an approved intent and inventory exist. Otherwise the page explains what is missing (see States).
- Filters: resource type, Region, finding severity, and `Show only nodes involved in findings`. Resource type, Region and the findings toggle are sent to the API (`resourceType`, `region`, `findingOnly`). Severity and search filter the returned nodes client-side (the API has no such parameters), so they only narrow what is already loaded.
- Search by resource ID, ARN, name or tag, or type. Matching nodes are emphasised, others dim, with `n matches` and `Enter` to step through them. Search never fetches.
- `Fit graph`, zoom in and out, `Reset layout`, and refresh. Icon controls have accessible names.
- A `Canvas` or `List` toggle opens `ResourceList` (§7.10).
- Legend: part of the title block (§6.6).

**Wireframe (desktop)**

```
┌ Architecture Explorer                       [Intended │ Live │ Differences]  ⟳ ┐
│ [Search resource ID, ARN, name, tag, type]                        Canvas │ List │
│ Type ▾   Region ▾   Severity ▾   [ ] Show only nodes involved in findings        │
├───────────┬───────────────────────────────────────────────┬─────────────────────┤
│ Filters   │                                               │ Details              │
│ drawer    │   ⬡ CloudFront ──routes to──▶ ⬔ app function  │ Details Relationships│
│ (optional,│                                   │            │ Conformance Evidence │
│ collapsi- │                      allows ingress│           │                      │
│ ble)      │                                   ▼            │ name, type, region,  │
│ 220-260   │                              ▭▭ database       │ ARN, tags, observed, │
│           │                          ┌─ title block ──┐    │ source               │
│           │                          │ v3 · 24 shown  │    │      320-380 px      │
└───────────┴──────────────────────────┴────────────────┴────┴─────────────────────┘
```

**Details drawer [SPEC]** opens on node or edge selection, 320 to 380 px. On small screens it is a full-height sheet.

| Tab | Content |
|---|---|
| `Details` | Name, resource type, AWS Region, ARN or ID, tags, last observed time, source. Fields the API did not return show `Not provided by the API`. |
| `Relationships` | Inbound and outbound edges, taken from the already-loaded graph. Each lists the label, the other node (click to select) and the state. |
| `Conformance` | Constraints and findings associated with the node (§ Data). Severity, title, status, a link to the finding. |
| `Evidence` | Evidence summary for the node's findings and edges. Evidence ids that cannot be resolved without another endpoint show the id and a link to the finding. |

**Edge selection [SPEC]** shows the source node, target node, relationship type, intended status, live status, evidence and related findings. If the backend has not implemented a relationship type, the drawer shows `Not collected`. It never infers an edge or a status (INV-07).

**Deep links.** The selected node or edge, the view and the filters live in the URL: `/architecture?view=DIFF&node=resource_db`. The Finding detail `Violation path` links here.

**Performance [SPEC]:** only the current result set is rendered. The title block shows the resource count and a `Truncated` warning when `truncated` is true, with a hint to narrow the filters. A node click makes no full-account request. Layout is computed once per dataset (§6.6), and node components are memoised.

**States**

| State | Treatment |
|---|---|
| Loading | Skeleton canvas with the title block and toolbar |
| Empty account | The API returns empty arrays plus an explanatory state (OCI-08). The page explains how to proceed: `No resources observed yet. Run an evaluation to take the first inventory.` and, if no approved intent exists, `No approved intent yet. Upload and approve an intent to compare against.` with the matching action. |
| Missing intent or inventory | `Differences` is unavailable and the page says which of the two is missing and offers the other views |
| Normal | Graph |
| Truncated | Graph plus warning |
| Partial | Warning bar naming what is missing (for example a source reporting an error) |
| Error | `ErrorState` with `Retry`. The toolbar stays usable. |
| Unknown edge or node types | Rendered with their label. No crash. |
| Long names | One line with ellipsis, full text in tooltip and drawer |

**Acceptance**

- AC-ARC-01 Every node and edge on the canvas appears in the API response. A test with an unknown `relationshipType` and an unknown `resourceType` renders both without error.
- AC-ARC-02 Each of the five states is distinguishable without colour (text label, outline pattern, shape).
- AC-ARC-03 No file under `components/architecture` or `utils/graph.ts` decides a state, derives a severity or infers an edge.
- AC-ARC-04 Switching view keeps the position of nodes present in both views.
- AC-ARC-05 Every node is reachable and selectable by keyboard, and `ResourceList` offers the same selection and the same drawer.
- AC-ARC-06 With `truncated: true` the warning is visible, and the resource count matches `nodes.length`.
- AC-ARC-07 `UNKNOWN` is never styled as a violation.
- AC-ARC-08 Opening the `Conformance` tab triggers at most 10 detail requests, and only for that node.
- AC-ARC-09 A graph of 500 nodes pans and zooms at an interactive frame rate on a mid-range laptop (§11.1).

### 8.4 Findings list (`/findings`) [P0, M2]

**Header [SPEC]:** `Findings`, with a subtitle explaining that findings are violations against approved intent or explicitly enabled security checks.

**Data:** `GET /v1/findings?severity&status&category&resourceType&limit&cursor` (key `['findings', filters]`).

**Filter row [SPEC]**

| Control | Options | Wire |
|---|---|---|
| Search text | free text | `q` (OCI-06). Until then it filters the loaded results only, and a caption says `Searching the n loaded results`. |
| Severity | Critical, High, Medium, Low, Info | `severity` (single value until OCI-06 confirms multi-value) |
| Status | Open, Acknowledged, In progress, Resolved, Suppressed | `status` |
| Category | Network path, Identity & permissions, Public exposure, Missing resource, Configuration drift, Other | `category` (canonical codes from the backend, display text from `categoryLabel`) |
| Resource type | from a list built from loaded results and known types | `resourceType` |
| First seen / last seen range | date range | Proposed parameters (OCI-06). Rendered as `Not enabled` until then. |
| Sort | Severity, Newest, Oldest, Last updated | `sort` (OCI-06). Rendered as `Not enabled` until then. The page then shows the backend's default order and says so. |
| `Clear filters` | | Clears all filter parameters |

All filter state, the sort and the cursor live in the URL, so a filtered page is shareable [SPEC]. Unknown parameter values are ignored.

**Table [SPEC]:** columns in this order: severity, finding title, category, affected resource, expected vs. observed summary, status, first seen, last seen. The `summary` field fills the expected-versus-observed column (OCI-06 asks for separate fields). Affected resource shows the name and the type, with the ID in mono. A row opens `/findings/:findingId`.

**Bulk actions:** none in the MVP [SPEC].

**Pagination [SPEC]:** opaque cursor, default 25 per page, with 25 and 50 offered if the backend supports it (a `400` on 50 falls back to 25 once). `CursorPagination` provides `Previous` and `Next`, keeping a stack of visited cursors in state. The current cursor is in the URL.

**States [SPEC]** (each shown distinctly)

| State | Treatment |
|---|---|
| Loading | Row skeletons with real column widths |
| No findings at all | `No findings.` plus, if no evaluation has run, `Run an evaluation to check your environment against approved intent.` |
| No filtered matches | `No findings match these filters.` plus `Clear filters` |
| Permission error (`403`) | `You do not have access to findings.` and what to do |
| API error | `ErrorState` with `Retry` and request ID |

**Acceptance**

- AC-FND-01 Reloading the page with a filtered URL reproduces the same filter state and page.
- AC-FND-02 The five required states are visually and textually distinct.
- AC-FND-03 Changing any filter resets the cursor.
- AC-FND-04 Severity is shown as shape plus label in every row.
- AC-FND-05 No control is shown as active when its parameter is not supported; it reads `Not enabled`.
- AC-FND-06 Rows are keyboard-operable and the title is a real link.

### 8.5 Finding detail (`/findings/:findingId`) [P0, M3]

**Goal [SPEC]:** the investigation page and the most useful page for demonstrating the product.

**Data:** `GET /v1/findings/{findingId}` (key `['finding', findingId]`). Actions: `PATCH /v1/findings/{findingId}`, `POST /v1/findings/{findingId}/remediation-requests`.

**Header [SPEC]:** breadcrumb `Findings / [finding title]`, severity badge, current status, resource display name, and the actions `Acknowledge` and `Request remediation`.

**Wireframe**

```
Findings / Unexpected network path to private database
[▲ High] [Open]   app-db-access   sg-0123456789abcdef0        [Acknowledge] [Request remediation]
┌ Why it matters ┐ ┌ What was intended ┐ ┌ What was observed ┐ ┌ Evidence completeness ┐
│                │ │                   │ │                   │ │ (only if returned)    │
└────────────────┘ └───────────────────┘ └───────────────────┘ └───────────────────────┘
┌ Violation path ─────────────────────────────────────────┐ ┌ Lifecycle ────────────────┐
│ [Web entry] ─ relation ─▶ [Application] ─ relation ─▶    │ │ timeline                  │
│ [Private database]   each step opens the Explorer        │ ├ Related findings ─────────┤
├ Expected vs observed ───────────────────────────────────┤ │                           │
│ constraint, intent version, live relationship, rule ID   │ ├ Remediation ──────────────┤
├ Evidence (accordion) ───────────────────────────────────┤ │ eligibility and reason    │
│ source, evidence id, observed time, fields               │ └───────────────────────────┘
├ AI-assisted explanation ────────────────────────────────┤
└──────────────────────────────────────────────────────────┘
```

**First row of cards [SPEC]**

| Card | Source |
|---|---|
| `Why it matters` | `description` (CC-09; a dedicated field is requested in OCI-07) |
| `What was intended` | `intent.expected`, with the intent version and constraint ID |
| `What was observed` | `observed.summary`, observed time, source |
| Confidence / evidence completeness | Shown **only** if the backend returns it with a definition. Otherwise the card is not rendered. |

**Violation path.** A horizontal chain of resource chips with a connector and relation label between steps, wrapping vertically on narrow screens. Each chip shows the category glyph, the label and the short type, and opens `/architecture?view=DIFF&node=<nodeId>` [SPEC: opens the resource detail drawer in the Explorer]. The current `path` carries nodes only. Relation labels appear once the backend adds them (OCI-07). Until then connectors are plain arrows with the caption `Relationship labels were not provided.`

**Expected vs observed [SPEC]:** shows the exact constraint text, the relevant intent version, the live relationship or configuration, and the backend rule ID (`intent.constraintId`, in mono).

**Evidence accordion [SPEC]:** one item per `evidence[]` entry. Header: source label (`AWS Config`, `CloudTrail`), evidence ID (mono), observation time. Body: the selected, already-redacted `fields` as a key-value list, with the observation time shown in local time and UTC. A console link is rendered only if the API provides one, and only if it is `https` on an allowed AWS console host (`utils/url.ts`), opened with `rel="noopener noreferrer"`. Items open when linked from the AI panel's cited evidence.

**Right rail [SPEC]**

- **Lifecycle timeline** from `timeline[]`: time, humanised action (`DETECTED` becomes `Detected`), actor, message.
- **Related findings** (OCI-07). Hidden until supplied.
- **Remediation eligibility** from `remediation.available` and `remediation.reason`.

**AI-assisted explanation [SPEC]** (`ExplanationPanel`)

| `explanation.status` | Treatment |
|---|---|
| Bedrock reported `NOT_ENABLED` in system status | Label `AI-assisted explanation` with `Not enabled` |
| `NOT_GENERATED` | `Not generated`. A `Generate explanation` button appears only if that endpoint exists (OCI-11). |
| Generated | The text, the cited evidence ids as links to the accordion, and the disclaimer `This explanation is advisory. Check it against the evidence.` |
| Pending or failed (codes proposed in OCI-11) | Neutral status text and `Retry` if supported |

The panel has a plain border and a text label. It carries no sparkle icon or special colour.

**Actions [SPEC]**

- `Acknowledge` opens a small dialog with an optional comment, then sends `PATCH` `{ "action": "ACKNOWLEDGE", "comment": "…" }`. Shown when status is `OPEN` [DERIVED]. The server validates the transition, and a `409` is shown as a conflict message.
- `Suppress` and `Reopen` are hidden until the backend confirms they are permitted (feature flags, §10.4).
- `Request remediation` is disabled when the finding is informational or `remediation.available` is false, with the reason as visible text. Otherwise it opens a dialog that states: `This creates a request for approval. It does not change anything in AWS.` and offers a comment. On success (`PENDING_APPROVAL` or dry run) it shows a toast and a link to the request in Remediation, and the finding is refetched.
- If no safe runbook exists, the page explains why remediation is unavailable. There is no fake success button (INV-15).

**States:** loading skeleton shaped like the page; `404` shows `This finding does not exist or was removed.` with a link to Findings; `403` permission message; API error with `Retry`; partial (for example evidence missing) with a warning.

**Acceptance**

- AC-FDT-01 Each card, panel and accordion item is built from a field in the response, and the confidence card never renders without data.
- AC-FDT-02 `Acknowledge` disables during submission, shows a toast only after success, and refreshes the finding, the list and the dashboard summary.
- AC-FDT-03 A stale or repeated action shows the server's conflict as a message, not a generic error.
- AC-FDT-04 `Request remediation` is never enabled for a finding the response marks unavailable, and its reason is visible without hovering.
- AC-FDT-05 A path step opens the Explorer with that node selected.
- AC-FDT-06 The AI panel is always labelled, always shows its evidence references, and never appears without the advisory text.
- AC-FDT-07 Console links that are not `https` AWS console URLs are not rendered as links.

### 8.6 Intent & Policies list (`/intents`) [P1, M4]

**Header [SPEC]:** title `Intent & Policies`. Short explanation: `Approved versions describe what your AWS architecture is allowed to look like.` Primary action `Upload IaC / ADR`.

**Data:** `GET /v1/intents?status&limit&cursor` (key `['intents']`).

**Table [SPEC]:** name, source files, current version, status (`Draft`, `Processing`, `Needs review`, `Approved`, `Failed`), created by, updated time. Fields: `name`, `sourceFilesCount`, `currentApprovedVersion`, `status`, `uploadedBy`, `updatedAt`. Search and status filter above it. Search is server-side if `q` is supported, otherwise limited to loaded rows with the same caption as Findings. Failed rows show `errorMessage`. A row opens `/intents/:intentId`.

**Upload flow [SPEC]** (`UploadIntentDialog`, a dialog or a dedicated page on small screens)

| Step | Content |
|---|---|
| 1. Source type | Terraform, CloudFormation, ADR/document, JSON constraint manifest |
| 2. Files | File input and drop zone. Per file: name, size, type, validation result. Validation is by extension and size. The content type sent comes from a fixed map in `config/constants.ts`, never from `file.type`, so it matches what the backend signed. |
| 3. Details | Optional human-authored architecture name (sent as `name`). A rationale field appears only once the backend has a place for it (OCI-09). |
| 4. Confirmation | Checkbox: `This file contains no secrets or credentials.` Required. Client-side only. |
| 5. Upload and processing | Per-file progress, then processing status, then success or a validation error |

Warnings shown in the dialog: do not upload secrets, and do not paste AWS keys. The UI never asks for credentials (INV-21). Terraform state and variable files (`.tfstate`, `.tfvars`) are rejected with the message `State and variable files often contain secrets and are not accepted.`

Sequence: for each file `POST /v1/intents/upload-url` (`fileName`, `contentType`, `sizeBytes`) then `PUT` the bytes to the returned URL with the same content type and **no `Authorization` header**, then `POST /v1/intents/ingest` (`name`, `objectKeys`, `sourceType`) which returns `202` with `intentId`, `jobId`, `status`. Then poll `GET /v1/jobs/{jobId}` until terminal, and on success open `/intents/:intentId`.

Rules:

- If the `PUT` fails because the URL expired (default 300 s), request a fresh URL once and retry that file.
- Upload can be cancelled (the in-flight request is aborted).
- Presigned URLs and file contents are held in memory only. They are never logged, stored or put in an error report (INV-09).
- Object keys are used exactly as returned. The client never builds or edits them.
- Allowed types and limits live in `config/constants.ts` and are confirmed in OCI-09 and OCI-16. The server remains the authority.

**States:** loading, no intents (`No intents yet. Upload an IaC file or an ADR to create the first one.`), filtered empty, error, and a `Processing` row that updates when its job completes.

**Acceptance**

- AC-INT-01 The upload button stays disabled until a valid file is chosen and the confirmation is ticked.
- AC-INT-02 A rejected file shows its reason next to the file, and nothing is uploaded.
- AC-INT-03 The `PUT` request carries no `Authorization` header and the exact content type that was signed.
- AC-INT-04 A processing failure shows the job's safe `errorMessage` and `Try again`, and offers no `Review and approve`.
- AC-INT-05 No file contents appear in the console, in network error reports or in the query cache devtools.

### 8.7 Intent detail (`/intents/:intentId`) [P1, M4]

**Data:** `GET /v1/intents/{intentId}` returns metadata, available versions and constraints (key `['intent', intentId]`). The selected version is in the URL (`?version=v3`).

**Header:** intent name, status badge, current approved version, version selector, and `Review and approve`.

**Tabs [SPEC]**

| Tab | Content |
|---|---|
| `Overview` | Source files, who uploaded, processing status, created date |
| `Extracted constraints` | A `ConstraintCard` per constraint |
| `Diff from approved version` | Added, removed and changed constraints (OCI-09). Rendered as `Not enabled` until the backend provides the diff. |
| `Source files` | File names and safe metadata. Raw source content only if access controls and redaction exist (not in the MVP). |

**Constraint card [SPEC]:** ID (mono), description (title), source reference as `fileName` with `lineStart` to `lineEnd` when available, expected relationship or property (the `expected` object rendered as labelled values, with unknown keys shown generically), scope (resource type chips), severity badge, extraction confidence as a percentage in text with a thin bar, and review status.

**Review and approve [SPEC]:** disabled when extraction or validation failed. It requires a confirmation dialog stating the version and the number of constraints, with `Approve version` and `Cancel`. The page notes `Suggested constraints must be reviewed by a person before approval.` while the version is `NEEDS_REVIEW`. It shows the current approved version, which stays in history, because an existing approved version is never silently overwritten [SPEC trust model]. Until the approve endpoint exists (OCI-09) the button reads `Not enabled`.

**Acceptance**

- AC-IND-01 `Review and approve` is disabled for a failed version and shows why.
- AC-IND-02 The confirmation dialog shows the version and the number of constraints before any request is sent.
- AC-IND-03 Every constraint field in the Spec is displayed, and missing optional fields (source reference) are omitted cleanly.
- AC-IND-04 Confidence is readable as text, not only as a bar.
- AC-IND-05 After approval the intent, the intents list and the architecture queries are invalidated.

### 8.8 Drift Events (`/drift-events`) [P1, M4]

A timeline or table of **raw observed changes**, distinct from Findings: a change is an event, a finding is a violation [SPEC]. The page says so in one line.

**Data:** `GET /v1/drift-events?source&limit&cursor` (key `['drift-events', filters]`).

**Columns [SPEC]:** event time, AWS source, resource, change summary, actor if known, evaluation status, related finding. `actor` null renders as `Not established by the source`. Related finding links to its detail page.

**Filters [SPEC]:** date range, source, resource type, processed or unprocessed, actor. Parameters beyond `source` are proposed (OCI-13). Unsupported filters render as `Not enabled`.

**Detail drawer [SPEC]:** source event ID, event time, affected resource, normalised before and after fields **if available**, related evaluation job, related finding. A missing before-state is stated as `The source did not provide a before-state.` It is never inferred (INV-08).

**States:** loading, empty (`No configuration changes observed yet.` with the reason if a source is not connected), filtered empty, error, permission error.

**Acceptance:** AC-DRF-01 No before or after value is shown unless it is in the payload. AC-DRF-02 A change with no finding shows a neutral `No finding`, not a success mark.

### 8.9 Remediation (`/remediation`) [P1, M5]

**Tabs [SPEC]:** `Pending approval`, `In progress`, `Completed`, `Rejected / failed`. Each tab maps to one or more status codes (OCI-10) and shows its count only if the backend provides one.

**Data:** `GET /v1/remediations?status&limit&cursor` (key `['remediations', status]`). Actions: `POST /v1/remediations/{id}/decision`.

**Fields [SPEC]:** request ID, finding (link), proposed runbook or action, target resource, requester, created time, impact or risk, status. Every request created in the MVP is labelled **`Dry run`** where `dryRun` is true.

**Approval detail [SPEC]:** original finding, proposed operation, affected resource ARN or ID, exact parameters, risk note, dry-run output where available, and the audit timeline. Buttons: `Approve`, `Reject`, and `Cancel request` if supported (hidden until its endpoint exists, OCI-10). The detail endpoint is OCI-10.

**Decision dialog [SPEC]:** explicit confirmation that restates the action and target, plus a reason field (required for `Reject`, optional for `Approve`, CC-21). Both buttons disable during submission and double submission is prevented. The body is `{ "decision": "APPROVE" | "REJECT", "comment": "…" }`. A `409 STATE_CONFLICT` shows `This request was already decided or has changed. Refresh to see its current state.` with a refresh action. A `403` shows a permission message. The browser sends no role flag (INV-13).

**MVP safety [SPEC]:** the page states `Dry run: no change will be made in AWS.` on every request that is a dry run. A completed dry run reads `Simulated result`, never `Fixed` or `Resolved`. The UI contains no control for automatic remediation or for deletion, IAM policy replacement or security-group changes (INV-15). No task token is ever present in a payload the client handles.

**States:** loading, empty per tab (`No requests are waiting for approval.`), error, permission error, stale decision (conflict).

**Acceptance**

- AC-REM-01 Approve and Reject cannot be submitted twice, and the second attempt of a decided request surfaces the `409` message.
- AC-REM-02 A dry-run request is labelled as a dry run in the table, the detail and the dialog.
- AC-REM-03 The decision toast appears only after a successful response.
- AC-REM-04 After a decision, the request, its tab list, the finding, the summary (pending approvals) and the audit queries refresh.

### 8.10 Audit Trail (`/audit-trail`) [P1, M5]

A **read-only** table of important actions [SPEC]: intent uploaded or approved, evaluation started or completed, finding acknowledged, suppressed or resolved, remediation requested, approved, rejected or executed, and configuration changes.

**Data:** `GET /v1/audit-events?from&to&action&limit&cursor` (key `['audit-events', filters]`).

**Columns [SPEC]:** timestamp, actor, action, target, result, correlation or request ID (mono, copyable). **Filters [SPEC]:** action, actor, date range, result. Parameters beyond `from`, `to`, `action` are proposed (OCI-12).

**Detail drawer:** structured event metadata as labelled values. The UI never receives or shows credentials, raw JWTs, secrets, task tokens or unnecessary document content, and `utils/redact.ts` masks anything that looks like a token or key as a second line of defence.

There is no control anywhere that creates, edits or deletes an audit entry (INV-17).

**States:** loading, empty, filtered empty, error, permission error.

**Acceptance:** AC-AUD-01 The page has no mutation. AC-AUD-02 Selecting an event shows the request ID and lets the user copy it. AC-AUD-03 A sequence of finding request, remediation request and decision appears in time order after the Milestone 5 exit scenario.

### 8.11 Settings (`/settings`) [P0 read-only, M2]

Read-only in the MVP [SPEC].

| Section [SPEC] | Content and source |
|---|---|
| `AWS environment` | Account alias and ID (ID masked by default as `••••••••9012` with a `Show` control, to help when sharing a screen), active Region, role or configuration source, last successful inventory. Source: `/v1/dashboard/summary`, `/v1/system/status`. |
| `Data sources` | Config, CloudTrail, optional flow logs, Bedrock status and last successful query |
| `Evaluation settings` | Enabled constraint set, severity threshold, scheduled scan frequency. Each shows `Not enabled` if unsupported, and says whether the schedule is active or unsupported (OCI-17). |
| `Remediation safety` | A fixed statement: `Human approval required.` With a lock mark. It is not a toggle, and there is no client-side switch for automatic remediation [SPEC]. |
| `Application` | User info, session and `Sign out`, app version, privacy and help links (shown only if configured) |

No field ever asks for AWS access keys [SPEC]. Multi-account onboarding is not offered.

**Acceptance:** AC-SET-01 There is no input that accepts credentials. AC-SET-02 `Remediation safety` has no interactive control. AC-SET-03 Unsupported items say `Not enabled` and are not shown as active.

### 8.12 Not found (`*`) [P0, M1]

Heading `Page not found`. One sentence: `The address does not match a page in this application.` A link `Go to Overview`. Detail routes whose record is missing use their own `404` state with a link back to the list.

---

## 9. API integration layer

This section is the frontend half of the contract. The backend developer should read it with §16 and Appendix C.

### 9.1 `apiClient` contract [SPEC §5]

`api/apiClient.ts` is plain TypeScript with no React. Every application call goes through it.

```ts
export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH";
  query?: Record<string, string | number | boolean | undefined>; // undefined values are omitted
  body?: unknown;                 // JSON
  signal?: AbortSignal;           // wired from TanStack Query for cancellation
  auth?: boolean;                 // default true; false only for GET /v1/health
}

export function request<T>(
  path: string,                   // relative, e.g. "/v1/findings"
  schema: ZodType<ApiSuccess<T>>, // runtime contract
  options?: RequestOptions
): Promise<ApiSuccess<T>>;

export class ApiError extends Error {
  status: number;                 // HTTP status, or 0 for network failure
  code: string;                   // from the envelope, or derived (see 9.4)
  requestId?: string;
  details?: unknown[];
  retryAfterSeconds?: number;     // when the response exposes Retry-After
  kind: "network" | "auth" | "forbidden" | "not_found" | "conflict"
      | "rate_limited" | "validation" | "server" | "contract";
}
```

Behaviour, all from the Spec unless tagged:

1. Prefix relative paths with `VITE_API_BASE_URL`.
2. Get a **fresh** token from `authClient` for each request. Attach `Authorization: Bearer <token>` to every request except the public health route.
3. Send `Content-Type: application/json` for JSON bodies. Send no other custom headers, so CORS preflights stay simple [DESIGN].
4. Parse the JSON body, then validate it against the schema (§9.6).
5. On failure throw a typed `ApiError` carrying status, `code`, message and `requestId`.
6. On `401`: force one token refresh and retry **once**. If it fails again, end the session. Never loop.
7. Map `403` to a permission error, `404` to missing resource, `409` to a state conflict, `429` to rate limiting, `5xx` to server failure.
8. Tolerate bodies that are not the envelope: API Gateway's own errors such as `{"message":"Unauthorized"}`, empty bodies, and HTML. `code` is then derived from the status [CC-22].
9. Pass `AbortSignal` through, so leaving a page cancels its requests.
10. Never log the token, the request body of an upload, or presigned URLs.

### 9.2 Endpoint index

| # | Method and path | Spec | Hook | Query key | Flag | First live in |
|---|---|---|---|---|---|---|
| 1 | `GET /v1/health` (public) | §6.1 | `useApiHealth` | `['api-health']` | always | M2 |
| 2 | `GET /v1/system/status` | §6.12 | `useSystemStatus` | `['system-status']` | always | M2 |
| 3 | `GET /v1/dashboard/summary` | §6.2 | `useDashboardSummary` | `['dashboard-summary', region]` | always | M2 |
| 4 | `GET /v1/findings` | §6.3 | `useFindings` | `['findings', filters]` | always | M2 |
| 5 | `GET /v1/findings/{findingId}` | §6.4 | `useFinding` | `['finding', findingId]` | always | M2 |
| 6 | `PATCH /v1/findings/{findingId}` | §6.5 | `useFindingActions` | mutation | `findings.update` | M3 |
| 7 | `GET /v1/architecture` | §6.6 | `useArchitecture` | `['architecture', view, filters]` | `architecture` | M3 |
| 8 | `POST /v1/evaluations` | §6.9 | `useJobs` | mutation | `evaluations` | M3 |
| 9 | `GET /v1/jobs/{jobId}` | §6.9 | `useJobs` | `['job', jobId]` | `evaluations` | M3 |
| 10 | `GET /v1/intents` | §6.7 | `useIntents` | `['intents']` | `intents` | M4 |
| 11 | `GET /v1/intents/{intentId}` | §6.7 | `useIntent` | `['intent', intentId]` | `intents` | M4 |
| 12 | `POST /v1/intents/upload-url` | §6.8 | `useIntentUpload` | mutation | `intents.upload` | M4 |
| 13 | `POST /v1/intents/ingest` | §6.8 | `useIntentUpload` | mutation | `intents.upload` | M4 |
| 14 | `GET /v1/drift-events` | §6.10 | `useDriftEvents` | `['drift-events', filters]` | `driftEvents` | M4 |
| 15 | `GET /v1/remediations` | §6.11 | `useRemediations` | `['remediations', status]` | `remediation` | M5 |
| 16 | `POST /v1/findings/{findingId}/remediation-requests` | §6.11 | `useFindingActions` | mutation | `remediation` | M5 |
| 17 | `POST /v1/remediations/{remediationId}/decision` | §6.11 | `useRemediationDecision` | mutation | `remediation` | M5 |
| 18 | `GET /v1/audit-events` | §6.12 | `useAuditEvents` | `['audit-events', filters]` | `auditTrail` | M5 |
| P1 | Approve intent version, version diff | gap | `useIntent` | mutation | `intents.approve`, `intents.diff` | M4 (OCI-09) |
| P2 | Remediation detail and cancel | gap | `useRemediations` | `['remediation', id]` | `remediation.detail`, `remediation.cancel` | M5 (OCI-10) |
| P3 | Generate explanation | gap | `useFindingActions` | mutation | `explanations.generate` | M5 (OCI-11) |
| P4 | Settings, current user and permissions | gap | n/a | n/a | n/a | OCI-14, OCI-17 |

Presigned `PUT` to S3 (§9.8) is the only network call outside this table, and it lives in `api/uploadClient.ts`.

### 9.3 Query keys and invalidation

Keys are built by `api/queryKeys.ts`, never written inline. They match Spec §4: `['dashboard-summary', region]`, `['findings', filters]`, `['finding', findingId]`, `['architecture', view, filters]`, `['intents']`, `['drift-events', filters]`, `['remediations', status]`, `['audit-events', filters]`, `['system-status']`. Additions: `['job', jobId]`, `['intent', intentId]`, `['remediation', id]`, `['api-health']`.

After a mutation, invalidate **only** what it affects [SPEC §4]:

| Event | Invalidate |
|---|---|
| Evaluation job reaches a terminal state | `dashboard-summary`, `findings`, `finding`, `architecture`, `drift-events`, `system-status`, `audit-events` |
| `PATCH` finding | `['finding', id]`, `findings`, `dashboard-summary`, `architecture`, `audit-events` |
| Remediation request created | `['finding', id]`, `remediations`, `dashboard-summary`, `audit-events` |
| Remediation decision | `['remediation', id]`, `remediations`, the related `['finding', id]`, `dashboard-summary`, `audit-events` |
| Ingestion job reaches a terminal state | `intents`, `['intent', id]`, `audit-events` |
| Intent version approved | `['intent', id]`, `intents`, `architecture`, `dashboard-summary`, `audit-events` |
| Refresh button | Keys of the current page, plus `system-status` and `dashboard-summary` |
| Sign out | Clear the whole cache |

No optimistic updates for status changes, approvals or evaluations. The UI waits for the response (INV-11, INV-12).

### 9.4 Error handling matrix

| Condition | `kind` and derived `code` | User-visible handling |
|---|---|---|
| Network failure, CORS block, timeout | `network` / `NETWORK_ERROR` | `Could not reach the API.` with `Retry`. The connection pill shows `Disconnected`. |
| `400` | `validation` / `VALIDATION_ERROR` | Map `details` to form fields when present, otherwise show the message in the dialog or page. |
| `401` | `auth` / `UNAUTHENTICATED` | One silent refresh and retry, then `/login` with the expiry message (§7.4). |
| `403` | `forbidden` / `FORBIDDEN` | `You do not have permission to do this.` Shown in place. Not a sign-out. |
| `404` | `not_found` / `NOT_FOUND` | Missing-resource state with a link back to the list. |
| `409` | `conflict` / `STATE_CONFLICT` | `This item was already changed by someone else. Refresh to see its current state.` with a refresh action. |
| `429` | `rate_limited` / `RATE_LIMITED` | `Too many requests. Try again in n seconds.` (or `shortly` when `Retry-After` is not readable). The retry control is disabled for that time. |
| `5xx`, `502`, `503`, `504` | `server` / `INTERNAL_ERROR` | `The server could not complete the request.` with the request ID and `Retry`. GETs retry automatically twice with backoff. Mutations never retry automatically. |
| Schema mismatch | `contract` / `CONTRACT_MISMATCH` | `The server sent data this version of the app does not understand.` with the request ID and the failing field path in development. |

Every error state shows the `requestId` when available, with a copy control, so a backend developer can find the log line.

### 9.5 Caching, polling and retry

| Setting | Value |
|---|---|
| Default `staleTime` | 30 s for lists and summary, 15 s for detail views and `system-status`, 60 s for the graph |
| `gcTime` | 5 minutes |
| `system-status` | Refetch every 30 s while the tab is visible, and on window focus |
| Query retry | Up to 2 retries, exponential backoff (1 s, 2 s), only for `network` and `server` kinds. Never for `4xx`. |
| Mutation retry | None |
| Job polling | Every 2 s for the first 30 s, then every 5 s. Pauses while the tab is hidden. Stops on `SUCCEEDED`, `PARTIAL` or `FAILED`, and on `403` or `404`. Gives up after 10 minutes with `This job is taking longer than expected. Check again later.` and a manual refresh. Any status string other than the three terminal ones is treated as in progress (CC-03). |
| Prefetch | Finding detail is prefetched on row hover or focus after 200 ms |
| Request cancellation | Enabled through `AbortSignal` |

### 9.6 Runtime validation and tolerance

`api/schemas.ts` holds a zod schema per response. `api/apiTypes.ts` exports the TypeScript types inferred from them, under the names used in Spec §13.

The reader is **strict about shape and tolerant about vocabulary**:

- Required fields in the contract must be present. If one is missing the call fails as `CONTRACT_MISMATCH`.
- Extra fields are ignored, so the backend can add fields without breaking the UI.
- Enumerations that may grow (`relationshipType`, `resourceType`, `source`, `processingStatus`, `kind`, remediation statuses, job statuses) are plain strings. Known values get specific styling and unknown values render humanised, never as an error.
- For closed Spec enumerations (`Severity`, `FindingStatus`, `DiffState`, `GraphView`), an unknown value is mapped to a safe neutral presentation (`INFO`, `UNKNOWN`) with a development-only console warning.
- Fixtures are parsed against the same schemas in CI, so a fixture cannot drift from the types.

### 9.7 Pagination

Opaque cursors from `meta.nextCursor` (INV-19). `CursorPagination` keeps a stack of visited cursors for `Previous`. Changing any filter or the page size resets the stack. The page size comes from `meta.limit`. An invalid or expired cursor (`400`) restarts at the first page with a notice.

### 9.8 Upload client (`api/uploadClient.ts`) [CC-18]

- Takes the `uploadUrl` returned by the backend, the `File`, and the content type signed by the backend.
- Sends `PUT` with `Content-Type` only. **No `Authorization` header.**
- Uses `XMLHttpRequest` for upload progress events and `abort()`.
- Returns success or a typed error (`expired`, `rejected`, `network`). On `expired`, the caller asks for a new URL once.
- Holds the URL and bytes in memory only and never logs them (INV-09).
- Requires the bucket's CORS to allow `PUT` from the app origins (OCI-16).

---

## 10. Backend connection plan

### 10.1 Environments

| Environment | UI served from | API | Auth | Purpose |
|---|---|---|---|---|
| **Mock** | `localhost` dev server | MSW inside the browser, fixtures from `api/mocks/` | A fake signed-in user, clearly bannered | Milestone 1 and all state testing. Development only. |
| **Dev stack** | `localhost` dev server | Deployed API Gateway in the dev AWS account | Real Cognito | Daily integration. Needs CORS for the local origin. |
| **Demo stack** | CloudFront and private S3 | Deployed API Gateway in the demo account | Real Cognito | Milestone 6 end-to-end and the demo. Dedicated stack, not production resources [SPEC §14 M6]. |

### 10.2 What the frontend needs from the backend

These are the concrete preconditions for the UI to work. Items 1 to 4 are the usual cause of "it works in Postman but not in the browser".

| ID | Requirement | Spec basis |
|---|---|---|
| BE-01 | **CORS (HTTP API):** allowed origins are exactly the local dev origin(s) and the CloudFront URL. Methods `GET, POST, PATCH, OPTIONS`. Allowed headers `authorization, content-type`. Expose `retry-after`. No wildcard origin. | §10, §17 |
| BE-02 | Gateway-generated `401`, `403`, `404`, `429` and `5xx` responses carry the CORS headers too. Otherwise the browser reports a network error instead of a status. Verify with a deliberately bad token and a throttled call. | §17 (CC-22) |
| BE-03 | **JWT authorizer:** issuer is the user pool, audience is the app client ID, and the token type is agreed (OCI-01). | §5 |
| BE-04 | **Cognito app client:** public client with no secret, authorization code grant with PKCE, scopes `openid email profile`, a managed-login domain, and callback and logout URLs for `http://localhost:<port>/login` and `https://<cloudfront-domain>/login` (OCI-02). | §5 |
| BE-05 | Every response uses the envelope with `data` and `meta.requestId` (and `nextCursor` and `limit` for lists). Errors use the error envelope with a stable `code` and `requestId`. | §5 |
| BE-06 | Timestamps are ISO 8601 UTC. Trend dates are UTC days (OCI-20). | §4 |
| BE-07 | Cursors are opaque and stable. `nextCursor` is `null` at the end. A cursor is valid only for the filters it came from. | §3.3 |
| BE-08 | Async work returns `202` with a `jobId`, and `GET /v1/jobs/{id}` reports status and `progressStage` (OCI-04). | §6.8, §6.9 |
| BE-09 | **S3 upload bucket CORS** allows `PUT` from the app origins and the `Content-Type` header. Presigned URLs live at least 300 s. Object keys are server-scoped (OCI-16). | §6.8 |
| BE-10 | No payload contains secrets, tokens, task tokens, stack traces or unredacted evidence. | §5, §6.4 |
| BE-11 | A failed AWS data source yields a status or error state and partial results, never a success-shaped response. | §16.3 |
| BE-12 | Mutations are state-checked. A stale or repeated decision returns `409 STATE_CONFLICT`. | §6.11 |
| BE-13 | Every canonical code (category, severity, status) comes with a display label where the UI shows text (`categoryLabel`). | §3.3 |
| BE-14 | The backend runs the same fixtures as the frontend in its tests. | §14 M1, §16.1 |

### 10.3 Contract governance [SPEC §16.1]

1. The contract lives in the frontend repository at `docs/CONTRACT.md` plus `api/schemas.ts`, `api/apiTypes.ts` and `api/mocks/fixtures/*.json`. The backend repository consumes the same fixtures.
2. A change to a field, status code, enumeration or route updates the schema, the types, the fixtures and the backend tests **in the same pull request**. Both owners review it.
3. Additive changes (new optional fields, new enumeration values handled as strings) are safe and need no coordination beyond the pull request. Removing or renaming a field, or changing its meaning, is a breaking change and needs both owners' agreement and, if unavoidable, a new route version.
4. A nightly job fetches responses from the dev stack and validates them against the schemas (§12.4). A failure opens an issue naming the endpoint and field.
5. An OCI is closed only when the backend confirms the shape and the fixture and schema are updated.

### 10.4 Capability flags

The frontend never advertises an action the backend cannot perform (INV-14). A capability is on only when its endpoint is deployed. Flags are set with `VITE_FEATURES` (comma-separated). In mock mode all are on.

| Flag | Enables | Needs | Default on from |
|---|---|---|---|
| `evaluations` | `Run evaluation`, job drawer, polling | endpoints 8, 9 | M3 |
| `architecture` | Explorer data | endpoint 7 | M3 |
| `findings.update` | `Acknowledge` | endpoint 6 | M3 |
| `findings.suppress`, `findings.reopen` | `Suppress`, `Reopen` | backend policy (OCI-14) | off until confirmed |
| `findings.query` | Server-side search, date range, sort, multi-value filters | OCI-06 | off until confirmed |
| `intents` | Intents pages | endpoints 10, 11 | M4 |
| `intents.upload` | Upload dialog | endpoints 12, 13, OCI-16 | M4 |
| `intents.approve`, `intents.diff` | `Review and approve`, `Diff from approved version` | OCI-09 | M4, when confirmed |
| `driftEvents` | Drift Events page | endpoint 14 | M4 |
| `explanations.generate` | `Generate explanation` | OCI-11 | M5, when confirmed |
| `remediation` | Request and decision | endpoints 15 to 17 | M5 |
| `remediation.detail`, `remediation.cancel` | Approval detail, `Cancel request` | OCI-10 | M5, when confirmed |
| `auditTrail` | Audit Trail page and Recent activity | endpoint 18 | M5 |

A disabled capability shows `NotEnabled`: the control is hidden or rendered disabled with the text `Not enabled`, and its page, if any, shows `This part of the product is not enabled in this environment.`

### 10.5 Moving an endpoint from mock to live

For each endpoint, in this order:

1. Backend deploys the route and shares a sample response and the error cases (`401`, `403`, `404`, `409`, `429` where relevant).
2. The sample is compared with the fixture and schema. Differences go through §10.3.
3. CORS is checked from the browser, including a deliberate error response (BE-02).
4. The frontend turns the flag on for the dev stack and runs the contract test.
5. The mock handler stays in the repository for tests. Only the flag changes.

---

## 11. Non-functional requirements

### 11.1 Performance targets

Targets are measured in CI with a bundle analyser and Lighthouse on the demo stack, and in a profile of the graph.

| Metric | Target |
|---|---|
| Initial JavaScript (login and shell), gzip | 150 KB or less |
| Each route chunk (excluding shared vendor), gzip | 120 KB or less |
| Architecture chunk (React Flow and layout), gzip | 250 KB or less, loaded only on `/architecture` |
| Largest Contentful Paint (overview, broadband, warm API) | 2.5 s or less |
| Interaction to Next Paint | 200 ms or less |
| Cumulative Layout Shift | 0.1 or less (fonts use size-adjusted fallbacks, skeletons match layouts) |
| Graph with 500 nodes and 800 edges | Pan and zoom at 30 frames per second or better on a mid-range laptop. `onlyRenderVisibleElements` on, memoised nodes, layout computed once. |
| Table of 50 rows | Renders in under 100 ms after data arrives |
| Search input | Debounced 250 ms, client-side search never blocks typing |

### 11.2 Security

- No secret in the bundle or in `VITE_` variables. Only public configuration (INV-09). A build scan fails on key-like strings.
- Tokens are handled only by Amplify. Nothing else reads or stores them (INV-10). The app does not render, log or send tokens anywhere except the `Authorization` header of API calls.
- Anything the API returns is rendered as text. There is no `dangerouslySetInnerHTML`. Links from data are validated (`https` and an allowed host) before rendering.
- `returnTo` accepts only same-origin relative paths.
- Content Security Policy and response headers are set at CloudFront (§13.4).
- Source maps are not served publicly.
- Uploaded content and presigned URLs are never persisted or logged (INV-09, §9.8).
- `utils/redact.ts` masks token-like and key-like strings in anything shown from audit metadata or evidence, as a second line of defence behind the backend's redaction.

### 11.3 Browser support

The latest two versions of Chrome, Edge, Firefox and Safari. No Internet Explorer.

### 11.4 Observability

Errors carry the `requestId` from the API. In development the console reports contract mismatches with the failing path. The Spec defines no client telemetry endpoint, so none is built. If client error reporting is added later, it must redact request bodies, tokens and URLs, and it needs a contract.

### 11.5 Resilience

A failed request affects only its region of the page. Chart, graph and drawer each have their own boundary. Polling stops when a tab is hidden. Aborted navigation cancels in-flight requests.

---

## 12. Test and acceptance plan

### 12.1 Layers

| Layer | Tooling | Covers |
|---|---|---|
| Unit | Vitest | `utils/*`, `apiClient` (token attach, 401 retry once, error mapping, non-envelope bodies), `uploadClient`, schema parsing, filter and URL-state parsing |
| Component | Vitest and Testing Library, against MSW scenarios | Every page in each state: loading, empty, partial, error, success, not enabled |
| Contract | Vitest | Every fixture parses against its schema. Nightly: live dev-stack responses parse against the schemas. |
| End to end | Playwright against the mock scenarios, and a smaller suite against the dev stack | Journeys in §12.3 |
| Accessibility | `axe-core` in component and end-to-end runs, plus a manual keyboard and screen-reader pass | WCAG 2.2 AA |
| Performance | Bundle analyser and Lighthouse in CI, graph profile | §11.1 |
| Boundaries | ESLint rules and the build scans | §5.3 |

### 12.2 The Spec's frontend checklist [SPEC §17], mapped to tests

| Spec item | Test |
|---|---|
| Every page has loading, empty, partial, error and success states | Component test per page per scenario (§7.8 scenarios) |
| Expired or invalid session routes to sign-in and does not loop forever | Unit test of the `401` path (one refresh, then end session). Playwright: expired token ends on `/login` once, and a failed callback shows the message without redirecting again. |
| Search, filter, sort and pagination are driven by API response and query parameters | Component tests assert the outgoing query string for each control, that changing a filter resets the cursor, and that unsupported controls read `Not enabled` |
| Graph handles empty data, unknown edge types, long names, truncation and failed requests | Component tests with fixtures for each |
| Upload displays validation, progress and processing failure | Component and Playwright tests with a mocked presigned `PUT` and a failing job |
| Approval buttons disable during submission and stale requests show a conflict message | Component test with a delayed response and a `409` |
| The UI never displays `100% compliant` with no successful evaluation | Component test on `conformance.percent: null`, plus a string search in the page's rendered output |
| `401`, `403`, `400`, `404`, `409`, `429`, `5xx` are handled as in §9.4 | Unit and component tests per status |

The API-only and AWS-behaviour checks in Spec §17 belong to the backend. The frontend verifies that what they produce is displayed correctly.

### 12.3 End-to-end journeys

| ID | Journey | Mode |
|---|---|---|
| J1 | Deep link to `/findings/abc` while signed out, sign in, land on `/findings/abc` | Dev stack and mock |
| J2 | New account: Overview shows `Not evaluated yet`, empty charts, and a `Run evaluation` action | Mock |
| J3 | `Run evaluation`, watch the job reach `SUCCEEDED`, see the new finding in Findings and the changed node in the Explorer | Dev stack |
| J4 | Open a finding, `Acknowledge`, see the status change and the timeline entry | Dev stack |
| J5 | Explorer: switch views, filter, search, select a node and an edge, open the Evidence tab | Mock and dev stack |
| J6 | Upload an ADR, see processing, review constraints, approve with the confirmation dialog | Dev stack |
| J7 | Request remediation, reject it with a reason, see the sequence in Audit Trail | Dev stack |
| J8 | Session expiry mid-use: one refresh attempt, then a clean return to sign-in | Mock |
| J9 | Error states: `403`, `404`, `409`, `429`, `5xx` on representative pages | Mock |

### 12.4 Contract tests

- Every file in `api/mocks/fixtures/` parses against its schema in CI (a failing fixture fails the build).
- The nightly job calls the dev stack with a service test user, validates every endpoint's response against the schemas, and reports the endpoint and field path of any mismatch.

### 12.5 Pull-request checklist

A reviewer confirms, for each pull request:

- [ ] INV-01 to INV-22 are not violated (the automated rules pass, and the reviewer has looked at the rest).
- [ ] No hard-coded operational value or fake success path.
- [ ] No new control that advertises an action without an endpoint.
- [ ] Types, schemas and fixtures change together for any contract change.
- [ ] Loading, empty, partial and error states exist for any new data view.
- [ ] Nothing on the blocklist in §6.11.
- [ ] Keyboard path and accessible names verified for any new interactive element.
- [ ] No new dependency without a reason in the pull request.

### 12.6 Definition of done for a screen

The screen is built from real contract fields, has all required states, passes the component, accessibility and end-to-end checks in its scope, meets §11.1, uses only the tokens and components in §6, and its acceptance criteria in §8 pass.

---

## 13. Configuration and deployment

### 13.1 Environment variables

All values are public, shipped to the browser, and contain no secrets [SPEC §5]. `.env.example` is committed. `.env` is not.

| Variable | Example | Purpose | Source |
|---|---|---|---|
| `VITE_APP_ENV` | `development` | Build environment (`development`, `staging`, `production`) | Spec |
| `VITE_API_BASE_URL` | `https://YOUR_API_ID.execute-api.YOUR_REGION.amazonaws.com` | API origin | Spec |
| `VITE_AWS_REGION` | `YOUR_REGION` | Cognito and display Region | Spec |
| `VITE_COGNITO_USER_POOL_ID` | `YOUR_USER_POOL_ID` | User pool | Spec |
| `VITE_COGNITO_CLIENT_ID` | `YOUR_PUBLIC_APP_CLIENT_ID` | Public app client | Spec |
| `VITE_COGNITO_DOMAIN` | `YOUR_DOMAIN.auth.YOUR_REGION.amazoncognito.com` | Managed-login domain | Added (CC-02) |
| `VITE_COGNITO_REDIRECT_SIGN_IN` | `http://localhost:5173/login` | OAuth return URL | Added |
| `VITE_COGNITO_REDIRECT_SIGN_OUT` | `http://localhost:5173/login` | Sign-out return URL | Added |
| `VITE_DEPLOYMENT_MODE` | `demo` | Shows `DEMO` or `LIVE` in the sidebar chip | Added |
| `VITE_USE_MOCKS` | `false` | Development-only mock mode. Must be `false` in production builds. | Spec §14 M2 |
| `VITE_FEATURES` | `evaluations,architecture` | Enabled capabilities (§10.4) | Added |
| `VITE_PRIVACY_URL`, `VITE_HELP_URL` | optional | Links in Settings. Hidden when empty. | Added |

The app version shown in the sidebar footer comes from `package.json` at build time.

`config/env.ts` validates all of these at start-up. A missing or malformed value shows the config error screen (§5.8) naming the variable.

### 13.2 Scripts

`dev`, `build`, `preview`, `typecheck`, `lint` (includes boundary rules), `test`, `test:contract`, `e2e`, `analyze` (bundle size), `scan` (post-build secret and mock scan).

### 13.3 Hosting [SPEC §14 M6, §10]

- Static assets in a **private** S3 bucket behind CloudFront with Origin Access Control. The bucket is never public.
- **SPA fallback:** CloudFront custom error responses map `403` and `404` from the origin to `/index.html` with status `200`, so a refresh on `/findings/abc` works. Use a short error-caching TTL.
- Caching: `index.html` is served `no-cache`. Files under `/assets/` are content-hashed and served `public, max-age=31536000, immutable`.
- Deploy order: upload hashed assets first, then `index.html`, then invalidate `/index.html`.
- Both the local origin and the CloudFront origin are registered in Cognito and in API CORS (BE-01, BE-04).

### 13.4 Security headers (CloudFront response headers policy)

A starting policy. Verify it in staging, because React Flow and Recharts set inline `style` attributes.

```text
Content-Security-Policy:
  default-src 'self';
  script-src 'self';
  style-src 'self';
  style-src-attr 'unsafe-inline';
  img-src 'self' data:;
  font-src 'self';
  connect-src 'self'
    https://<api-id>.execute-api.<region>.amazonaws.com
    https://<cognito-domain>
    https://cognito-idp.<region>.amazonaws.com
    https://*.s3.<region>.amazonaws.com
    https://s3.<region>.amazonaws.com;
  frame-ancestors 'none';
  base-uri 'self';
  object-src 'none';
  form-action 'self'
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
```

### 13.5 CI pipeline

1. Install with a frozen lockfile.
2. Typecheck, lint (including boundaries), unit and component tests, fixture contract tests.
3. Build. Fail if `VITE_USE_MOCKS=true` in a production build.
4. Post-build scan for mock code, MSW and secret-like strings in `dist/`.
5. Bundle-size check against §11.1.
6. End-to-end suite on the mock scenarios, with accessibility checks.
7. On the main branch: deploy to the demo stack (§13.3) and run the dev-stack journeys.

---

## 14. Delivery plan

The order follows Spec §14. Dates are not set here because the Spec sets none.

### Milestone 1: agree the contract and make the UI run (no AWS) [P0]

Frontend work, in order:

1. Repository, tooling, boundary rules, tokens, fonts.
2. `AppShell`, `Sidebar`, `TopBar`, route table, not-found.
3. `apiClient`, schemas, fixtures from the Spec's JSON examples, MSW handlers, scenario switcher.
4. Common components and `StateBoundary` (loading, empty, error, partial, not enabled).
5. Findings list and detail, Overview.
6. Architecture Explorer (all three views from fixtures).
7. Intents, Drift Events, Remediation, Audit Trail, Settings.
8. Accessibility, responsive and test pass. `docs/CONTRACT.md`. The OCI register (§16) is handed to the backend.

**Exit [SPEC]:** every route renders, all states are represented, and components consume the agreed API client rather than hard-coded page data.

### Milestone 2: API Gateway, Lambda, Cognito [P0]

Replace mocks for login, overview, findings and status. Flags on: none beyond the always-on endpoints (1 to 5). Settings read-only. CORS verified from localhost and the deployed origin.

**Exit [SPEC]:** an authenticated user loads real backend data, unauthenticated requests to protected routes are denied, and CORS works from localhost and the deployed frontend origin.

### Milestone 3: first real AWS inventory and deterministic detection [P0]

Flags on: `architecture`, `evaluations`, `findings.update`. Connect the Explorer, job progress and Finding detail to live data.

**Exit [SPEC]:** run inventory and evaluation, see real resource metadata, and demonstrate a controlled change that creates a finding. The graph shows live backend nodes and edges, not fixtures (AC-ARC-01).

### Milestone 4: intent upload and version review, event-driven updates [P1]

Flags on: `intents`, `intents.upload`, `driftEvents`, and `intents.approve` and `intents.diff` once OCI-09 is closed. Upload, processing job, review and approval, drift timeline, graph diff mode against an approved version.

**Exit [SPEC]:** an approved intent is versioned, and a live state change triggers or can be followed by an evaluation against that version.

### Milestone 5: Bedrock explanations and human-gated response [P1]

Flags on: `remediation`, `auditTrail`, and `explanations.generate`, `remediation.detail`, `remediation.cancel` once OCI-10 and OCI-11 are closed. Explanation panel, remediation request, approve and reject, audit trail.

**Exit [SPEC]:** a finding can be investigated, a remediation requested, approval or rejection recorded, and the whole sequence appears in the audit trail. No task token or unrestricted AWS permission reaches the browser (INV-09, INV-15).

### Milestone 6: deployment and hardening [P2]

CloudFront and private S3 with SPA fallback, CSP and headers, CORS with explicit origins, sanitised logging, end-to-end tests against the dedicated demo stack, bundle and accessibility budgets met.

---

## 15. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Contract drift between frontend and backend | Screens break or show wrong data | One contract in the repository, zod schemas, shared fixtures, nightly contract test, same-pull-request rule (§10.3) |
| Open contract items answered late | Pages stay `Not enabled` | OCIs ranked by milestone, with a stated fallback for each (§16). Backend sees the list at the end of M1. |
| Graph slows down or becomes unreadable on large data | The signature screen fails | Server-side limits, `onlyRenderVisibleElements`, memoised nodes, filters, `ResourceList`, a profile in CI (§11.1) |
| Dagre layout is weak for dense graphs | Overlap and tangles | Layout isolated in `utils/graph.ts`. The engine can be swapped (for example ELK) without touching components. |
| Authentication loops or silent token problems | Users locked out | One token strategy, one retry, a loop guard, explicit failure states (§7.4) |
| CORS or gateway error responses without CORS headers | Opaque network errors instead of statuses | BE-01 and BE-02 verified from a browser at each milestone |
| Over-design against the Spec | Identity work contradicts a Spec rule | The fixed-versus-free matrix (§6.2) and the blocklist (§6.11) are review gates |
| Unconfirmed font packages | Fallback look | Named fallbacks (§6.4). Fonts are a single token change. |
| Scope creep beyond the narrow first version | Missed demo | Spec §18 order is kept. P2 items stay P2. |
| "Not enabled" labels clutter a live demo | Looks unfinished | Capability flags are switched on as each endpoint is verified, and the demo environment sets only verified flags |
| Presigned upload blocked by S3 CORS | Upload fails in the browser only | BE-09 verified in the dev stack in M4 before the dialog is built against it |

---

## 16. Open Contract Items (OCI) for the backend

Each item states what the frontend needs, a proposal, and what the frontend does until it is closed. Proposals are **[PROPOSED]**: the backend may choose a different shape if the contract, fixtures and schemas are updated with it.

| ID | Topic | Frontend needs | Proposal [PROPOSED] | Fallback until closed | Needed by |
|---|---|---|---|---|---|
| OCI-01 | Bearer token type | Which Cognito token the authorizer accepts | Send the **access token**. Authorizer audience is the app client ID. | Access token | M2 |
| OCI-02 | Managed-login configuration | Domain, scopes, callback and logout URLs | Public client with PKCE, scopes `openid email profile`, callbacks `…/login` for localhost and CloudFront | Block on this for real login | M2 |
| OCI-03 | `/v1/system/status` payload | A full response shape | See §16.1 | Pill shows `Checking`, then `Disconnected` on failure | M2 |
| OCI-04 | `/v1/jobs/{jobId}` payload and the `PROCESSING` status | A response shape and one set of statuses | See §16.1. Ingest returns `QUEUED` or `RUNNING`, or `PROCESSING` is added to `JobStatus`. | Unknown statuses are in progress | M2 |
| OCI-05 | Dashboard summary additions | An explicit not-evaluated flag, the denominator definition, open-state list, evaluator status, source codes `NEEDS_SETUP` and `ERROR`, an optional `region` parameter | See §16.1 | Derive not-evaluated from `conformance.percent === null`. Evaluator and errors from `/v1/system/status`. | M2 |
| OCI-06 | Findings query | `q`, date ranges, `sort`, multi-value `severity` and `status`, a default newest-first order, the open-state list, optional `expectedSummary` and `observedSummary` | `q`, `firstSeenFrom`, `firstSeenTo`, `lastSeenFrom`, `lastSeenTo` (ISO dates), `sort` = `SEVERITY`, `NEWEST`, `OLDEST`, `UPDATED`, comma-separated multi-values | Search over loaded results (captioned). Sort and date range `Not enabled`. | M2 |
| OCI-07 | Finding detail additions | `whyItMatters`, path relation labels, related findings, confidence with definition, `ruleId`, evidence `consoleUrl`, `allowedActions` | See §16.1 | `description` for why it matters. `intent.constraintId` as the rule. Related findings and confidence hidden. | M3 |
| OCI-08 | Graph additions | Highest severity per node and edge, `arn`, `tags`, `lastObservedAt`, edge intended and live status, explanation text, `source` values, collected relationship types, an empty-state field, and the meaning of `state` in `INTENDED` and `LIVE` views | See §16.1 | `CHANGED` uses the `sev-high` outline. Missing fields show `Not provided by the API`. Neutral styling in `INTENDED` and `LIVE` (CC-27). | M3 |
| OCI-09 | Intents | Approve-version endpoint, version list and shape, diff endpoint, per-constraint review, source-type codes, upload limits, a rationale field, `q` search | See §16.1 | `Review and approve` and diff read `Not enabled`. Codes `TERRAFORM`, `CLOUDFORMATION`, `ADR`, `MANIFEST` assumed. | M4 |
| OCI-10 | Remediation | List item and detail shapes, status set and tab mapping, multi-status filter, detail endpoint, cancel endpoint | See §16.1 | Statuses shown humanised. Detail uses list fields. `Cancel request` hidden. | M5 |
| OCI-11 | Explanation generation | An endpoint and status values | `POST /v1/findings/{id}/explanation`, statuses `NOT_GENERATED`, `PENDING`, `GENERATED`, `FAILED`, `NOT_ENABLED` | `Generate explanation` hidden | M5 |
| OCI-12 | Audit events | Row shape and filters (`actor`, `result`, `target`) | See §16.1 | Filters beyond `from`, `to`, `action` read `Not enabled` | M5 |
| OCI-13 | Drift events | `processingStatus` values, detail fields, filters | Values `UNPROCESSED`, `PROCESSED`, `FAILED`. Filters `resourceType`, `processingStatus`, `actor`, `from`, `to`. | Unknown values humanised. Extra filters `Not enabled`. | M4 |
| OCI-14 | Authorization hints | Whether the caller may acknowledge, suppress, approve or reject | Per-resource `allowedActions: string[]` computed by the server (preferred), or `GET /v1/me` | Show actions, handle `403` | M2 |
| OCI-15 | Error contract | A code registry, envelope on gateway errors, `Retry-After` exposed | `VALIDATION_ERROR` (400), `UNAUTHENTICATED` (401), `FORBIDDEN` (403), `NOT_FOUND` (404), `STATE_CONFLICT` (409), `RATE_LIMITED` (429), `INTERNAL_ERROR` (5xx), `UPSTREAM_UNAVAILABLE` (502, 503), `FEATURE_NOT_ENABLED` | Codes derived from the HTTP status | M2 |
| OCI-16 | Upload limits and CORS | Allowed extensions and content types, maximum size and file count, S3 CORS for `PUT` | Frontend defaults in `config/constants.ts`: `.tf`, `.tf.json`, `.yaml`, `.yml`, `.json`, `.template`, `.md`, `.txt`. 1 MB per file, 5 files. State and variable files rejected. | Defaults apply. The server is the authority. | M4 |
| OCI-17 | Settings data | Evaluation settings, schedule state, doc links | `GET /v1/settings` (read-only) | `Not enabled` for each item | M5 |
| OCI-18 | Pagination details | Maximum `limit`, cursor lifetime, behaviour when filters change | Max 50. A cursor is valid only with the filters it came from. | 25 and 50 offered, a `400` falls back to 25 | M2 |
| OCI-19 | Notifications | No endpoint exists | None needed for the MVP | Client-derived activity menu (§7.6) | n/a |
| OCI-20 | Trend date semantics | Whether `findingTrend[].date` is a UTC day | UTC day | Displayed as returned, labelled `UTC days` | M2 |

### 16.1 Proposed shapes

All use the Spec's envelope (`data`, `meta`). Only the `data` part is shown.

**`GET /v1/system/status`** (OCI-03)

```json
{
  "state": "DEGRADED",
  "generatedAt": "2026-10-11T06:00:00Z",
  "sources": [
    { "source": "AWS_CONFIG", "status": "CONNECTED", "lastSuccessAt": "2026-10-11T05:45:00Z", "message": null },
    { "source": "CLOUDTRAIL", "status": "ERROR", "lastSuccessAt": "2026-10-11T04:10:00Z", "message": "CloudTrail lookup failed. Actor details may be missing." },
    { "source": "BEDROCK", "status": "NOT_ENABLED", "lastSuccessAt": null, "message": "AI explanations are not enabled in this environment." }
  ],
  "evaluator": { "status": "CONNECTED", "version": "1.0.0", "lastSuccessAt": "2026-10-11T05:50:00Z" },
  "lastInventoryAt": "2026-10-11T05:45:00Z",
  "lastEvaluationAt": "2026-10-11T05:50:00Z",
  "lastErrorAt": "2026-10-11T05:55:00Z",
  "errorSummary": "CloudTrail lookup failed. Actor details may be missing."
}
```

`state` is one of `CONNECTED`, `DEGRADED`, `DISCONNECTED` (Spec `SystemState`). `status` is one of `CONNECTED`, `NEEDS_SETUP`, `ERROR`, `NOT_ENABLED`.

**`GET /v1/jobs/{jobId}`** (OCI-04)

```json
{
  "jobId": "job_01JDEMO",
  "type": "EVALUATION",
  "status": "RUNNING",
  "progressStage": "Evaluating constraints",
  "startedAt": "2026-10-11T06:00:02Z",
  "completedAt": null,
  "resultSummary": null,
  "errorMessage": null,
  "relatedIntentId": null
}
```

When terminal, `resultSummary` is `{ "resourcesEvaluated": 24, "findingsCreated": 1, "findingsResolved": 0, "warnings": [] }`. `type` is `EVALUATION` or `INTENT_INGEST`. `status` is one of the Spec's five values.

**Dashboard summary additions** (OCI-05)

```json
{
  "state": "NOT_EVALUATED",
  "openStates": ["OPEN", "ACKNOWLEDGED", "IN_PROGRESS"],
  "conformance": { "percent": null, "passing": 0, "evaluated": 0, "definition": "Share of evaluated resources with no open violation." }
}
```

`state` is `NOT_EVALUATED` or `EVALUATED`.

**Finding detail additions** (OCI-07)

```json
{
  "whyItMatters": "Application tiers should not be reachable from the internet side of the database.",
  "ruleId": "NET-DB-01",
  "path": [
    { "nodeId": "resource_web", "label": "Web entry", "resourceType": "AWS::CloudFront::Distribution",
      "relationToNext": { "label": "routes to", "relationshipType": "ROUTES_TO" } }
  ],
  "relatedFindings": [ { "findingId": "finding_01JDEMO2", "title": "…", "severity": "MEDIUM", "status": "OPEN" } ],
  "confidence": { "value": 0.92, "definition": "Share of required evidence fields present." },
  "evidence": [ { "evidenceId": "evidence_config_001", "consoleUrl": "https://console.aws.amazon.com/…" } ],
  "allowedActions": ["ACKNOWLEDGE", "REQUEST_REMEDIATION"]
}
```

**Graph additions** (OCI-08)

```json
{
  "state": "READY",
  "message": null,
  "collectedRelationshipTypes": ["NETWORK_ACCESS", "ROUTES_TO", "USES_ROLE"],
  "nodes": [
    { "id": "resource_db", "highestSeverity": "HIGH", "arn": "arn:aws:rds:…", "tags": { "tier": "data" },
      "lastObservedAt": "2026-10-11T05:45:00Z", "explanation": "Observed ingress differs from the approved constraint.",
      "source": "LIVE_AND_INTENT" }
  ],
  "edges": [
    { "id": "edge_app_db", "severity": "HIGH", "intendedStatus": "PRESENT", "liveStatus": "PRESENT",
      "explanation": "Observed rule allows a source outside the approved set." }
  ]
}
```

`state` is `READY`, `NO_INTENT`, `NO_INVENTORY` or `NOT_EVALUATED`. `source` is `LIVE_AND_INTENT`, `LIVE_ONLY` or `INTENT_ONLY`. `intendedStatus` and `liveStatus` are `PRESENT`, `ABSENT` or `UNKNOWN`.

**Intents** (OCI-09)

```text
POST /v1/intents/{intentId}/versions/{version}/approve   body: { "comment": "…" }
  200 -> { "intentId": "intent_123", "version": "v4", "status": "APPROVED", "approvedAt": "…" }
  409 STATE_CONFLICT when the version is not awaiting review
GET  /v1/intents/{intentId}/versions/{version}/diff?against=approved
  -> { "added": [Constraint], "removed": [Constraint], "changed": [{ "before": Constraint, "after": Constraint }] }
GET  /v1/intents/{intentId}   adds: "versions": [
  { "version": "v4", "status": "NEEDS_REVIEW", "createdAt": "…", "createdBy": "…", "constraintCount": 7,
    "sourceFiles": [ { "fileName": "architecture-adr.md", "sizeBytes": 12000, "contentType": "text/markdown" } ] } ]
```

Intent statuses: `DRAFT`, `PROCESSING`, `NEEDS_REVIEW`, `APPROVED`, `FAILED`.

**Remediation** (OCI-10)

```text
List item: { "remediationId": "rem_123", "status": "PENDING_APPROVAL", "dryRun": true, "findingId": "finding_01JDEMO",
  "runbookId": "REVOKE_UNAPPROVED_INGRESS_V1",
  "target": { "resourceId": "sg-0123456789abcdef0", "resourceType": "AWS::EC2::SecurityGroup", "arn": null },
  "requestedBy": "…", "requestedAt": "…", "impact": "…", "riskLevel": "MEDIUM" }
GET /v1/remediations/{id}  adds: "parameters": {…}, "riskNote": "…", "dryRunOutput": {…} | null,
  "timeline": [ { "timestamp": "…", "action": "…", "actor": "…", "message": "…" } ],
  "allowedActions": ["APPROVE", "REJECT", "CANCEL"]
POST /v1/remediations/{id}/cancel   body: { "comment": "…" }
Statuses: PENDING_APPROVAL, APPROVED, IN_PROGRESS, COMPLETED, REJECTED, FAILED, CANCELLED
Tabs: Pending approval = PENDING_APPROVAL; In progress = APPROVED, IN_PROGRESS; Completed = COMPLETED;
      Rejected / failed = REJECTED, FAILED, CANCELLED. Multi-value: ?status=REJECTED,FAILED,CANCELLED
```

**Audit event** (OCI-12)

```json
{
  "auditId": "audit_01JDEMO",
  "timestamp": "2026-10-11T06:10:00Z",
  "actor": { "id": "user-sub", "displayName": "A. Rao" },
  "action": "FINDING_ACKNOWLEDGED",
  "target": { "type": "FINDING", "id": "finding_01JDEMO", "label": "Unexpected network path to private database" },
  "result": "SUCCESS",
  "requestId": "req_123",
  "metadata": { "comment": "Investigating with the platform team." }
}
```

`result` is `SUCCESS`, `FAILURE` or `DENIED`. `metadata` must be pre-redacted by the backend.

---

## Appendix A. Copy deck

Strings marked **[SPEC]** are quoted from the Spec. Others follow the voice rules in §6.10. Strings live in `utils/labels.ts` and the feature folders, so wording stays consistent.

### A.1 Action vocabulary (a verb keeps its name from button to toast)

| Button [SPEC unless noted] | Toast after a successful response |
|---|---|
| `Run evaluation` | `Evaluation queued`. At completion: `Evaluation finished`, `Evaluation finished with partial results`, or `Evaluation failed` |
| `View architecture` | none |
| `Acknowledge` | `Finding acknowledged` |
| `Request remediation` | `Remediation requested for approval` |
| `Approve` | `Request approved` |
| `Reject` | `Request rejected` |
| `Cancel request` | `Request cancelled` |
| `Upload IaC / ADR` | `Upload complete`, then processing status on the page |
| `Review and approve` (opens the dialog), `Approve version` (confirms) | `Intent version approved` |
| `Generate explanation` | `Explanation requested` |
| `Fit graph`, `Reset layout`, `Clear filters`, `Retry`, `Refresh`, `Sign in`, `Sign out`, `Try again` | none |

### A.2 Labels

| Code | Text |
|---|---|
| Severity | Critical, High, Medium, Low, Info |
| Finding status | Open, Acknowledged, In progress, Resolved, Suppressed |
| Finding category (display text comes from `categoryLabel`) | Network path, Identity & permissions, Public exposure, Missing resource, Configuration drift, Other |
| Intent status | Draft, Processing, Needs review, Approved, Failed |
| Source status | Connected, Needs setup, Error, Not enabled |
| System state | Connected, Degraded, Disconnected |
| Job status | Queued, Running, Succeeded, Partial, Failed |
| Diff state on the canvas | none (Matched), Unmatched, Missing, Changed, Unknown |
| Graph view | Intended, Live, Differences |
| Remediation tabs | Pending approval, In progress, Completed, Rejected / failed |

### A.3 Empty, partial and error copy

| Where | Text |
|---|---|
| Overview, no evaluation | `Not evaluated yet` |
| Overview, charts without history | `No history yet. Run an evaluation to start the trend.` |
| Overview, partial | `{Region name} could not be loaded.` plus `Retry` |
| Findings, none | `No findings.` plus the hint to run an evaluation |
| Findings, filtered empty | `No findings match these filters.` plus `Clear filters` |
| Findings, forbidden | `You do not have access to findings.` |
| Finding, not found | `This finding does not exist or was removed.` |
| Architecture, empty | `No resources observed yet. Run an evaluation to take the first inventory.` |
| Architecture, no intent | `No approved intent yet. Upload and approve an intent to compare against.` |
| Architecture, relationship | `Not collected` |
| Architecture, truncated | `Showing the first {n} resources. Narrow the filters to see the rest.` |
| Intents, none | `No intents yet. Upload an IaC file or an ADR to create the first one.` |
| Drift, none | `No configuration changes observed yet.` |
| Remediation, none | `No requests are waiting for approval.` |
| Remediation, dry run | `Dry run: no change will be made in AWS.` |
| Audit, none | `No audit events match.` |
| Feature off | `Not enabled` and `This part of the product is not enabled in this environment.` |
| Session expired | `Your session expired. Sign in again to continue.` |
| Network | `Could not reach the API.` |
| Permission | `You do not have permission to do this.` |
| Conflict | `This item was already changed by someone else. Refresh to see its current state.` |
| Rate limit | `Too many requests. Try again in {n} seconds.` |
| Server | `The server could not complete the request.` |
| Contract | `The server sent data this version of the app does not understand.` |
| Page not found | `Page not found`. `The address does not match a page in this application.` plus `Go to Overview` |
| AI panel | `AI-assisted explanation`, `Not generated`, `This explanation is advisory. Check it against the evidence.` |

---

## Appendix B. Traceability: Spec to PRD

| Spec | Subject | PRD | Status |
|---|---|---|---|
| §0 | Decisions, MVP assumptions, AWS-connected | §1, §4, §10 | Covered |
| §1 | Visual direction, layout, global frame, connection banner | §6, §7.2, §7.3 | Covered (CC-14, CC-19, CC-24, CC-25) |
| §2 | Route map, SPA refresh | §7.1, §13.3 | Covered (CC-15) |
| §3.1 | Overview | §8.2 | Covered (CC-05, CC-11, CC-16, CC-20, CC-23) |
| §3.2 | Architecture Explorer | §8.3, §6.5, §6.6 | Covered, with contract additions (CC-08, CC-27) |
| §3.3 | Findings list | §8.4 | Covered, with contract additions (CC-10) |
| §3.4 | Finding detail | §8.5 | Covered, with contract additions (CC-09) |
| §3.5 | Intent & Policies | §8.6, §8.7 | Covered, with contract additions (CC-06, CC-26) |
| §3.6 | Drift Events | §8.8 | Covered (CC-28) |
| §3.7 | Remediation | §8.9 | Covered (CC-07, CC-21) |
| §3.8 | Audit Trail | §8.10 | Covered (CC-28) |
| §3.9 | Settings | §8.11 | Covered (CC-12) |
| §4 | Shared behaviour: states, dates, accessibility, caching | §5.6, §7.5 to §7.10, §9.3, §9.5 | Covered |
| §5 | Authentication, request flow, env, `apiClient`, envelope | §7.4, §9.1, §13.1 | Covered (CC-01, CC-02, CC-22) |
| §6.1 to §6.12 | API endpoints | §9.2, Appendix C | Covered, with gaps tracked in §16 (CC-03, CC-04) |
| §7 to §11 | Backend architecture, persistence, IAM, evaluation logic | §10.2 (what the UI needs) | Backend-only. Nothing for the frontend to build. |
| §12 | Frontend repository structure | §5.4, §5.5 | Covered, additions only |
| §13 | Shared TypeScript types | Appendix C | Covered |
| §14 | Milestones | §14 | Covered |
| §15 | Ownership split | §1.3 | Covered |
| §16 | Pull-request and integration rules | §3, §10.3, §12.5 | Covered |
| §17 | Test checklist | §12.2 | Frontend items covered. API and AWS items are backend-owned. |
| §18 | Keep the first version narrow | §1.5, §14 | Covered |
| §19 | Official references | §13.3, §13.4 (CloudFront, CORS, JWT authorizer, Cognito managed login apply to the backend and deploy setup) | Informational |

---

## Appendix C. Contract types (frontend view)

These are the types in `api/apiTypes.ts`, inferred from the zod schemas. Names and fields follow the Spec's JSON examples (§6) and starter types (§13). Anything not in the Spec is marked `[PROPOSED]` and tracked in §16. All responses are wrapped in `ApiSuccess<T>`.

```ts
// ---- Spec §13, verbatim ----
export type Severity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFO";
export type FindingStatus = "OPEN" | "ACKNOWLEDGED" | "IN_PROGRESS" | "RESOLVED" | "SUPPRESSED";
export type GraphView = "INTENDED" | "LIVE" | "DIFF";
export type DiffState = "MATCHED" | "ADDED" | "MISSING" | "CHANGED" | "UNKNOWN";
export type JobStatus = "QUEUED" | "RUNNING" | "SUCCEEDED" | "PARTIAL" | "FAILED";
export type SystemState = "CONNECTED" | "DEGRADED" | "DISCONNECTED";

export interface ApiMeta { requestId: string; generatedAt: string; nextCursor?: string | null; limit?: number; }
export interface ApiSuccess<T> { data: T; meta: ApiMeta; }
export interface ApiFailure { error: { code: string; message: string; details?: unknown[]; requestId?: string; }; }

export interface GraphNode {
  id: string; label: string; resourceType: string; state: DiffState; source: string;
  region?: string; properties?: Record<string, unknown>; findingIds: string[];
}
export interface GraphEdge {
  id: string; source: string; target: string; label: string; relationshipType: string;
  state: DiffState; evidenceIds: string[]; findingIds: string[];
}

// ---- Shared ----
export interface AccountRef { id: string; alias: string | null; }
export type SourceKey = "AWS_CONFIG" | "CLOUDTRAIL" | "BEDROCK" | "FLOW_LOGS"; // first three in Spec §6.2; FLOW_LOGS [PROPOSED]
export type SourceStatusCode = "CONNECTED" | "NEEDS_SETUP" | "ERROR" | "NOT_ENABLED"; // CONNECTED, NOT_ENABLED in Spec; others [PROPOSED] OCI-05
export interface SourceStatus { source: SourceKey; status: SourceStatusCode; lastSuccessAt: string | null; message: string | null; }
export interface ResourceRef { resourceId: string; resourceType: string; name: string | null; region: string; arn?: string | null; }

// ---- GET /v1/dashboard/summary (Spec §6.2) ----
export interface DashboardSummary {
  account: AccountRef; region: string;
  lastInventoryAt: string | null; lastEvaluationAt: string | null;
  resourcesObserved: number;
  conformance: { percent: number | null; passing: number; evaluated: number; definition?: string }; // definition [PROPOSED]
  openFindings: number;
  severityCounts: Record<Severity, number>;
  pendingApprovals: number;
  findingTrend: Array<{ date: string } & Partial<Record<Severity, number>>>; // INFO optional; date is a UTC day (OCI-20)
  sourceStatus: SourceStatus[];
  state?: "NOT_EVALUATED" | "EVALUATED";   // [PROPOSED] OCI-05
  openStates?: FindingStatus[];            // [PROPOSED] OCI-05
}

// ---- GET /v1/findings (Spec §6.3) ----
export interface FindingsQuery {
  severity?: Severity; status?: FindingStatus; category?: string; resourceType?: string; limit?: number; cursor?: string;
  q?: string; firstSeenFrom?: string; firstSeenTo?: string; lastSeenFrom?: string; lastSeenTo?: string; // [PROPOSED] OCI-06
  sort?: "SEVERITY" | "NEWEST" | "OLDEST" | "UPDATED";                                                    // [PROPOSED] OCI-06
}
export interface FindingListItem {
  findingId: string; title: string; severity: Severity; status: FindingStatus;
  category: string; categoryLabel: string; resource: ResourceRef; summary: string;
  firstSeenAt: string; lastSeenAt: string; intentVersion: string; ruleId: string; remediationAvailable: boolean;
  expectedSummary?: string; observedSummary?: string; // [PROPOSED] OCI-06
}

// ---- GET /v1/findings/{findingId} (Spec §6.4) ----
export interface PathStep {
  nodeId: string; label: string; resourceType: string;
  relationToNext?: { label: string; relationshipType: string } | null; // [PROPOSED] OCI-07
}
export interface EvidenceItem {
  evidenceId: string; source: string; observedAt: string; description: string;
  fields: Record<string, unknown>; consoleUrl?: string | null; // consoleUrl [PROPOSED]
}
export type ExplanationStatus = "NOT_GENERATED" | "PENDING" | "GENERATED" | "FAILED" | "NOT_ENABLED"; // only NOT_GENERATED in Spec
export interface FindingDetail {
  findingId: string; title: string; severity: Severity; status: FindingStatus; category: string;
  description: string; resource: ResourceRef;
  intent: { intentId: string; version: string; constraintId: string; expected: string };
  observed: { summary: string; observedAt: string; source: string; evidenceIds: string[] };
  path: PathStep[]; evidence: EvidenceItem[];
  explanation: { status: ExplanationStatus; text: string | null; evidenceIds: string[] };
  remediation: { available: boolean; runbookId: string | null; reason: string | null };
  timeline: Array<{ timestamp: string; action: string; actor: string; message: string }>;
  firstSeenAt: string; lastSeenAt: string;
  whyItMatters?: string; ruleId?: string; relatedFindings?: Array<{ findingId: string; title: string; severity: Severity; status: FindingStatus }>;
  confidence?: { value: number; definition: string }; allowedActions?: string[]; // [PROPOSED] OCI-07, OCI-14
}
export interface PatchFindingRequest { action: "ACKNOWLEDGE" | "SUPPRESS" | "REOPEN"; comment?: string; } // Spec §6.5

// ---- GET /v1/architecture (Spec §6.6) ----
export interface ArchitectureData {
  view: GraphView; intentVersion: string | null; generatedAt: string; truncated: boolean;
  nodes: Array<GraphNode & {
    highestSeverity?: Severity | null; arn?: string | null; tags?: Record<string, string>;
    lastObservedAt?: string | null; explanation?: string | null;                       // [PROPOSED] OCI-08
  }>;
  edges: Array<GraphEdge & {
    severity?: Severity | null; intendedStatus?: "PRESENT" | "ABSENT" | "UNKNOWN";
    liveStatus?: "PRESENT" | "ABSENT" | "UNKNOWN"; explanation?: string | null;        // [PROPOSED] OCI-08
  }>;
  state?: "READY" | "NO_INTENT" | "NO_INVENTORY" | "NOT_EVALUATED"; message?: string | null;
  collectedRelationshipTypes?: string[];                                                // [PROPOSED] OCI-08
}

// ---- Intents (Spec §6.7, §6.8) ----
export type IntentStatus = "DRAFT" | "PROCESSING" | "NEEDS_REVIEW" | "APPROVED" | "FAILED"; // from the Spec's UI labels
export type SourceType = "ADR" | "TERRAFORM" | "CLOUDFORMATION" | "MANIFEST";              // only ADR in the Spec
export interface IntentListItem {
  intentId: string; name: string; status: IntentStatus; currentApprovedVersion: string | null;
  createdAt: string; updatedAt: string; uploadedBy: string; sourceFilesCount: number;
  constraintCount: number; errorMessage: string | null;
}
export interface Constraint {
  constraintId: string; title: string; kind: string; scope: { resourceTypes: string[] };
  expected: Record<string, unknown>; severity: Severity;
  sourceReference?: { fileName: string; lineStart?: number; lineEnd?: number };
  extractionConfidence: number; reviewStatus: string;
}
export interface UploadUrlRequest { fileName: string; contentType: string; sizeBytes: number; }
export interface UploadUrlResponse { uploadUrl: string; objectKey: string; expiresInSeconds: number; }
export interface IngestRequest { name: string; objectKeys: string[]; sourceType: SourceType; }
export interface IngestResponse { intentId: string; jobId: string; status: string; } // status "PROCESSING" in Spec; see CC-03

// ---- Jobs (Spec §6.9) ----
export interface StartEvaluationRequest { scope: "SUPPORTED_RESOURCES"; reason?: string; }
export interface StartEvaluationResponse { jobId: string; status: JobStatus; statusUrl: string; createdAt: string; }
export interface JobData { // fields named in Spec §6.9; payload shape [PROPOSED] OCI-04
  jobId: string; status: JobStatus | string; progressStage: string | null;
  startedAt: string | null; completedAt: string | null;
  resultSummary: Record<string, unknown> | null; errorMessage: string | null;
}

// ---- Drift events (Spec §6.10) ----
export interface DriftEvent {
  eventId: string; timestamp: string; source: string; resourceId: string; resourceType: string;
  changeSummary: string; actor: string | null; processingStatus: string; relatedFindingIds: string[];
  sourceEventId?: string | null; before?: Record<string, unknown> | null; after?: Record<string, unknown> | null; // [PROPOSED] OCI-13
}

// ---- Remediation (Spec §6.11) ----
export interface CreateRemediationRequest { mode: "REQUEST_APPROVAL"; comment?: string; }
export interface CreateRemediationResponse { remediationId: string; status: string; runbookId: string; dryRun: boolean; }
export interface DecisionRequest { decision: "APPROVE" | "REJECT"; comment?: string; }
// List item, detail and decision response shapes: [PROPOSED] OCI-10 (see §16.1).

// ---- Audit and system status (Spec §6.12) ----
// Audit event row and system status payload: [PROPOSED] OCI-12, OCI-03 (see §16.1).
```

The frontend does not read the body of `PATCH` or decision responses beyond the envelope. After a successful mutation it refetches the affected queries (§9.3), so those response shapes can evolve without breaking the UI.
