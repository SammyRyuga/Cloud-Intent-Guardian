import { useSearchParams, Link } from 'react-router-dom';
import { useFindings } from '@/hooks/apiHooks';
import { StateBoundary } from '@/components/common/StateBoundary';
import { SeverityBadge } from '@/components/common/SeverityBadge';
import { formatDateTime } from '@/utils/dates';
import { formatResourceType } from '@/utils/format';
import { Card } from '@/components/ui/Card';
import { Search, Filter } from 'lucide-react';

export function FindingsListPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const severityFilter = searchParams.get('severity') || '';
  const statusFilter = searchParams.get('status') || '';
  const searchQuery = searchParams.get('q') || '';

  const { data, isLoading, isError, error, refetch } = useFindings({
    severity: severityFilter,
    status: statusFilter,
    q: searchQuery,
  });

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
        <h1 className="font-title text-2xl font-bold text-ink">Architecture Findings</h1>
        <p className="text-xs text-graphite mt-1">
          Detailed drift and security policy compliance violations detected across monitored workloads
        </p>
      </div>

      {/* Filter Bar */}
      <Card padding="sm">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 flex-1 min-w-[200px] bg-film px-3 py-1.5 rounded border border-rule">
            <Search className="w-3.5 h-3.5 text-graphite stroke-[1.5]" />
            <input
              type="text"
              placeholder="Search findings, resources, or rule IDs..."
              value={searchQuery}
              onChange={(e) => updateParam('q', e.target.value)}
              className="bg-transparent text-xs text-ink placeholder:text-pencil focus:outline-none w-full"
            />
          </div>

          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-graphite stroke-[1.5]" />
            <select
              value={severityFilter}
              onChange={(e) => updateParam('severity', e.target.value)}
              className="bg-film text-xs text-ink border border-rule rounded px-2.5 py-1.5 focus:outline-none"
            >
              <option value="">All Severities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
              <option value="INFO">Info</option>
            </select>

            <select
              value={statusFilter}
              onChange={(e) => updateParam('status', e.target.value)}
              className="bg-film text-xs text-ink border border-rule rounded px-2.5 py-1.5 focus:outline-none"
            >
              <option value="">All Statuses</option>
              <option value="OPEN">Open</option>
              <option value="ACKNOWLEDGED">Acknowledged</option>
              <option value="RESOLVED">Resolved</option>
            </select>
          </div>
        </div>
      </Card>

      <StateBoundary
        isLoading={isLoading}
        isError={isError}
        error={error}
        isEmpty={data?.items.length === 0}
        emptyTitle="No findings match filter"
        emptyDescription="There are no active findings with the selected severity or search query."
        onRetry={() => refetch()}
      >
        {data && (
          <div className="rounded-[12px] border border-rule bg-sheet overflow-hidden">
            <table className="w-full text-left text-xs">
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
                {data.items.map((item) => (
                  <tr key={item.id} className="hover:bg-film/60 transition-colors">
                    <td className="py-3 px-4">
                      <SeverityBadge severity={item.severity} />
                    </td>
                    <td className="py-3 px-4">
                      <Link to={`/findings/${item.id}`} className="font-medium text-ink hover:text-prussian block">
                        {item.title}
                      </Link>
                      <span className="font-mono text-[11px] text-pencil">{item.ruleId}</span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-mono text-ink text-[11px]">{item.resourceId}</div>
                      <div className="text-[10px] text-pencil uppercase">{formatResourceType(item.resourceType)}</div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded text-[10px] font-medium border border-rule bg-film text-ink">
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
        )}
      </StateBoundary>
    </div>
  );
}
