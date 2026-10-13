# AGENTS.md — Cloud Intent Guardian Frontend

> This file is the authoritative instruction set for any AI coding agent (Copilot, Antigravity, Claude, etc.)
> working in this repository. Every rule here is grounded in the
> **Cloud Intent Guardian Frontend PRD v1.0** ("the PRD") and, by extension, in the
> **Cloud Intent Guardian Implementation Spec** ("the Spec") which the PRD defers to.
>
> Read this file **in full** before writing or modifying any code. Where a rule conflicts
> with general best practice, this file wins.

---

## 0. Project snapshot

| Field | Value |
|---|---|
| Product | Cloud Intent Guardian (CIG) |
| Repo type | React single-page application (frontend only) |
| Stack | React 18 + Vite + TypeScript (`strict: true`), Tailwind CSS, shadcn/ui, React Router (data router), TanStack Query, React Flow, Recharts |
| Auth | Amazon Cognito (Amplify Auth, Authorization Code + PKCE, managed-login) |
| API | REST over API Gateway, bearer access token, JSON envelope |
| PRD owner | Aritra |
| PRD version | 1.0 (2026-10-11) |

---

## 1. Non-negotiable invariants (INV-01 – INV-22)

These rules are **never** traded away for schedule, polish, or convenience.
Every pull request is checked against all 22 before merging.
An agent must refuse, or flag loudly, any instruction that would violate one.

| ID | Rule |
|---|---|
| **INV-01** | Only `src/api/` (and `src/api/uploadClient.ts`) may call `fetch`, `XMLHttpRequest`, or any HTTP library. No page, component, or hook does. ESLint enforces this. |
| **INV-02** | The frontend **never** invents successful data. If an API call fails, the UI shows an error or partial state, never a plausible-looking value. Mock data exists **only** in development, behind `VITE_USE_MOCKS=true`, with the visible `MockModeBanner`. |
| **INV-03** | `"Connected"` is shown **only** when `/v1/system/status` confirms the backend can read the configured AWS sources. API reachability alone is never enough. |
| **INV-04** | The UI never shows `100%` or `"compliant"` without a successful evaluation response. When `conformance.percent` is `null`, show `—` and `"Not evaluated yet"`. |
| **INV-05** | Severity is **never** expressed by colour alone. Every severity mark carries a **shape** (inline SVG, 12 px grid) **and** a **text label** (Critical / High / Medium / Low / Info). |
| **INV-06** | No diff, conformance, severity-derivation, or violation-path logic lives in React. The frontend renders `MATCHED`, `ADDED`, `MISSING`, `CHANGED`, `UNKNOWN` exactly as received. |
| **INV-07** | An edge is drawn only if the backend returned it. No edges or flows are inferred from resource names or types. `UNKNOWN` is never painted as a confirmed violation. |
| **INV-08** | A before-state is never fabricated. Drift events and evidence show only the fields the source provided. |
| **INV-09** | No secret reaches the browser or the logs: no AWS keys, no Bedrock keys, no Step Functions task tokens, no raw JWTs, no presigned URLs, no uploaded file contents. `VITE_` variables hold only **public** configuration. |
| **INV-10** | Tokens are handled by one strategy: **Amplify Auth** in `auth/authClient.ts`. Nothing else reads, stores, decodes, logs, or displays a token. |
| **INV-11** | A success toast appears **only** after the backend responds with a success code. Durable status on the page is the source of truth, not optimistic state. |
| **INV-12** | Mutating buttons are disabled while a request is pending. Double-submission is prevented. A stale or duplicate decision surfaces the server's `409` as a conflict message. |
| **INV-13** | Authorization is decided by the server. The browser **never** sends or trusts an `isAdmin`-style flag. |
| **INV-14** | A button or control that advertises an action exists **only** when the endpoint and behaviour exist. Otherwise it is hidden or labelled `"Not enabled"`. |
| **INV-15** | Remediation is dry-run or approval-gated, and is always labelled as such. A dry-run result is never worded as a real fix. There is no client-side switch for automatic remediation. |
| **INV-16** | Bedrock output is labelled `"AI-assisted explanation"`, shown with its cited evidence, and always carries the advisory: `"This explanation is advisory. Check it against the evidence."` It is never the authority for an AWS fact, and it never carries a sparkle icon or special accent colour. |
| **INV-17** | Audit entries are created by the backend only. The client has no code path that creates one. |
| **INV-18** | Timestamps are ISO 8601 UTC from the API, displayed in local time, with the timezone made explicit in detailed evidence panels. |
| **INV-19** | Lists are paginated with the **opaque cursor** from `meta.nextCursor`. The client never assumes the first page is complete and never fetches all records. |
| **INV-20** | The graph renders only the current, server-limited result set. The title block shows the resource count and a `"Truncated"` warning when `truncated` is `true`. A node click never triggers a full-account fetch. |
| **INV-21** | Users are **never** asked for AWS credentials. The upload dialog warns against including secrets. File contents are never rendered into logs. |
| **INV-22** | A breaking contract change (renamed field, removed field, changed meaning, removed route) updates types in `api/apiTypes.ts`, schemas in `api/schemas.ts`, fixtures in `api/mocks/fixtures/`, and backend tests **in the same pull request**. Both owners review it. |

