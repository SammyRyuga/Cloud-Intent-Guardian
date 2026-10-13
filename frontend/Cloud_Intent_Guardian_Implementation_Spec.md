# Cloud Intent Guardian — Frontend + AWS Backend Implementation Specification

**Purpose:** A shared, build-ready contract for the frontend developer and backend developers. The frontend can be developed against the exact API shapes below while AWS services are implemented incrementally.

## 0. Decisions to lock before coding

### Product
Cloud Intent Guardian is an AWS architecture-conformance platform. It represents an approved architecture as versioned intent, gathers a supported subset of live AWS resources and their relationships, detects violations of explicit architecture constraints, explains evidence, and routes risky remediation through human approval.

### MVP assumptions
- One AWS account and one AWS Region for the first working demo.
- The backend runs in AWS; do not run a Flask/Express server on a laptop as the production backend.
- Frontend: React + Vite + TypeScript.
- UI: Tailwind CSS plus a reusable component library such as shadcn/ui; Lucide icons.
- Routing: React Router.
- Server state: TanStack Query (loading, caching, retry and invalidation).
- Architecture visualization: React Flow (`@xyflow/react`).
- Charts: Recharts.
- Authentication: Amazon Cognito User Pool. Use Amplify Auth or the Cognito managed login flow; pick one and do not mix token-handling strategies.
- API: Amazon API Gateway HTTP API → AWS Lambda.
- Persistence: Amazon DynamoDB for indexed application records; Amazon S3 for original uploads and versioned graph snapshots/evidence archives.
- AWS observation: AWS Config and read-only AWS service APIs; CloudTrail for change provenance. EventBridge triggers ingestion when enabled.
- Evaluation: deterministic rules/graph comparisons first. Amazon Bedrock is optional for evidence-grounded explanations of ambiguous findings; it must not be the authority for declaring an AWS fact or approving destructive changes.
- Workflow: Step Functions for evaluations and gated remediation when needed; SNS for notifications in a later phase.
- No production remediation runs automatically during the initial demo. All remediation starts in dry-run / approval-required mode.

### Definition of “AWS-connected”
A demo is genuinely AWS-connected when the UI obtains its data through the deployed API, the backend reads current resource/configuration information from the selected AWS account, and a controlled test change creates or resolves a finding. A polished UI with hard-coded cards does not meet this definition.

---

# Part A — Frontend specification

## 1. Visual direction

Build a professional cloud-security operations dashboard, not a marketing landing page. The primary user is a cloud engineer or security analyst reviewing an AWS environment and investigating why it no longer conforms to approved architecture.

### Recommended layout
- Desktop: 240–256 px fixed left sidebar; top bar 64–72 px; main content with 24 px padding; max content width around 1600 px.
- Main canvas: light neutral (`#F6F8FB`) or dark navy if the team deliberately chooses a dark SOC theme. Pick one theme globally; do not mix light cards with random dark panels.
- Suggested light theme: page `#F6F8FB`, card white, main text `#172033`, secondary text `#68758A`, border `#E2E8F0`, primary accent deep blue, good/connected green, warning amber, critical red.
- Severity colors must always pair color with a text label and/or icon. Do not use color alone to express severity.
- Cards use restrained borders, 10–14 px radius, minimal shadow, consistent 16–24 px internal spacing.
- Use one spacing scale and a consistent typography scale. Page heading 24–28 px; section heading 16–18 px; table body 13–14 px.
- Animations should be short and subtle. Do not animate every metric, node, or card.

### Global frame
**Sidebar navigation**, in this order:
1. Overview
2. Architecture
3. Findings
4. Intent & Policies
5. Drift Events
6. Remediation
7. Audit Trail
8. Settings

Sidebar footer: environment chip (`DEMO` / `LIVE`), app version, and a small AWS-connected indicator. Never imply the account is healthy simply because the API is reachable.

**Top bar:** page breadcrumb/title on the left; current AWS account alias/account ID and Region selector/display; last successful sync time; refresh action; notifications; current user menu/sign out. In MVP the Region may be read-only if only one Region is supported.

**Global connection banner:** show `Connected`, `Degraded`, or `Disconnected`, derived from `/v1/system/status`. Make the label clickable to open the system status detail. Do not show green “Connected” solely because the browser can reach API Gateway—the backend must confirm it can read the configured AWS sources.

## 2. Route map

Use these browser routes; route names should remain stable as the application grows.

| Route | Page |
|---|---|
| `/login` | Sign-in / Cognito redirect status |
| `/overview` | Operational overview |
| `/architecture` | Intended/live/diff graph explorer |
| `/findings` | Filterable findings list |
| `/findings/:findingId` | Finding details and evidence |
| `/intents` | Versioned intent documents and policies |
| `/intents/:intentId` | Intent detail, extracted constraints, versions |
| `/drift-events` | Timeline of observed configuration changes |
| `/remediation` | Remediation requests and approvals |
| `/audit-trail` | Searchable action/evaluation history |
| `/settings` | Account, data source and application settings |
| `*` | Useful not-found page with link to Overview |

After login, direct navigation to a protected URL should work. Configure the AWS-hosted static frontend distribution to serve `index.html` for client-side routes, otherwise a refresh on `/findings/abc` can return a 403/404 from the static origin.

## 3. Page requirements

### 3.1 Overview (`/overview`)

**Goal:** Give a truthful snapshot of the configured AWS environment and the most important risks.

**Header:**
- Title: `Overview`
- Subtitle: `Architecture conformance for your AWS environment`
- Current account/Region context
- Primary button: `Run evaluation`
- Secondary action: `View architecture`

**Metric cards:**
- `Resources observed` — count of supported resources in the latest successful inventory.
- `Conformance` — percentage calculated by backend; display `—` when no successful evaluation exists. The backend must return numerator/denominator or a definition to avoid ambiguous calculations.
- `Open findings` — findings with a status included in the backend-defined open states.
- `Critical / High` — count of open findings by those severities.
- `Pending approvals` — remediation requests waiting for a human.

Never hard-code values. A new account with no data should display `Not evaluated yet`, not `100% compliant`.

**Below the cards:**
- Left 2/3: `Findings over time` line/area chart, grouped by day and severity; empty state if there are no history records.
- Right 1/3: `Finding severity` bar or donut chart with text legend.
- Bottom left: `Recent findings` compact table (latest 5–8).
- Bottom right: `System health` panel for Config, CloudTrail, last inventory, evaluator, Bedrock (optional), and latest error. Each source has `Connected`, `Needs setup`, `Error`, or `Not enabled`; do not label unsupported sources as connected.
- Optional `Recent activity` list showing evaluation started/completed and remediation decisions.

