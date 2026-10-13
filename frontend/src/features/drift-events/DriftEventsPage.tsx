import { hasCapability } from '@/config/capabilities';
import { useDriftEvents } from '@/hooks/apiHooks';
import { StateBoundary } from '@/components/common/StateBoundary';
import { CopyableId } from '@/components/common/CopyableId';
import { formatDateTime } from '@/utils/dates';
import { formatResourceType } from '@/utils/format';
import { Card } from '@/components/ui/Card';
import type { DriftEvent } from '@/types/domain';

export function DriftEventsPage() {
  const { data, isLoading, isError, error, refetch } = useDriftEvents();

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="font-title text-2xl font-bold text-ink">Configuration Drift Events</h1>
        <p className="text-xs text-graphite mt-1">
          Historical timeline of unapproved or out-of-band modifications captured from AWS CloudTrail and config streams
        </p>
      </div>

      <StateBoundary
        isNotEnabled={!hasCapability('driftEvents')}
        isLoading={isLoading}
        isError={isError}
        error={error}
        isEmpty={data?.items.length === 0}
        emptyTitle="No drift events detected"
        emptyDescription="There are currently no recorded divergence events between deployed cloud state and declared intent."
        onRetry={() => refetch()}
      >
        {data && (
          <div className="space-y-4">
            {data.items.map((event: DriftEvent) => {
              const eventTypeColors: Record<'CREATED' | 'MODIFIED' | 'DELETED', string> = {
                CREATED: 'bg-sev-low/10 text-sev-low border-sev-low/30',
                MODIFIED: 'bg-sev-medium/10 text-sev-medium border-sev-medium/30',
                DELETED: 'bg-sev-critical/10 text-sev-critical border-sev-critical/30',
              };

              return (
                <Card key={event.id} padding="md">
                  <div className="flex flex-col md:flex-row md:items-start justify-between gap-2 mb-3">
                    <div className="flex items-center gap-2">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold border ${
                          eventTypeColors[event.eventType]
                        }`}
                      >
                        {event.eventType}
                      </span>
                      <span className="font-title text-sm font-semibold text-ink">{event.diffSummary}</span>
                    </div>
                    <span className="text-xs text-pencil whitespace-nowrap">{formatDateTime(event.timestamp)}</span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs pt-2 border-t border-rule">
                    <div>
                      <span className="text-pencil block mb-1">Resource ID</span>
                      <CopyableId id={event.resourceId} />
                    </div>
                    <div>
                      <span className="text-pencil block mb-1">Resource Type</span>
                      <span className="font-mono text-ink">{formatResourceType(event.resourceType)}</span>
                    </div>
                  </div>

                  {/* Before / After state per INV-08: never fabricated, render only what was received */}
                  {(event.previousState || event.currentState) && (
                    <div className="mt-3 pt-3 border-t border-rule grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                      {event.previousState && (
                        <div className="bg-film p-2.5 rounded border border-rule">
                          <span className="text-[11px] font-semibold text-graphite block mb-1">Previous State</span>
                          <pre className="font-mono text-[11px] text-ink overflow-x-auto">
                            {JSON.stringify(event.previousState, null, 2)}
                          </pre>
                        </div>
                      )}
                      {event.currentState && (
                        <div className="bg-film p-2.5 rounded border border-rule">
                          <span className="text-[11px] font-semibold text-graphite block mb-1">Observed Drift State</span>
                          <pre className="font-mono text-[11px] text-ink overflow-x-auto">
                            {JSON.stringify(event.currentState, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </StateBoundary>
    </div>
  );
}