---

## 2. Architecture and layer rules

The codebase is organised into strict layers. The diagram below shows the **only** allowed import directions. Any import not shown is forbidden and will fail CI.

```
app/          <- composition root: providers, router, bootstrap
  |
  v
features/     <- one folder per route (page container + URL state)
  |       |
  v       v
hooks/    components/   <- presentational only
  |           |
  v           v
api/ --> auth/     utils/   types/   config/
```

### Layer responsibilities

| Layer | Owns | May import | Must not |
|---|---|---|---|
| `types/` | Domain types, independent of React and transport | nothing | contain runtime code touching the network or DOM |
| `config/` | Validated env (`env.ts`), feature flags (`capabilities.ts`), constants | `types/` | be read by raw `import.meta.env` anywhere else |
| `utils/` | Pure functions: dates, severity ordering, labels, graph layout transform, redaction, URL helpers | `types/`, `config/` | import React, `api/`, or perform I/O |
| `auth/` | `authClient.ts` (the **only** file importing `aws-amplify`), `AuthProvider`, `ProtectedRoute` | `config/`, `types/` | be imported by `components/` |
| `api/` | `apiClient`, `endpoints`, `schemas` (zod), `queryKeys`, `errors`, `uploadClient`, dev-only `mocks/` | `auth/`, `config/`, `types/`, `utils/` | import React or any UI code |
| `hooks/` | TanStack Query bindings: one hook per endpoint or mutation, cache policy, polling, invalidation | `api/`, `types/`, `utils/`, `config/` | render UI or read the router |
| `components/` | Presentational components: props in, events out | `utils/`, `types/`, other `components/` | fetch, use query hooks, read the router, or know about endpoints |
| `features/` | Route-level containers: read URL state, call hooks, map results to component props, choose which state to show | `hooks/`, `components/`, `utils/`, `types/`, `config/` | import another feature or call `api/` directly |
| `app/` | Providers, route table, bootstrap | everything | contain page logic |

### Key structural rules

- **`AppShell`, `Sidebar`, `TopBar`, `ConnectionStatus`** are presentational under `components/layout/`. Their data-bound wrappers live in `features/shell/`.
- **Shared code between features** moves down into `components/`, `hooks/`, or `utils/`. Features never import each other.
- The **only** network code outside `api/apiClient.ts` is `api/uploadClient.ts` (presigned S3 PUT). It uses `XMLHttpRequest` for progress events and abort, and **never** attaches the `Authorization` header.

---

## 3. State management policy

| Kind of state | Where it lives | Examples |
|---|---|---|
| Server state | TanStack Query | Summary, findings, graph, intents, jobs |
| Shareable UI state | URL search parameters | Filters, sort, cursor, selected node/edge, tab, open drawer, `?job=`, `?version=` |
| Ephemeral UI state | `useState` / `useReducer` in the component or feature | Dialog open, form fields, hover |
| Cross-cutting client state | React context | Auth session, validated env, capabilities |
| Persisted client state | `sessionStorage` or `localStorage`, non-sensitive only | Graph node positions, preferred page size, `returnTo` path, IDs of jobs started in this session |

**Never persisted:** tokens (owned by Amplify), presigned URLs, uploaded content, evidence payloads.

---

## 4. API and contract conventions

### 4.1 `apiClient` usage

- All calls go through `src/api/apiClient.ts`.
- `apiClient` attaches the bearer **access token** (`authClient.getAccessToken()`).
- On `401`: one silent token refresh and one retry; if that also fails, clear the session and navigate to `/login`.
- On all other errors: throw a typed `ApiError` with `kind`, `code`, `message`, `requestId`, and `status`.
- On a zod parse failure: throw `ApiError` with `code: "CONTRACT_MISMATCH"` and the failing field path (in development only).

