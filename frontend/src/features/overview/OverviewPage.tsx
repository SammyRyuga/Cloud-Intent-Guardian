import { useCapability } from '@/hooks/useCapability';
import { env } from '@/config/env';
import React, { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useDashboardSummary, useEvaluation, useEvaluations, useRunEvaluation } from '@/hooks/apiHooks';
import { queryKeys } from '@/api/queryKeys';
import { Card, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { SeverityBadge } from '@/components/common/SeverityBadge';
import { StateBoundary } from '@/components/common/StateBoundary';
import { formatDateTime } from '@/utils/dates';
import { Play, ShieldCheck, AlertTriangle, Layers } from 'lucide-react';
import { Link } from 'react-router-dom';
import { getEvaluationErrorGuidance } from './evaluationErrorGuidance';
import { getOptionalCountPresentation } from './optionalCountPresentation';

export function OverviewPage() {
  const { data: summary, isLoading, isError, error, refetch } = useDashboardSummary();
  const queryClient = useQueryClient();
  const runEvaluation = useRunEvaluation();
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
    runEvaluation.mutate(undefined, {
      onSuccess: ({ evaluation }) => setActiveEvaluationId(evaluation.evaluationId),
    });
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-title text-2xl font-bold text-ink">Architecture Conformance Overview</h1>
          <p className="text-xs text-graphite mt-1">
            Declared intent vs deployed AWS infrastructure state in <span className="font-mono text-ink">{summary?.evaluatedRegion || env.defaultRegion}</span>
          </p>
        </div>
        <Button
          variant="primary"
          onClick={handleRunEvaluation}
          isLoading={runEvaluation.isPending || isEvaluationActive || Boolean(activeEvaluationId && activeEvaluation.isLoading)}
          disabled={runEvaluation.isPending || isEvaluationActive || Boolean(activeEvaluationId && activeEvaluation.isLoading) || !evaluationsEnabled}
        >
          <Play className="w-3.5 h-3.5 mr-2 stroke-[1.5]" />
          {evaluationsEnabled ? 'Run evaluation' : 'AWS evaluation not enabled locally'}
        </Button>
      </div>

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
            {/* Top Stat Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {/* Conformance Card (INV-04: percent === null shows — and 'Not evaluated yet') */}
              <Card>
                <div className="flex items-center gap-2 text-graphite mb-1">
                  <ShieldCheck className="w-4 h-4 stroke-[1.5]" />
                  <span className="text-xs font-medium">Architecture Conformance</span>
                </div>
                <div className="flex items-baseline gap-2 mt-2">
                  <span className="font-title text-3xl font-bold text-ink">
                    {summary.conformance.percent !== null ? `${summary.conformance.percent}%` : '—'}
                  </span>
                  <span className="text-xs text-pencil">
                    {summary.conformance.percent !== null
                      ? `${summary.conformance.passingRules}/${summary.conformance.totalRules} evaluated constraints passing`
                      : summary.lastEvaluatedAt ? 'Conformance unavailable for the latest evaluation' : 'Not evaluated yet'}
                  </span>
                </div>
              </Card>

              {/* Total Findings */}
              <Card>
                <div className="flex items-center gap-2 text-graphite mb-1">
                  <AlertTriangle className="w-4 h-4 stroke-[1.5]" />
                  <span className="text-xs font-medium">Active Findings</span>
                </div>
                <div className="flex items-baseline gap-2 mt-2">
                  <span className="font-title text-3xl font-bold text-ink">{summary.totalFindings}</span>
                  <Link to="/findings" className="text-xs text-prussian hover:underline">
                    View findings
                  </Link>
                </div>
              </Card>

              {/* Active Drift Events */}
              <Card>
                <div className="flex items-center gap-2 text-graphite mb-1">
                  <Layers className="w-4 h-4 stroke-[1.5]" />
                  <span className="text-xs font-medium">Active Drift Events</span>
                </div>
                <div className="flex items-baseline gap-2 mt-2">
                  <span className="font-title text-3xl font-bold text-ink">{driftCount?.label}</span>
                  {driftCount?.showLink && <Link to="/drift-events" className="text-xs text-prussian hover:underline">
                    Inspect drift
                  </Link>}
                </div>
              </Card>

              {/* Open Remediations */}
              <Card>
                <div className="flex items-center gap-2 text-graphite mb-1">
                  <span className="text-xs font-medium">Pending Remediations</span>
                </div>
                <div className="flex items-baseline gap-2 mt-2">
                  <span className="font-title text-3xl font-bold text-ink">{remediationCount?.label}</span>
                  {remediationCount?.showLink && <Link to="/remediation" className="text-xs text-prussian hover:underline">
                    Review actions
                  </Link>}
                </div>
              </Card>
            </div>

            {/* Severity Distribution */}
            <Card>
              <CardHeader
                title="Active Violations by Severity"
                subtitle="All counts provided by backend telemetry evaluation"
              />
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
                <div className="p-3 bg-film rounded-lg border border-rule flex flex-col gap-1">
                  <SeverityBadge severity="CRITICAL" />
                  <span className="font-title text-2xl font-bold text-ink">{summary.severityCounts.critical}</span>
                </div>
                <div className="p-3 bg-film rounded-lg border border-rule flex flex-col gap-1">
                  <SeverityBadge severity="HIGH" />
                  <span className="font-title text-2xl font-bold text-ink">{summary.severityCounts.high}</span>
                </div>
                <div className="p-3 bg-film rounded-lg border border-rule flex flex-col gap-1">
                  <SeverityBadge severity="MEDIUM" />
                  <span className="font-title text-2xl font-bold text-ink">{summary.severityCounts.medium}</span>
                </div>
                <div className="p-3 bg-film rounded-lg border border-rule flex flex-col gap-1">
                  <SeverityBadge severity="LOW" />
                  <span className="font-title text-2xl font-bold text-ink">{summary.severityCounts.low}</span>
                </div>
                <div className="p-3 bg-film rounded-lg border border-rule flex flex-col gap-1">
                  <SeverityBadge severity="INFO" />
                  <span className="font-title text-2xl font-bold text-ink">{summary.severityCounts.info}</span>
                </div>
              </div>
            </Card>

            <div className="text-xs text-pencil flex items-center justify-between">
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
                  <ul className="divide-y divide-rule">
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
