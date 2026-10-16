import type { CandidateHistory } from '@/types/domain';
import { CopyableId } from './CopyableId';
const labels = { FIRST_OBSERVATION: 'First observation', PREVIOUSLY_OBSERVED: 'Previously observed', NEW: 'New in this comparison', UNKNOWN: 'Historical comparison unavailable' };
export function CandidateHistoryPanel({ history }: { history?: CandidateHistory }) {
  return <section className="border border-rule rounded-xl p-5 bg-sheet">
    <h3 className="text-base font-semibold">Historical context</h3>
    {!history ? <p className="mt-2 text-sm text-graphite">Historical context was not collected. This finding alone does not establish a change.</p> : <>
      <p className="mt-3 text-sm font-semibold">{labels[history.status]}</p><p className="mt-1 text-sm text-graphite">{history.reason}</p>
      <p className="mt-2 text-sm text-graphite">{history.isHistoricalChange ? 'The server correlated this record with a historical change.' : 'No historical change is established by this record.'}</p>
      <p className="mt-3 text-xs text-graphite">Comparison is limited to the same intent and immutable version.</p>
      {history.previousEvaluationId && <div className="mt-3 text-xs"><span className="text-graphite">Previous evaluation </span><CopyableId id={history.previousEvaluationId} /></div>}
      {history.driftEventIds.length > 0 && <div className="mt-3 text-xs"><span className="block mb-1 text-graphite">Correlated drift events</span>{history.driftEventIds.map(id => <div key={id}><CopyableId id={id} /></div>)}</div>}
    </>}
  </section>;
}