**Interactions:**
- Clicking an open finding navigates to its detail page.
- Clicking a severity metric navigates to Findings with that severity filter preselected.
- `Run evaluation` calls `POST /v1/evaluations`; it must immediately show queued/running state and poll the returned job URL or ID. It must not block the browser waiting for a long scan.
- Refresh invalidates the relevant TanStack Query cache.

**States:** loading skeletons; no-evaluation empty state; normal state; partial data warning; API error with retry; evaluation in progress with progress stage and `View job` link.

### 3.2 Architecture Explorer (`/architecture`)

This is the signature visual screen. It should clearly distinguish the approved architecture from what was observed in AWS.

**Header controls:**
- Title `Architecture Explorer`
- Segmented mode switch: `Intended`, `Live`, `Differences` (default `Differences` once an approved intent and inventory exist; otherwise explain what is missing).
- Filters for resource type, Region, finding severity, and “show only nodes involved in findings”.
- Search by resource ID, ARN, name/tag, or type.
- `Fit graph`, zoom in/out, reset layout, and refresh actions.
- Legend: intended-only node, live-only node, changed node/edge, matched node/edge, selected node.

**Main body:** three areas.
1. Optional left filter drawer, 220–260 px, collapsible.
2. Central graph canvas, filling most of the viewport. Use React Flow; render nodes by AWS resource category, not one generic rectangle. Node label should use a short name and type; keep long ARNs in the details drawer.
3. Right details drawer, 320–380 px, appears when a node/edge is selected. On small screens it becomes a modal/drawer.

**Node visual state:**
- Normal/matched: neutral border.
- Live-only / unexpected: amber outline and `Unmatched` label.
- Changed: warning/red outline determined by finding severity.
- Intended-only / missing in live environment: dashed outline and `Missing` label.
- Do not imply that a resource is insecure merely because it has no counterpart; label the actual comparison result.

**Edge visual state:** use arrow direction and an explicit relationship label, e.g. `uses role`, `allows ingress`, `connects to`, `reads from`, or `routes to`. An edge must only be rendered if its relationship type has evidence. Do not create speculative application/data-flow edges from names or LLM guesses.

**Right drawer tabs:**
- `Details`: name, resource type, AWS Region, ARN/ID, tags, last observed time, source.
- `Relationships`: inbound/outbound observed or declared edges.
- `Conformance`: constraints associated with this node and any findings.
- `Evidence`: source links/record identifiers and structured evidence summary.

**Edge selection:** show source node, target node, relationship type, intended status, live status, evidence and related finding(s). If the backend has not yet implemented a relationship type, show `Not collected` rather than inferring an edge.

**Diff behavior:** the frontend renders backend-provided diff classifications. Do not implement the security logic in React. The API returns `MATCHED`, `ADDED`, `MISSING`, `CHANGED`, or `UNKNOWN`, plus explanation/evidence references. The backend is the source of truth.

**Graph performance:** render only the current result set; include a resource count and a warning if the response was truncated. Large graphs need filtering and server-side limits. Do not fetch every account resource on every node click.

### 3.3 Findings list (`/findings`)

**Header:** `Findings`; subtitle explaining that findings are violations against approved intent or explicitly enabled security checks.

**Filter row:**
- Search text
- Severity: Critical / High / Medium / Low / Info
- Status: Open / Acknowledged / In progress / Resolved / Suppressed
- Category: Network path / Identity & permissions / Public exposure / Missing resource / Configuration drift / Other
- Resource type
- First seen / last seen date range
- Sort: severity, newest, oldest, last updated
- `Clear filters`

These are user-facing categories. The backend should return a canonical category code and a display label. Use URL query parameters to preserve filter state and make a filtered page shareable.

**Table columns:** severity, finding title, category, affected resource, expected vs. observed summary, status, first seen, last seen. Row click opens `/findings/:findingId`. Show loading skeleton, no findings, no filtered matches, permission error, and API error distinctly.

**Bulk actions:** do not implement bulk remediation in MVP. Acknowledge may become a bulk action only after server-side authorization and audit logging exist.

**Pagination:** use opaque cursor pagination supplied by API. Do not assume every record is on the first page. Default page size 25; allow 25/50 if backend supports it.

### 3.4 Finding detail (`/findings/:findingId`)

This is the investigation page, and should be the most useful page for demonstrating your contribution.

**Top header:** breadcrumb `Findings / [finding title]`, severity badge, current status, resource display name, `Acknowledge` and `Request remediation` actions (the latter disabled if the finding is informational or has no supported runbook).

**First row of cards:**
- Why it matters
- What was intended
- What was observed
- Confidence/evidence completeness (display only if returned by backend with a definition)

**Body layout:**
- Main 2/3: `Violation path` panel showing a compact graph path or relationship chain. Example: source → relation → intermediary → target. Each item can open the resource detail drawer in Architecture Explorer.
- `Expected vs observed` comparison: show exact constraint/policy, relevant intent version, live resource relationship/configuration, and backend rule ID.
- `Evidence` accordion: source (`AWS Config`, `CloudTrail`, etc.), event/config item identifier, observation timestamp, relevant fields, and link/reference if a console URL is safely available.
- Right rail: lifecycle timeline, related findings, and remediation eligibility.

**AI explanation:** if Bedrock is enabled, display `AI-assisted explanation` with clear labeling. Show evidence cited by the backend and a disclaimer that the explanation is advisory. If no explanation exists, show `Not generated`; allow a deliberate `Generate explanation` action only if that endpoint is implemented.

**Actions and rules:**
- `Acknowledge` sends a PATCH to the finding endpoint.
- `Request remediation` does not directly modify an AWS resource. It creates a remediation request in `PENDING_APPROVAL` (or a dry-run status) and logs who requested it.
- User must see the proposed change, target resource, impact summary, and approval requirement before approving.
- If no safe runbook exists, show why remediation is unavailable rather than a fake success button.

### 3.5 Intent & Policies (`/intents` and `/intents/:intentId`)

**List page:**
- Title `Intent & Policies`
- Short explanation: “Approved versions describe what your AWS architecture is allowed to look like.”
- `Upload IaC / ADR` button
- Table: name, source files, current version, status (`Draft`, `Processing`, `Needs review`, `Approved`, `Failed`), created by, updated time.
- Search and status filter.

**Upload flow:** modal or dedicated page with:
1. Source type: Terraform, CloudFormation, ADR/document, or JSON constraint manifest.
2. File input, filename, size and type validation.
3. Optional human-authored architecture name and short rationale.
4. Consent/confirmation that the uploaded file contains no secrets.
5. Upload progress, processing status, validation errors.

