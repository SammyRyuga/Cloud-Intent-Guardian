const approvedIntentAction = {
  to: '/intents',
  label: 'Create and approve an intent',
} as const;

export function getEvaluationErrorGuidance(error: unknown) {
  if (typeof error !== 'object' || error === null || !('code' in error)) return null;
  return error.code === 'NO_APPROVED_INTENT' ? approvedIntentAction : null;
}