### 4.2 Query keys

Keys are built exclusively by `api/queryKeys.ts`. Never write a query key inline.

| Resource | Key pattern |
|---|---|
| Dashboard summary | `['dashboard-summary', region]` |
| Findings list | `['findings', filters]` |
| Finding detail | `['finding', findingId]` |
| Architecture graph | `['architecture', view, filters]` |
| Intents list | `['intents']` |
| Intent detail | `['intent', intentId]` |
| Drift events | `['drift-events', filters]` |
| Remediations | `['remediations', status]` |
| Remediation detail | `['remediation', id]` |
| Audit events | `['audit-events', filters]` |
| System status | `['system-status']` |
| Job | `['job', jobId]` |
| API health | `['api-health']` |

### 4.3 Mutation invalidation

After a mutation, invalidate **only** what it affects.

| Event | Keys to invalidate |
|---|---|
| Evaluation job terminal | `dashboard-summary`, `findings`, `finding`, `architecture`, `drift-events`, `system-status`, `audit-events` |
| `PATCH` finding | `['finding', id]`, `findings`, `dashboard-summary`, `architecture`, `audit-events` |
| Remediation request created | `['finding', id]`, `remediations`, `dashboard-summary`, `audit-events` |
| Remediation decision | `['remediation', id]`, `remediations`, `['finding', id]`, `dashboard-summary`, `audit-events` |
| Ingestion job terminal | `intents`, `['intent', id]`, `audit-events` |
| Intent version approved | `['intent', id]`, `intents`, `architecture`, `dashboard-summary`, `audit-events` |
| Refresh button | Current-page keys + `system-status` + `dashboard-summary` |
| Sign out | Clear entire cache |

**No optimistic updates** for status changes, approvals, or evaluations. Always wait for the server response.

### 4.4 Runtime validation (zod)

- Every API response is parsed by a zod schema in `api/schemas.ts`.
- Required fields must be present; their absence throws `CONTRACT_MISMATCH`.
- Extra fields are ignored (backend can add fields without breaking the UI).
- Open enumerations (`relationshipType`, `resourceType`, `processingStatus`, `source`, etc.) are typed as `string`. Unknown values render humanised, never as an error.
- Closed enumerations (`Severity`, `FindingStatus`, `DiffState`, `GraphView`) map unknown values to a safe neutral and emit a development-only `console.warn`.
- Fixtures in `api/mocks/fixtures/` are parsed against the same schemas in CI.

### 4.5 Error handling matrix

| HTTP status / condition | `kind` | `code` | User-facing treatment |
|---|---|---|---|
| Network failure / CORS / timeout | `network` | `NETWORK_ERROR` | `"Could not reach the API."` + Retry. Connection pill to Disconnected. |
| 400 | `validation` | `VALIDATION_ERROR` | Map `details` to form fields when present, else show message in dialog/page. |
| 401 | `auth` | `UNAUTHENTICATED` | One silent refresh + retry; then `/login` with session-expired message. |
| 403 | `forbidden` | `FORBIDDEN` | `"You do not have permission to do this."` Shown in place. Not a sign-out. |
| 404 | `not_found` | `NOT_FOUND` | Missing-resource state with a link back to the list. |
| 409 | `conflict` | `STATE_CONFLICT` | `"This item was already changed by someone else. Refresh to see its current state."` |
| 429 | `rate_limited` | `RATE_LIMITED` | `"Too many requests. Try again in n seconds."` Retry control disabled for that period. |
| 5xx | `server` | `INTERNAL_ERROR` | `"The server could not complete the request."` + requestId + Retry. GETs retry twice with backoff; mutations never retry automatically. |
| zod mismatch | `contract` | `CONTRACT_MISMATCH` | `"The server sent data this version of the app does not understand."` + requestId. |

Every error state must display the `requestId` (when available) in a `CopyableId` component.

---

## 5. Design system rules

### 5.1 Tokens

All colours, spacing, radius, and typography are defined once in `styles/index.css` (Tailwind v4 `@theme` block, or `tailwind.config` for v3). Components use **token names**, never raw hex or hardcoded pixel values.

Key colour tokens:

