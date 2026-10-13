import { useState } from 'react';
import { useIntents } from '@/hooks/apiHooks';
import { StateBoundary } from '@/components/common/StateBoundary';
import { Card, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { formatDateTime } from '@/utils/dates';
import { Upload, History } from 'lucide-react';
import type { Intent, IntentVersion } from '@/types/domain';
import { env } from '@/config/env';
import { ManifestIntentsPage } from './ManifestIntentsPage';

export function IntentsPage() {
  return env.useMocks ? <MockIntentsPage /> : <ManifestIntentsPage />;
}

function MockIntentsPage() {
  const { data, isLoading, isError, error, refetch } = useIntents();
  const [selectedIntentId, setSelectedIntentId] = useState<string | null>(null);

  const selectedIntent = data?.items.find((i: Intent) => i.id === selectedIntentId) || data?.items[0];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-title text-2xl font-bold text-ink">Architecture Intents</h1>
          <p className="text-xs text-graphite mt-1">
            Declared infrastructure specifications, network topologies, and policy baselines
          </p>
        </div>

        {/* Upload Button */}
        <Button variant="secondary" size="sm" disabled title="File upload is not implemented">
          <Upload className="w-3.5 h-3.5 mr-1.5 stroke-[1.5]" />
          File upload not enabled
        </Button>
      </div>

      <StateBoundary
        isLoading={isLoading}
        isError={isError}
        error={error}
        isEmpty={data?.items.length === 0}
        emptyTitle="No intent baselines uploaded"
        emptyDescription="Upload an architecture intent specification (YAML or CloudFormation) to begin tracking drift."
        onRetry={() => refetch()}
      >
        {data && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Intents List */}
            <div className="space-y-3">
              <h2 className="text-xs font-semibold text-graphite uppercase tracking-wider">Registered Intents</h2>
              {data.items.map((intent: Intent) => (
                <div
                  key={intent.id}
                  onClick={() => setSelectedIntentId(intent.id)}
                  className={`p-4 rounded-[12px] border cursor-pointer transition-colors ${
                    selectedIntent?.id === intent.id
                      ? 'border-prussian bg-sheet ring-1 ring-prussian'
                      : 'border-rule bg-sheet hover:bg-film'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-semibold text-sm text-ink">{intent.name}</span>
                    <span className="text-[10px] font-mono bg-film px-1.5 py-0.5 rounded border border-rule">
                      {intent.currentVersion}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs text-pencil mt-2">
                    <span>{intent.resourceCount} declared resources</span>
                    <span>{formatDateTime(intent.lastUpdatedAt)}</span>
                  </div>
                </div>
              ))}
            </div>

            {/* Selected Intent Versions */}
            {selectedIntent && (
              <div className="md:col-span-2 space-y-4">
                <Card>
                  <CardHeader
                    title={selectedIntent.name}
                    subtitle={`Intent ID: ${selectedIntent.id}`}
                    action={
                      <span className="text-xs font-mono text-graphite">
                        Active version: {selectedIntent.currentVersion}
                      </span>
                    }
                  />

                  <div className="space-y-4">
                    <h3 className="text-xs font-semibold text-graphite flex items-center gap-1.5">
                      <History className="w-3.5 h-3.5 stroke-[1.5]" />
                      Version History & Approvals
                    </h3>

                    <div className="rounded-lg border border-rule overflow-hidden">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-film border-b border-rule text-graphite font-medium">
                          <tr>
                            <th className="py-2 px-3">Version</th>
                            <th className="py-2 px-3">Description</th>
                            <th className="py-2 px-3">Author</th>
                            <th className="py-2 px-3">Status</th>
                            <th className="py-2 px-3">Source File</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-rule">
                          {selectedIntent.versions.map((v: IntentVersion) => (
                            <tr key={v.versionId} className="hover:bg-film/60">
                              <td className="py-2.5 px-3 font-mono font-medium">{v.versionId}</td>
                              <td className="py-2.5 px-3 text-ink/90">{v.description}</td>
                              <td className="py-2.5 px-3 font-mono text-pencil">{v.createdBy}</td>
                              <td className="py-2.5 px-3">
                                <span
                                  className={`px-1.5 py-0.5 rounded text-[10px] font-medium border ${
                                    v.status === 'APPROVED'
                                      ? 'bg-survey/10 border-survey/30 text-survey'
                                      : 'bg-film border-rule text-pencil'
                                  }`}
                                >
                                  {v.status}
                                </span>
                              </td>
                              <td className="py-2.5 px-3 font-mono text-pencil">{v.sourceFile}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </Card>
              </div>
            )}
          </div>
        )}
      </StateBoundary>
    </div>
  );
}
