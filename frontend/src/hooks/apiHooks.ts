import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { apiClient } from '@/api/apiClient';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import * as S from '@/api/schemas';
import type * as T from '@/types/domain';

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

export function useFindings(filters?: { severity?: string; status?: string; q?: string }) {
  const params = new URLSearchParams();
  if (filters?.severity) params.set('severity', filters.severity);
  if (filters?.status) params.set('status', filters.status);
  if (filters?.q) params.set('q', filters.q);

  return useQuery({
    queryKey: queryKeys.findings(filters),
    queryFn: () => apiClient<T.FindingsResponse>(endpoints.findings(params.toString()), S.FindingsResponseSchema),
    staleTime: 30000,
  });
}

export function useFinding(id: string) {
  return useQuery({
    queryKey: queryKeys.finding(id),
    queryFn: () => apiClient<T.Finding>(endpoints.finding(id), S.FindingSchema),
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
  });
}

export function useRemediations(status?: string) {
  return useQuery({
    queryKey: queryKeys.remediations(status),
    queryFn: () => apiClient<T.RemediationsResponse>(endpoints.remediations(status), S.RemediationsResponseSchema),
    staleTime: 30000,
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
  });
}

export function useRunEvaluation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiClient<{ jobId: string; message: string; status: string }>(
        endpoints.evaluations(),
        z.object({ jobId: z.string(), message: z.string(), status: z.string() }),
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