Never ask the user to paste AWS access keys or secret credentials. IaC files can contain secrets; warn users not to upload them and avoid rendering full file contents into client logs.

**Version detail page:**
- `Overview` tab: source files, who uploaded, processing status, created date.
- `Extracted constraints` tab: machine-readable constraint cards. Each constraint has ID, description, source line/document reference if available, expected relationship or property, scope, severity, and extraction confidence.
- `Diff from approved version` tab: added/removed/changed constraints.
- `Source files` tab: filenames and safe metadata; raw source content only if access controls and redaction are implemented.
- `Review and approve` button. It must be disabled when extraction/validation failed. Require a confirmation dialog showing the version and number of constraints before approval.

**Crucial trust model:** Bedrock may suggest constraints from text, but a human must review and approve the intent version. The approved version is the comparison baseline. Do not silently overwrite an existing approved version.

### 3.6 Drift Events (`/drift-events`)

Show a timeline/table of raw observed changes that may or may not become findings. This is distinct from Findings: a change is an event; a finding is a violation of intended architecture or a configured rule.

Columns: event time, AWS source, resource, change summary, actor if known, evaluation status, related finding. Filters: date range, source, resource type, processed/unprocessed, actor.

Event detail drawer: source event ID, event time, affected resource, normalized before/after fields if available, related evaluation job, related finding. Never fabricate a before-state when the source does not provide one.

### 3.7 Remediation (`/remediation`)

Tabs: `Pending approval`, `In progress`, `Completed`, `Rejected / failed`.

Table/card fields: request ID, finding, proposed runbook/action, target resource, requester, created time, impact/risk, status.

**Approval detail:** show original finding, proposed operation, affected resource ARN/ID, exact parameters, risk note, dry-run output where available, and audit timeline. Buttons: `Approve`, `Reject`, `Cancel request` if supported.

Approval dialog requires an explicit confirmation and optional required reason. On submit, disable buttons while pending and prevent double submission. The server decides whether the user is authorized and whether the workflow is still awaiting approval. Never trust an `isAdmin` boolean sent by the browser.

**MVP safety:** do not implement automatic deletion, IAM policy replacement, or security-group changes in the first demonstration. The initial flow can end with a simulated/dry-run result, clearly labeled as such. When real remediation is added, execute only allowlisted reviewed SSM Automation runbooks with least-privilege roles and durable audit records.

### 3.8 Audit Trail (`/audit-trail`)

A read-only table of important actions: intent uploaded/approved, evaluation started/completed, finding acknowledged/suppressed/resolved, remediation requested/approved/rejected/executed, and configuration changes.

Columns: timestamp, actor, action, target, result, correlation/request ID. Filters: action, actor, date range, result. Details show structured event metadata but never credentials, raw JWTs, secrets, Step Functions task tokens, or unnecessary sensitive document content.

Audit records must be generated by the backend; the client must not be able to create arbitrary audit entries.

### 3.9 Settings (`/settings`)

Sections:
- **AWS environment:** account alias/ID, active Region, role/configuration source, last successful inventory. Display masked/non-sensitive identifiers as appropriate.
- **Data sources:** Config, CloudTrail, optional flow logs, Bedrock status and last successful query. The MVP may make these read-only.
- **Evaluation settings:** enabled constraint set, severity threshold, scheduled scan frequency if implemented. Show whether schedule is active or unsupported.
- **Remediation safety:** start with `Human approval required` fixed/enforced. Do not expose a client-side toggle that enables dangerous automatic remediation unless the backend has strong admin authorization and guardrails.
- **Application:** user info, session/sign out, version, privacy/help links.

Do not ask users for AWS access keys in the frontend. For the first demo, the backend's Lambda roles should read the same account in which the stack is deployed. Multi-account onboarding through an assumed IAM role is a later feature requiring a dedicated setup and external ID/trust-policy flow.

## 4. Shared frontend behavior

### Loading and errors
Every API-driven page must have:
- Loading skeleton that resembles the final layout.
- Empty state explaining what is missing and a valid next action.
- Error state showing a useful summary and Retry action.
- Partial-data state when one card/source failed but the rest of the page loaded.
- Disabled states for unavailable backend capabilities.

Never show a successful toast before the backend responds successfully. Use toasts for confirmation, but leave durable status on the page as the source of truth.

### Date and time
API timestamps should be ISO 8601 UTC strings, e.g. `2026-10-11T06:00:00Z`. Render in local time but make the timezone clear in detailed evidence.

### Accessibility and responsive behavior
- Use semantic headings and buttons with visible focus states.
- Every icon-only button gets an accessible label and tooltip.
- Ensure tables work on tablet/mobile using horizontal overflow or a card presentation.
- Graph controls need keyboard-accessible alternatives such as search and resource list.
- Never rely on severity colors alone.

### Query caching
Use TanStack Query keys such as:
- `['dashboard-summary', region]`
- `['findings', filters]`
- `['finding', findingId]`
- `['architecture', view, filters]`
- `['intents']`
- `['drift-events', filters]`
- `['remediations', status]`
- `['audit-events', filters]`
- `['system-status']`

After a mutation, invalidate only the affected queries. Poll a job at a modest interval while its state is `QUEUED` or `RUNNING`, and stop polling when terminal.

---

# Part B — Frontend/backend connection contract

## 5. Authentication and request flow

1. User opens the CloudFront URL.
2. Unauthenticated user is sent to Cognito sign-in (or your agreed Amplify Auth login view).
3. Cognito authenticates the user and returns tokens through the selected flow.
4. Frontend API client attaches `Authorization: Bearer <JWT>` to protected API calls.
5. API Gateway validates the JWT using a Cognito-compatible JWT authorizer.
6. Lambda receives the request and verified claims, validates input, applies application-level authorization, reads/writes DynamoDB/S3, and returns JSON.
7. Frontend parses the JSON response and updates state.

**Do not hard-code tokens. Do not store secrets in Vite environment variables.** `VITE_` values are shipped to the browser. It is acceptable to expose non-secret public configuration such as API URL, Cognito User Pool ID, Cognito App Client ID, and Region; never expose AWS secret keys, access keys, IAM credentials, Bedrock keys, or database credentials.

### Example frontend environment file

```dotenv
VITE_APP_ENV=development
VITE_API_BASE_URL=https://YOUR_API_ID.execute-api.YOUR_REGION.amazonaws.com
VITE_AWS_REGION=YOUR_REGION
VITE_COGNITO_USER_POOL_ID=YOUR_USER_POOL_ID
VITE_COGNITO_CLIENT_ID=YOUR_PUBLIC_APP_CLIENT_ID
```

