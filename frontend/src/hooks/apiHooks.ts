import { useEffect, useRef } from 'react';
import { evaluationPollInterval } from '@/utils/evaluationPolling';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/api/apiClient';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import * as S from '@/api/schemas';
import type * as T from '@/types/domain';
import * as B from '@/api/backendSchemas';
import { env } from '@/config/env';
import { hasCapability } from '@/config/capabilities';
import { ApiError } from '@/api/errors';

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

export function useFindingLifecycle() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...request }: { id: string } & B.FindingLifecycleRequest) =>
      apiClient(
        endpoints.findingLifecycle(id),
        B.FindingLifecycleResponseSchema,
        { method: 'PATCH', body: B.FindingLifecycleRequestSchema.parse(request) }
      ),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.finding(id) });
      for (const queryKey of queryKeys.findingLifecycleResults()) {
        queryClient.invalidateQueries({ queryKey });
      }
    },
  });
}

export function useArchitectureGraph(
  view: T.GraphView = 'DIFF',
  selection: { intentId?: string; version?: string } = {},
) {
  const filters = { intentId: selection.intentId, version: selection.version };
  const systemStatus = useSystemStatus();
  return useQuery({
    queryKey: queryKeys.architecture(view, filters),
    queryFn: () => apiClient<T.ArchitectureGraph>(endpoints.architecture(view, selection), S.ArchitectureGraphSchema),
    staleTime: 60000,
    enabled: hasCapability('architecture', systemStatus.data),
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

export function useDriftEvents(cursor?: string) {
  const systemStatus = useSystemStatus();
  return useQuery({
    queryKey: queryKeys.driftEvents({ cursor }),
    queryFn: () => apiClient<T.DriftEventsResponse>(endpoints.driftEvents(cursor ? new URLSearchParams({ nextToken: cursor }).toString() : undefined), S.DriftEventsResponseSchema),
    staleTime: 30000,
    enabled: hasCapability('driftEvents', systemStatus.data),
  });
}

export function useRemediations(filters?: { status?: string; cursor?: string }) {
  const systemStatus = useSystemStatus();
  const params = new URLSearchParams({ limit: '25' });
  if (filters?.status) params.set('status', filters.status);
  if (filters?.cursor) params.set('nextToken', filters.cursor);
  return useQuery({
    queryKey: queryKeys.remediations(filters),
    queryFn: () => apiClient(endpoints.remediations(params.toString()), B.RemediationsSchema),
    staleTime: 30000,
    enabled: hasCapability('remediation', systemStatus.data),
  });
}

export function useRemediation(id: string) {
  const systemStatus = useSystemStatus();
  return useQuery({
    queryKey: queryKeys.remediation(id),
    queryFn: () => apiClient(endpoints.remediation(id), B.RemediationDetailSchema),
    enabled: Boolean(id) && hasCapability('remediation.detail', systemStatus.data),
  });
}

function useRemediationMutation<TBody>(path: (id: string) => string, method: 'POST', body: (data: TBody) => unknown) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: TBody }) =>
      apiClient(path(id), B.RemediationDetailSchema,
        { method, body: body(data) }
      ),
    onSuccess: (result) => {
      const id = result.item.proposalId;
      queryClient.invalidateQueries({ queryKey: queryKeys.remediation(id) });
      queryClient.invalidateQueries({ queryKey: ['remediations'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
      queryClient.invalidateQueries({ queryKey: ['audit'] });
    },
  });
}

export function useCreateRemediation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { findingId: string; actionId: T.RemediationRequest['actionId'] }) =>
      apiClient(endpoints.remediations(), B.RemediationDetailSchema, { method: 'POST', body }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['remediations'] });
      queryClient.invalidateQueries({ queryKey: ['audit'] });
    },
  });
}

export function useApproveRemediation() {
  return useRemediationMutation(endpoints.remediationApprove, 'POST', (data: { expectedRevision: number; reason: string }) => data);
}

export function useExecuteRemediation() {
  return useRemediationMutation(endpoints.remediationExecute, 'POST', (data: { expectedRevision: number }) => data);
}

export function useAuditEvents(cursor?: string) {
  const systemStatus = useSystemStatus();
  const params = new URLSearchParams({ limit: '25' });
  if (cursor) params.set('nextToken', cursor);
  return useQuery({
    queryKey: queryKeys.audit({ cursor }),
    queryFn: () => apiClient(endpoints.audit(params.toString()), B.AuditEventsSchema),
    staleTime: 30000,
    enabled: hasCapability('auditTrail', systemStatus.data),
  });
}

export function useRunEvaluation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (selection: { intentId: string; intentVersion: number }) =>
      apiClient(
        endpoints.evaluations(),
        B.EvaluationAcceptedSchema,
        { method: 'POST', body: selection }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.evaluationLists() });
      queryClient.invalidateQueries({ queryKey: queryKeys.audit() });
    },
  });
}

