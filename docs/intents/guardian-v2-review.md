# Guardian version 2 review

Status: saved as DRAFT; version 1 remains active until explicit owner approval.
Intent: `9af2782d-f80b-41f8-9bd7-eeefddeb672d`.
Name: Guardian serverless architecture baseline.

The refreshed draft includes the deployed drift handler/table and retains the
original resource groups and evaluations-stream-to-worker requirement. It adds
exact observed API/JWT/Cognito wiring and role/policy declarations to the model.

| Zone | Members | Criticality |
| --- | ---: | --- |
| Compute | 14 Lambda functions | HIGH |
| Data | 8 DynamoDB tables | CRITICAL |
| Ingress | 29 routes plus API | HIGH |
| Identity | 14 execution roles, authorizer, user pool | HIGH |

There are 68 exact-ID components, 144 required structural relationships and four
trust boundaries. Fresh metadata preview passed 217 checks, with zero UNKNOWN
outcomes or findings. All 28 application routes use JWT; health is public.
No AWS resource configuration was changed to make the preview pass.

Approval establishes this configuration as the intended serverless baseline.
It does not assert effective IAM access, application-session success, packet
reachability or completeness of IAM permission analysis. Declarations remain
partial evidence; authorization remains UNKNOWN. Missing network corroboration
requires human review. Remediation stays disabled and dry-run.

The complete manifest and service observations are intentionally ignored local
artifacts under `backend/local-evidence/guardian-expanded-*`. The canonical
manifest SHA-256 is
`f68b65b30f89413a2038cd08bc2c75e5f6c31c6558412fcc68b6e3d61f5f452e`.
A version-creation handler call saved the exact manifest as version 2; no approval
was performed as part of preparation.