| Token | Hex | Role |
|---|---|---|
| `film` | `#F6F8FB` | Page background |
| `sheet` | `#FFFFFF` | Card and surface |
| `ink` | `#172033` | Primary text |
| `graphite` | `#5A677B` | Secondary text on `film` |
| `pencil` | `#68758A` | Secondary text on `sheet` only |
| `rule` | `#E2E8F0` | Borders and dividers |
| `prussian` | `#183B87` | Primary accent |
| `survey` | `#1B7A4B` | Connected / good |
| `sev-critical` | `#B42318` | Critical severity |
| `sev-high` | `#C2410C` | High severity |
| `sev-medium` | `#8A5A00` | Medium severity / warning text |
| `sev-low` | `#1F6C8C` | Low severity |
| `sev-info` | `#5A677B` | Info severity |

### 5.2 Typography

Three font families only. No others.

| Role | Family |
|---|---|
| Interface and body | Atkinson Hyperlegible Next (weights 400, 500, 600, 700) |
| Identifiers — ARNs, IDs, CIDRs, ports, rule IDs | Atkinson Hyperlegible Mono |
| Titles and large figures | Archivo variable (weight 600, `wdth` axis ~85) |

Fallback: IBM Plex Sans / IBM Plex Mono if the Atkinson packages are unavailable.
All fonts are **self-hosted** via `@fontsource`. No third-party font CDN.

Typography rules:

- Sentence case everywhere. No letter-spaced all-caps labels (the `DEMO`/`LIVE` chip is the one exception).
- No `dangerouslySetInnerHTML`. All API-returned strings render as text.
- Minimum visible text size: 12 px.
- Tabular figures wherever the family provides them.

### 5.3 Component visual rules (summary)

- **Cards:** `sheet`, 1 px `rule` border, 12 px radius, **no shadow**, 16 or 24 px padding.
- **Tables:** 44 px row height (36 px dense), 1 px `rule` between rows, no zebra stripes, sticky header, full-row link.
- **Buttons:** Primary — `prussian` fill, white text, 36 px high. Secondary — `sheet` + 1 px `rule-strong`. Danger secondary (Reject) — outlined, `sev-critical` text. While submitting: keep label, add left-side spinner (no width jump). No trailing arrows.
- **Drawers:** docked (graph details) or overlay. 180 ms slide. Focus moves in on open and returns to trigger on close. Esc closes.
- **Dialogs:** 14 px radius, 150 ms fade + 4 px rise. Focus trapped. Esc closes unless submission is pending.
- **Error states:** heading = what failed; body = what to do + `Retry` + `requestId` in mono with a copy control. No apologetic language. No "Oops".
- **Empty states:** left-aligned in the content area. One heading (what is missing), one sentence (why), one valid next action. No illustrations.
- **Toasts:** top-right, below top bar, 4 s, `aria-live="polite"`. Success toasts only after a confirmed successful response (INV-11). Dialog errors stay in the dialog.

### 5.4 Severity system (INV-05)

| Level | Shape (inline SVG, 12 px grid) | Colour token |
|---|---|---|
| `CRITICAL` | Filled octagon | `sev-critical` |
| `HIGH` | Filled triangle | `sev-high` |
| `MEDIUM` | Filled diamond | `sev-medium` |
| `LOW` | Open circle (ring) | `sev-low` |
| `INFO` | Open square | `sev-info` |

`SeverityBadge` always renders shape + label. A compact variant (shape only) exists for dense areas but always has an accessible name and tooltip.

### 5.5 Diff state rendering (INV-06)

| State | Canvas label | Node treatment | Edge treatment |
|---|---|---|---|
| `MATCHED` | none (shows "Matched" in the drawer) | 1 px `rule-strong` outline, white fill | Solid 1.5 px, neutral |
| `ADDED` | `Unmatched` | 2 px amber outline | Solid, amber |
| `MISSING` | `Missing` | 1.5 px dashed `ink` outline, white fill | Dashed, `ink` |
| `CHANGED` | `Changed` + finding count | 2 px outline in highest-finding-severity colour + revision triangle | Solid, same severity colour |
| `UNKNOWN` | `Unknown` | 1.5 px dotted `graphite` outline, light diagonal hatch fill | Dotted, `graphite` |

`UNKNOWN` is **never** red or amber. No canvas text calls an unmatched node insecure.

### 5.6 Motion rules

Only these motions are permitted. Adding any other requires a design review.

| Motion | Spec |
|---|---|
| Route content | 120 ms opacity cross-fade. No slide. |
| Drawer | 180 ms slide from right edge. |
| Dialog | 150 ms fade + 4 px rise. |
| Toast | 150 ms fade. |
| Skeleton | 1.4 s opacity pulse. |
| Graph DIFF first load | 400 ms stroke-dashoffset draw-in on `CHANGED` and `ADDED` node outlines, once per dataset load. Nothing else animates on load. |

