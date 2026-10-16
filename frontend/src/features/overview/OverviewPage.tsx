import { useCapability } from '@/hooks/useCapability';
import { env } from '@/config/env';
import React, { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useDashboardSummary, useEvaluation, useEvaluations, useRunEvaluation, useManifestIntents } from '@/hooks/apiHooks';
import { queryKeys } from '@/api/queryKeys';
import { Card, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { SeverityBadge } from '@/components/common/SeverityBadge';
import { StateBoundary } from '@/components/common/StateBoundary';
import { formatDateTime } from '@/utils/dates';
import { Play, Network } from 'lucide-react';
import { Link } from 'react-router-dom';
import { getEvaluationErrorGuidance } from './evaluationErrorGuidance';
import { getOptionalCountPresentation } from './optionalCountPresentation';

export function OverviewPage() {
  const { data: summary, isLoading, isError, error, refetch } = useDashboardSummary();
  const queryClient = useQueryClient();
  const runEvaluation = useRunEvaluation();
  const [intentCursor, setIntentCursor] = useState<string | undefined>();
  const [selectedIntentId, setSelectedIntentId] = useState('');
  const intents = useManifestIntents(intentCursor);
  const approvedIntents = intents.data?.items.filter(item => (item.activeVersion ?? (item.status === 'APPROVED' ? item.version : 0)) > 0) ?? [];
  const selectedIntent = approvedIntents.find(item => item.intentId === selectedIntentId);
  const selectedVersion = selectedIntent?.activeVersion ?? selectedIntent?.version;
  const evaluationsEnabled = useCapability('evaluations');
  const [activeEvaluationId, setActiveEvaluationId] = useState<string | null>(null);
  const [historyCursor, setHistoryCursor] = useState<string | undefined>();
  const activeEvaluation = useEvaluation(activeEvaluationId);
  const history = useEvaluations({ cursor: historyCursor });
  const currentStatus = activeEvaluation.data?.item.status;
  const isEvaluationActive = currentStatus === 'QUEUED' || currentStatus === 'RUNNING';
  const evaluationErrorGuidance = getEvaluationErrorGuidance(runEvaluation.error);
  const driftCount = summary ? getOptionalCountPresentation(summary.activeDriftCount, summary.features?.driftEvents) : null;
  const remediationCount = summary ? getOptionalCountPresentation(summary.openRemediations, summary.features?.remediation) : null;

  useEffect(() => {
    if (currentStatus === 'SUCCEEDED' || currentStatus === 'PARTIAL' || currentStatus === 'FAILED') {
      for (const queryKey of [...queryKeys.evaluationResults(), queryKeys.evaluationLists()]) {
        void queryClient.invalidateQueries({ queryKey });
      }
    }
  }, [currentStatus, activeEvaluationId, queryClient]);

  const handleRunEvaluation = () => {
    if (!selectedIntent || !selectedVersion) return;
    runEvaluation.mutate({ intentId: selectedIntent.intentId, intentVersion: selectedVersion }, {
      onSuccess: ({ evaluation }) => setActiveEvaluationId(evaluation.evaluationId),
    });
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto overview-workspace">
      <div className="space-y-5">
        <div>
          <h1 className="font-title text-2xl font-bold text-ink">Overview</h1>
          <p className="text-xs text-graphite mt-1">
            Architecture conformance for your AWS environment in <span className="font-mono text-ink">{summary?.evaluatedRegion || env.defaultRegion}</span>
          </p>
        </div>
        <div className="review-command flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="evaluation-intent" className="block text-sm font-medium mb-2">Approved intent to evaluate</label>
            <select id="evaluation-intent" value={selectedIntentId} disabled={runEvaluation.isPending || isEvaluationActive || intents.isLoading} onChange={(event) => setSelectedIntentId(event.target.value)} className="border border-rule-strong rounded-lg bg-sheet px-3 py-2 text-sm max-w-full">
              <option value="">Select an approved intent</option>
              {approvedIntents.map(item => <option key={item.intentId} value={item.intentId}>{item.name} (version {item.activeVersion ?? item.version})</option>)}
            </select>
          </div>
        <Button
          variant="primary"
          onClick={handleRunEvaluation}
          isLoading={runEvaluation.isPending || isEvaluationActive || Boolean(activeEvaluationId && activeEvaluation.isLoading)}
          disabled={runEvaluation.isPending || isEvaluationActive || Boolean(activeEvaluationId && activeEvaluation.isLoading) || !evaluationsEnabled || !selectedIntent || !selectedVersion}
        >
          <Play className="w-3.5 h-3.5 mr-2 stroke-[1.5]" />
          {evaluationsEnabled ? 'Run evaluation' : 'AWS evaluation not enabled locally'}
        </Button>
          <Link to="/architecture" className="inline-flex items-center gap-2 text-sm text-prussian px-2 py-2"><Network className="w-4 h-4 stroke-[1.5]" />View architecture</Link>
        </div>
      </div>
      {intents.isError && <p role="alert" className="text-sm text-sev-critical">Approved intents could not be loaded: {intents.error.message} <Button variant="secondary" size="sm" onClick={() => intents.refetch()}>Retry intents</Button></p>}
      {intents.data && approvedIntents.length === 0 && <p className="text-sm text-graphite">No approved intent on this page. <Link to="/intents" className="text-prussian underline">Review intents</Link> or check the next page.</p>}
      {(intentCursor || intents.data?.nextToken) && <div className="flex gap-2">
        {intentCursor && <Button size="sm" variant="secondary" disabled={runEvaluation.isPending || isEvaluationActive} onClick={() => { setIntentCursor(undefined); setSelectedIntentId(''); }}>First intent page</Button>}
        {intents.data?.nextToken && <Button size="sm" variant="secondary" disabled={runEvaluation.isPending || isEvaluationActive} onClick={() => { setIntentCursor(intents.data!.nextToken!); setSelectedIntentId(''); }}>Next intent page</Button>}
      </div>}
      {selectedIntent && <p className="text-xs text-graphite">Evaluation will use {selectedIntent.name}, approved version {selectedVersion}. Intent ID: <span className="font-mono">{selectedIntent.intentId}</span></p>}

      {runEvaluation.isPending && <p role="status" className="text-sm text-graphite">Submitting evaluation request.</p>}
      {runEvaluation.error && <div role="alert" className="text-sm text-sev-critical">
        <p>{runEvaluation.error.message}</p>
        {evaluationErrorGuidance && <Link to={evaluationErrorGuidance.to} className="mt-1 inline-block text-prussian underline">
          {evaluationErrorGuidance.label}
        </Link>}
      </div>}
      {runEvaluation.data && <p role="status" className="text-sm">Evaluation request accepted. ID: {runEvaluation.data.evaluation.evaluationId}</p>}
      {activeEvaluation.error && <p role="alert" className="text-sm text-sev-critical">Evaluation status could not be loaded: {activeEvaluation.error.message}</p>}
      {activeEvaluation.data && <div className="flex items-center gap-3 text-sm"><p role="status">Evaluation {activeEvaluation.data.item.status.toLowerCase()}. ID: {activeEvaluation.data.item.evaluationId}{activeEvaluation.data.item.progressStage ? ` · ${activeEvaluation.data.item.progressStage}` : ''}</p><Button variant="secondary" size="sm" onClick={() => activeEvaluation.refetch()}>Refresh status</Button></div>}
      {activeEvaluation.data?.item.status === 'PARTIAL' && <div role="status" className="text-sm text-sev-medium">
        <p>Evaluation completed with incomplete coverage. Review the reported coverage gaps before using these results.</p>
        {activeEvaluation.data.item.ruleResults?.filter((rule) => rule.outcome === 'UNKNOWN').map((rule) => <p key={rule.ruleId}>{rule.ruleId}: {rule.explanation || 'The backend could not evaluate this rule with the available evidence.'}</p>)}
        {activeEvaluation.data.item.warnings?.map((warning, index) => <p key={index}>{warning.source ? `${warning.source}: ` : ''}{warning.message}</p>)}
      </div>}
      {activeEvaluation.data?.item.error && <p role="alert" className="text-sm text-sev-critical">{activeEvaluation.data.item.error.message}</p>}
      {summary?.partial && <p role="status" className="text-sm text-sev-medium">Stored data is incomplete. Some counts or conformance results may be unavailable.</p>}
      <StateBoundary
        isLoading={isLoading}
        isError={isError}
        error={error}
        onRetry={() => refetch()}
      >
        {summary && (
          <>
            <section className="grid xl:grid-cols-[minmax(0,1.8fr)_minmax(280px,1fr)] gap-6" aria-label="Evaluation review">
              <div className="border border-rule rounded-xl bg-sheet overflow-hidden">
                <div className="p-6 md:p-8">
                  <div className="flex justify-between items-start gap-4">
                    <h2 className="text-base font-semibold">Architecture conformance</h2>
                    <span className="text-xs text-graphite">Latest evaluation</span>
                  </div>
                  <div className="mt-6 flex flex-wrap items-end gap-x-6 gap-y-2">
                    <strong className="font-title text-5xl md:text-6xl font-semibold tracking-tight tabular-nums">{summary.conformance.percent !== null ? `${summary.conformance.percent}%` : '—'}</strong>
                    <p className="text-sm text-graphite max-w-64 pb-1">{summary.conformance.percent !== null
                      ? `${summary.conformance.passingRules} of ${summary.conformance.totalRules} evaluated constraints passing`
                      : summary.lastEvaluatedAt ? 'Conformance unavailable for the latest evaluation' : 'Not evaluated yet'}</p>
                  </div>
                  {summary.conformance.percent !== null && <meter className="conformance-meter mt-6 w-full h-2" min={0} max={Math.max(1, summary.conformance.totalRules)} value={summary.conformance.passingRules} aria-label="Passing evaluated constraints" />}
                  <p className="mt-6 text-xs text-graphite">Compare the approved declaration with the observed architecture. Incomplete evidence remains unknown.</p>
                </div>
                <div className="review-register grid sm:grid-cols-3 divide-x divide-rule">
                  <div className="review-metric !block"><span className="block text-xs text-graphite">Active findings</span><div className="mt-1 flex items-baseline gap-3"><strong>{summary.totalFindings}</strong><Link to="/findings" className="text-xs text-prussian">View findings</Link></div></div>
                  <div className="review-metric !block"><span className="block text-xs text-graphite">Latest snapshot changes</span><div className="mt-1 flex items-baseline gap-3"><strong className={driftCount?.showLink ? undefined : "!text-sm !font-medium"}>{driftCount?.label}</strong>{driftCount?.showLink && <Link to="/drift-events" className="text-xs text-prussian">Inspect drift</Link>}</div></div>
                  <div className="review-metric !block"><span className="block text-xs text-graphite">Pending remediations</span><div className="mt-1 flex items-baseline gap-3"><strong className={remediationCount?.showLink ? undefined : "!text-sm !font-medium"}>{remediationCount?.label}</strong>{remediationCount?.showLink && <Link to="/remediation" className="text-xs text-prussian">Review actions</Link>}</div></div>
                </div>
              </div>
              <section className="bg-sheet border border-rule rounded-xl p-6" aria-labelledby="severity-heading">
                <h2 id="severity-heading" className="text-base font-semibold">Findings to review</h2>
                <p className="mt-1 mb-4 text-xs text-graphite">Active findings by server-reported severity</p>
                <div className="severity-register">
                  {(['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'] as const).map(severity => <Link key={severity} to={`/findings?severity=${severity}`}><SeverityBadge severity={severity} /><strong>{summary.severityCounts[severity.toLowerCase() as keyof typeof summary.severityCounts]}</strong></Link>)}
                </div>
              </section>
            </section>

            <div className="text-xs text-graphite flex flex-wrap gap-2 items-center justify-between">
              <span>Last evaluated: {formatDateTime(summary.lastEvaluatedAt)}</span>
              <span>Region: {summary.evaluatedRegion}</span>
            </div>

            {evaluationsEnabled && (
              <Card>
                <CardHeader title="Evaluation history" subtitle="Server-reported runs in the configured scope" />
                {history.isLoading && <p className="text-sm text-graphite">Loading evaluation history.</p>}
                {history.isError && <p role="alert" className="text-sm text-sev-critical">Evaluation history could not be loaded: {history.error.message}</p>}
                {history.data?.items.length === 0 && <p className="text-sm text-graphite">No history yet. Run an evaluation to start the trend.</p>}
                {history.data && history.data.items.length > 0 && (
                  <ul className="evaluation-register divide-y divide-rule">
                    {history.data.items.map((item) => (
                      <li key={item.evaluationId} className="py-2 flex flex-wrap items-center justify-between gap-2 text-sm">
                        <button className="font-mono text-xs underline text-left" onClick={() => setActiveEvaluationId(item.evaluationId)} aria-label={`Inspect evaluation ${item.evaluationId}`}>{item.evaluationId}</button>
                        <span>{item.status}</span>
                        <span className="text-pencil">{item.createdAt ? formatDateTime(item.createdAt) : 'Not recorded'}</span>
                        {item.intentVersion !== undefined && item.intentVersion !== null && <span className="text-pencil">Intent version {item.intentVersion}</span>}
                      </li>
                    ))}
                  </ul>
                )}
                {history.error && <Button variant="secondary" size="sm" onClick={() => history.refetch()}>Retry history</Button>}
                <div className="mt-3 flex gap-2">
                  {historyCursor && <Button variant="secondary" size="sm" onClick={() => setHistoryCursor(undefined)}>First page</Button>}
                  {history.data?.nextToken && <Button variant="secondary" size="sm" onClick={() => setHistoryCursor(history.data!.nextToken!)}>Next page</Button>}
                </div>
              </Card>
            )}
          </>
        )}
      </StateBoundary>
    </div>
  );
}
