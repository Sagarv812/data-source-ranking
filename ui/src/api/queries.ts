import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiGet, apiPost } from './client'
import type {
  AgentRunRequest,
  ApiRunListResponse,
  ApiRunRecord,
  FixtureListResponse,
  FixtureRunRequest,
  HealthResponse,
  ReliabilitySnapshot,
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

export function useCreateDecisionRunMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: FixtureRunRequest) =>
      apiPost<ApiRunRecord, FixtureRunRequest>('/runs/decide', request),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['runs'] }),
        queryClient.invalidateQueries({ queryKey: ['feedback-snapshot'] }),
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
      ])
    },
  })
}