With `prefers-reduced-motion: reduce`, every motion above is removed except an instant state change.
No count-up numbers, no hover lift, no staggered entrances, no parallax, no animated backgrounds.

### 5.7 Design blocklist

A pull request that introduces any of the following is **rejected**:

- Gradients (backgrounds, text, buttons, chart fills)
- Glass / blur effects, neumorphism
- Emoji or sparkle iconography; "magic" wording for Bedrock output
- Identical shadowed cards in a uniform grid; any shadow on cards
- Hover lift or scale on cards; fade-up on every section; count-up figures
- Tracked-out all-caps eyebrow labels above headings
- Meta strings joined with middle dots, spaced em-dash labels, trailing arrows on buttons or links
- Centred hero-style empty states or stock illustrations
- "Oops", "Something went wrong", "Welcome back!", exclamation marks
- Purple-to-blue gradient palettes, neon-on-black palettes, cream-and-terracotta palettes
- Inter, Roboto, or Arial as the visible interface typeface
- Mixed icon families or stroke widths (Lucide at 1.5 px stroke only; custom SVG for the logomark, severity shapes, and graph silhouettes)

---

## 6. Page and feature rules

Every route-level page must implement all five states from `StateBoundary`:
**loading → empty → partial → error → success**.
A page that has data may also need a **not-enabled** state (INV-14).

### 6.1 Loading state

Skeleton shaped like the final layout. Same row heights and column widths. Static when `prefers-reduced-motion: reduce`.

### 6.2 Empty state

Left-aligned. One heading (what is missing), one sentence (why), one valid next action.
Never `"No data."` or `"Nothing here."`.

### 6.3 Error state

Heading = what failed. Body = next step. `Retry` button. `requestId` in mono with a copy control.

### 6.4 Partial state

Warning bar naming the failed region. The rest of the page renders and stays usable.

### 6.5 Not-enabled state

Use the `NotEnabled` component. The label reads `"Not enabled"`. The page, if any, says `"This part of the product is not enabled in this environment."` Never show a control that implies an action exists when it does not (INV-14).

### 6.6 Route-specific highlights

**Overview (`/overview`)**

- `conformance.percent === null` shows `—` and `"Not evaluated yet"`. Never `100%` without a successful evaluation (INV-04).
- `Run evaluation` posts to `/v1/evaluations`, then polls the returned job. The button is disabled while the user's own job is active.
- Every number on the page comes from the API. No numeric literals as data in `features/overview`.

**Architecture Explorer (`/architecture`)**

- Never compute a state, severity, or edge in React (INV-06, INV-07).
- `UNKNOWN` is never styled as a violation.
- Every node and edge on the canvas must appear in the API response.
- With `truncated: true`, show a visible warning and the resource count from `nodes.length`.
- `ResourceList` is the keyboard and screen-reader alternative; it offers the same selection and the same details drawer.
- Node positions are cached by node ID; switching views keeps shared nodes in place.

**Findings (`/findings`, `/findings/:findingId`)**

- All filter state lives in the URL (shareable).
- Changing any filter resets the cursor.
- Controls lacking backend support render as `"Not enabled"` (INV-14).
- `Acknowledge` waits for the server response before showing a success toast (INV-11).
- `Request remediation` is never enabled for a finding the response marks unavailable (INV-15).
- The AI panel always shows its cited evidence and the advisory disclaimer (INV-16).

**Intents (`/intents`, `/intents/:intentId`)**

- `"Review and approve"` and the version diff tab are hidden or `"Not enabled"` until OCI-09 is closed.
- Upload warns against secrets; file contents are never logged (INV-21).

**Remediation (`/remediation`)**

- Approval and rejection are always labelled as gated actions. Dry-run results are never worded as real fixes (INV-15).
- `"Cancel request"` is hidden until its endpoint exists (INV-14).

---

## 7. Authentication rules

