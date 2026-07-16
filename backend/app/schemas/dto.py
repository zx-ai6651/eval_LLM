from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ApiMessage(BaseModel):
    message: str


class TaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    task_type: str = "web_search"
    background: str = ""
    focus_points: str = ""
    use_default_targets: bool = True


class TaskUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    background: str | None = None
    focus_points: str | None = None
    status: str | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    task_type: str
    background: str
    focus_points: str
    status: str
    created_at: datetime
    updated_at: datetime


class PromptCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    system_prompt: str | None = None
    user_prompt: str = ""
    content: str | None = None
    version: str = "v1"
    is_enabled: bool = True
    is_default: bool = False
    parent_prompt_id: int | None = None
    source_type: str = "manual"
    optimization_note: str = ""

    @model_validator(mode="after")
    def normalize_prompt_fields(self) -> "PromptCreate":
        if not self.system_prompt and self.content:
            self.system_prompt = self.content
        if not self.content and self.system_prompt:
            self.content = self.system_prompt
        if not self.system_prompt:
            raise ValueError("system_prompt is required")
        return self


class PromptUpdate(BaseModel):
    name: str | None = None
    system_prompt: str | None = None
    user_prompt: str | None = None
    content: str | None = None
    version: str | None = None
    is_enabled: bool | None = None
    is_default: bool | None = None
    parent_prompt_id: int | None = None
    source_type: str | None = None
    optimization_note: str | None = None


