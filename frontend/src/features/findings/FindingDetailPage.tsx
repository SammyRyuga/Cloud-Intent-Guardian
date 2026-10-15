import { hasCapability } from '@/config/capabilities';
import { useParams, Link } from 'react-router-dom';
import { useFinding, useAcknowledgeFinding } from '@/hooks/apiHooks';
import { StateBoundary } from '@/components/common/StateBoundary';
import { SeverityBadge } from '@/components/common/SeverityBadge';
import { CopyableId } from '@/components/common/CopyableId';
import { Card, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { formatDateTime } from '@/utils/dates';
import { formatResourceType } from '@/utils/format';
import { ArrowLeft, CheckCircle2, Bot, Wrench } from 'lucide-react';

export function FindingDetailPage() {
  const { findingId } = useParams<{ findingId: string }>();
  const { data: finding, isLoading, isError, error, refetch } = useFinding(findingId || '');
  const acknowledgeFinding = useAcknowledgeFinding();

  const handleAcknowledge = () => {
    if (findingId && finding?.revision !== undefined) {
      acknowledgeFinding.mutate({ id: findingId, expectedRevision: finding.revision });
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <Link to="/findings" className="inline-flex items-center text-xs text-graphite hover:text-ink gap-1 mb-2">
        <ArrowLeft className="w-3.5 h-3.5 stroke-[1.5]" />
        Back to findings
      </Link>

      <StateBoundary isLoading={isLoading} isError={isError} error={error} onRetry={() => refetch()}>
        {finding && (
          <>
            {/* Header info */}
            <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <SeverityBadge severity={finding.severity} />
                  <span className="font-mono text-xs text-pencil bg-film px-1.5 py-0.5 rounded border border-rule">
                    {finding.ruleId}
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded font-medium border border-rule bg-sheet text-ink">
                    {finding.status}
                  </span>
                </div>
                <h1 className="font-title text-xl font-bold text-ink">{finding.title}</h1>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                {finding.status === 'OPEN' && hasCapability('findings.update') && finding.revision !== undefined && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleAcknowledge}
                    isLoading={acknowledgeFinding.isPending}
                    disabled={acknowledgeFinding.isPending}
                  >
                    <CheckCircle2 className="w-3.5 h-3.5 mr-1.5 stroke-[1.5]" />
                    Acknowledge
                  </Button>
                )}

                {/* INV-14 & INV-15: Remediation is approval-gated and visible only if available */}
                {finding.remediationAvailable ? (
                  <Link to="/remediation">
                    <Button variant="primary" size="sm">
                      <Wrench className="w-3.5 h-3.5 mr-1.5 stroke-[1.5]" />
                      Request remediation
                    </Button>
                  </Link>
                ) : (
                  <Button variant="secondary" size="sm" disabled title="No automated remediation playbook">
                    Remediation not enabled
                  </Button>
                )}
              </div>
            </div>
            {acknowledgeFinding.data && <p role="status" className="text-sm">Finding acknowledged.</p>}
            {finding.status === 'OPEN' && hasCapability('findings.update') && finding.revision === undefined && <p className="text-xs text-graphite">Acknowledge is unavailable because the server did not provide a revision.</p>}
            {acknowledgeFinding.error && <p role="alert" className="text-sm text-sev-critical">{acknowledgeFinding.error.message}</p>}

            {finding.evidence && <Card><CardHeader title="Evaluation evidence" /><p className="text-sm mb-3">{finding.explanation}</p>{finding.evidence.map((entry, index) => <div key={index} className="border-t border-rule py-3"><p className="text-xs">{entry.source} - {formatDateTime(entry.observedAt)}</p><CopyableId id={entry.resourceId} /><pre className="text-xs whitespace-pre-wrap break-words mt-2">{JSON.stringify(entry.details, null, 2)}</pre></div>)}</Card>}
            {/* Finding Details Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Card className="md:col-span-2">
                <CardHeader title="Violation Description" />
                <p className="text-sm text-ink/90 leading-relaxed">{finding.description}</p>

                <div className="mt-6 pt-4 border-t border-rule grid grid-cols-2 gap-4 text-xs">
                  <div>
                    <span className="text-pencil block mb-1">Target Resource</span>
                    <CopyableId id={finding.resourceId} />
                  </div>
                  <div>
                    <span className="text-pencil block mb-1">Resource Type</span>
                    <span className="font-mono text-ink">{formatResourceType(finding.resourceType)}</span>
                  </div>
                  <div>
                    <span className="text-pencil block mb-1">First Detected</span>
                    <span className="text-ink">{formatDateTime(finding.detectedAt)}</span>
                  </div>
                  <div>
                    <span className="text-pencil block mb-1">Last Evaluation</span>
                    <span className="text-ink">{formatDateTime(finding.updatedAt)}</span>
                  </div>
                </div>
              </Card>

              {/* AI-Assisted Explanation Panel (INV-16: Strictly labelled and advisory disclaimer) */}
              <Card>
                <div className="flex items-center gap-2 border-b border-rule pb-2 mb-3">
                  <Bot className="w-4 h-4 text-graphite stroke-[1.5]" />
                  <h3 className="font-title text-sm font-semibold text-ink">AI-assisted explanation</h3>
                </div>

                {finding.aiExplanation ? (
                  <div className="space-y-3 text-xs">
                    <div>
                      <span className="text-pencil font-medium block mb-1">Summary</span>
                      <p className="text-ink/90">{finding.aiExplanation.summary}</p>
                    </div>

                    <div>
                      <span className="text-pencil font-medium block mb-1">Rationale</span>
                      <p className="text-ink/90">{finding.aiExplanation.rationale}</p>
                    </div>

                    <div>
                      <span className="text-pencil font-medium block mb-1">Cited Evidence</span>
                      <ul className="list-disc pl-4 space-y-1 text-pencil font-mono text-[11px]">
                        {finding.aiExplanation.citedEvidence.map((ev, idx) => (
                          <li key={idx}>{ev}</li>
                        ))}
                      </ul>
                    </div>

                    <div className="pt-2 border-t border-rule text-[11px] text-pencil italic">
                      "This explanation is advisory. Check it against the evidence."
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-pencil">No AI explanation has been requested for this finding.</p>
                )}
              </Card>
            </div>
          </>
        )}
      </StateBoundary>
    </div>
  );
}
