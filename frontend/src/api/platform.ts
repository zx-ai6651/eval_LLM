import { api } from './client'
import type {
  Batch,
  EvaluationTarget,
  ModelConfig,
  ModelProfile,
  ModelProfileCreate,
  ModelProfileUpdate,
  OptimizationPlan,
  ParameterConfig,
  PipelineCommitResult,
  PipelineDraft,
  Prompt,
  PromptCompareResult,
  PromptDiagnosis,
  PromptOptimizationResult,
  Report,
  Task
} from '../types'

export async function getSummary() {
  const { data } = await api.get('/tasks/summary')
  return data
}

export async function listTasks(): Promise<Task[]> {
  const { data } = await api.get('/tasks')
  return data
}

export async function createTask(payload: Partial<Task> & { use_default_targets: boolean }): Promise<Task> {
  const { data } = await api.post('/tasks', payload)
  return data
}

export async function deleteTask(taskId: number): Promise<void> {
  await api.delete(`/tasks/${taskId}`)
}

export async function getTask(taskId: number): Promise<Task> {
  const { data } = await api.get(`/tasks/${taskId}`)
  return data
}

export async function listPrompts(taskId: number): Promise<Prompt[]> {
  const { data } = await api.get(`/tasks/${taskId}/prompts`)
  return data
}

export async function addPrompt(taskId: number, payload: Partial<Prompt>): Promise<Prompt> {
  const { data } = await api.post(`/tasks/${taskId}/prompts`, payload)
  return data
}

export async function deletePrompt(promptId: number): Promise<Prompt> {
  const { data } = await api.delete(`/prompts/${promptId}`)
  return data
}

export async function diagnosePrompt(
  promptId: number,
  payload: { batch_id?: number | null; combination_id?: number | null }
): Promise<PromptDiagnosis> {
  const { data } = await api.post(`/prompts/${promptId}/diagnose`, payload, { timeout: 180000 })
  return data
}

export async function optimizePrompt(
  promptId: number,
  payload: {
    diagnosis?: PromptDiagnosis | null
    optimization_goal?: string
    batch_id?: number | null
    combination_id?: number | null
  }
): Promise<PromptOptimizationResult> {
  const { data } = await api.post(`/prompts/${promptId}/optimize`, payload, { timeout: 180000 })
  return data
}

export async function saveOptimizedPrompt(
  promptId: number,
  payload: {
    name: string
    system_prompt: string
    user_prompt?: string
    optimization_note?: string
    version?: string
  }
): Promise<Prompt> {
  const { data } = await api.post(`/prompts/${promptId}/optimized-copy`, payload)
  return data
}

export async function comparePrompts(params: {
  original_prompt_id: number
  optimized_prompt_id: number
  original_batch_id?: number | null
  optimized_batch_id?: number | null
}): Promise<PromptCompareResult> {
  const { data } = await api.get('/prompts/compare', { params })
  return data
}

export async function listModels(taskId: number): Promise<ModelConfig[]> {
  const { data } = await api.get(`/tasks/${taskId}/models`)
  return data
}

export async function listModelAdapters() {
  const { data } = await api.get('/model-adapters')
  return data
}

export async function addModel(taskId: number, payload: Partial<ModelConfig>): Promise<ModelConfig> {
  const { data } = await api.post(`/tasks/${taskId}/models`, payload)
  return data
}

export async function deleteModel(modelId: number): Promise<ModelConfig> {
  const { data } = await api.delete(`/models/${modelId}`)
  return data
}

export async function listParameters(taskId: number): Promise<ParameterConfig[]> {
  const { data } = await api.get(`/tasks/${taskId}/parameters`)
  return data
}

export async function addParameter(taskId: number, payload: Partial<ParameterConfig>): Promise<ParameterConfig> {
  const { data } = await api.post(`/tasks/${taskId}/parameters`, payload)
  return data
}

export async function deleteParameter(parameterId: number): Promise<ParameterConfig> {
  const { data } = await api.delete(`/parameters/${parameterId}`)
  return data
}

export async function listTargets(taskId: number): Promise<EvaluationTarget[]> {
  const { data } = await api.get(`/tasks/${taskId}/evaluation-targets`)
  return data
}

