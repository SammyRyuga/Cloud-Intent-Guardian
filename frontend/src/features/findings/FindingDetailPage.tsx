import { AttachmentImpactPanel } from '@/components/common/AttachmentImpactPanel';
import { CandidateHistoryPanel } from '@/components/common/CandidateHistoryPanel';
import { useState } from 'react';
import { hasCapability } from '@/config/capabilities';
import { useParams, Link } from 'react-router-dom';
import { useFinding, useFindingLifecycle } from '@/hooks/apiHooks';
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
  const lifecycle = useFindingLifecycle();
  const [suppressionOpen, setSuppressionOpen] = useState(false);
  const [reason, setReason] = useState('');
  const busy = lifecycle.isPending;
  const hasRevision = finding?.revision !== undefined;

  const transition = (action: 'ACKNOWLEDGE' | 'SUPPRESS' | 'REOPEN') => {
    if (!findingId || finding?.revision === undefined || busy) return;
    lifecycle.mutate(action === 'SUPPRESS'
      ? { id: findingId, action, expectedRevision: finding.revision, reason: reason.trim() }
      : { id: findingId, action, expectedRevision: finding.revision }, {
      onSuccess: () => { setSuppressionOpen(false); setReason(''); },
    });
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
                <h1 className="font-title text-xl font-semibold text-ink max-w-[65ch]">{finding.title}</h1>
              </div>

              <div className="flex flex-wrap items-center gap-2 shrink-0">
                {finding.status === 'OPEN' && hasCapability('findings.update') && finding.revision !== undefined && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => transition('ACKNOWLEDGE')}
                    isLoading={busy}
                    disabled={busy}
                  >
                    <CheckCircle2 className="w-3.5 h-3.5 mr-1.5 stroke-[1.5]" />
                    Acknowledge
                  </Button>
                )}

                {['OPEN', 'ACKNOWLEDGED'].includes(finding.status) && hasCapability('findings.suppress') && hasRevision && (
                  <Button variant="secondary" size="sm" disabled={busy} onClick={() => { lifecycle.reset(); setSuppressionOpen(true); }}>Suppress</Button>
                )}
                {['ACKNOWLEDGED', 'SUPPRESSED'].includes(finding.status) && hasCapability('findings.reopen') && hasRevision && (
                  <Button variant="secondary" size="sm" disabled={busy} isLoading={busy && lifecycle.variables?.action === 'REOPEN'} onClick={() => transition('REOPEN')}>Reopen</Button>
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
            {lifecycle.data && <p role="status" className="text-sm">Finding {lifecycle.variables?.action === 'SUPPRESS' ? 'suppressed' : lifecycle.variables?.action === 'REOPEN' ? 'reopened' : 'acknowledged'}. Server status: {lifecycle.data.item.status}.</p>}
            {!hasRevision && hasCapability('findings.update') && <p className="text-xs text-graphite">Status changes are unavailable because the server did not provide a revision.</p>}
            {lifecycle.error && <div role="alert" className="text-sm text-sev-critical">
              <p>{lifecycle.error.message}</p>
              {'requestId' in lifecycle.error && typeof lifecycle.error.requestId === 'string' && <CopyableId id={lifecycle.error.requestId} />}
              <Button variant="secondary" size="sm" disabled={busy} onClick={() => { lifecycle.reset(); void refetch(); }}>Refresh finding</Button>
            </div>}
            {suppressionOpen && ['OPEN', 'ACKNOWLEDGED'].includes(finding.status) && <Card>
              <CardHeader title="Suppress finding" />
              <p className="text-sm mb-3">Suppression records an audited monitoring decision. It does not change the AWS resource. Approver or admin access is required.</p>
              <form onSubmit={(event) => { event.preventDefault(); if (reason.trim()) transition('SUPPRESS'); }}>
                <label htmlFor="suppression-reason" className="text-sm block mb-1">Suppression reason</label>
                <textarea id="suppression-reason" required maxLength={1000} value={reason} disabled={busy} onChange={(event) => setReason(event.target.value)} className="w-full border border-rule rounded p-2 text-sm bg-sheet text-ink" rows={3} />
                <div className="flex gap-2 mt-3">
                  <Button type="submit" disabled={busy || !reason.trim() || !hasRevision} isLoading={busy && lifecycle.variables?.action === 'SUPPRESS'}>Confirm suppression</Button>
                  <Button type="button" variant="secondary" disabled={busy} onClick={() => { setSuppressionOpen(false); setReason(''); }}>Cancel</Button>
                </div>
              </form>
            </Card>}
            {finding.suppressionReason && <Card><CardHeader title={finding.status === 'SUPPRESSED' ? 'Suppression decision' : 'Previous suppression decision'} /><p className="text-sm">{finding.suppressionReason}</p>{finding.suppressedAt && <p className="mt-2 text-xs text-graphite">Recorded {formatDateTime(finding.suppressedAt)}</p>}</Card>}

            {finding.resourceType === 'AWS::EC2::SecurityGroup' && <AttachmentImpactPanel impact={finding.observed?.attachmentImpact} />}
            {finding.tier === 'TIER_2' && <CandidateHistoryPanel history={finding.history ?? finding.observed?.history} />}
            {finding.evidence && <Card><CardHeader title="Evaluation evidence" /><p className="text-sm mb-3">{finding.explanation}</p>{finding.evidence.map((entry, index) => <div key={index} className="border-t border-rule py-3"><p className="text-xs">{entry.source} - {formatDateTime(entry.observedAt)}</p><CopyableId id={entry.resourceId} /><pre className="text-xs whitespace-pre-wrap break-words mt-2">{JSON.stringify(entry.details, null, 2)}</pre></div>)}</Card>}
            {(finding.tier || finding.reviewStatus || finding.crossValidation || finding.llmConclusion) && (
              <Card>
                <CardHeader
                  title="Cross-validation review"
                  subtitle={[finding.tier, finding.reviewStatus].filter(Boolean).join(' · ')}
                />
                {finding.crossValidation && <div className="space-y-3 text-sm">
                  <p>{finding.crossValidation.reason}</p>
                  <p className="text-xs text-graphite">
                    {finding.crossValidation.accepted ? 'Cross-validation accepted' : 'Cross-validation not accepted'}
                    {finding.crossValidation.simulated ? ' · simulated evidence' : ''}
                  </p>
                  {finding.crossValidation.sourceVerdicts.length > 0 ? (
                    <ul className="divide-y divide-rule border-y border-rule">
                      {finding.crossValidation.sourceVerdicts.map((verdict, index) => <li key={`${verdict.evidenceId}-${index}`} className="py-3 space-y-1">
                        <div className="flex flex-wrap gap-x-2 text-xs font-medium">
                          <span>{verdict.sourceFamily}</span><span>{verdict.verdict}</span>
                          {verdict.eligible !== undefined && <span>{verdict.eligible ? 'Eligible' : 'Not eligible'}</span>}
                        </div>
                        <p className="text-xs">{verdict.predicate}</p>
                        <div className="flex flex-wrap gap-2 text-xs text-graphite">
                          <span>Observed {formatDateTime(verdict.observedAt)}</span>
                          {verdict.evidenceId && <span>Evidence <CopyableId id={verdict.evidenceId} /></span>}
                          {verdict.originId && <span>Origin <CopyableId id={verdict.originId} /></span>}
                          {verdict.sourceId && <span>Source <CopyableId id={verdict.sourceId} /></span>}
                          {verdict.targetId && <span>Target <CopyableId id={verdict.targetId} /></span>}
                          {verdict.snapshotId && <span>Snapshot <CopyableId id={verdict.snapshotId} /></span>}
                        </div>
                      </li>)}
                    </ul>
                  ) : <p className="text-xs text-graphite">The server returned no source verdicts for this finding.</p>}
                </div>}
                {finding.llmConclusion && <div className="mt-4 border-t border-rule pt-3 space-y-1">
                  <h3 className="text-xs font-semibold">Advisory model conclusion · {finding.llmConclusion.verdict}</h3>
                  <p className="text-sm">{finding.llmConclusion.explanation}</p>
                  <p className="text-xs text-graphite">Candidate {finding.llmConclusion.candidateId}; this conclusion does not change the finding or its eligibility.</p>
                </div>}
                {finding.tier === 'TIER_2' && <p className="mt-3 border-t border-rule pt-3 text-xs text-graphite">Tier 2 findings require human review. Automated remediation is unavailable for this tier.</p>}
              </Card>
            )}
            {(finding.severityScore !== undefined || finding.severityFactors || finding.confidence || finding.constraintSeverity) && (
              <Card>
                <CardHeader
                  title="Server severity factors"
                  subtitle={finding.severityScore !== undefined ? `Score ${finding.severityScore}` : `Severity ${finding.severity}`}
                />
                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                  <div>
                    <dt className="text-pencil text-xs">Displayed severity</dt>
                    <dd className="mt-1"><SeverityBadge severity={finding.severity} /></dd>
                  </div>
                  {finding.constraintSeverity && <div>
                    <dt className="text-pencil text-xs">Original constraint severity</dt>
                    <dd className="mt-1">{finding.constraintSeverity}</dd>
                  </div>}
                  {(finding.confidence || finding.severityFactors?.confidence) && <div>
                    <dt className="text-pencil text-xs">Evidence confidence</dt>
                    <dd className="mt-1">{finding.confidence ?? finding.severityFactors?.confidence.label}</dd>
                    {finding.severityFactors?.confidence && <p className="mt-1 text-xs text-graphite">{finding.severityFactors.confidence.explanation}</p>}
                  </div>}
                </dl>
                {finding.severityFactors && <div className="mt-4 border-t border-rule pt-3 space-y-3">
                  <p className="text-xs text-pencil">Formula version {finding.severityFactors.formulaVersion}</p>
                  <p className="text-sm">{finding.severityFactors.explanation}</p>
                  <dl className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div>
                      <dt className="text-pencil text-xs">Base severity</dt>
                      <dd>{finding.severityFactors.baseSeverity.label} · {finding.severityFactors.baseSeverity.points} points</dd>
                    </div>
                    <div>
                      <dt className="text-pencil text-xs">Component criticality</dt>
                      <dd>{finding.severityFactors.componentCriticality.label} · {finding.severityFactors.componentCriticality.points} points</dd>
                      {finding.severityFactors.componentCriticality.defaulted && <p className="text-xs text-graphite">Default criticality was used.</p>}
                      {finding.severityFactors.componentCriticality.componentIds.length > 0 && <div className="mt-1 flex flex-wrap gap-2">{finding.severityFactors.componentCriticality.componentIds.map((id) => <CopyableId key={id} id={id} />)}</div>}
                    </div>
                    <div>
                      <dt className="text-pencil text-xs">Blast radius</dt>
                      <dd>{finding.severityFactors.blastRadius.count} downstream resources · {finding.severityFactors.blastRadius.points} points</dd>
                      <p className="mt-1 text-xs text-graphite">{finding.severityFactors.blastRadius.explanation}</p>
                      <p className="text-xs text-graphite">Coverage: {finding.severityFactors.blastRadius.complete ? 'complete' : 'incomplete'}</p>
                      {finding.severityFactors.blastRadius.downstreamResourceIds.length > 0 && <div className="mt-1 flex flex-wrap gap-2">{finding.severityFactors.blastRadius.downstreamResourceIds.map((id) => <CopyableId key={id} id={id} />)}</div>}
                    </div>
                    <div>
                      <dt className="text-pencil text-xs">Exposure</dt>
                      <dd>{finding.severityFactors.exposure.label} · {finding.severityFactors.exposure.points} points</dd>
                      <p className="mt-1 text-xs text-graphite">{finding.severityFactors.exposure.explanation}</p>
                    </div>
                    <div>
                      <dt className="text-pencil text-xs">Confidence factor</dt>
                      <dd>{finding.severityFactors.confidence.label} · {finding.severityFactors.confidence.points} points</dd>
                      <p className="mt-1 text-xs text-graphite">{finding.severityFactors.confidence.explanation}</p>
                    </div>
                  </dl>
                </div>}
              </Card>
            )}
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
                      <ul className="list-disc pl-4 space-y-1 text-pencil font-mono text-xs">
                        {finding.aiExplanation.citedEvidence.map((ev, idx) => (
                          <li key={idx}>{ev}</li>
                        ))}
                      </ul>
                    </div>

                    <div className="pt-2 border-t border-rule text-xs text-pencil italic">
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
