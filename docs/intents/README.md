# Guardian intent review

The exact-ARN draft is stored locally in ignored `backend/local-evidence/guardian-intent-review.json`; its read-only AWS evidence is in `backend/local-evidence/guardian-live-resource-evidence.json`. These files describe only the confirmed Guardian stack: 12 API Lambda functions, one evaluation worker, the evaluations table, and six other DynamoDB tables. No intent was approved or activated during preparation.

The draft requires the observed evaluations-table-to-worker stream relationship in the STRUCTURAL family. Compute and data boundaries request STRUCTURAL assessment. This is a structural stream check, not evidence of IAM data authorization or network reachability. Its boundary edgeTypes field is validated by the updated schema/evaluator. The exact local draft passes validate_manifest. Exact IDs and resource counts were read from CloudFormation and ARN-only service projections; no environment variables or secret values were retrieved.

The existing EC2/RDS baseline remains unchanged. Those observed resources belong to other applications and do not have the required tier tags. They are excluded from the Guardian draft.
