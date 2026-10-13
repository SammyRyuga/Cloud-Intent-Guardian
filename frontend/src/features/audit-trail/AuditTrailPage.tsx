import { hasCapability } from '@/config/capabilities';
import { useAuditEvents } from '@/hooks/apiHooks';
import { StateBoundary } from '@/components/common/StateBoundary';
import { CopyableId } from '@/components/common/CopyableId';
import { formatDateTime } from '@/utils/dates';
import type { AuditEvent } from '@/types/domain';

export function AuditTrailPage() {
  const { data, isLoading, isError, error, refetch } = useAuditEvents();

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="font-title text-2xl font-bold text-ink">Immutable Audit Trail</h1>
        <p className="text-xs text-graphite mt-1">
          Server-generated activity log recording evaluations, remediation approvals, and system events (INV-17)
        </p>
      </div>

      <StateBoundary
        isNotEnabled={!hasCapability('auditTrail')}
        isLoading={isLoading}
        isError={isError}
        error={error}
        isEmpty={data?.items.length === 0}
        emptyTitle="No audit log entries recorded"
        emptyDescription="System activity will appear here once actions are performed."
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
                  <th className="py-2.5 px-4">Details</th>
                  <th className="py-2.5 px-4">IP Address</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {data.items.map((item: AuditEvent) => (
                  <tr key={item.id} className="hover:bg-film/60">
                    <td className="py-3 px-4 text-pencil whitespace-nowrap">{formatDateTime(item.timestamp)}</td>
                    <td className="py-3 px-4 font-mono font-medium text-ink">{item.actor}</td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-[11px] bg-film px-1.5 py-0.5 rounded border border-rule text-ink">
                        {item.action}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-ink/90">
                      <div>{item.details}</div>
                      {item.resourceId && (
                        <div className="mt-1">
                          <CopyableId id={item.resourceId} />
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-4 font-mono text-pencil">{item.ipAddress || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </StateBoundary>
    </div>
  );
}