class PromptRead(PromptCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    created_at: datetime
    updated_at: datetime


class ModelConfigCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    provider: str = "deepseek"
    base_url: str = ""
    api_key_ref: str = ""
    is_enabled: bool = True


class ModelConfigUpdate(BaseModel):
    name: str | None = None
    provider: str | None = None
    base_url: str | None = None
    api_key_ref: str | None = None
    is_enabled: bool | None = None


class ModelConfigRead(ModelConfigCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    created_at: datetime
    updated_at: datetime


class ParameterConfigCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    temperature: float = 0.2
    top_p: float = 0.9
    max_tokens: int = 1800
    search_limit: int = 5
    search_strategy: str = "default"
    force_citations: bool = True
    require_structured_output: bool = True
    enable_evaluator: bool = True
    allow_model_memory: bool = False
    enable_secondary_verification: bool = False
    is_enabled: bool = True


class ParameterConfigUpdate(BaseModel):
    name: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    search_limit: int | None = None
    search_strategy: str | None = None
    force_citations: bool | None = None
    require_structured_output: bool | None = None
    enable_evaluator: bool | None = None
    allow_model_memory: bool | None = None
    enable_secondary_verification: bool | None = None
    is_enabled: bool | None = None


class ParameterConfigRead(ParameterConfigCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    created_at: datetime
    updated_at: datetime


class EvaluationTargetCreate(BaseModel):
    name: str
    description: str = ""
    weight: float
    is_enabled: bool = True


class EvaluationTargetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    weight: float | None = None
    is_enabled: bool | None = None


class EvaluationTargetRead(EvaluationTargetCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    created_at: datetime
    updated_at: datetime


class BatchCreate(BaseModel):
    name: str = "默认测试批次"
    prompt_ids: list[int] | None = None


class CombinationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    batch_id: int
    prompt_id: int
    model_config_id: int
    parameter_config_id: int
    status: str
    duration_ms: int
    cost: float
    created_at: datetime
    updated_at: datetime


class TestResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    combination_id: int
    raw_output: str
    structured_output: str
    sources_json: str
    search_logs_json: str
    error_message: str
    created_at: datetime
    updated_at: datetime


class EvaluationResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    combination_id: int
    total_score: float
    truthfulness_score: float
    completeness_score: float
    source_quality_score: float
    stability_score: float
    structure_score: float
    cost_efficiency_score: float
    issue_summary: str
    rationale: str
    rule_metrics_json: str = "{}"
    is_recommended: bool
    risk_level: str
    created_at: datetime
    updated_at: datetime


class CombinationDetail(CombinationRead):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    prompt_name: str = ""
    model_name: str = ""
    parameter_name: str = ""
    result: TestResultRead | None = None
    evaluation: EvaluationResultRead | None = None


class BatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    name: str
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    duration_ms: int
    total_cost: float
    failure_reason: str
    created_at: datetime
    updated_at: datetime


class BatchDetail(BatchRead):
    combinations: list[CombinationDetail] = []
    progress: dict[str, int] = {}


class ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_id: int
    title: str
    content: str
    recommended_combination_id: int | None
    created_at: datetime
    updated_at: datetime


class DashboardSummary(BaseModel):
    task_count: int
    batch_count: int
    completed_batch_count: int
    latest_tasks: list[TaskRead]


class GeneratedCombinations(BaseModel):
    batch: BatchRead
    combinations: list[CombinationRead]
    estimated_count: int


class HealthRead(BaseModel):
    status: str
    app: str
    environment: str


class PromptDiagnoseRequest(BaseModel):
    batch_id: int | None = None
    combination_id: int | None = None


class PromptIssue(BaseModel):
    type: str
    severity: str
    evidence: str
    impact: str
    suggestion: str


class PromptDiagnosisRead(BaseModel):
    prompt_id: int
    batch_id: int | None = None
    combination_id: int | None = None
    summary: str
    issues: list[PromptIssue]
    optimization_directions: list[str]
    agent_name: str = "rule_fallback"
    agent_model: str = "rule_fallback"
    prompt_location: str = ""


class PromptOptimizeRequest(BaseModel):
    diagnosis: PromptDiagnosisRead | None = None
    optimization_goal: str = ""
    batch_id: int | None = None
    combination_id: int | None = None


class PromptOptimizeRead(BaseModel):
    prompt_id: int
    optimized_system_prompt: str
    optimized_user_prompt: str = ""
    optimization_goal: str
    change_summary: str
    solved_issues: list[str]
    possible_side_effects: list[str]
    recommend_retest: bool = True
    recommendation: str
    diagnosis: PromptDiagnosisRead
    agent_name: str = "rule_fallback"
    agent_model: str = "rule_fallback"
    prompt_location: str = ""


class PromptOptimizedCopyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    system_prompt: str
    user_prompt: str = ""
    optimization_note: str = ""
    version: str = "optimized"


class PromptCompareRead(BaseModel):
    original_prompt_id: int
    optimized_prompt_id: int
    original_batch_id: int | None = None
    optimized_batch_id: int | None = None
    original_score: float | None = None
    optimized_score: float | None = None
    total_delta: float | None = None
    truthfulness_delta: float | None = None
    source_quality_delta: float | None = None
    completeness_delta: float | None = None
    original_risk_level: str | None = None
    optimized_risk_level: str | None = None
    cost_delta: float | None = None
    recommendation: str


JsonDict = dict[str, Any]


class PipelineDraftRequest(BaseModel):
    requirement: str = Field(min_length=1)


class PipelineTaskDraft(BaseModel):
    name: str = "新评测任务"
    description: str = ""
    background: str = ""
    focus_points: str = ""


class PipelinePromptDraft(BaseModel):
    name: str = "初版 Prompt"
    version: str = "v1"
    system_prompt: str
    user_prompt: str = ""


class PipelineModelDraft(BaseModel):
    provider: str = "bailian"
    name: str = "qwen-plus"
    base_url: str = ""
    api_key_ref: str = ""
    is_enabled: bool = True
    rationale: str = ""


class PipelineParameterDraft(BaseModel):
    name: str = "推荐参数"
    temperature: float = 0.2
    top_p: float = 0.9
    max_tokens: int = 3000
    search_limit: int = 5
    search_strategy: str = "turbo"
    force_citations: bool = True
    require_structured_output: bool = True
    enable_evaluator: bool = True
    enable_secondary_verification: bool = False
    allow_model_memory: bool = False
    is_enabled: bool = True
    rationale: str = ""


class PipelineCandidateDraft(BaseModel):
    """单个候选配置方案，包含独立的 prompt + model + parameter 组合"""
    label: str = "候选方案"
    prompt: PipelinePromptDraft
    model: PipelineModelDraft
    parameter: PipelineParameterDraft
    rationale: str = ""


class PipelineDraftRead(BaseModel):
    requirement: str
    task: PipelineTaskDraft
    evaluation_targets: list[EvaluationTargetCreate]
    candidates: list[PipelineCandidateDraft] = []
    selected_candidate_index: int = 0
    # 以下字段从选中的候选方案自动填充，保持向后兼容
    prompt: PipelinePromptDraft | None = None
    model: PipelineModelDraft | None = None
    parameter: PipelineParameterDraft | None = None
    assumptions: list[str] = []
    review_notes: list[str] = []
    agent_name: str = "pipeline_planner"
    agent_model: str = ""
    prompt_location: str = ""

    @model_validator(mode="after")
    def sync_selected_candidate(self) -> "PipelineDraftRead":
        """从 candidates 列表中同步选中方案到单字段，保持向后兼容"""
        if self.candidates and 0 <= self.selected_candidate_index < len(self.candidates):
            selected = self.candidates[self.selected_candidate_index]
            if self.prompt is None:
                self.prompt = selected.prompt
            if self.model is None:
                self.model = selected.model
            if self.parameter is None:
                self.parameter = selected.parameter
        elif self.candidates:
            # 索引越界时回退到第一个候选
            self.selected_candidate_index = 0
            selected = self.candidates[0]
            if self.prompt is None:
                self.prompt = selected.prompt
            if self.model is None:
                self.model = selected.model
            if self.parameter is None:
                self.parameter = selected.parameter
        return self


class PipelineCommitRequest(BaseModel):
    draft: PipelineDraftRead


class PipelineCommitRead(BaseModel):
    task: TaskRead
    prompt: PromptRead
    model: ModelConfigRead
    parameter: ParameterConfigRead
    evaluation_targets: list[EvaluationTargetRead]


# ── 模型库 DTO ──────────────────────────────────────────────


class ModelProfileCreate(BaseModel):
    provider: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    display_name: str = ""
    api_base: str = ""
    api_key_env: str = ""
    supports_search: bool = False
    search_mode: str = "none"
    input_price_per_1k: float = 0
    output_price_per_1k: float = 0
    currency: str = "CNY"
    characteristics: list[str] = []
    is_active: bool = True
    notes: str = ""


class ModelProfileUpdate(BaseModel):
    provider: str | None = None
    name: str | None = None
    display_name: str | None = None
    api_base: str | None = None
    api_key_env: str | None = None
    supports_search: bool | None = None
    search_mode: str | None = None
    input_price_per_1k: float | None = None
    output_price_per_1k: float | None = None
    currency: str | None = None
    characteristics: list[str] | None = None
    is_active: bool | None = None
    notes: str | None = None


class ModelProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    name: str
    display_name: str
    api_base: str
    api_key_env: str
    supports_search: bool
    search_mode: str
    input_price_per_1k: float
    output_price_per_1k: float
    currency: str
    characteristics: list[str] = []
    avg_total_score: float
    avg_truthfulness_score: float
    avg_cost_efficiency_score: float
    total_test_count: int
    is_active: bool
    notes: str
    created_at: datetime
    updated_at: datetime


# ── 优化方案 DTO ──────────────────────────────────────────────


class OptimizationActionDetail(BaseModel):
    type: str
    target_id: int | None = None
    rationale: str = ""
    details: dict[str, Any] = {}


class OptimizationPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    source_batch_id: int
    target_batch_id: int | None
    status: str
    diagnosis: dict[str, Any] = Field(default_factory=dict, alias="diagnosis_json")
    actions: list[OptimizationActionDetail] = Field(default_factory=list, alias="actions_json")
    new_prompt_ids: list[int] = Field(default_factory=list, alias="new_prompt_ids_json")
    new_model_ids: list[int] = Field(default_factory=list, alias="new_model_ids_json")
    new_parameter_ids: list[int] = Field(default_factory=list, alias="new_parameter_ids_json")
    agent_name: str
    agent_model: str
    summary: str
    recommendation: str
    round_number: int
    stop_optimization: bool
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def deserialize_json_fields(cls, data: Any) -> Any:
        json_fields_spec = [
            ("diagnosis_json", dict),
            ("actions_json", list),
            ("new_prompt_ids_json", list),
            ("new_model_ids_json", list),
            ("new_parameter_ids_json", list),
        ]
        # 处理 ORM 对象：转换为 dict 并解析 JSON 字符串字段
        if not isinstance(data, dict):
            result = {}
            # 复制所有普通属性
            for field_name in cls.model_fields:
                # 找到对应的 ORM 属性名（alias 映射回原始字段名）
                field_info = cls.model_fields[field_name]
                orm_attr = field_info.alias if field_info.alias else field_name
                value = getattr(data, orm_attr, None)
                result[orm_attr] = value
            # 解析 JSON 字符串字段
            for json_field, default_type in json_fields_spec:
                value = result.get(json_field)
                if isinstance(value, str):
                    try:
                        result[json_field] = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        result[json_field] = default_type()
                elif value is None:
                    result[json_field] = default_type()
            return result
        # 处理 dict 数据
        for json_field, default_type in json_fields_spec:
            value = data.get(json_field)
            if isinstance(value, str):
                try:
                    data[json_field] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    data[json_field] = default_type()
        return data
