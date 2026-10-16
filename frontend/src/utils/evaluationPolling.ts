const POLL_INTERVAL_MS = 5000;
const POLL_WINDOW_MS = 15 * 60 * 1000;

/** Refresh only the visible page while it contains unfinished server-reported runs. */
export function evaluationPollInterval(
  items: readonly { status: string }[] | undefined,
  startedAt: number,
  now = Date.now(),
): number | false {
  if (now - startedAt >= POLL_WINDOW_MS) return false;
  if (items && !items.some(({ status }) => status === 'QUEUED' || status === 'RUNNING')) return false;
  return POLL_INTERVAL_MS;
}
