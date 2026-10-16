# Guardian architecture review workspace

## Design direction

Guardian is a working instrument for reviewing a declared AWS architecture against observed evidence. Its distinctive object is the relationship map and the chain from approved intent to evaluation, findings and an audited decision. The interface should make that chain legible, rather than present an interchangeable collection of metric cards.

### Tokens

Keep the PRD palette and self-hosted fonts. Use `film` #F6F8FB as the working surface, `sheet` #FFFFFF for evidence, `ink` #172033 for reading, `graphite` #5A677B for secondary text, `prussian` #183B87 for selection and primary actions, and `survey` #1B7A4B only for confirmed healthy states. Retain the existing severity colors and shape labels. Borders encode regions and grouping; no shadows, gradients or decorative color washes.

Atkinson Hyperlegible Next is the reading and control face. Archivo titles have a narrower, deliberate 600-weight treatment. Atkinson Mono is restricted to real identifiers, timestamps where useful, and code. Titles: 28/32 desktop, 24/28 mobile; body: 14/21; supporting labels: 12/18. No tracked uppercase labels or invented category eyebrows.

### Layout alternatives and choice

A conventional four-card overview makes unrelated counts equally important. A full-screen map as the only entry obscures incomplete evaluation states. Choose a review desk: one clearly framed evaluation control, one dominant conformance/evidence summary, then a quiet supporting register of findings and recent evaluations. Navigation mirrors the review workflow.

```text
Desktop
[Guardian / review navigation] [route context          connection / user]
                              [Page title and purpose                  ]
                              [Selected approved intent / evaluate     ]
                              [Evaluation result       | Attention     ]
                              [Rule/severity register  | Drift/actions ]
                              [Evaluation history with real status     ]

Architecture
[title / view controls] [intent / version / component scope]
[resource index        | relationship canvas             | details]
[                      | map controls + provenance       |        ]

Mobile
[Guardian / connection] [scrollable complete navigation]
[title]
[scope selector]
[action]
[result / attention stacked]
[records with deliberate horizontal table scroll]
```

Left-align text and actions. Keep page widths bounded for reading, but allow the architecture canvas to occupy the available workspace. Use dividers and rows for data registers instead of repeated nested cards. Desktop navigation is compact and grouped by review/operations; mobile exposes every route, not just four of them. All primary controls remain keyboard reachable with visible focus.

### Principles

- The map is a map, with a persistent resource index and an inspectable evidence drawer.
- Evaluation must begin from an explicit approved baseline and show its identity before running.
- Conformance is meaningful only beside coverage and evaluation provenance. Unknown stays neutral.
- Findings are a working register. Reason, revision and confirmation accompany lifecycle decisions.
- Keep every backend response, pagination cursor, error state and action contract intact.
- Keep visual emphasis scarce: active navigation, selected graph nodes and the primary action.

## Review before implementation

The initial idea of a dark navigation rail was rejected: it would add a generic developer-console accent without conveying evidence. The default four-stat-card grid is rejected because it hides the evaluation workflow. The revised design uses the existing light palette, a compact workflow navigation rail, an asymmetric overview and a persistent graph index. The subject-specific chain of intent, observation and decision carries the identity; decorative illustrations or stock metrics do not.

## Verification and critique

Two screenshot review rounds will cover 390, 768 and 1440 pixel widths using explicit local fixtures. Check the overview, graph, findings, intents, remediation and audit. Verify mobile navigation, selector width, table overflow, graph detail focus, pending actions and non-success states. Record final checks and remaining limits here after implementation.

### Screenshot critique, round 1

Inspected overview, architecture and findings at 1440 and 390 pixels. The review command and asymmetric summary establish a clearer task hierarchy, while the graph index makes resources reachable without decoding the canvas. Corrected three concrete weaknesses: mobile header omitted product identity; left-to-right layout still used top/bottom node handles; nonnumeric capability states were oversized like counts. Reduced grid strength, collapsed the drawing key by default to give the relationship map more room, removed a duplicate resource count, and condensed mobile supporting metrics into readable rows. Kept all values and graph classifications sourced from responses.

### Screenshot critique, round 2 and final verification

Reviewed final screenshots at 390, 768 and 1440 pixels, including overview, the mobile resource index, tablet canvas, desktop map, intent editor, remediation and audit. Final map frames encode resource categories: compute chamfers, network hexagons, data plates and identity capsules. Known edge types have readable labels; unknown labels and all raw relationship evidence remain intact. Search highlights loaded nodes without requesting more inventory. The intent editor and stored declarations form a two-column desktop workspace; mobile findings become readable records. Wide audit data stays inside its own scroll container. Audit targets render as typed identifiers rather than forcing readers through serialized JSON.

Final local validation: 42 unit tests, 19 contract tests, production TypeScript/build and lint passed. Lint retains two existing Fast Refresh warnings in AuthProvider and Button. Ten Chrome browser tests passed: all six review pages at 390/768/1440, complete mobile navigation, no horizontal main overflow, resource keyboard selection and Escape/focus return, partial attachment context, first-observation history, suppression/reopening, permission/conflict handling, explicit approved-intent selection, and stale evaluation history/polling. The screenshot set is `/private/tmp/cig-review-round2-{page}-{width}.png`; the first comparison set uses `round1`.

These browser tests intercept APIs with explicit local fixtures. They do not prove Cognito or cloud connectivity, and no cloud mutations were performed. The real local API browser journey requires its DynamoDB/SAM services and was not rerun during this visual pass. Large live-account graph performance was not benchmarked. No new packages, authentication changes or API routes were introduced.
