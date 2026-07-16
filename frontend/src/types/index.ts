export interface Task {
  id: number
  name: string
  description: string
  task_type: string
  background: string
  focus_points: string
  status: string
  created_at: string
  updated_at: string
}

export interface Prompt {
  id: number
  task_id: number
  name: string
  system_prompt: string
  user_prompt: string
  content: string
  version: string
  is_enabled: boolean
  is_default: boolean
  parent_prompt_id?: number | null
  source_type?: string
  optimization_note?: string
}

export interface ModelConfig {
  id: number
  task_id: number
  name: string
  provider: string
  base_url: string
  api_key_ref: string
  is_enabled: boolean
}

export interface ParameterConfig {
  id: number
  task_id: number
  name: string
  temperature: number
  top_p: number
  max_tokens: number
  search_limit: number
  search_strategy: string
  force_citations: boolean
  require_structured_output: boolean
  enable_evaluator: boolean
  allow_model_memory: boolean
  enable_secondary_verification: boolean
  is_enabled: boolean
}

export interface EvaluationTarget {
  id: number
  task_id: number
  name: string
  description: string
  weight: number
  is_enabled: boolean
}

export interface EvaluationResult {
  total_score: number
  truthfulness_score: number
  completeness_score: number
  source_quality_score: number
  stability_score: number
  structure_score: number
  cost_efficiency_score: number
  issue_summary: string
  rationale: string
  rule_metrics_json: string
  is_recommended: boolean
  risk_level: string
}

export interface TestResult {
  raw_output: string
  structured_output: string
  sources_json: string
  search_logs_json: string
  error_message: string
}

export interface Combination {
  id: number
  batch_id: number
  status: string
  duration_ms: number
  cost: number
  prompt_name: string
  model_name: string
  parameter_name: string
  result?: TestResult | null
  evaluation?: EvaluationResult | null
}

export interface Batch {
  id: number
  task_id: number
  name: string
  status: string
  started_at?: string | null
  ended_at?: string | null
  duration_ms: number
  total_cost: number
  failure_reason: string
  combinations?: Combination[]
  progress?: Record<string, number>
}

export interface Report {
  id: number
  batch_id: number
  title: string
  content: string
  recommended_combination_id?: number | null
}

export interface PromptIssue {
  type: string
  severity: string
  evidence: string
  impact: string
  suggestion: string
}

export interface PromptDiagnosis {
  prompt_id: number
  batch_id?: number | null
  combination_id?: number | null
  summary: string
  issues: PromptIssue[]
  optimization_directions: string[]
  agent_name: string
  agent_model: string
  prompt_location: string
}

export interface PromptOptimizationResult {
  prompt_id: number
  optimized_system_prompt: string
  optimized_user_prompt: string
  optimization_goal: string
  change_summary: string
  solved_issues: string[]
  possible_side_effects: string[]
  recommend_retest: boolean
  recommendation: string
  diagnosis: PromptDiagnosis
  agent_name: string
  agent_model: string
  prompt_location: string
}

export interface PromptCompareResult {
  original_prompt_id: number
  optimized_prompt_id: number
  original_batch_id?: number | null
  optimized_batch_id?: number | null
  original_score?: number | null
  optimized_score?: number | null
  total_delta?: number | null
  truthfulness_delta?: number | null
  source_quality_delta?: number | null
  completeness_delta?: number | null
  original_risk_level?: string | null
  optimized_risk_level?: string | null
  cost_delta?: number | null
  recommendation: string
}

export interface PipelineTaskDraft {
  name: string
  description: string
  background: string
  focus_points: string
}

export interface PipelinePromptDraft {
  name: string
  version: string
  system_prompt: string
  user_prompt: string
}

export interface PipelineModelDraft {
  provider: string
  name: string
  base_url: string
  api_key_ref: string
  is_enabled: boolean
  rationale: string
}

export interface PipelineParameterDraft {
  name: string
  temperature: number
  top_p: number
  max_tokens: number
  search_limit: number
  search_strategy: string
  force_citations: boolean
  require_structured_output: boolean
  enable_evaluator: boolean
  enable_secondary_verification: boolean
  allow_model_memory: boolean
  is_enabled: boolean
  rationale: string
}

export interface PipelineCandidateDraft {
  label: string
  prompt: PipelinePromptDraft
  model: PipelineModelDraft
  parameter: PipelineParameterDraft
  rationale: string
}

export interface PipelineDraft {
  requirement: string
  task: PipelineTaskDraft
  evaluation_targets: Array<{
    name: string
    description: string
    weight: number
    is_enabled: boolean
  }>
  candidates: PipelineCandidateDraft[]
  selected_candidate_index: number
  prompt?: PipelinePromptDraft | null
  model?: PipelineModelDraft | null
  parameter?: PipelineParameterDraft | null
  assumptions: string[]
  review_notes: string[]
  agent_name: string
  agent_model: string
  prompt_location: string
}

export interface PipelineCommitResult {
  task: Task
  prompt: Prompt
  model: ModelConfig
  parameter: ParameterConfig
  evaluation_targets: EvaluationTarget[]
}

// ── 模型库类型 ──────────────────────────────────────────────

export interface ModelProfile {
  id: number
  provider: string
  name: string
  display_name: string
  api_base: string
  api_key_env: string
  supports_search: boolean
  search_mode: string
  input_price_per_1k: number
  output_price_per_1k: number
  currency: string
  characteristics: string[]
  avg_total_score: number
  avg_truthfulness_score: number
  avg_cost_efficiency_score: number
  total_test_count: number
  is_active: boolean
  notes: string
  created_at: string
  updated_at: string
}

export interface ModelProfileCreate {
  provider: string
  name: string
  display_name?: string
  api_base?: string
  api_key_env?: string
  supports_search?: boolean
  search_mode?: string
  input_price_per_1k?: number
  output_price_per_1k?: number
  currency?: string
  characteristics?: string[]
  is_active?: boolean
  notes?: string
}

export interface ModelProfileUpdate {
  provider?: string
  name?: string
  display_name?: string
  api_base?: string
  api_key_env?: string
  supports_search?: boolean
  search_mode?: string
  input_price_per_1k?: number
  output_price_per_1k?: number
  currency?: string
  characteristics?: string[]
  is_active?: boolean
  notes?: string
}

// ── 优化方案类型 ──────────────────────────────────────────────

export interface OptimizationAction {
  type: string
  target_id: number | null
  rationale: string
  details: Record<string, any>
}

export interface OptimizationPlan {
  id: number
  task_id: number
  source_batch_id: number
  target_batch_id: number | null
  status: string
  diagnosis: Record<string, any>
  actions: OptimizationAction[]
  new_prompt_ids: number[]
  new_model_ids: number[]
  new_parameter_ids: number[]
  agent_name: string
  agent_model: string
  summary: string
  recommendation: string
  round_number: number
  stop_optimization: boolean
  created_at: string
  updated_at: string
}
