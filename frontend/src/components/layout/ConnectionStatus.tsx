import React from 'react';
import { useSystemStatus } from '@/hooks/apiHooks';

export function ConnectionStatus() {
  const { data: status, isLoading, isError } = useSystemStatus();

  // INV-03: "Connected" is shown ONLY when /v1/system/status confirms the backend can read the configured AWS sources.
  const isFullyConnected = !isLoading && !isError && status?.backendReachable && status?.awsSourcesConnected;

  let label = 'Connected';
  let pillColor = 'bg-survey text-white';
  let dotColor = 'bg-white';

  if (isLoading) {
    label = 'Connecting...';
    pillColor = 'bg-pencil/20 text-ink';
    dotColor = 'bg-pencil';
  } else if (isError || !status?.backendReachable) {
    label = 'Disconnected';
    pillColor = 'bg-sev-critical text-white';
    dotColor = 'bg-white';
  } else if (!status?.awsSourcesConnected) {
    label = 'AWS Unreachable';
    pillColor = 'bg-sev-high text-white';
    dotColor = 'bg-white';
  }

  return (
    <div
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${pillColor}`}
      title={isFullyConnected ? `Telemetry live (${status?.evaluatedRegion})` : label}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
      <span>{label}</span>
    </div>
  );
}
