import { useCapability } from '@/hooks/useCapability';
import { useAuditEvents } from '@/hooks/apiHooks';
import { StateBoundary } from '@/components/common/StateBoundary';
import { formatDateTime } from '@/utils/dates';
import { useSearchParams } from 'react-router-dom';
import type { AuditEvent } from '@/api/backendSchemas';
import { Button } from '@/components/ui/Button';

export function AuditTrailPage() {
  const auditEnabled = useCapability('auditTrail');
  const [params, setParams] = useSearchParams();
  const cursor = params.get('nextToken') || undefined;
  const { data, isLoading, isError, error, refetch } = useAuditEvents(cursor);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="font-title text-2xl font-bold text-ink">Immutable Audit Trail</h1>
        <p className="text-xs text-graphite mt-1">
          Server-generated activity in the configured scope (INV-17)
        </p>
      </div>

      <StateBoundary
        isNotEnabled={!auditEnabled}
        isLoading={isLoading}
        isError={isError}
        error={error}
        isEmpty={data?.items.length === 0}
        emptyTitle="No audit entries on this page"
        emptyDescription="Server activity will appear here after an audited action is recorded."
        onRetry={() => refetch()}
      >
        {data && (
          <div className="rounded-[12px] border border-rule bg-sheet overflow-hidden">
            <table className="w-full text-left text-xs">
              <thead className="bg-film border-b border-rule text-graphite font-medium">
                <tr>
                  <th className="py-2.5 px-4">Timestamp</th>
                  <th className="py-2.5 px-4">Actor</th>
                  <th className="py-2.5 px-4">Action</th>
                  <th className="py-2.5 px-4">Result and target</th>
                  <th className="py-2.5 px-4">Request</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {data.items.map((item: AuditEvent) => (
                  <tr key={item.auditId} className="hover:bg-film/60">
                    <td className="py-3 px-4 text-pencil whitespace-nowrap">{formatDateTime(item.timestamp)}</td>
                    <td className="py-3 px-4 font-mono font-medium text-ink">{item.actor.displayName || item.actor.sub}</td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-[11px] bg-film px-1.5 py-0.5 rounded border border-rule text-ink">
                        {item.action}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-ink/90">
                      <div>{item.result}</div>
                      <pre className="mt-1 max-w-lg whitespace-pre-wrap break-words font-mono text-[11px] text-pencil">{typeof item.target === 'string' ? item.target : JSON.stringify(item.target)}</pre>
                      {item.evaluationId && <div className="mt-1 font-mono text-[11px]">Evaluation {item.evaluationId}</div>}
                    </td>
                    <td className="py-3 px-4 font-mono text-pencil">{item.requestId}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </StateBoundary>
      {data?.nextToken && <Button variant="secondary" onClick={() => {
        const next = new URLSearchParams(params);
        next.set('nextToken', data.nextToken!);
        setParams(next);
      }}>Next page</Button>}
      {cursor && <Button variant="secondary" onClick={() => {
        const next = new URLSearchParams(params);
        next.delete('nextToken');
        setParams(next);
      }}>First page</Button>}
    </div>
  );
}
