from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TestTask(TimestampMixin, Base):
    __tablename__ = "test_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    task_type: Mapped[str] = mapped_column(String(50), default="web_search", nullable=False)
    background: Mapped[str] = mapped_column(Text, default="", nullable=False)
    focus_points: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)

    prompts: Mapped[list["Prompt"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    model_configs: Mapped[list["ModelConfig"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    parameter_configs: Mapped[list["ParameterConfig"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    evaluation_targets: Mapped[list["EvaluationTarget"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    batches: Mapped[list["TestBatch"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class Prompt(TimestampMixin, Base):
    __tablename__ = "prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("test_tasks.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    user_prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    version: Mapped[str] = mapped_column(String(50), default="v1", nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    parent_prompt_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)
    optimization_note: Mapped[str] = mapped_column(Text, default="", nullable=False)

    task: Mapped[TestTask] = relationship(back_populates="prompts")


class ModelConfig(TimestampMixin, Base):
    __tablename__ = "model_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("test_tasks.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), default="deepseek", nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    api_key_ref: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    task: Mapped[TestTask] = relationship(back_populates="model_configs")


class ParameterConfig(TimestampMixin, Base):
    __tablename__ = "parameter_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("test_tasks.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    temperature: Mapped[float] = mapped_column(Float, default=0.2, nullable=False)
    top_p: Mapped[float] = mapped_column(Float, default=0.9, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, default=1800, nullable=False)
    search_limit: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    search_strategy: Mapped[str] = mapped_column(String(50), default="default", nullable=False)
    force_citations: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    require_structured_output: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    enable_evaluator: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_model_memory: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enable_secondary_verification: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    task: Mapped[TestTask] = relationship(back_populates="parameter_configs")


class EvaluationTarget(TimestampMixin, Base):
    __tablename__ = "evaluation_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("test_tasks.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    task: Mapped[TestTask] = relationship(back_populates="evaluation_targets")


class TestBatch(TimestampMixin, Base):
    __tablename__ = "test_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("test_tasks.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cost: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    failure_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)

    task: Mapped[TestTask] = relationship(back_populates="batches")
    combinations: Mapped[list["TestCombination"]] = relationship(back_populates="batch", cascade="all, delete-orphan")
    reports: Mapped[list["Report"]] = relationship(back_populates="batch", cascade="all, delete-orphan")


class TestCombination(TimestampMixin, Base):
    __tablename__ = "test_combinations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("test_batches.id"), index=True, nullable=False)
    prompt_id: Mapped[int] = mapped_column(ForeignKey("prompts.id"), nullable=False)
    model_config_id: Mapped[int] = mapped_column(ForeignKey("model_configs.id"), nullable=False)
    parameter_config_id: Mapped[int] = mapped_column(ForeignKey("parameter_configs.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost: Mapped[float] = mapped_column(Float, default=0, nullable=False)

    batch: Mapped[TestBatch] = relationship(back_populates="combinations")
    prompt: Mapped[Prompt] = relationship()
    model_config: Mapped[ModelConfig] = relationship()
    parameter_config: Mapped[ParameterConfig] = relationship()
    result: Mapped["TestResult"] = relationship(back_populates="combination", cascade="all, delete-orphan")
    evaluation: Mapped["EvaluationResult"] = relationship(back_populates="combination", cascade="all, delete-orphan")


class TestResult(TimestampMixin, Base):
    __tablename__ = "test_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    combination_id: Mapped[int] = mapped_column(ForeignKey("test_combinations.id"), unique=True, nullable=False)
    raw_output: Mapped[str] = mapped_column(Text, default="", nullable=False)
    structured_output: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sources_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    search_logs_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)

    combination: Mapped[TestCombination] = relationship(back_populates="result")


class EvaluationResult(TimestampMixin, Base):
    __tablename__ = "evaluation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    combination_id: Mapped[int] = mapped_column(ForeignKey("test_combinations.id"), unique=True, nullable=False)
    total_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    truthfulness_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    completeness_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    source_quality_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    stability_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    structure_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    cost_efficiency_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    issue_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    rule_metrics_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    is_recommended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(50), default="medium", nullable=False)

    combination: Mapped[TestCombination] = relationship(back_populates="evaluation")


class Report(TimestampMixin, Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("test_batches.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_combination_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    batch: Mapped[TestBatch] = relationship(back_populates="reports")


class PromptOptimization(TimestampMixin, Base):
    __tablename__ = "prompt_optimizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("test_tasks.id"), index=True, nullable=False)
    original_prompt_id: Mapped[int] = mapped_column(ForeignKey("prompts.id"), index=True, nullable=False)
    optimized_prompt_id: Mapped[int | None] = mapped_column(ForeignKey("prompts.id"), nullable=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("test_batches.id"), nullable=True)
    combination_id: Mapped[int | None] = mapped_column(ForeignKey("test_combinations.id"), nullable=True)
    diagnosis_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    optimized_system_prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    optimized_user_prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    optimization_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, default="", nullable=False)


class OptimizationPlan(TimestampMixin, Base):
    """优化方案 - 记录每轮优化的诊断、动作列表和生成的配置"""
    __tablename__ = "optimization_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("test_tasks.id"), index=True, nullable=False)
    source_batch_id: Mapped[int] = mapped_column(ForeignKey("test_batches.id"), nullable=False)
    target_batch_id: Mapped[int | None] = mapped_column(ForeignKey("test_batches.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    # 优化方案内容
    diagnosis_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    actions_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    # 生成的配置ID列表
    new_prompt_ids_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    new_model_ids_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    new_parameter_ids_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    # 元信息
    agent_name: Mapped[str] = mapped_column(String(100), default="optimization_planner", nullable=False)
    agent_model: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    stop_optimization: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ModelProfile(TimestampMixin, Base):
    """模型库 - 存储模型配置、特点标签和性能统计"""
    __tablename__ = "model_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    # 基础配置
    api_base: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    api_key_env: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    supports_search: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    search_mode: Mapped[str] = mapped_column(String(50), default="none", nullable=False)
    # 定价信息
    input_price_per_1k: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    output_price_per_1k: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="CNY", nullable=False)
    # 模型特点标签（JSON 数组，如 ["擅长报告写作", "搜索能力强", "易产生幻觉"]）
    characteristics_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    # 性能统计（从测试结果自动聚合）
    avg_total_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    avg_truthfulness_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    avg_cost_efficiency_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    total_test_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 管理状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