export async function updateTarget(targetId: number, payload: Partial<EvaluationTarget>): Promise<EvaluationTarget> {
  const { data } = await api.patch(`/evaluation-targets/${targetId}`, payload)
  return data
}

export async function listBatches(taskId: number): Promise<Batch[]> {
  const { data } = await api.get(`/batches/task/${taskId}`)
  return data
}

export async function createBatch(taskId: number, name: string, promptIds?: number[]) {
  const { data } = await api.post(`/batches/task/${taskId}`, { name, prompt_ids: promptIds })
  return data
}

export async function runBatch(batchId: number): Promise<Batch> {
  const { data } = await api.post(`/batches/${batchId}/run`)
  return data
}

export async function deleteBatch(batchId: number): Promise<void> {
  await api.delete(`/batches/${batchId}`)
}

export async function getBatch(batchId: number): Promise<Batch> {
  const { data } = await api.get(`/batches/${batchId}`)
  return data
}

export async function getReport(batchId: number): Promise<Report> {
  const { data } = await api.get(`/reports/batch/${batchId}`)
  return data
}

export async function generatePipelineDraft(requirement: string): Promise<PipelineDraft> {
  const { data } = await api.post('/pipeline/draft', { requirement })
  return data
}

export async function commitPipelineDraft(draft: PipelineDraft): Promise<PipelineCommitResult> {
  const { data } = await api.post('/pipeline/commit', { draft })
  return data
}

// ── 模型库 API ──────────────────────────────────────────────

export async function listModelProfiles(activeOnly: boolean = true): Promise<ModelProfile[]> {
  const { data } = await api.get('/models', { params: { active_only: activeOnly } })
  return data
}

export async function getModelProfile(modelId: number): Promise<ModelProfile> {
  const { data } = await api.get(`/models/${modelId}`)
  return data
}

export async function createModelProfile(payload: ModelProfileCreate): Promise<ModelProfile> {
  const { data } = await api.post('/models', payload)
  return data
}

export async function updateModelProfile(modelId: number, payload: ModelProfileUpdate): Promise<ModelProfile> {
  const { data } = await api.put(`/models/${modelId}`, payload)
  return data
}

export async function deactivateModelProfile(modelId: number): Promise<ModelProfile> {
  const { data } = await api.post(`/models/${modelId}/deactivate`)
  return data
}

export async function activateModelProfile(modelId: number): Promise<ModelProfile> {
  const { data } = await api.post(`/models/${modelId}/activate`)
  return data
}

export async function refreshModelStats(modelId: number): Promise<ModelProfile> {
  const { data } = await api.post(`/models/${modelId}/refresh-stats`)
  return data
}

export async function recommendModels(requirement: string, limit: number = 3): Promise<ModelProfile[]> {
  const { data } = await api.get('/models/recommend', { params: { requirement, limit } })
  return data
}

// ── 优化方案 API ──────────────────────────────────────────────

export async function createOptimizationPlan(batchId: number, roundNumber: number = 1): Promise<OptimizationPlan> {
  const { data } = await api.post(`/optimization/batches/${batchId}/plan`, null, {
    params: { round_number: roundNumber },
    timeout: 180000,
  })
  return data
}

export async function applyOptimizationPlan(planId: number): Promise<OptimizationPlan> {
  const { data } = await api.post(`/optimization/plans/${planId}/apply`)
  return data
}

export async function listOptimizationPlans(taskId: number): Promise<OptimizationPlan[]> {
  const { data } = await api.get(`/optimization/tasks/${taskId}/plans`)
  return data
}

export async function getOptimizationPlan(planId: number): Promise<OptimizationPlan> {
  const { data } = await api.get(`/optimization/plans/${planId}`)
  return data
}

export async function optimizeAndRetest(batchId: number, maxRounds: number = 3): Promise<OptimizationPlan> {
  const { data } = await api.post(`/optimization/batches/${batchId}/optimize-and-retest`, null, {
    params: { max_rounds: maxRounds },
    timeout: 600000, // 10分钟超时，因为这是长运行操作
  })
  return data
}
