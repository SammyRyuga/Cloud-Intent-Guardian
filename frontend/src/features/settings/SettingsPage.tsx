import React from 'react';
import { useSystemStatus } from '@/hooks/apiHooks';
import { Card, CardHeader } from '@/components/ui/Card';
import { StateBoundary } from '@/components/common/StateBoundary';
import { formatDateTime } from '@/utils/dates';
import { Shield, Database, Radio, Server } from 'lucide-react';

export function SettingsPage() {
  const { data: status, isLoading, isError, error, refetch } = useSystemStatus();

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div>
        <h1 className="font-title text-2xl font-bold text-ink">System & Environment Settings</h1>
        <p className="text-xs text-graphite mt-1">
          Target region configuration, telemetry status, and connection diagnostics
        </p>
      </div>

      <StateBoundary isLoading={isLoading} isError={isError} error={error} onRetry={() => refetch()}>
        {status && (
          <div className="space-y-6">
            <Card>
              <CardHeader title="Backend & Cloud Telemetry Status" />
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                <div className="p-3 bg-film rounded border border-rule flex items-start gap-3">
                  <Server className="w-4 h-4 text-graphite shrink-0 mt-0.5" />
                  <div>
                    <span className="font-medium text-ink block">API Gateway Backend</span>
                    <span className="text-pencil text-[11px] block mt-0.5">
                      Status: {status.backendReachable ? 'Reachable & Healthy' : 'Unreachable'}
                    </span>
                  </div>
                </div>

                <div className="p-3 bg-film rounded border border-rule flex items-start gap-3">
                  <Radio className="w-4 h-4 text-graphite shrink-0 mt-0.5" />
                  <div>
                    <span className="font-medium text-ink block">AWS Sources Telemetry</span>
                    <span className="text-pencil text-[11px] block mt-0.5">
                      Status: {status.awsSourcesConnected ? 'Connected (AWS discovery probes)' : 'Not connected or disabled locally'}
                    </span>
                  </div>
                </div>

                <div className="p-3 bg-film rounded border border-rule flex items-start gap-3">
                  <Database className="w-4 h-4 text-graphite shrink-0 mt-0.5" />
                  <div>
                    <span className="font-medium text-ink block">Target AWS Region</span>
                    <span className="font-mono text-ink text-[11px] block mt-0.5">{status.evaluatedRegion}</span>
                  </div>
                </div>

                <div className="p-3 bg-film rounded border border-rule flex items-start gap-3">
                  <Shield className="w-4 h-4 text-graphite shrink-0 mt-0.5" />
                  <div>
                    <span className="font-medium text-ink block">App & Engine Version</span>
                    <span className="font-mono text-ink text-[11px] block mt-0.5">{status.version}</span>
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-4 border-t border-rule text-xs text-pencil">
                Last backend readiness check: {formatDateTime(status.lastSyncAt)}
              </div>
            </Card>

            <Card>
              <CardHeader title="Authentication & Session Policies" />
              <div className="text-xs text-pencil space-y-2 leading-relaxed">
                <p>
                  Deployed sign-in uses Cognito hosted login with the authorization-code flow and PKCE.
                </p>
                <p>
                  Amplify owns the session and token refresh. API requests use Cognito access tokens; this interface never requests AWS access keys.
                </p>
              </div>
            </Card>
          </div>
        )}
      </StateBoundary>
    </div>
  );
}
