import { hasCapability } from '@/config/capabilities';
import { env } from '@/config/env';
import React from 'react';
import { useDashboardSummary, useRunEvaluation } from '@/hooks/apiHooks';
import { Card, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { SeverityBadge } from '@/components/common/SeverityBadge';
import { StateBoundary } from '@/components/common/StateBoundary';
import { formatDateTime } from '@/utils/dates';
import { Play, ShieldCheck, AlertTriangle, Layers } from 'lucide-react';
import { Link } from 'react-router-dom';

export function OverviewPage() {
  const { data: summary, isLoading, isError, error, refetch } = useDashboardSummary();
  const runEvaluation = useRunEvaluation();

  const handleRunEvaluation = () => {
    runEvaluation.mutate();
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
          isLoading={runEvaluation.isPending}
          disabled={runEvaluation.isPending || !hasCapability('evaluations')}
        >
          <Play className="w-3.5 h-3.5 mr-2 stroke-[1.5]" />
          {hasCapability('evaluations') ? 'Run evaluation' : 'AWS evaluation not enabled locally'}
        </Button>
      </div>

      {runEvaluation.isPending && <p role="status" className="text-sm text-graphite">Evaluation is running. Results appear after the backend completes.</p>}
      {runEvaluation.error && <p role="alert" className="text-sm text-sev-critical">{runEvaluation.error.message}</p>}
      {runEvaluation.data && <p role="status" className="text-sm">{runEvaluation.data.status}: {runEvaluation.data.message} ID: {runEvaluation.data.id}</p>}
      {summary?.partial && <p role="status" className="text-sm text-sev-medium">Stored data is incomplete. Counts cover retrieved records; conformance is unavailable.</p>}
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
                  <span className="font-title text-3xl font-bold text-ink">{summary.activeDriftCount ?? 'Not enabled'}</span>
                  {summary.activeDriftCount !== null && <Link to="/drift-events" className="text-xs text-prussian hover:underline">
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
                  <span className="font-title text-3xl font-bold text-ink">{summary.openRemediations ?? 'Not enabled'}</span>
                  {summary.openRemediations !== null && <Link to="/remediation" className="text-xs text-prussian hover:underline">
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
          </>
        )}
      </StateBoundary>
    </div>
  );
}