export function useEvaluations(filters?: { cursor?: string; intentId?: string; status?: string }) {
  const pollStartedAt = useRef<number | null>(null);
  useEffect(() => { pollStartedAt.current = Date.now(); }, [filters?.cursor, filters?.intentId, filters?.status]);
  const systemStatus = useSystemStatus();
  const params = new URLSearchParams({ limit: '25' });
  if (filters?.cursor) params.set('nextToken', filters.cursor);
  if (filters?.intentId) params.set('intentId', filters.intentId);
  if (filters?.status) params.set('status', filters.status);
  return useQuery({
    queryKey: queryKeys.evaluations(filters),
    queryFn: () => apiClient(endpoints.evaluations(params.toString()), B.EvaluationsSchema),
    staleTime: 10000,
    enabled: hasCapability('evaluations', systemStatus.data),
    refetchInterval: (query) => {
      if (query.state.error instanceof ApiError && [403, 404].includes(query.state.error.status ?? 0)) return false;
      return evaluationPollInterval(query.state.data?.items, pollStartedAt.current ?? Date.now());
    },
    refetchIntervalInBackground: false,
  });
}

export function useEvaluation(evaluationId: string | null) {
  const pollStartedAt = useRef<number | null>(null);
  useEffect(() => { pollStartedAt.current = Date.now(); }, [evaluationId]);
  return useQuery({
    queryKey: queryKeys.evaluation(evaluationId || ''),
    queryFn: () => apiClient(endpoints.evaluation(evaluationId || ''), B.EvaluationDetailSchema),
    enabled: Boolean(evaluationId),
    retry: (failureCount, error) => {
      if (error instanceof ApiError && (error.status === 403 || error.status === 404)) return false;
      return failureCount < 3;
    },
    refetchInterval: (query) => {
      const error = query.state.error;
      if (error instanceof ApiError && (error.status === 403 || error.status === 404)) return false;
      if (!evaluationPollInterval(query.state.data ? [query.state.data.item] : undefined, pollStartedAt.current ?? Date.now())) return false;
      const createdAt = query.state.data?.item.createdAt;
      if (createdAt && Date.now() - Date.parse(createdAt) >= 15 * 60 * 1000) return false;
      const retryDelay = Math.min(2500 * (2 ** Math.max(0, query.state.fetchFailureCount - 1)), 15000);
      return retryDelay;
    },
    refetchIntervalInBackground: false,
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

export function useIntentVersions(id: string, cursor?: string) {
  const params = new URLSearchParams({ limit: '25' });
  if (cursor) params.set('nextToken', cursor);
  return useQuery({
    queryKey: queryKeys.intentVersions(id, { cursor }),
    queryFn: () => apiClient(endpoints.intentVersions(id, params.toString()), B.IntentVersionsSchema),
    enabled: Boolean(id),
  });
}

export function useIntentVersion(id: string, version: number | null) {
  return useQuery({
    queryKey: queryKeys.intentVersion(id, version || 0),
    queryFn: () => apiClient(endpoints.intentVersion(id, version || 0), B.IntentVersionDetailSchema),
    enabled: Boolean(id && version),
  });
}

export function useCreateIntentVersion() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, manifest, expectedRevision }: { id: string; manifest: unknown; expectedRevision: number }) =>
      apiClient(endpoints.intentVersions(id), B.IntentVersionDetailSchema, {
        method: 'POST', body: { manifest, expectedRevision },
      }),
    onSuccess: (_, { id }) => {
      client.invalidateQueries({ queryKey: queryKeys.intentVersions(id) });
      client.invalidateQueries({ queryKey: queryKeys.intent(id) });
    },
  });
}

export function useApproveIntentVersion() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, version, expectedRevision }: { id: string; version: number; expectedRevision: number }) =>
      apiClient(endpoints.intentVersionApprove(id, version), B.ManifestDetailSchema, {
        method: 'POST', body: { expectedRevision },
      }),
    onSuccess: (_, { id, version }) => {
      client.invalidateQueries({ queryKey: queryKeys.intentVersions(id) });
      client.invalidateQueries({ queryKey: queryKeys.intentVersion(id, version) });
      client.invalidateQueries({ queryKey: queryKeys.intent(id) });
      client.invalidateQueries({ queryKey: queryKeys.intents() });
    },
  });
}

export function useRollbackIntent() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, targetVersion, expectedRevision, reason }: { id: string; targetVersion: number; expectedRevision: number; reason: string }) =>
      apiClient(endpoints.intentRollback(id), B.ManifestDetailSchema, {
        method: 'POST', body: { targetVersion, expectedRevision, reason },
      }),
    onSuccess: (_, { id }) => {
      client.invalidateQueries({ queryKey: queryKeys.intent(id) });
      client.invalidateQueries({ queryKey: queryKeys.intentVersions(id) });
      client.invalidateQueries({ queryKey: queryKeys.intents() });
    },
  });
}

export function useIntentDiff(id: string, fromVersion: number | null, toVersion: number | null) {
  return useQuery({
    queryKey: queryKeys.intentDiff(id, fromVersion || 0, toVersion || 0),
    queryFn: () => apiClient(endpoints.intentDiff(id, fromVersion || 0, toVersion || 0), B.IntentDiffSchema),
    enabled: Boolean(id && fromVersion && toVersion && fromVersion !== toVersion),
  });
}
