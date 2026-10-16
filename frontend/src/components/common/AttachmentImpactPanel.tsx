import type { AttachmentImpact } from '@/types/domain';
import { CopyableId } from './CopyableId';
import { formatResourceType } from '@/utils/format';

export function AttachmentImpactPanel({ impact }: { impact?: AttachmentImpact }) {
  return <section className="border border-rule rounded-xl bg-sheet p-5" aria-labelledby="attachment-impact-heading">
    <h3 id="attachment-impact-heading" className="text-base font-semibold">Security group attachment context</h3>
    {!impact ? <p className="mt-2 text-sm text-graphite">Attachment impact was not collected for this observation. Review resource attachments before approving a change.</p> : <>
      <div className="mt-4 flex flex-wrap items-baseline gap-3"><strong className="font-title text-2xl font-semibold">{impact.coverage === 'COMPLETE' && impact.attachmentCount !== null ? impact.attachmentCount : `At least ${impact.knownAttachmentCount}`}</strong><span className="text-sm text-graphite">attachment records / {impact.coverage.toLowerCase()} coverage</span></div>
      <p className="mt-2 text-sm text-graphite">{impact.interpretation}</p>
      <p className="mt-2 text-sm font-medium">Human approval is required before changing the security group.</p>
      <ul className="mt-4 divide-y divide-rule">{impact.attachments.map((row, index) => <li key={`${row.resourceId}-${index}`} className="py-3 text-sm"><div className="flex flex-wrap items-center justify-between gap-2"><CopyableId id={row.resourceId} /><span className="text-xs text-graphite">{formatResourceType(row.resourceType)}</span></div><p className="mt-1 text-xs text-graphite">{row.source ?? 'Source not recorded'}{row.interfaceType ? ` / ${row.interfaceType}` : ''}{row.status ? ` / ${row.status}` : ''}</p>{(row.vpcId || row.subnetId || row.instanceId) && <dl className="mt-2 space-y-1 text-xs">{([['VPC', row.vpcId], ['Subnet', row.subnetId], ['Instance', row.instanceId]] as const).map(([label, id]) => id ? <div key={label} className="flex flex-wrap gap-2"><dt className="text-graphite">{label}</dt><dd><CopyableId id={id} /></dd></div> : null)}</dl>}</li>)}</ul>
      <details className="mt-3 text-xs"><summary className="cursor-pointer text-graphite">Collection coverage by source</summary><dl className="mt-2 grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1">{Object.entries(impact.sourceCoverage).map(([source, state]) => <div key={source} className="contents"><dt className="break-words">{source}</dt><dd>{state}</dd></div>)}</dl></details>
      {impact.observedAt && <p className="mt-3 text-xs text-graphite">Observed <time dateTime={impact.observedAt}>{impact.observedAt}</time></p>}
    </>}
  </section>;
}
