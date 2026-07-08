import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiGet, apiPost } from './client'
import type {
  AgentRunRequest,
  ApiRunListResponse,
  ApiRunRecord,
  CustomRankRequest,
  CustomDecisionRunRequest,
  FixtureKind,
  FixtureListResponse,
  FixtureRunRequest,
  HealthResponse,
  RankedBundle,
  ReliabilitySnapshot,
  ResetLocalDataRequest,
  ResetLocalDataResponse,
  RunFeedbackRequest,
  RunFeedbackResponse,
  ReviewQueueResponse,
  RunReviewRequest,
  RunReviewResponse,
} from './types'

export function useHealthQuery() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => apiGet<HealthResponse>('/health'),
  })
}

export function useBundleFixturesQuery() {
  return useQuery({
    queryKey: ['fixtures', 'bundle', 'grouped'],
    queryFn: () => apiGet<FixtureListResponse>('/fixtures?kind=bundle&grouped=true'),
  })
}

export function useFixturesByKindQuery(kind: FixtureKind) {
  return useQuery({
    queryKey: ['fixtures', kind],
    queryFn: () => apiGet<FixtureListResponse>(`/fixtures?kind=${kind}`),
  })
}

export function useRunsQuery() {
  return useQuery({
    queryKey: ['runs'],
    queryFn: () => apiGet<ApiRunListResponse>('/runs'),
  })
}

export function useRunQuery(runId: string | undefined) {
  return useQuery({
    queryKey: ['runs', runId],
    queryFn: () => apiGet<ApiRunRecord>(`/runs/${runId}`),
    enabled: Boolean(runId),
  })
}

export function useFeedbackSnapshotQuery() {
  return useQuery({
    queryKey: ['feedback-snapshot'],
    queryFn: () => apiGet<ReliabilitySnapshot>('/feedback/snapshot'),
  })
}

export function useReviewQueueQuery() {
  return useQuery({
    queryKey: ['reviews', 'queue'],
    queryFn: () => apiGet<ReviewQueueResponse>('/reviews/queue'),
  })
}

export function useRankBundleMutation() {
  return useMutation({
    mutationFn: (request: FixtureRunRequest) =>
      apiPost<RankedBundle, FixtureRunRequest>('/rank', request),
  })
}

export function useRankCustomBundleMutation() {
  return useMutation({
    mutationFn: (request: CustomRankRequest) =>
      apiPost<RankedBundle, CustomRankRequest>('/rank/custom', request),
  })
}

export function useCreateDecisionRunMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: FixtureRunRequest) =>
      apiPost<ApiRunRecord, FixtureRunRequest>('/runs/decide', request),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['runs'] }),
        queryClient.invalidateQueries({ queryKey: ['feedback-snapshot'] }),
        queryClient.invalidateQueries({ queryKey: ['reviews', 'queue'] }),
      ])
    },
  })
}

export function useCreateCustomDecisionRunMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: CustomDecisionRunRequest) =>
      apiPost<ApiRunRecord, CustomDecisionRunRequest>('/runs/custom/decide', request),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['runs'] }),
        queryClient.invalidateQueries({ queryKey: ['feedback-snapshot'] }),
        queryClient.invalidateQueries({ queryKey: ['reviews', 'queue'] }),
      ])
    },
  })
}

export function useCreateAgentRunMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: AgentRunRequest) =>
      apiPost<ApiRunRecord, AgentRunRequest>('/runs/agent', request),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['runs'] }),
        queryClient.invalidateQueries({ queryKey: ['feedback-snapshot'] }),
        queryClient.invalidateQueries({ queryKey: ['reviews', 'queue'] }),
      ])
    },
  })
}

export function useSubmitRunReviewMutation(runId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: RunReviewRequest) => {
      if (!runId) throw new Error('No check selected for review.')
      return apiPost<RunReviewResponse, RunReviewRequest>(`/runs/${runId}/review`, request)
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['runs'] }),
        queryClient.invalidateQueries({ queryKey: ['runs', runId] }),
        queryClient.invalidateQueries({ queryKey: ['reviews', 'queue'] }),
      ])
    },
  })
}

export function useSubmitRunFeedbackMutation(runId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: RunFeedbackRequest) => {
      if (!runId) throw new Error('No check selected for feedback.')
      return apiPost<RunFeedbackResponse, RunFeedbackRequest>(`/runs/${runId}/feedback`, request)
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['feedback-snapshot'] }),
        queryClient.invalidateQueries({ queryKey: ['runs', runId] }),
        queryClient.invalidateQueries({ queryKey: ['reviews', 'queue'] }),
      ])
    },
  })
}

export function useResetLocalDataMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: ResetLocalDataRequest) =>
      apiPost<ResetLocalDataResponse, ResetLocalDataRequest>('/admin/reset-local-data', request),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['runs'] }),
        queryClient.invalidateQueries({ queryKey: ['feedback-snapshot'] }),
        queryClient.invalidateQueries({ queryKey: ['reviews', 'queue'] }),
      ])
    },
  })
}
