import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { apiClient } from '@/api/apiClient';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import * as S from '@/api/schemas';
import type * as T from '@/types/domain';
import * as B from '@/api/backendSchemas';
import { env } from '@/config/env';
import { hasCapability } from '@/config/capabilities';

export function useSystemStatus() {
  return useQuery({
    queryKey: queryKeys.systemStatus(),
    queryFn: () => apiClient<T.SystemStatus>(endpoints.systemStatus(), S.SystemStatusSchema),
    refetchInterval: 30000,
    staleTime: 15000,
  });
}

export function useDashboardSummary(region?: string) {
  return useQuery({
    queryKey: queryKeys.dashboardSummary(region),
    queryFn: () => apiClient<T.DashboardSummary>(endpoints.dashboardSummary(region), S.DashboardSummarySchema),
    staleTime: 30000,
  });
}

export function useFindings(filters?: { severity?: string; status?: string; q?: string; cursor?: string }) {
  const params = new URLSearchParams();
  if (filters?.severity) params.set('severity', filters.severity);
  if (filters?.status) params.set('status', filters.status);
  if (filters?.q && env.useMocks) params.set('q', filters.q);
  if (filters?.cursor) params.set(env.useMocks ? 'cursor' : 'nextToken', filters.cursor);

  return useQuery({
    queryKey: queryKeys.findings(filters),
    queryFn: () => apiClient<T.FindingsResponse>(endpoints.findings(params.toString()), env.useMocks ? S.FindingsResponseSchema : B.BackendFindingsSchema),
    staleTime: 30000,
  });
}

export function useFinding(id: string) {
  return useQuery({
    queryKey: queryKeys.finding(id),
    queryFn: () => apiClient<T.Finding>(endpoints.finding(id), env.useMocks ? S.FindingSchema : B.BackendFindingDetailSchema),
    enabled: Boolean(id),
    staleTime: 15000,
  });
}

export function useAcknowledgeFinding() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiClient<{ success: boolean; findingId: string }>(
        endpoints.findingAcknowledge(id),
        z.object({ success: z.boolean(), findingId: z.string() }),
        { method: 'PATCH' }
      ),
    onSuccess: (_, id) => {
      // Invalidate per AGENTS.md §4.3
      queryClient.invalidateQueries({ queryKey: queryKeys.finding(id) });
      queryClient.invalidateQueries({ queryKey: ['findings'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
      queryClient.invalidateQueries({ queryKey: ['architecture'] });
      queryClient.invalidateQueries({ queryKey: ['audit-events'] });
    },
  });
}

export function useArchitectureGraph(view: string = 'DIFF') {
  return useQuery({
    queryKey: queryKeys.architecture(view),
    queryFn: () => apiClient<T.ArchitectureGraph>(endpoints.architecture(view), S.ArchitectureGraphSchema),
    staleTime: 60000,
    enabled: hasCapability('architecture'),
  });
}

export function useIntents() {
  return useQuery({
    queryKey: queryKeys.intents(),
    queryFn: () => apiClient<T.IntentsResponse>(endpoints.intents(), S.IntentsResponseSchema),
    staleTime: 30000,
  });
}

export function useIntent(id: string) {
  return useQuery({
    queryKey: queryKeys.intent(id),
    queryFn: () => apiClient<T.Intent>(endpoints.intent(id), S.IntentSchema),
    enabled: Boolean(id),
    staleTime: 15000,
  });
}

export function useDriftEvents() {
  return useQuery({
    queryKey: queryKeys.driftEvents(),
    queryFn: () => apiClient<T.DriftEventsResponse>(endpoints.driftEvents(), S.DriftEventsResponseSchema),
    staleTime: 30000,
    enabled: hasCapability('driftEvents'),
  });
}

export function useRemediations(status?: string) {
  return useQuery({
    queryKey: queryKeys.remediations(status),
    queryFn: () => apiClient<T.RemediationsResponse>(endpoints.remediations(status), S.RemediationsResponseSchema),
    staleTime: 30000,
    enabled: hasCapability('remediation'),
  });
}

export function useRemediationDecision() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, decision, note }: { id: string; decision: 'APPROVE' | 'REJECT'; note?: string }) =>
      apiClient<{ success: boolean; remediationId: string }>(
        endpoints.remediationDecision(id),
        z.object({ success: z.boolean(), remediationId: z.string() }),
        { method: 'POST', body: { decision, note } }
      ),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.remediation(id) });
      queryClient.invalidateQueries({ queryKey: ['remediations'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
      queryClient.invalidateQueries({ queryKey: ['audit-events'] });
    },
  });
}

export function useAuditEvents() {
  return useQuery({
    queryKey: queryKeys.auditEvents(),
    queryFn: () => apiClient<T.AuditEventsResponse>(endpoints.auditEvents(), S.AuditEventsResponseSchema),
    staleTime: 30000,
    enabled: hasCapability('auditTrail'),
  });
}

export function useRunEvaluation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiClient<{ id: string; message: string; status: string }>(
        endpoints.evaluations(),
        env.useMocks ? z.object({ jobId: z.string(), message: z.string(), status: z.string() }).transform(row => ({...row, id: row.jobId})) : B.EvaluationResultSchema,
        { method: 'POST' }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
      queryClient.invalidateQueries({ queryKey: ['findings'] });
      queryClient.invalidateQueries({ queryKey: ['architecture'] });
      queryClient.invalidateQueries({ queryKey: ['system-status'] });
      queryClient.invalidateQueries({ queryKey: ['audit-events'] });
    },
  });
}

export function useManifestIntents(cursor?: string) {
  return useQuery({ queryKey: [...queryKeys.intents(), {cursor}],
    queryFn: () => apiClient(endpoints.intents() + (cursor ? `?nextToken=${encodeURIComponent(cursor)}` : ''), B.ManifestsSchema),
    staleTime: 5000 });
}

export function useManifestIntent(id: string) {
  return useQuery({ queryKey: queryKeys.intent(id), queryFn: () => apiClient(endpoints.intent(id), B.ManifestDetailSchema), enabled: Boolean(id) });
}

export function useCreateManifest() {
  const client = useQueryClient();
  return useMutation({ mutationFn: (manifest: unknown) => apiClient(endpoints.intents(), B.ManifestDetailSchema, {method: 'POST', body: manifest}),
    onSuccess: () => client.invalidateQueries({queryKey: queryKeys.intents()}) });
}

export function useApproveManifest() {
  const client = useQueryClient();
  return useMutation({ mutationFn: (id: string) => apiClient(endpoints.intentApprove(id), B.ManifestDetailSchema, {method: 'POST'}),
    onSuccess: (_, id) => { client.invalidateQueries({queryKey: queryKeys.intents()}); client.invalidateQueries({queryKey: queryKeys.intent(id)}); } });
}

export function useJob(jobId: string | null) {
  return useQuery({
    queryKey: queryKeys.job(jobId || ''),
    queryFn: () => apiClient<T.JobStatus>(endpoints.job(jobId || ''), S.JobStatusSchema),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === 'SUCCEEDED' || status === 'FAILED') return false;
      return 2500;
    },
  });
}
