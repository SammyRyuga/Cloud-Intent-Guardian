import { hasCapability } from '@/config/capabilities';
import { useRemediations, useRemediationDecision } from '@/hooks/apiHooks';
import { StateBoundary } from '@/components/common/StateBoundary';
import { SeverityBadge } from '@/components/common/SeverityBadge';
import { CopyableId } from '@/components/common/CopyableId';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { formatDateTime } from '@/utils/dates';
import { ShieldCheck, XCircle } from 'lucide-react';
import type { RemediationRequest } from '@/types/domain';

export function RemediationPage() {
  const { data, isLoading, isError, error, refetch } = useRemediations();
  const decisionMutation = useRemediationDecision();

  const handleDecision = (id: string, decision: 'APPROVE' | 'REJECT') => {
    decisionMutation.mutate({ id, decision });
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="font-title text-2xl font-bold text-ink">Remediation Approvals</h1>
        <p className="text-xs text-graphite mt-1">
          Review, dry-run inspect, and gate actions for aligning drift violations back to declared baseline
        </p>
      </div>

      <StateBoundary
        isNotEnabled={!hasCapability('remediation')}
        isLoading={isLoading}
        isError={isError}
        error={error}
        isEmpty={data?.items.length === 0}
        emptyTitle="No remediation requests"
        emptyDescription="There are no pending remediation approval workflows awaiting review."
        onRetry={() => refetch()}
      >
        {data && (
          <div className="space-y-4">
            {data.items.map((rem: RemediationRequest) => (
              <Card key={rem.id}>
                <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 pb-3 border-b border-rule">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <SeverityBadge severity={rem.severity} />
                      <span className="font-mono text-xs text-pencil bg-film px-1.5 py-0.5 rounded border border-rule">
                        {rem.id}
                      </span>
                      <span
                        className={`text-xs px-2 py-0.5 rounded font-semibold border ${
                          rem.status === 'APPROVED'
                            ? 'bg-survey/10 border-survey/30 text-survey'
                            : rem.status === 'REJECTED'
                            ? 'bg-sev-critical/10 border-sev-critical/30 text-sev-critical'
                            : 'bg-sev-medium/10 border-sev-medium/30 text-sev-medium'
                        }`}
                      >
                        {rem.status}
                      </span>
                    </div>
                    <h3 className="font-title text-base font-semibold text-ink">{rem.findingTitle}</h3>
                  </div>

                  {/* Approval Actions (INV-12, INV-15: dry-run or approval-gated only) */}
                  {rem.status === 'PENDING_APPROVAL' && (
                    <div className="flex items-center gap-2">
                      <Button
                        variant="danger-outline"
                        size="sm"
                        onClick={() => handleDecision(rem.id, 'REJECT')}
                        isLoading={decisionMutation.isPending}
                        disabled={decisionMutation.isPending}
                      >
                        <XCircle className="w-3.5 h-3.5 mr-1.5 stroke-[1.5]" />
                        Reject plan
                      </Button>
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => handleDecision(rem.id, 'APPROVE')}
                        isLoading={decisionMutation.isPending}
                        disabled={decisionMutation.isPending}
                      >
                        <ShieldCheck className="w-3.5 h-3.5 mr-1.5 stroke-[1.5]" />
                        Approve action
                      </Button>
                    </div>
                  )}
                </div>

                <div className="pt-3 space-y-3 text-xs">
                  <div>
                    <span className="text-pencil font-medium block mb-1">Planned Remediation Command</span>
                    <div className="p-2.5 bg-film rounded font-mono text-[11px] text-ink border border-rule">
                      {rem.plannedAction}
                    </div>
                  </div>

                  {rem.dryRunOutput && (
                    <div>
                      <span className="text-pencil font-medium block mb-1">Dry-Run Simulation Output (INV-15)</span>
                      <div className="p-2.5 bg-film rounded font-mono text-[11px] text-graphite border border-rule">
                        {rem.dryRunOutput}
                      </div>
                    </div>
                  )}

                  <div className="flex flex-wrap items-center justify-between text-pencil pt-2 border-t border-rule">
                    <div className="flex items-center gap-3">
                      <span>
                        Resource: <CopyableId id={rem.resourceId} />
                      </span>
                      <span>Requested by: <strong className="font-mono text-ink">{rem.requestedBy}</strong></span>
                    </div>
                    <span>{formatDateTime(rem.requestedAt)}</span>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </StateBoundary>
    </div>
  );
}
