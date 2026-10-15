import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useCapability } from '@/hooks/useCapability';
import { useApproveRemediation, useCreateRemediation, useExecuteRemediation, useFindings, useRemediation, useRemediations } from '@/hooks/apiHooks';
import { StateBoundary } from '@/components/common/StateBoundary';
import { CopyableId } from '@/components/common/CopyableId';
import { Card, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { formatDateTime } from '@/utils/dates';

function JsonValue({ value }: { value: unknown }) {
  return <pre className="p-2 bg-film rounded border border-rule font-mono text-[11px] whitespace-pre-wrap break-words">{JSON.stringify(value, null, 2)}</pre>;
}

export function RemediationPage() {
  const [params, setParams] = useSearchParams();
  const cursor = params.get('nextToken') || undefined;
  const selectedId = params.get('proposalId') || '';
  const list = useRemediations({ cursor });
  const findings = useFindings();
  const detail = useRemediation(selectedId);
  const create = useCreateRemediation();
  const approve = useApproveRemediation();
  const execute = useExecuteRemediation();
  const remediationEnabled = useCapability('remediation');
  const approvalEnabled = useCapability('remediation.approve');
  const executionEnabled = useCapability('remediation.execute');
  const [approvalReason, setApprovalReason] = useState('');
  const [selectedFindingId, setSelectedFindingId] = useState('');
  const eligibleFindings = (findings.data?.items ?? []).filter((finding) =>
    finding.remediationAvailable && Boolean(finding.remediationActionId) && finding.tier !== 'TIER_2' && finding.actionEligible !== false,
  );
  const selectedFinding = eligibleFindings.find((finding) => finding.id === selectedFindingId) ?? eligibleFindings[0];

  function select(id: string) {
    const next = new URLSearchParams(params);
    if (id) next.set('proposalId', id); else next.delete('proposalId');
    setParams(next);
  }
  function updatePage(token?: string | null) {
    const next = new URLSearchParams(params);
    if (token) next.set('nextToken', token); else next.delete('nextToken');
    setParams(next);
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="font-title text-2xl font-bold text-ink">Remediation proposals</h1>
        <p className="text-xs text-graphite mt-1">Review the server plan and revision before approving. Execution remains blocked until a proposal is approved. Proposals default to dry-run; the server reports whether a cloud action was performed.</p>
      </div>

      {remediationEnabled && <Card>
        <CardHeader title="Create a proposal" subtitle="Only findings marked eligible by the server are offered." />
        {findings.isLoading && <p className="text-sm text-graphite">Loading eligible findings.</p>}
        {findings.isError && <p role="alert" className="text-sm text-sev-critical">Eligible findings could not be loaded: {findings.error.message}</p>}
        {eligibleFindings.length > 0 ? <div className="flex flex-wrap items-end gap-3">
          <label htmlFor="remediation-finding" className="text-xs">Finding
            <select id="remediation-finding" value={selectedFinding?.id ?? ''} onChange={(event) => setSelectedFindingId(event.target.value)} className="mt-1 block min-w-72 border border-rule rounded p-2 bg-sheet">
              {eligibleFindings.map((finding) => <option key={finding.id} value={finding.id}>{finding.title} · {finding.resourceId}</option>)}
            </select>
          </label>
          {selectedFinding && <span className="text-xs text-graphite">Server-allowed action: {selectedFinding.remediationActionId}</span>}
          <Button disabled={!selectedFinding || create.isPending} isLoading={create.isPending} onClick={() => selectedFinding?.remediationActionId && create.mutate({ findingId: selectedFinding.id, actionId: selectedFinding.remediationActionId })}>Create proposal</Button>
        </div> : <p className="text-sm text-graphite">No findings in the current response are eligible for a remediation proposal.</p>}
        {create.error && <p role="alert" className="mt-2 text-sm text-sev-critical">{create.error.message}</p>}
        {create.data && <p role="status" className="mt-2 text-sm">Proposal created by the server: {create.data.item.proposalId}.</p>}
      </Card>}

      <StateBoundary
        isNotEnabled={!remediationEnabled}
        isLoading={list.isLoading}
        isError={list.isError}
        error={list.error}
        isEmpty={list.data?.items.length === 0}
        emptyTitle="No proposals on this page"
        emptyDescription="Eligible proposals will appear here when the remediation API is enabled."
        onRetry={() => list.refetch()}
      >
        {list.data && <Card>
          <CardHeader title="Proposal history" subtitle={`${list.data.count} proposals in this server response`} />
          <ul className="divide-y divide-rule">
            {list.data.items.map((item) => <li key={item.proposalId} className="py-3 flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-1">
                <p className="font-mono text-xs"><CopyableId id={item.proposalId} /></p>
                <p className="text-sm">{item.actionId} · {item.status}{item.dryRun ? ' · dry run' : ''}</p>
                <p className="text-xs text-pencil">Created {formatDateTime(item.createdAt)} · revision {item.revision}</p>
              </div>
              <Button variant="secondary" size="sm" aria-pressed={selectedId === item.proposalId} onClick={() => select(item.proposalId)}>
                {selectedId === item.proposalId ? 'Selected' : 'Review proposal'}
              </Button>
            </li>)}
          </ul>
          <div className="mt-4 flex gap-2">
            {cursor && <Button variant="secondary" size="sm" onClick={() => updatePage()}>First page</Button>}
            {list.data.nextToken && <Button variant="secondary" size="sm" onClick={() => updatePage(list.data!.nextToken)}>Next page</Button>}
          </div>
        </Card>}
      </StateBoundary>

      {selectedId && <StateBoundary isLoading={detail.isLoading} isError={detail.isError} error={detail.error} onRetry={() => detail.refetch()}>
        {detail.data && (() => {
          const item = detail.data.item;
          const canApprove = item.status === 'PROPOSED' && approvalEnabled;
          const canExecute = item.status === 'APPROVED' && item.revision >= 0 && executionEnabled;
          return <Card>
            <CardHeader title="Proposal detail" subtitle={`${item.actionId} · ${item.status}`} />
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
              <div><dt className="text-xs text-pencil">Proposal ID</dt><dd><CopyableId id={item.proposalId} /></dd></div>
              <div><dt className="text-xs text-pencil">Finding ID</dt><dd><CopyableId id={item.findingId} /></dd></div>
              <div><dt className="text-xs text-pencil">Resource</dt><dd><CopyableId id={item.resourceId} /> <span className="text-xs text-graphite">{item.resourceType}</span></dd></div>
              <div><dt className="text-xs text-pencil">Revision and run mode</dt><dd>{item.revision} · {item.dryRun ? 'dry run' : 'live execution'}</dd></div>
              <div><dt className="text-xs text-pencil">Created by</dt><dd>{item.createdBy.displayName ?? item.createdBy.sub}{item.createdBy.role ? ` · ${item.createdBy.role}` : ''}</dd></div>
              <div><dt className="text-xs text-pencil">Created / expires</dt><dd>{formatDateTime(item.createdAt)} / {formatDateTime(item.expiresAt)}</dd></div>
              {item.approvedAt && <div><dt className="text-xs text-pencil">Approved</dt><dd>{formatDateTime(item.approvedAt)}{item.approvedBy ? ` · ${item.approvedBy.displayName ?? item.approvedBy.sub}` : ''}</dd></div>}
              {item.reason && <div className="sm:col-span-2"><dt className="text-xs text-pencil">Approval reason</dt><dd>{item.reason}</dd></div>}
            </dl>
            {item.dryRun && <p role="status" className="mt-3 border border-sev-medium/30 bg-sev-medium/10 rounded p-2 text-xs">Dry-run mode is active. Running this proposal records a simulation and does not change cloud resources.</p>}
            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
              <div><h3 className="mb-1 text-xs font-semibold">Before</h3><JsonValue value={item.plan.before} /></div>
              <div><h3 className="mb-1 text-xs font-semibold">After</h3><JsonValue value={item.plan.after} /></div>
              <div><h3 className="mb-1 text-xs font-semibold">Rollback</h3><JsonValue value={item.plan.rollback} /></div>
              <div><h3 className="mb-1 text-xs font-semibold">Server plan</h3><p className="text-sm">{item.plan.description}</p>{item.execution && <div className="mt-2 text-xs">Execution: {item.execution.status}{item.execution.completedAt ? ` · ${formatDateTime(item.execution.completedAt)}` : ''}</div>}</div>
            </div>
            {canApprove && <div className="mt-4 border-t border-rule pt-4 space-y-2">
              <label htmlFor="approval-reason" className="block text-xs font-medium">Approval reason</label>
              <textarea id="approval-reason" value={approvalReason} onChange={(event) => setApprovalReason(event.target.value)} rows={2} maxLength={500} className="w-full border border-rule rounded p-2 text-sm" />
              <Button disabled={approve.isPending || !approvalReason.trim()} isLoading={approve.isPending} onClick={() => approve.mutate({ id: item.proposalId, data: { expectedRevision: item.revision, reason: approvalReason.trim() } })}>Approve proposal</Button>
            </div>}
            {canExecute && <div className="mt-4 border-t border-rule pt-4">
              <p className="mb-2 text-xs text-graphite">The API returned this proposal as approved at revision {item.revision}. The action remains subject to backend authorization and expiry checks.</p>
              <Button variant="primary" disabled={execute.isPending} isLoading={execute.isPending} onClick={() => {
                if (!item.dryRun && !window.confirm('Run the approved remediation against the resource?')) return;
                execute.mutate({ id: item.proposalId, data: { expectedRevision: item.revision } });
              }}>{item.dryRun ? 'Run approved dry run' : 'Execute approved action'}</Button>
            </div>}
            {(approve.error || execute.error) && <p role="alert" className="mt-3 text-sm text-sev-critical">{approve.error?.message || execute.error?.message}</p>}
            {approve.data && <p role="status" className="mt-3 text-sm">Proposal approved. Server status: {approve.data.item.status}.</p>}
            {execute.data && <p role="status" className="mt-3 text-sm">Execution request recorded. Server status: {execute.data.item.status}.</p>}
            {!canApprove && item.status === 'PROPOSED' && <p className="mt-4 text-xs text-graphite">Approval is unavailable in this frontend capability set.</p>}
            {!canExecute && item.status === 'APPROVED' && <p className="mt-4 text-xs text-graphite">Execution is unavailable in this frontend capability set.</p>}
          </Card>;
        })()}
      </StateBoundary>}
    </div>
  );
}