The exact Cognito callback/logout URLs and token acquisition approach depend on whether the team uses Cognito managed login or Amplify Auth. Agree on one approach and configure the corresponding callback URLs for localhost and deployed CloudFront URL.

### Request helper contract

All application calls go through one `apiClient.ts` helper. It should:
- Get a fresh/current token from the agreed Cognito auth library.
- Prefix relative paths with `VITE_API_BASE_URL`.
- Send `Content-Type: application/json` for JSON requests.
- Attach the bearer token except to the explicitly public health route.
- Parse JSON response bodies.
- Throw a typed error containing HTTP status, `code`, message and `requestId`.
- Handle `401` by attempting the auth library's supported refresh/sign-in route once; do not create an infinite refresh loop.
- Treat `403` as a permission error, `404` as missing resource, `409` as a state conflict, `429` as rate limiting, and `5xx` as server failure.

### Standard API response shape

Success responses may include domain fields directly and a `requestId` in metadata. For consistent handling, the recommended envelope is:

```json
{
  "data": {},
  "meta": {
    "requestId": "req_example",
    "generatedAt": "2026-10-11T06:00:00Z"
  }
}
```

List responses also include pagination:

```json
{
  "data": [],
  "meta": {
    "requestId": "req_example",
    "generatedAt": "2026-10-11T06:00:00Z",
    "nextCursor": null,
    "limit": 25
  }
}
```