- Only `src/auth/authClient.ts` imports `aws-amplify`. ESLint enforces this.
- The Cognito **access token** is sent in the `Authorization: Bearer <token>` header of API calls.
- The ID token is read **client-side only** for display (name, email). It is never sent to the API.
- No token is logged, rendered, stored (except by Amplify's own storage), or passed anywhere except the `Authorization` header.
- On `401`: one silent refresh and one retry. If that fails, clear the session and navigate to `/login` with `"Your session expired. Sign in again to continue."`.
- Loop guard: if `/login` has an `error` query parameter, or a sign-in attempt was made in the last 60 s, the page shows the failure and a `Sign in` button. No automatic redirect.
- On `403`: do not sign out. Show a permission message in place.
- `returnTo` accepts only same-origin relative paths (prevent open redirect).
- Sign out clears the entire TanStack Query cache.

---

## 8. Capability flags

The frontend never advertises an action the backend cannot perform (INV-14).
Flags are set via `VITE_FEATURES` (comma-separated). In mock mode all flags are on.

| Flag | Enables | Default on from |
|---|---|---|
| `evaluations` | `Run evaluation`, job drawer, polling | M3 |
| `architecture` | Explorer data | M3 |
| `findings.update` | `Acknowledge` | M3 |
| `findings.suppress`, `findings.reopen` | `Suppress`, `Reopen` | off until confirmed |
| `findings.query` | Server-side search, date range, sort, multi-value filters | off until OCI-06 confirmed |
| `intents` | Intents pages | M4 |
| `intents.upload` | Upload dialog | M4 |
| `intents.approve`, `intents.diff` | `Review and approve`, version diff | M4, when OCI-09 is confirmed |
| `driftEvents` | Drift Events page | M4 |
| `explanations.generate` | `Generate explanation` button | M5, when OCI-11 confirmed |
| `remediation` | Request and decision | M5 |
| `remediation.detail`, `remediation.cancel` | Approval detail, `Cancel request` | M5, when OCI-10 confirmed |
| `auditTrail` | Audit Trail page and Recent activity | M5 |

---

## 9. Environment variables

All values are public. No secrets may appear in any `VITE_` variable.
`config/env.ts` validates all of these at startup with zod.

| Variable | Example | Purpose |
|---|---|---|
| `VITE_APP_ENV` | `development` | Build environment |
| `VITE_API_BASE_URL` | `https://...execute-api....amazonaws.com` | API origin |
| `VITE_AWS_REGION` | `us-east-1` | Cognito and display Region |
| `VITE_COGNITO_USER_POOL_ID` | `us-east-1_...` | User pool |
| `VITE_COGNITO_CLIENT_ID` | `...` | Public app client (no secret) |
| `VITE_COGNITO_DOMAIN` | `....auth.us-east-1.amazoncognito.com` | Managed-login domain |
| `VITE_COGNITO_REDIRECT_SIGN_IN` | `http://localhost:5173/login` | OAuth return URL |
| `VITE_COGNITO_REDIRECT_SIGN_OUT` | `http://localhost:5173/login` | Sign-out return URL |
| `VITE_DEPLOYMENT_MODE` | `demo` | Shows `DEMO` or `LIVE` chip in the sidebar footer |
| `VITE_USE_MOCKS` | `false` | Dev-only mock mode. **Must be `false` in production builds.** |
| `VITE_FEATURES` | `evaluations,architecture` | Enabled capabilities |
| `VITE_PRIVACY_URL`, `VITE_HELP_URL` | optional | Links in Settings. Hidden when empty. |

A missing or malformed variable renders a `ConfigErrorScreen` that lists the **names** of the failing variables (never their values) before any other rendering.

---

## 10. CI and build gates

The following checks must all pass before merging to the main branch. The agent should not commit code that would fail any of them.

| Gate | What fails it |
|---|---|
| `typecheck` | Any TypeScript error with `strict: true` |
| `lint` | Any ESLint rule violation, including `eslint-plugin-boundaries` import violations, `no-restricted-imports` for `fetch`/`XHR` outside `api/`, and `aws-amplify` outside `auth/` |
| `test` (unit + component) | Any Vitest failure. Every page tested in all five states. Every fixture parsed against its zod schema. |
| `test:contract` | Any fixture that fails its zod schema parse |
| `build` | Build with `VITE_USE_MOCKS=true` must be rejected in production |
| `scan` (post-build) | `dist/` contains any string that looks like an AWS access key, private key, MSW code, or mock fixture |
| `analyze` | Any route chunk (excl. shared vendor, gzip) exceeds 120 KB, or the architecture chunk exceeds 250 KB, or the initial shell exceeds 150 KB |
| `e2e` | Any Playwright journey fails on the mock scenarios |
| Nightly contract | Live dev-stack API response fails its zod schema |

---

## 11. Pull request checklist

Before marking a PR ready for review, verify every item below.

- [ ] INV-01 through INV-22 are not violated.
- [ ] No hard-coded operational value or numeric literal that should come from the API.
- [ ] No fake success path (fabricated state on API failure).
- [ ] No new control that advertises an action without a deployed endpoint and its capability flag.
- [ ] For any contract change: types, schemas, fixtures, and backend tests updated in the same PR.
- [ ] Loading, empty, partial, error, and not-enabled states exist for any new data view.
- [ ] Nothing on the design blocklist (§5.7 above).
- [ ] Keyboard path and accessible names verified for any new interactive element.
- [ ] No new package added without a justification in the PR description.
- [ ] Severity is expressed as shape + label + colour in every new usage.
- [ ] Console links from API data validated as `https` + allowed AWS console host before rendering.
- [ ] `returnTo` in any new auth flow accepts only same-origin relative paths.

---

## 12. Copy and voice rules

- Sentence case. Plain verbs. Active voice.
- A button states exactly what happens (`Run evaluation`, `Acknowledge`, `Approve`). The toast that follows uses the same verb.
- Error states say what failed and what to do next. Never apologise; never say "Oops" or "Something went wrong".
- Empty states are directions: what is missing and the next action.
- All strings live in `utils/labels.ts` or within the relevant feature folder.
- Fixture data uses fictional but realistic AWS names. No "Acme Corp", no lorem ipsum.

### Standard copy deck (abbreviated)

| Situation | Text |
|---|---|
| No evaluation | `Not evaluated yet` |
| Charts with no history | `No history yet. Run an evaluation to start the trend.` |
| No findings | `No findings.` + hint to run an evaluation |
| No filtered matches | `No findings match these filters.` + `Clear filters` |
| Finding not found | `This finding does not exist or was removed.` |
| Architecture empty | `No resources observed yet. Run an evaluation to take the first inventory.` |
| No approved intent | `No approved intent yet. Upload and approve an intent to compare against.` |
| Relationship not collected | `Not collected` |
| Graph truncated | `Showing the first {n} resources. Narrow the filters to see the rest.` |
| Feature off | `Not enabled` / `This part of the product is not enabled in this environment.` |
| Session expired | `Your session expired. Sign in again to continue.` |
| Network error | `Could not reach the API.` |
| Permission denied | `You do not have permission to do this.` |
| Conflict | `This item was already changed by someone else. Refresh to see its current state.` |
| Rate limited | `Too many requests. Try again in {n} seconds.` |
| Server error | `The server could not complete the request.` |
| Contract mismatch | `The server sent data this version of the app does not understand.` |
| Page not found | `Page not found. The address does not match a page in this application.` + `Go to Overview` |
| AI panel label | `AI-assisted explanation` |
| AI advisory | `This explanation is advisory. Check it against the evidence.` |

---

## 13. Packages: allowed, forbidden, and one-file rules

### Allowed

React, Vite, TypeScript, Tailwind CSS, shadcn/ui (Radix primitives), Lucide icons, React Router (data router), TanStack Query, React Flow (`@xyflow/react`), `@dagrejs/dagre`, Recharts, `aws-amplify` (auth only), `zod`, `clsx`, `tailwind-merge`, `class-variance-authority`, `@fontsource/*`, MSW (dev only), Vitest, Testing Library, Playwright, `axe-core`, ESLint, `eslint-plugin-boundaries`, Prettier.

### Forbidden

Redux, Zustand, axios, moment, dayjs, date-fns, CSS-in-JS, icon fonts, external font CDNs, MUI, Ant Design, Chakra UI, any other AWS SDK package besides `aws-amplify`, any package that fetches from the network and is not in `src/api/`.

### One-file rules

| Import | Allowed only in |
|---|---|
| `aws-amplify` | `src/auth/authClient.ts` |
| `XMLHttpRequest` | `src/api/uploadClient.ts` |
| `import.meta.env` | `src/config/env.ts` |
| MSW / mock handlers | `src/api/mocks/` (dev only, behind `import.meta.env.DEV`) |

---

## 14. Accessibility requirements

Target: **WCAG 2.2 AA**.

- Semantic landmarks: `<header>`, `<nav>`, `<main>`. One `<h1>` per page. Skip link to `<main>`.
- Visible focus ring on every interactive element (2 px `prussian` ring, 2 px `sheet` offset).
- Every icon-only button has an accessible name and a visible tooltip.
- Severity and diff state are always text + shape (never colour alone).
- Status changes announced through an `aria-live` region.
- The graph canvas is not the only way to interact; `ResourceList` provides the same interaction by keyboard and screen reader.
- Dialogs trap focus and restore it on close. Drawers move focus in and return it.
- Each chart has a visually hidden data table and a text summary.
- Touch target minimum: 24 px; 40 px for primary controls.
- `prefers-reduced-motion: reduce` removes all motion.
- `axe-core` runs in component tests and in Playwright end-to-end tests.

---

## 15. Security

- No `dangerouslySetInnerHTML` anywhere in the codebase.
- Console links from API data: validate as `https` on an allowed AWS console host (`utils/url.ts`) before rendering. Non-conforming values are displayed as plain text, not as links.
- `returnTo` parameter: accept only same-origin relative paths. Reject anything with a protocol, a double slash, or a different host.
- Post-build scan fails if `dist/` contains strings matching AWS key patterns or private key headers.
- Source maps are not served publicly.
- `utils/redact.ts` masks token-like and key-like strings in anything derived from audit metadata or evidence (second line of defence behind backend redaction).
- Content Security Policy is set at CloudFront. The agent must not introduce inline scripts, inline event handlers, or `eval`.

---

## 16. Open Contract Items (OCI) — fallback until closed

OCIs are proposals sent to the backend. Until a given OCI is confirmed and its fixture/schema updated, use the fallback below. **Never invent data or claim an OCI is closed when it has not been.**

| OCI | Topic | Fallback until confirmed |
|---|---|---|
| OCI-01 | Bearer token type | Send the access token |
| OCI-02 | Cognito managed-login config | Blocks real login; use mock mode |
| OCI-03 | `/v1/system/status` payload shape | Pill shows `"Checking"`, then `"Disconnected"` on failure |
| OCI-04 | `/v1/jobs/{jobId}` payload and status set | Any status other than `SUCCEEDED`, `PARTIAL`, `FAILED` is treated as in-progress |
| OCI-05 | Dashboard summary additions | Derive not-evaluated from `conformance.percent === null`; evaluator and errors from `/v1/system/status` |
| OCI-06 | Findings query additions (`q`, date range, sort, multi-value) | `q` filters loaded results only (captioned); sort and date range render as `"Not enabled"` |
| OCI-07 | Finding detail additions (`whyItMatters`, path labels, related findings, `ruleId`, `consoleUrl`) | Map `description` to "Why it matters"; `intent.constraintId` as rule ID; related findings and confidence hidden |
| OCI-08 | Graph additions (severity per node, ARN, tags, edge statuses, empty-state field) | `CHANGED` uses `sev-high` outline; missing fields show `"Not provided by the API"` |
| OCI-09 | Intent approve, diff, version list | `"Review and approve"` and diff read `"Not enabled"` |
| OCI-10 | Remediation detail shape and cancel endpoint | Statuses humanised; `"Cancel request"` hidden |
| OCI-11 | Explanation generation endpoint | `"Generate explanation"` hidden |
| OCI-12 | Audit event row shape and filters | Extra filters beyond `from`, `to`, `action` render as `"Not enabled"` |
| OCI-13 | Drift event `processingStatus` values | Unknown values humanised |
| OCI-14 | Authorization hints (`allowedActions`) | Show all actions; handle `403` in place |
| OCI-15 | Error code registry | Codes derived from HTTP status |
| OCI-16 | Upload limits and S3 CORS | Defaults in `config/constants.ts`; server is the authority |
| OCI-17 | Settings read endpoint | Each item reads `"Not enabled"` |
| OCI-18 | Pagination: max `limit` and cursor lifetime | Offer 25 and 50; a `400` falls back to 25 |
| OCI-19 | Notifications endpoint | Client-derived activity menu only |
| OCI-20 | `findingTrend[].date` semantics | Display as returned, labelled `"UTC days"` |

---

## 17. Milestone scope (P priority)

| Milestone | Key work | Priority |
|---|---|---|
| M1 | Repository setup, tokens, MSW mocks, all routes in fixture mode | P0 |
| M2 | Login, Overview, Findings list, Settings, CORS, real auth | P0 |
| M3 | Architecture Explorer, Finding detail, evaluation job, first real AWS data | P0 |
| M4 | Intents (upload, review, approve), Drift Events, intent diff | P1 |
| M5 | Remediation (request, approve, reject), Audit Trail, Bedrock explanations | P1 |
| M6 | CloudFront + S3 hosting, CSP headers, CORS with explicit origins, end-to-end demo | P2 |

P2 items stay P2. Do not pull them forward without explicit agreement.

---

*Last updated: 2026-10-12. Derived from Cloud Intent Guardian Frontend PRD v1.0.*
