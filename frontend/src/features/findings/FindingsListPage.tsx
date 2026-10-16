import { useSearchParams, Link } from 'react-router-dom';
import { useFindings } from '@/hooks/apiHooks';
import { StateBoundary } from '@/components/common/StateBoundary';
import { SeverityBadge } from '@/components/common/SeverityBadge';
import { formatDateTime } from '@/utils/dates';
import { formatResourceType } from '@/utils/format';
import { Card } from '@/components/ui/Card';
import { Search, Filter } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { env } from '@/config/env';

export function FindingsListPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const severityFilter = searchParams.get('severity') || '';
  const statusFilter = searchParams.get('status') || '';
  const searchQuery = searchParams.get('q') || '';

  const { data, isLoading, isError, error, refetch } = useFindings({
    severity: severityFilter,
    status: statusFilter,
    q: searchQuery,
    cursor: searchParams.get('cursor') || undefined,
  });
  const displayed = data?.items.filter(row => env.useMocks || !searchQuery || `${row.title} ${row.resourceId} ${row.ruleId}`.toLowerCase().includes(searchQuery.toLowerCase())) || [];

  const updateParam = (key: string, val: string) => {
    const next = new URLSearchParams(searchParams);
    if (val) {
      next.set(key, val);
    } else {
      next.delete(key);
    }
    // INV-19: Changing any filter resets cursor
    next.delete('cursor');
    setSearchParams(next);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="font-title text-2xl font-bold text-ink">Findings</h1>
        <p className="text-xs text-graphite mt-1">
          Review observed violations against approved intent and enabled security checks.
        </p>
      </div>

      {/* Filter Bar */}
      <Card padding="md">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 flex-1 min-w-[200px] bg-film px-3 py-1.5 rounded border border-rule">
            <Search className="w-3.5 h-3.5 text-graphite stroke-[1.5]" />
            <input
              type="text"
              aria-label="Search loaded findings" placeholder="Find a rule, resource or finding"
              value={searchQuery}
              onChange={(e) => updateParam('q', e.target.value)}
              className="bg-transparent text-xs text-ink placeholder:text-pencil focus:outline-none w-full"
            />
          </div>

          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-graphite stroke-[1.5]" />
            <select
              aria-label="Finding severity" value={severityFilter}
              onChange={(e) => updateParam('severity', e.target.value)}
              className="bg-film text-xs text-ink border border-rule rounded px-2.5 py-1.5 focus:outline-none"
            >
              <option value="">All severities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
              <option value="INFO">Info</option>
            </select>

            <select
              aria-label="Finding status" value={statusFilter}
              onChange={(e) => updateParam('status', e.target.value)}
              className="bg-film text-xs text-ink border border-rule rounded px-2.5 py-1.5 focus:outline-none"
            >
              <option value="">All statuses</option>
              <option value="OPEN">Open</option>
              <option value="ACKNOWLEDGED">Acknowledged</option>
              <option value="RESOLVED">Resolved</option>
              <option value="SUPPRESSED">Suppressed</option>
            </select>
          </div>
        </div>
      </Card>
      {!env.useMocks && <p className="text-xs text-pencil">Search filters this loaded page only. Severity and status are filtered by the backend.</p>}

      <StateBoundary
        isLoading={isLoading}
        isError={isError}
        error={error}
        isEmpty={Boolean(data) && displayed.length === 0}
        emptyTitle="No findings match filter"
        emptyDescription="There are no active findings with the selected severity or search query."
        onRetry={() => refetch()}
      >
        {data && (
          <div className="space-y-3">
            <div className="sm:hidden divide-y divide-rule border border-rule rounded-xl bg-sheet">{displayed.map(item => <article key={item.id} className="p-4 space-y-3"><div className="flex items-center justify-between gap-3"><SeverityBadge severity={item.severity} /><span className="text-xs text-graphite">{item.status}</span></div><Link to={`/findings/${item.id}`} className="block font-semibold text-sm text-ink">{item.title}</Link><p className="text-xs text-graphite break-all">{item.resourceId}</p><p className="text-xs text-graphite">{formatDateTime(item.detectedAt)}</p></article>)}</div>
            <div className="hidden sm:block rounded-xl border border-rule bg-sheet overflow-x-auto">
            <table className="w-full min-w-[780px] text-left text-sm">
              <thead className="bg-film border-b border-rule text-graphite font-medium">
                <tr>
                  <th className="py-2.5 px-4">Severity</th>
                  <th className="py-2.5 px-4">Rule & Finding</th>
                  <th className="py-2.5 px-4">Resource</th>
                  <th className="py-2.5 px-4">Status</th>
                  <th className="py-2.5 px-4">Detected</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {displayed.map((item) => (
                  <tr key={item.id} className="hover:bg-film/60 transition-colors">
                    <td className="py-3 px-4">
                      <SeverityBadge severity={item.severity} />
                    </td>
                    <td className="py-3 px-4">
                      <Link to={`/findings/${item.id}`} className="font-medium text-ink hover:text-prussian block">
                        {item.title}
                      </Link>
                      <span className="font-mono text-xs text-pencil">{item.ruleId}</span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-mono text-ink text-xs">{item.resourceId}</div>
                      <div className="text-xs text-pencil">{formatResourceType(item.resourceType)}</div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded text-xs font-medium border border-rule bg-film text-ink">
                        {item.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-pencil whitespace-nowrap">
                      {formatDateTime(item.detectedAt)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </div>
        )}
      </StateBoundary>
      <div className="flex gap-2">{searchParams.get('cursor') && <Button variant="secondary" onClick={() => { const next = new URLSearchParams(searchParams); next.delete('cursor'); setSearchParams(next); }}>First page</Button>}{data?.meta.nextCursor && <Button variant="secondary" onClick={() => { const next = new URLSearchParams(searchParams); next.set('cursor', data.meta.nextCursor!); setSearchParams(next); }}>Next page</Button>}</div>
    </div>
  );
}