Error response:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "severity must be one of CRITICAL, HIGH, MEDIUM, LOW, INFO",
    "details": [],
    "requestId": "req_example"
  }
}
```

The API should never return raw AWS credentials, internal exception stack traces, full secret values, task tokens, or unrestricted raw Config/CloudTrail archives.

## 6. API endpoints (version 1)

Prefix all routes with `/v1`. The following JSON fields are the contract frontend and backend should agree on before implementation. If a field name changes, change the shared API types and sample fixtures at the same time.

### 6.1 Health

`GET /v1/health` — can be public and should only confirm the API process/handler is reachable. It does not imply AWS sources are healthy.

Example:

```json
{
  "data": {
    "status": "ok",
    "apiVersion": "v1"
  },
  "meta": { "requestId": "req_1", "generatedAt": "2026-10-11T06:00:00Z" }
}
```

### 6.2 Dashboard summary

`GET /v1/dashboard/summary`

```json
{
  "data": {
    "account": { "id": "123456789012", "alias": "cloud-intent-demo" },
    "region": "ap-south-1",
    "lastInventoryAt": "2026-10-11T05:45:00Z",
    "lastEvaluationAt": "2026-10-11T05:50:00Z",
    "resourcesObserved": 24,
    "conformance": { "percent": 87.5, "passing": 21, "evaluated": 24 },
    "openFindings": 5,
    "severityCounts": { "CRITICAL": 1, "HIGH": 2, "MEDIUM": 1, "LOW": 1, "INFO": 0 },
    "pendingApprovals": 1,
    "findingTrend": [
      { "date": "2026-10-09", "CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 1 },
      { "date": "2026-10-10", "CRITICAL": 1, "HIGH": 2, "MEDIUM": 1, "LOW": 1 }
    ],
    "sourceStatus": [
      { "source": "AWS_CONFIG", "status": "CONNECTED", "lastSuccessAt": "2026-10-11T05:45:00Z", "message": null },
      { "source": "CLOUDTRAIL", "status": "CONNECTED", "lastSuccessAt": "2026-10-11T05:42:00Z", "message": null },
      { "source": "BEDROCK", "status": "NOT_ENABLED", "lastSuccessAt": null, "message": "AI explanations are not enabled in this environment." }
    ]
  },
  "meta": { "requestId": "req_2", "generatedAt": "2026-10-11T06:00:00Z" }
}
```

Rules:
- If no evaluation has ever run, return `conformance.percent: null`, counts as appropriate, and a `NOT_EVALUATED` state or message. Do not present a fabricated 100%.
- `resourcesObserved` means supported/collected resources, not every possible AWS resource in an account.
- Define the conformance denominator consistently; resources without applicable constraints should not silently count as passing.

### 6.3 Findings list

`GET /v1/findings?severity=HIGH&status=OPEN&category=NETWORK_PATH&resourceType=AWS::EC2::SecurityGroup&limit=25&cursor=...`

Allowed values should be documented in shared TypeScript types. Suggested status codes: `OPEN`, `ACKNOWLEDGED`, `IN_PROGRESS`, `RESOLVED`, `SUPPRESSED`. Suggested severity values: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`.

```json
{
  "data": [
    {
      "findingId": "finding_01JDEMO",
      "title": "Unexpected network path to private database",
      "severity": "HIGH",
      "status": "OPEN",
      "category": "NETWORK_PATH",
      "categoryLabel": "Network path",
      "resource": {
        "resourceId": "sg-0123456789abcdef0",
        "resourceType": "AWS::EC2::SecurityGroup",
        "name": "app-db-access",
        "region": "ap-south-1"
      },
      "summary": "Observed relationship violates approved constraint NET-DB-01.",
      "firstSeenAt": "2026-10-10T12:00:00Z",
      "lastSeenAt": "2026-10-11T05:45:00Z",
      "intentVersion": "v3",
      "ruleId": "NET-DB-01",
      "remediationAvailable": false
    }
  ],
  "meta": { "requestId": "req_3", "generatedAt": "2026-10-11T06:00:00Z", "nextCursor": null, "limit": 25 }
}
```

### 6.4 Finding detail

`GET /v1/findings/{findingId}`

```json
{
  "data": {
    "findingId": "finding_01JDEMO",
    "title": "Unexpected network path to private database",
    "severity": "HIGH",
    "status": "OPEN",
    "category": "NETWORK_PATH",
    "description": "The observed relationship violates an explicit approved architecture constraint.",
    "resource": { "resourceId": "sg-0123456789abcdef0", "resourceType": "AWS::EC2::SecurityGroup", "name": "app-db-access", "arn": null, "region": "ap-south-1" },
    "intent": { "intentId": "intent_prod_web", "version": "v3", "constraintId": "NET-DB-01", "expected": "Only the application security group may reach the database on the approved port." },
    "observed": { "summary": "A new ingress relationship was observed.", "observedAt": "2026-10-11T05:45:00Z", "source": "AWS_CONFIG", "evidenceIds": ["evidence_config_001"] },
    "path": [
      { "nodeId": "resource_web", "label": "Web entry", "resourceType": "AWS::CloudFront::Distribution" },
      { "nodeId": "resource_app", "label": "Application", "resourceType": "AWS::Lambda::Function" },
      { "nodeId": "resource_db", "label": "Private database", "resourceType": "AWS::RDS::DBInstance" }
    ],
    "evidence": [
      { "evidenceId": "evidence_config_001", "source": "AWS_CONFIG", "observedAt": "2026-10-11T05:45:00Z", "description": "Security group configuration item", "fields": { "fieldName": "ipPermissions", "comparison": "unexpected ingress relationship" } }
    ],
    "explanation": { "status": "NOT_GENERATED", "text": null, "evidenceIds": [] },
    "remediation": { "available": false, "runbookId": null, "reason": "No approved runbook is configured for this finding type." },
    "timeline": [
      { "timestamp": "2026-10-10T12:00:00Z", "action": "DETECTED", "actor": "system", "message": "Finding created by evaluation." }
    ],
    "firstSeenAt": "2026-10-10T12:00:00Z",
    "lastSeenAt": "2026-10-11T05:45:00Z"
  },
  "meta": { "requestId": "req_4", "generatedAt": "2026-10-11T06:00:00Z" }
}
```

Do not return secrets or entire unredacted service responses by default. Evidence fields should be deliberately selected and redacted.

### 6.5 Update finding status

`PATCH /v1/findings/{findingId}`

Request:

```json
{ "action": "ACKNOWLEDGE", "comment": "Investigating with the platform team." }
```

Allowed initial actions: `ACKNOWLEDGE`, `SUPPRESS` (only if backend policy permits), and optionally `REOPEN`. Resolution should normally be driven by a fresh evaluation that confirms the violation no longer exists, or a separately audited analyst workflow. The backend must validate state transitions, identify the actor from verified auth claims, and write an audit event.

### 6.6 Architecture graph

`GET /v1/architecture?view=DIFF&region=ap-south-1&resourceType=AWS::EC2::SecurityGroup&findingOnly=false`

Allowed `view`: `INTENDED`, `LIVE`, `DIFF`.

```json
{
  "data": {
    "view": "DIFF",
    "intentVersion": "v3",
    "generatedAt": "2026-10-11T05:50:00Z",
    "truncated": false,
    "nodes": [
      {
        "id": "resource_app",
        "label": "Application function",
        "resourceType": "AWS::Lambda::Function",
        "state": "MATCHED",
        "source": "LIVE_AND_INTENT",
        "region": "ap-south-1",
        "properties": { "name": "demo-app" },
        "findingIds": []
      },
      {
        "id": "resource_db",
        "label": "Private database",
        "resourceType": "AWS::RDS::DBInstance",
        "state": "CHANGED",
        "source": "LIVE_AND_INTENT",
        "region": "ap-south-1",
        "properties": { "name": "demo-db" },
        "findingIds": ["finding_01JDEMO"]
      }
    ],
    "edges": [
      {
        "id": "edge_app_db",
        "source": "resource_app",
        "target": "resource_db",
        "label": "connects to",
        "relationshipType": "NETWORK_ACCESS",
        "state": "CHANGED",
        "evidenceIds": ["evidence_config_001"],
        "findingIds": ["finding_01JDEMO"]
      }
    ]
  },
  "meta": { "requestId": "req_5", "generatedAt": "2026-10-11T06:00:00Z" }
}
```

State codes: `MATCHED`, `ADDED`, `MISSING`, `CHANGED`, `UNKNOWN`. Relationship types and their evidence semantics must be defined by backend code. `UNKNOWN` means insufficient data; it must not be painted as a confirmed violation.

For an empty account, return empty arrays plus an explanatory state so the frontend can show how to upload intent/run the first inventory.

### 6.7 Intent list and detail

`GET /v1/intents?status=APPROVED&limit=25&cursor=...`

List object fields: `intentId`, `name`, `status`, `currentApprovedVersion`, `createdAt`, `updatedAt`, `uploadedBy`, `sourceFilesCount`, `constraintCount`, `errorMessage`.

`GET /v1/intents/{intentId}` returns metadata, available versions and reviewed constraints. Constraint example:

```json
{
  "constraintId": "NET-DB-01",
  "title": "Database access is restricted to the application layer",
  "kind": "ALLOWED_RELATIONSHIP",
  "scope": { "resourceTypes": ["AWS::RDS::DBInstance"] },
  "expected": { "allowedSourceTypes": ["AWS::Lambda::Function"], "port": 5432 },
  "severity": "HIGH",
  "sourceReference": { "fileName": "architecture-adr.md", "lineStart": 18, "lineEnd": 24 },
  "extractionConfidence": 0.91,
  "reviewStatus": "NEEDS_REVIEW"
}
```

These are illustrative fields: the team must implement only constraint types it can validate reliably. Do not claim to understand arbitrary natural-language architecture documents until corresponding extraction and validation logic exists.

### 6.8 Upload intent source

Use a two-step upload so larger files do not have to be sent through a Lambda request body.

1. `POST /v1/intents/upload-url`

Request:

```json
{ "fileName": "architecture-adr.md", "contentType": "text/markdown", "sizeBytes": 12000 }
```

Response:

```json
{
  "data": {
    "uploadUrl": "https://presigned-url-returned-by-backend",
    "objectKey": "incoming/user-scope/upload-id/architecture-adr.md",
    "expiresInSeconds": 300
  },
  "meta": { "requestId": "req_6", "generatedAt": "2026-10-11T06:00:00Z" }
}
```

Frontend PUTs the file bytes to `uploadUrl` with the expected content type; do not send the file to the app's API a second time. Then call the ingestion endpoint.

2. `POST /v1/intents/ingest`

```json
{ "name": "Web application architecture", "objectKeys": ["incoming/user-scope/upload-id/architecture-adr.md"], "sourceType": "ADR" }
```

Return `202 Accepted` and `{ "data": { "intentId": "intent_123", "jobId": "job_123", "status": "PROCESSING" } }`. The frontend polls `GET /v1/jobs/{jobId}` until terminal.

Never allow the client to choose arbitrary S3 object keys outside its authorized scope. Validate filename, extension, content type and size on the server; use unique random object prefixes; use encryption and a lifecycle policy where appropriate.

### 6.9 Evaluation job

`POST /v1/evaluations`

Request:

```json
{ "scope": "SUPPORTED_RESOURCES", "reason": "Manual demo evaluation" }
```

Response: `202 Accepted`

```json
{
  "data": { "jobId": "job_01JDEMO", "status": "QUEUED", "statusUrl": "/v1/jobs/job_01JDEMO", "createdAt": "2026-10-11T06:00:00Z" },
  "meta": { "requestId": "req_7", "generatedAt": "2026-10-11T06:00:00Z" }
}
```

`GET /v1/jobs/{jobId}` returns `QUEUED`, `RUNNING`, `SUCCEEDED`, `PARTIAL`, or `FAILED`, with `progressStage`, `startedAt`, `completedAt`, `resultSummary`, and a safe user-facing `errorMessage` if failed. Never expose exception stack traces in this payload.

### 6.10 Drift events

`GET /v1/drift-events?source=AWS_CONFIG&limit=25&cursor=...`

Rows should include `eventId`, `timestamp`, `source`, `resourceId`, `resourceType`, `changeSummary`, `actor`, `processingStatus`, `relatedFindingIds`, and source event identifiers. `actor` may be null if the source does not establish it.

### 6.11 Remediation requests

`GET /v1/remediations?status=PENDING_APPROVAL&limit=25&cursor=...`

`POST /v1/findings/{findingId}/remediation-requests`

Request:

```json
{ "mode": "REQUEST_APPROVAL", "comment": "Please review the proposed change." }
```

Response:

```json
{
  "data": { "remediationId": "rem_123", "status": "PENDING_APPROVAL", "runbookId": "REVOKE_UNAPPROVED_INGRESS_V1", "dryRun": true },
  "meta": { "requestId": "req_8", "generatedAt": "2026-10-11T06:00:00Z" }
}
```

`POST /v1/remediations/{remediationId}/decision`

```json
{ "decision": "REJECT", "comment": "The path is required for the approved test." }
```

Allowed decisions: `APPROVE`, `REJECT`. Backend must check current status, caller authorization, allowed runbook, and whether the request has already been decided. On duplicate or stale approval, return `409 STATE_CONFLICT`. Step Functions may pause for a callback while approval is pending, but task tokens must remain server-side and must never be sent to React.

### 6.12 Audit and system status

`GET /v1/audit-events?from=...&to=...&action=...&limit=25&cursor=...`

`GET /v1/system/status` returns an overall state plus data source and evaluator status, `lastInventoryAt`, `lastEvaluationAt`, `lastErrorAt`, and a safe error summary. Avoid showing sensitive service details.

---

# Part C — AWS backend architecture and ownership

## 7. Request path vs. background event path

### Interactive request path
React → CloudFront/S3 static files → API Gateway HTTP API (JWT authorizer) → Lambda API handler → DynamoDB/S3 → JSON response.

Use API Gateway Lambda proxy integration. API handlers should validate schemas, authorize actions, call service/repository modules, and return predictable HTTP status codes. Keep long scans, document extraction, and AI calls out of a synchronous dashboard request; return a job ID and run them asynchronously.

### Observation/evaluation path
AWS Config and CloudTrail observe the deployed account. EventBridge rules (where configured) trigger ingestion functions for selected change events. Ingestion normalizes supported resources/relationships and records evidence. The evaluator compares live graph facts with approved intent constraints. Findings are persisted and an audit event is recorded. Optional Step Functions orchestration can call Bedrock only for ambiguous explanations. The API reads the stored result; it does not need to re-run the entire evaluation every time the user opens a page.

### Important AWS data limitations
- AWS Config only supplies details and relationships for resource types it records/supports and the chosen recording configuration. Do not state that it sees every resource relationship in AWS.
- CloudTrail is provenance/change evidence, not a complete current-state graph.
- VPC Flow Logs show observed traffic; they do not prove that every possible path is impossible when no flow is present.
- Start with a small declared resource scope (for example selected VPC/security-group, IAM-role/policy, Lambda, S3 and RDS resources) and label unsupported types.
- A new configuration event should trigger re-evaluation of relevant constraints, but don't cause unbounded full-account scans for every event. Deduplicate and debounce where possible.

## 8. Suggested backend modules

A clean backend repository can use TypeScript/Node.js or Python for Lambda. Pick one runtime for the initial backend to reduce deployment complexity. Python is suitable for parsing IaC/normalizing configuration; Node.js is also suitable for API handlers. Do not split runtime languages unless there is a clear reason.

Suggested logical Lambda functions:
- `api-dashboard`: summary and system status.
- `api-findings`: list/detail/status updates.
- `api-architecture`: graph data for the selected view.
- `api-intents`: create upload URL, list/details, approve version.
- `api-evaluations`: start job and query job status.
- `api-remediation`: request/decide remediation, enforce safety gates.
- `ingest-config-change`: normalize selected Config changes/resource reads.
- `ingest-cloudtrail-event`: capture actor/change metadata where needed.
- `evaluate-conformance`: deterministic constraint checks and graph diff.
- `extract-intent`: parse uploaded files and optionally call Bedrock for candidate extraction.
- `explain-finding`: optional Bedrock explanation grounded in backend-provided evidence.

These are logical boundaries, not a requirement to create every function on day one. MVP can begin with fewer deployed Lambdas if code modules and API contracts stay separated. Use a shared domain package for types, error formats and validation schemas.

## 9. Suggested persistence layout

Keep the physical design matched to access patterns. DynamoDB is not a graph database and does not perform arbitrary joins; do not rely on graph traversals being automatically efficient just because edges are stored there.

A reasonable student MVP:
- **Intent metadata/version table:** intent ID, version, status, author, timestamps, source object keys, constraint count and approval metadata.
- **Resource/relationship storage:** small resource and edge records for the latest inventory. For a small demo, DynamoDB items are sufficient; archive full normalized graph snapshots/evidence JSON in S3.
- **Findings table:** finding ID, severity, status, category, resource ID/type, first/last seen, related constraint, evidence references. Add GSIs for actual list access patterns (`status + createdAt`, `severity + createdAt`) rather than scanning the entire table for every list page.
- **Jobs table:** job ID, status, stage, timestamps, summary and safe error code.
- **Remediation table:** request ID, finding, runbook, requester/approver, status, dry-run/approval timestamps and result.
- **Audit events:** append-oriented records with timestamps, actor and action; write from backend only. For the small demo this can be DynamoDB, with optional S3 archival later.

Exact table names and key design can evolve, but the API response schema should remain stable. Use pay-per-request/on-demand capacity initially only after considering budget needs; it is not a guarantee that the whole AWS deployment is free.

## 10. IAM/security rules

- Each Lambda has a separate execution role or at least distinct policies by function group.
- API read handlers should not have permissions to modify AWS security resources.
- The evaluator/ingestor should get only the read/list/describe permissions needed for selected resource types.
- The remediation worker, when added, gets permissions only for allowlisted reviewed runbooks and target resources.
- Frontend code has no IAM permissions to read AWS account data directly.
- Verify the identity claims in API Gateway; enforce authorization again in the handler for sensitive actions.
- Validate every input. Do not accept arbitrary table names, ARNs, S3 prefixes, runbook IDs, or AWS actions from the browser.
- Use a private S3 bucket and CloudFront Origin Access Control for website hosting. Do not make the bucket publicly readable solely to host the frontend.
- Configure API CORS for the exact development origin(s) and deployed CloudFront origin. Do not use a wildcard origin in production when authenticated requests are involved.
- Never log JWTs, presigned URLs, secrets, full raw user uploads or Step Functions task tokens.
- Use AWS Budgets/cost alerts before enabling AWS Config recording broadly, frequent rule evaluations, Bedrock calls or always-on compute.

## 11. Evaluation logic (the technical core)

For the first version implement a small, auditable rule set—not arbitrary natural-language reasoning.

For each approved constraint:
1. Load the approved intent version and the relevant normalized live resource/edge evidence.
2. Confirm the constraint type is supported by the evaluator.
3. Evaluate it deterministically.
4. Return a clear outcome: `PASS`, `VIOLATION`, `UNKNOWN`, or `NOT_APPLICABLE`.
5. Attach source record IDs and exact fields used to make the decision.
6. Create/update a finding only when the violation satisfies finding-creation/deduplication rules.
7. Preserve the approved intent version and evaluator version on the finding so the result can be reproduced.

LLM responsibilities:
- May propose structured constraints from ADR text for human review.
- May explain a deterministic result in understandable language using a fixed evidence bundle.
- Must not invent a missing resource, relationship, actor, source event or AWS setting.
- Must not directly run arbitrary AWS API actions.
- If source evidence conflicts or is incomplete, return `UNKNOWN` or request human review.

The distinctive demo should prove at least one case where a set of individually ordinary resource configurations violates an explicit approved relationship/path constraint. Compare this against the baseline tools used for the demonstration, and accurately document where they do or do not detect the case.

---

# Part D — Frontend repository structure

## 12. Recommended React project structure

```text
cloud-intent-guardian-frontend/
  src/
    app/
      App.tsx
      router.tsx
      providers.tsx
    auth/
      AuthProvider.tsx
      ProtectedRoute.tsx
      authClient.ts
    api/
      apiClient.ts
      apiTypes.ts
      endpoints.ts
      errors.ts
    components/
      layout/
        AppShell.tsx
        Sidebar.tsx
        TopBar.tsx
        ConnectionStatus.tsx
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
      findings/
        FindingsTable.tsx
        FindingFilters.tsx
        EvidencePanel.tsx
        ViolationPath.tsx
      architecture/
        ArchitectureGraph.tsx
        ArchitectureNode.tsx
        ArchitectureEdge.tsx
        GraphLegend.tsx
        ResourceDetailsDrawer.tsx
      intents/
        UploadIntentDialog.tsx
        ConstraintCard.tsx
        IntentVersionHistory.tsx
      remediation/
        RemediationTable.tsx
        ApprovalDialog.tsx
    features/
      overview/
      architecture/
      findings/
      intents/
      drift-events/
      remediation/
      audit-trail/
      settings/
    hooks/
      useDashboardSummary.ts
      useFindings.ts
      useArchitecture.ts
      useJobs.ts
    types/
      domain.ts
    utils/
      dates.ts
      severity.ts
      graph.ts
    styles/
      index.css
    main.tsx
  public/
  .env.example
  package.json
  README.md
```

Keep API types independent from React components. No page should call `fetch()` directly. Do not place AWS-specific graph diff logic in the frontend.

## 13. Shared TypeScript types (starter contract)

```ts
export type Severity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFO";
export type FindingStatus = "OPEN" | "ACKNOWLEDGED" | "IN_PROGRESS" | "RESOLVED" | "SUPPRESSED";
export type GraphView = "INTENDED" | "LIVE" | "DIFF";
export type DiffState = "MATCHED" | "ADDED" | "MISSING" | "CHANGED" | "UNKNOWN";
export type JobStatus = "QUEUED" | "RUNNING" | "SUCCEEDED" | "PARTIAL" | "FAILED";
export type SystemState = "CONNECTED" | "DEGRADED" | "DISCONNECTED";

export interface ApiMeta {
  requestId: string;
  generatedAt: string;
  nextCursor?: string | null;
  limit?: number;
}

export interface ApiSuccess<T> {
  data: T;
  meta: ApiMeta;
}

export interface ApiFailure {
  error: {
    code: string;
    message: string;
    details?: unknown[];
    requestId?: string;
  };
}

export interface GraphNode {
  id: string;
  label: string;
  resourceType: string;
  state: DiffState;
  source: string;
  region?: string;
  properties?: Record<string, unknown>;
  findingIds: string[];
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label: string;
  relationshipType: string;
  state: DiffState;
  evidenceIds: string[];
  findingIds: string[];
}
```

Expand these types as each endpoint is implemented. Commit shared API fixture files (sanitized fake IDs) so frontend work can continue before AWS resources exist.

---

# Part E — Build sequence and division of responsibilities

## 14. Milestones

### Milestone 1: Agree the contract and make the UI run (no AWS required yet)
**Both:** freeze route names, statuses, severity codes, graph states, and the JSON examples above. Put the contract in the repository and agree how changes are reviewed.

**Frontend owner:** build AppShell, routes, reusable components, and all screens using mock JSON fixtures. Mark demo fixtures clearly in development mode so they are not mistaken for live AWS data.

**Backend owner:** implement the same TypeScript/Python domain types and schema validation; build a basic local Lambda-handler test harness or unit tests. Keep payloads identical to the shared fixtures.

Exit criteria: every route renders, all states are represented, and frontend components consume the agreed API client rather than hard-coded page data.

### Milestone 2: API Gateway + Lambda + Cognito
**Backend pair:** create the Cognito user pool/app client, HTTP API, JWT authorizer, `/v1/health`, `/v1/system/status`, `/v1/dashboard/summary`, findings endpoints, DynamoDB tables and least-privilege roles.

**Frontend owner:** replace mock API calls with real API calls for login, overview, findings and status; preserve mocks behind a deliberate `VITE_USE_MOCKS` development flag if needed.

Exit criteria: an authenticated user loads actual backend data; unauthenticated requests to protected routes are denied; CORS works from localhost and the deployed frontend origin.

### Milestone 3: First real AWS inventory and deterministic detection
**Backend pair:** enable AWS Config for only the needed resource types in the demo account/Region; add read-only collector logic, normalized resource records, graph endpoint and a manual evaluation job. Add one or two well-defined constraints and evidence-backed findings.

**Frontend owner:** connect Architecture Explorer, Evaluation job progress and Finding detail. The graph must show live backend nodes and edges, not fixture data.

Exit criteria: run inventory/evaluation, see real resource metadata, and demonstrate a controlled change that creates a finding.

### Milestone 4: Intent upload/version review and event-driven updates
**Backend pair:** upload through presigned S3 URLs, parse the supported input types, store a draft intent version, expose constraints for review, approve a version, and add EventBridge ingestion for selected Config changes. Do not claim generic Terraform/ADR understanding unless the parser supports it.

**Frontend owner:** implement upload, processing job, review/approve flow, drift event timeline and the graph diff mode.

Exit criteria: approved intent is versioned; a live state change triggers or can be followed by evaluation against that version.

### Milestone 5: Bedrock explanations and human-gated response
**Backend pair:** add evidence-grounded Bedrock explanations behind a feature flag, plus remediation request records and Step Functions approval workflow. Keep real modifying AWS actions disabled at first; use dry-run or a narrowly allowlisted test runbook only after review.

**Frontend owner:** connect explanation panel, remediation request, approval/reject flow and audit trail.

Exit criteria: a finding can be investigated, a remediation requested, approval/rejection recorded, and the entire sequence appears in the audit trail. No task token or unrestricted AWS permission reaches the browser.

### Milestone 6: Deployment and hardening
- Deploy frontend assets to a private S3 bucket behind CloudFront and Origin Access Control.
- Configure SPA route fallback to `index.html`.
- Configure API CORS with explicit localhost/deployed origins.
- Configure logging and alarms, but redact sensitive inputs.
- Set AWS Budgets/cost alerts and clean up unused resources.
- Run end-to-end tests against a dedicated demo stack, not production resources.

## 15. Ownership split

| Workstream | Frontend friend | You / backend pair |
|---|---|---|
| Visual system, routes, responsive shell | Owner | Review API-driven states |
| Overview, findings table, detail UI | Owner | Supply exact payloads and query filters |
| Architecture graph visualization | Owner | Define node/edge schema and compute diff state |
| Intent upload/review UI | Owner | Presigned upload, parser, versioning, constraint approval |
| Cognito frontend login integration | Owner, jointly reviewed | Configure user pool, app client and API authorizer |
| API endpoint handlers and validation | Consume contract | Owner/pair |
| AWS Config/CloudTrail ingestion | Display status | Owner/pair |
| Deterministic conformance engine | Display results only | Owner/pair |
| Bedrock explanation | Display advisory explanation | Owner/pair |
| Remediation approval UI | Owner | Enforce server-side authorization and workflow |
| AWS deployment, cost and security | Collaborate | Owner/pair; frontend handles build/deploy config |

## 16. Pull request and integration rules

1. The shared API contract is the source of truth. Any breaking change must update API types, mock fixtures and backend tests in the same PR.
2. Frontend must never invent successful data if an API fails. Provide an explicit mock mode only in development.
3. Backend must never return a success-shaped response for a failed AWS data source; use a status/error state and partial results where appropriate.
4. Every backend mutation must validate authentication, authorization, state transition, and input schema, and must write a server-generated audit record.
5. Use environment variables for endpoint configuration; do not commit `.env` with private information.
6. Put account IDs, ARNs, and evidence from the demo environment in fixtures only if sanitized and clearly fictionalized where appropriate.
7. Do not merge a frontend button that advertises an action until an API endpoint and backend behavior exist. Hide it or label it “Not enabled” instead.

## 17. Test checklist

### Frontend
- Every page has loading, empty, partial, error and success states.
- Expired/invalid session routes to sign-in and does not loop forever.
- Search/filter/sort/pagination are driven by API response/query parameters.
- Graph handles empty data, unknown edge types, long resource names, truncation and failed requests.
- Upload displays validation, progress and processing failure.
- Approval buttons disable during submission and stale requests show a conflict message.
- The UI never displays `100% compliant` with no successful evaluation.

### API/security
- No token: protected endpoint returns 401.
- Authenticated but unauthorized user: returns 403 for restricted action.
- Invalid request fields: returns 400 with stable error code.
- Missing finding/job: returns 404.
- Stale/double approval: returns 409.
- Rate-limited request: frontend displays retry guidance for 429.
- Internal exception: sanitized 5xx response with request ID; details remain in protected logs.
- CORS works for only the intended origins.
- IAM roles do not let read endpoints modify AWS resources.

### AWS behavior
- Config collector only claims supported resources/relationships.
- Manual evaluation creates stable/deduplicated findings with intent version and evidence.
- Known violation appears in the Findings list and Architecture graph.
- Correcting the test resource causes a later evaluation to resolve/close the finding according to the agreed lifecycle rules.
- Missing/conflicting source data results in `UNKNOWN`/degraded status, not an invented pass.
- Bedrock disabled/unavailable does not break deterministic evaluation.
- Remediation is dry-run or approval-gated; failed/rejected actions are auditable.
- Cost alerts exist before resource recording, repeated evaluations or Bedrock usage are broadened.

---

# Part F — Constraints and references

## 18. Keep the first version narrow

Do not start by implementing every service from the original report (Fargate + ALB, RDS audit store, multi-account Organizations aggregation, Security Hub publication, WAF, Flow Logs analytics, and auto-remediation simultaneously). That would make integration and cost harder to control.

The first credible demo should do these things exceptionally well:
1. Authenticate a user.
2. Read a bounded subset of real AWS inventory/configuration.
3. Maintain one explicitly approved, versioned intent.
4. Evaluate at least one meaningful relationship/path constraint deterministically.
5. Show evidence in Findings and Architecture Explorer.
6. Record every evaluation and analyst decision.

Then add Bedrock explanations, EventBridge near-real-time triggers, and the Step Functions approval workflow.

## 19. Official implementation references

- API Gateway HTTP APIs: https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api.html
- Lambda proxy integration for HTTP APIs: https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html
- HTTP API JWT authorizer: https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html
- Cognito managed login: https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-managed-login.html
- Cognito access to API Gateway resources: https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-accessing-resources-api-gateway-and-lambda.html
- HTTP API CORS: https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-cors.html
- CloudFront private S3 origin / Origin Access Control: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html
- AWS Config resource recording considerations: https://docs.aws.amazon.com/config/latest/developerguide/select-resources.html
- AWS Config pricing: https://aws.amazon.com/config/pricing/
- DynamoDB on-demand capacity: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/on-demand-capacity-mode.html
- Step Functions callback tasks: https://docs.aws.amazon.com/step-functions/latest/dg/connect-to-resource.html

**Bottom line:** keep a single API contract, make every dashboard screen data-driven, keep all AWS access on the server, and build the AWS collector + deterministic intent conformance before the advanced AI/remediation features. That order maximizes the chance of finishing a real, demonstrable AWS project.
