"""优化方案 Agent 服务层 - 生成和应用优化方案"""

import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.agents.optimization_planner_prompts import (
    OPTIMIZATION_PLANNER_AGENT_KEY,
    OPTIMIZATION_PLANNER_PROMPT_LOCATION,
    OPTIMIZATION_PLANNER_SYSTEM_PROMPT,
)
from app.core.model_adapters import get_agent_model
from app.models.entities import (
    EvaluationResult,
    ModelConfig,
    OptimizationPlan,
    ParameterConfig,
    Prompt,
    TestBatch,
    TestCombination,
    TestTask,
)
from app.schemas.dto import (
    ModelConfigCreate,
    OptimizationActionDetail,
    OptimizationPlanRead,
    ParameterConfigCreate,
    PromptCreate,
)
from app.services.crud import (
    create_model_config,
    create_parameter_config,
    create_prompt,
    get_or_404,
)
from app.services.model_library import list_model_profiles, model_profile_to_dict
from app.services.output_contracts import STRUCTURED_OUTPUT_INSTRUCTIONS
from app.services.recommendation import recommendation_score, recommendation_sort_key
from app.tools.model_client import ModelClient


def _load_batch_for_optimization(db: Session, batch_id: int) -> TestBatch:
    """加载批次及其所有关联数据，用于生成优化方案"""
    stmt = (
        select(TestBatch)
        .where(TestBatch.id == batch_id)
        .options(
            selectinload(TestBatch.task).selectinload(TestTask.evaluation_targets),
            selectinload(TestBatch.combinations).selectinload(TestCombination.prompt),
            selectinload(TestBatch.combinations).selectinload(TestCombination.model_config),
            selectinload(TestBatch.combinations).selectinload(TestCombination.parameter_config),
            selectinload(TestBatch.combinations).selectinload(TestCombination.result),
            selectinload(TestBatch.combinations).selectinload(TestCombination.evaluation),
        )
    )
    batch = db.scalar(stmt)
    if batch is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="TestBatch not found")
    return batch


def _build_optimization_payload(batch: TestBatch, model_profiles: list[dict]) -> str:
    """构建发送给 optimization_planner Agent 的 payload"""
    task = batch.task
    completed = [combo for combo in batch.combinations if combo.evaluation]
    ranked = sorted(completed, key=recommendation_sort_key, reverse=True)

    lines = [
        f"# 任务信息",
        f"- 名称：{task.name}",
        f"- 描述：{task.description}",
        f"- 背景：{task.background}",
        f"- 关注点：{task.focus_points}",
        "",
        f"# 评测目标",
    ]
    for target in task.evaluation_targets:
        lines.append(f"- {target.name}（权重 {target.weight}）：{target.description}")

    lines.extend(["", "# 测试组合评分（按推荐分排序）", ""])
    for i, combo in enumerate(ranked):
        eval_result = combo.evaluation
        lines.extend([
            f"## 组合 {i + 1}（ID: {combo.id}）",
            f"- Prompt: {combo.prompt.name} (ID: {combo.prompt.id})",
            f"- 模型: {combo.model_config.name} (ID: {combo.model_config.id}, provider: {combo.model_config.provider})",
            f"- 参数: {combo.parameter_config.name} (ID: {combo.parameter_config.id})",
            f"  - temperature: {combo.parameter_config.temperature}",
            f"  - search_strategy: {combo.parameter_config.search_strategy}",
            f"  - search_limit: {combo.parameter_config.search_limit}",
            f"  - enable_secondary_verification: {combo.parameter_config.enable_secondary_verification}",
            f"- 总分: {eval_result.total_score}",
            f"- 真实性: {eval_result.truthfulness_score}",
            f"- 完整性: {eval_result.completeness_score}",
            f"- 来源质量: {eval_result.source_quality_score}",
            f"- 稳定性: {eval_result.stability_score}",
            f"- 结构: {eval_result.structure_score}",
            f"- 成本效率: {eval_result.cost_efficiency_score}",
            f"- 风险等级: {eval_result.risk_level}",
            f"- 推荐分: {recommendation_score(combo)}",
            f"- 问题摘要: {eval_result.issue_summary[:500]}",
            f"- 规则指标: {eval_result.rule_metrics_json[:300]}",
            "",
        ])

    if model_profiles:
        lines.extend(["# 可用模型列表（来自模型库）", ""])
        for profile in model_profiles:
            lines.append(
                f"- {profile['name']} ({profile['provider']}): "
                f"特点{profile.get('characteristics', [])}, "
                f"平均评分{profile.get('avg_total_score', 0)}, "
                f"搜索支持: {profile.get('supports_search', False)}"
            )
        lines.append("")

    return "\n".join(lines)


def _parse_json_object(text: str) -> dict[str, Any] | None:
    """从 LLM 输出中解析 JSON 对象"""
    if not text:
        return None
    candidates = [text.strip()]
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    candidates.extend(item.strip() for item in fenced)
    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def _rule_fallback_plan(batch: TestBatch) -> dict[str, Any]:
    """当 LLM 不可用时，基于评分自动生成规则兜底优化方案"""
    completed = [combo for combo in batch.combinations if combo.evaluation]
    if not completed:
        return {
            "summary": "没有已完成的测试组合，无法生成优化方案。",
            "actions": [],
            "recommendation": "请先运行测试批次。",
            "stop_optimization": True,
        }

    # 计算平均分
    avg_truthfulness = sum(c.evaluation.truthfulness_score for c in completed) / len(completed)
    avg_stability = sum(c.evaluation.stability_score for c in completed) / len(completed)
    avg_completeness = sum(c.evaluation.completeness_score for c in completed) / len(completed)
    avg_source_quality = sum(c.evaluation.source_quality_score for c in completed) / len(completed)
    avg_cost_efficiency = sum(c.evaluation.cost_efficiency_score for c in completed) / len(completed)
    avg_total = sum(c.evaluation.total_score for c in completed) / len(completed)

    # 找到最优组合
    best = max(completed, key=recommendation_sort_key)

    actions: list[dict] = []

    if avg_truthfulness < 5:
        actions.append({
            "type": "prompt_optimize",
            "target_id": best.prompt.id,
            "rationale": f"平均真实性评分 {avg_truthfulness:.1f} 偏低，需要强化来源约束和事实核验要求。",
            "details": {
                "optimized_system_prompt": (best.prompt.system_prompt or best.prompt.content) + "\n\n" + STRUCTURED_OUTPUT_INSTRUCTIONS,
                "change_summary": "强化结构化输出协议和来源引用要求。",
            },
        })

    if avg_stability < 5:
        actions.append({
            "type": "param_adjust",
            "target_id": best.parameter_config.id,
            "rationale": f"平均稳定性评分 {avg_stability:.1f} 偏低，降低 temperature 以提高输出一致性。",
            "details": {
                "temperature": max(0.05, best.parameter_config.temperature - 0.1),
            },
        })

    if avg_completeness < 5:
        actions.append({
            "type": "search_enhance",
            "target_id": best.parameter_config.id,
            "rationale": f"平均完整性评分 {avg_completeness:.1f} 偏低，增加搜索条数以获取更全面的信息。",
            "details": {
                "search_limit": min(10, best.parameter_config.search_limit + 3),
            },
        })

    if avg_source_quality < 5:
        actions.append({
            "type": "structure_enforce",
            "target_id": best.prompt.id,
            "rationale": f"平均来源质量评分 {avg_source_quality:.1f} 偏低，强化来源引用要求。",
            "details": {
                "add_structured_output_instructions": True,
            },
        })

    if avg_cost_efficiency < 3 and avg_total > 6:
        actions.append({
            "type": "model_swap",
            "target_id": None,
            "rationale": f"成本效率评分 {avg_cost_efficiency:.1f} 偏低但质量尚可，尝试换用更经济的模型。",
            "details": {
                "provider": "bailian",
                "name": "qwen-turbo",
                "rationale": "轻量模型降低成本",
            },
        })

    if not actions:
        return {
            "summary": f"当前配置表现良好（平均总分 {avg_total:.1f}），无需进一步优化。",
            "actions": [],
            "recommendation": "当前配置已达标，可停止优化。",
            "stop_optimization": True,
        }

    return {
        "summary": f"基于规则兜底生成 {len(actions)} 个优化动作。平均总分 {avg_total:.1f}，真实性 {avg_truthfulness:.1f}，稳定性 {avg_stability:.1f}，完整性 {avg_completeness:.1f}，来源质量 {avg_source_quality:.1f}。",
        "actions": actions,
        "recommendation": "建议应用优化方案后创建新批次复测。",
        "stop_optimization": False,
    }


async def generate_optimization_plan(
    db: Session,
    batch_id: int,
    round_number: int = 1,
) -> OptimizationPlanRead:
    """根据批次测试结果生成优化方案"""
    batch = _load_batch_for_optimization(db, batch_id)

    if batch.status != "completed":
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"批次状态为 {batch.status}，只有已完成的批次才能生成优化方案。")

    # 检查是否已有 draft 状态的优化方案
    existing = db.scalar(
        select(OptimizationPlan).where(
            OptimizationPlan.source_batch_id == batch_id,
            OptimizationPlan.status == "draft",
        )
    )
    if existing:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="该批次已存在一个草稿状态的优化方案，请先应用或删除。")

    # 获取模型库信息
    model_profiles = []
    try:
        profiles = list_model_profiles(db, active_only=True)
        model_profiles = [model_profile_to_dict(p) for p in profiles[:10]]
    except Exception:
        pass

    # 构建 payload
    payload = _build_optimization_payload(batch, model_profiles)

    # 调用 optimization_planner Agent
    agent_model = get_agent_model(OPTIMIZATION_PLANNER_AGENT_KEY)
    model_result = await ModelClient().complete_for_agent(
        OPTIMIZATION_PLANNER_AGENT_KEY,
        OPTIMIZATION_PLANNER_SYSTEM_PROMPT,
        payload,
    )

    parsed = _parse_json_object(model_result.output) if model_result.success else None

    if parsed:
        summary = str(parsed.get("summary") or "优化方案已生成。")
        actions_raw = parsed.get("actions") or []
        recommendation = str(parsed.get("recommendation") or "建议应用优化方案后创建新批次复测。")
        stop_optimization = bool(parsed.get("stop_optimization", False))
        agent_name = OPTIMIZATION_PLANNER_AGENT_KEY
        agent_model_label = f"{agent_model.provider}/{agent_model.model}"
    else:
        # 规则兜底
        fallback = _rule_fallback_plan(batch)
        summary = fallback["summary"]
        actions_raw = fallback["actions"]
        recommendation = fallback["recommendation"]
        stop_optimization = fallback["stop_optimization"]
        agent_name = "rule_fallback"
        agent_model_label = "rule_fallback"

    # 标准化 actions
    actions = []
    for action in actions_raw:
        if not isinstance(action, dict):
            continue
        actions.append({
            "type": str(action.get("type", "prompt_optimize")),
            "target_id": action.get("target_id"),
            "rationale": str(action.get("rationale", "")),
            "details": action.get("details") if isinstance(action.get("details"), dict) else {},
        })

    # 构建诊断信息
    completed = [combo for combo in batch.combinations if combo.evaluation]
    diagnosis = {
        "batch_id": batch_id,
        "total_combinations": len(batch.combinations),
        "completed_combinations": len(completed),
        "avg_total_score": round(sum(c.evaluation.total_score for c in completed) / max(len(completed), 1), 2),
        "avg_truthfulness_score": round(sum(c.evaluation.truthfulness_score for c in completed) / max(len(completed), 1), 2),
        "best_combination_id": max(completed, key=recommendation_sort_key).id if completed else None,
    }

    # 保存到数据库
    plan = OptimizationPlan(
        task_id=batch.task_id,
        source_batch_id=batch_id,
        status="draft",
        diagnosis_json=json.dumps(diagnosis, ensure_ascii=False),
        actions_json=json.dumps(actions, ensure_ascii=False),
        agent_name=agent_name,
        agent_model=agent_model_label,
        summary=summary,
        recommendation=recommendation,
        round_number=round_number,
        stop_optimization=stop_optimization,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    return _plan_to_read(plan)


def apply_optimization_plan(db: Session, plan_id: int) -> OptimizationPlanRead:
    """执行优化方案：创建新 Prompt/参数/模型配置"""
    plan = get_or_404(db, OptimizationPlan, plan_id)

    if plan.status != "draft":
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"优化方案状态为 {plan.status}，只有草稿状态的方案才能应用。")

    actions = _safe_json_list(plan.actions_json)
    task_id = plan.task_id

    new_prompt_ids: list[int] = []
    new_model_ids: list[int] = []
    new_parameter_ids: list[int] = []
    errors: list[str] = []

    for i, action in enumerate(actions):
        action_type = action.get("type", "")
        details = action.get("details", {})
        target_id = action.get("target_id")

        try:
            if action_type in ("prompt_optimize", "prompt_new"):
                prompt = _apply_prompt_action(db, task_id, action_type, target_id, details)
                if prompt:
                    new_prompt_ids.append(prompt.id)

            elif action_type in ("param_adjust", "param_new"):
                param = _apply_param_action(db, task_id, action_type, target_id, details)
                if param:
                    new_parameter_ids.append(param.id)

            elif action_type == "model_swap":
                model = _apply_model_action(db, task_id, details)
                if model:
                    new_model_ids.append(model.id)

            elif action_type == "verification_toggle":
                _apply_verification_toggle(db, target_id, details)

            elif action_type == "search_enhance":
                param = _apply_search_enhance(db, target_id, details)
                if param:
                    new_parameter_ids.append(param.id)

            elif action_type == "structure_enforce":
                prompt = _apply_structure_enforce(db, target_id, details)
                if prompt:
                    new_prompt_ids.append(prompt.id)

        except Exception as exc:
            errors.append(f"动作 {i + 1} ({action_type}) 失败: {exc}")

    # 更新 plan
    plan.new_prompt_ids_json = json.dumps(new_prompt_ids)
    plan.new_model_ids_json = json.dumps(new_model_ids)
    plan.new_parameter_ids_json = json.dumps(new_parameter_ids)
    plan.status = "applied"
    if errors:
        plan.summary += f"\n\n部分动作执行失败：{'; '.join(errors)}"
    db.commit()
    db.refresh(plan)

    return _plan_to_read(plan)


def _apply_prompt_action(
    db: Session,
    task_id: int,
    action_type: str,
    target_id: int | None,
    details: dict,
) -> Prompt | None:
    """应用 Prompt 相关的优化动作"""
    if action_type == "prompt_optimize" and target_id:
        original = db.get(Prompt, target_id)
        if not original:
            return None
        optimized_system = details.get("optimized_system_prompt") or original.system_prompt
        change_summary = details.get("change_summary", "")
        return create_prompt(
            db,
            task_id,
            PromptCreate(
                name=f"{original.name} 优化版",
                system_prompt=optimized_system,
                user_prompt=original.user_prompt,
                content=optimized_system,
                version="optimized",
                is_enabled=True,
                source_type="optimized",
                parent_prompt_id=original.id,
                optimization_note=change_summary,
            ),
        )
    elif action_type == "prompt_new":
        name = details.get("name", "新 Prompt")
        system_prompt = details.get("system_prompt", "")
        user_prompt = details.get("user_prompt", "")
        if not system_prompt:
            return None
        return create_prompt(
            db,
            task_id,
            PromptCreate(
                name=name,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                content=system_prompt,
                version="v1",
                is_enabled=True,
                source_type="optimized",
                optimization_note="由优化方案 Agent 生成",
            ),
        )
    return None


def _apply_param_action(
    db: Session,
    task_id: int,
    action_type: str,
    target_id: int | None,
    details: dict,
) -> ParameterConfig | None:
    """应用参数相关的优化动作"""
    if action_type == "param_adjust" and target_id:
        original = db.get(ParameterConfig, target_id)
        if not original:
            return None
        # 基于原参数创建新参数组，应用调整
        new_data = {
            "name": f"{original.name} 调整版",
            "temperature": details.get("temperature", original.temperature),
            "top_p": details.get("top_p", original.top_p),
            "max_tokens": details.get("max_tokens", original.max_tokens),
            "search_limit": details.get("search_limit", original.search_limit),
            "search_strategy": details.get("search_strategy", original.search_strategy),
            "force_citations": details.get("force_citations", original.force_citations),
            "require_structured_output": details.get("require_structured_output", original.require_structured_output),
            "enable_evaluator": details.get("enable_evaluator", original.enable_evaluator),
            "allow_model_memory": details.get("allow_model_memory", original.allow_model_memory),
            "enable_secondary_verification": details.get("enable_secondary_verification", original.enable_secondary_verification),
            "is_enabled": True,
        }
        return create_parameter_config(db, task_id, ParameterConfigCreate(**new_data))
    elif action_type == "param_new":
        name = details.get("name", "新参数组")
        new_data = {
            "name": name,
            "temperature": details.get("temperature", 0.2),
            "top_p": details.get("top_p", 0.9),
            "max_tokens": details.get("max_tokens", 1800),
            "search_limit": details.get("search_limit", 5),
            "search_strategy": details.get("search_strategy", "default"),
            "force_citations": details.get("force_citations", True),
            "require_structured_output": details.get("require_structured_output", True),
            "enable_evaluator": details.get("enable_evaluator", True),
            "allow_model_memory": details.get("allow_model_memory", False),
            "enable_secondary_verification": details.get("enable_secondary_verification", False),
            "is_enabled": True,
        }
        return create_parameter_config(db, task_id, ParameterConfigCreate(**new_data))
    return None


def _apply_model_action(
    db: Session,
    task_id: int,
    details: dict,
) -> ModelConfig | None:
    """应用模型替换动作"""
    provider = details.get("provider", "bailian")
    name = details.get("name", "")
    if not name:
        return None
    rationale = details.get("rationale", "")
    return create_model_config(
        db,
        task_id,
        ModelConfigCreate(
            name=name,
            provider=provider,
            base_url="",
            api_key_ref="",
            is_enabled=True,
        ),
    )


def _apply_verification_toggle(
    db: Session,
    target_id: int | None,
    details: dict,
) -> None:
    """应用二次核验开关切换"""
    if not target_id:
        return
    param = db.get(ParameterConfig, target_id)
    if not param:
        return
    enable = details.get("enable_secondary_verification")
    if enable is not None:
        param.enable_secondary_verification = bool(enable)
        db.flush()


def _apply_search_enhance(
    db: Session,
    target_id: int | None,
    details: dict,
) -> ParameterConfig | None:
    """应用搜索增强：基于原参数创建新参数组，调整 search_limit"""
    if not target_id:
        return None
    original = db.get(ParameterConfig, target_id)
    if not original:
        return None
    new_search_limit = details.get("search_limit", original.search_limit + 3)
    new_data = {
        "name": f"{original.name} 搜索增强版",
        "temperature": original.temperature,
        "top_p": original.top_p,
        "max_tokens": original.max_tokens,
        "search_limit": new_search_limit,
        "search_strategy": original.search_strategy,
        "force_citations": original.force_citations,
        "require_structured_output": original.require_structured_output,
        "enable_evaluator": original.enable_evaluator,
        "allow_model_memory": original.allow_model_memory,
        "enable_secondary_verification": original.enable_secondary_verification,
        "is_enabled": True,
    }
    return create_parameter_config(db, original.task_id, ParameterConfigCreate(**new_data))


def _apply_structure_enforce(
    db: Session,
    target_id: int | None,
    details: dict,
) -> Prompt | None:
    """应用结构化输出强化：基于原 Prompt 创建新 Prompt，添加输出协议"""
    if not target_id:
        return None
    original = db.get(Prompt, target_id)
    if not original:
        return None
    system_prompt = original.system_prompt or original.content
    if STRUCTURED_OUTPUT_INSTRUCTIONS not in system_prompt:
        system_prompt = f"{system_prompt.rstrip()}\n\n{STRUCTURED_OUTPUT_INSTRUCTIONS}"
    return create_prompt(
        db,
        original.task_id,
        PromptCreate(
            name=f"{original.name} 结构强化版",
            system_prompt=system_prompt,
            user_prompt=original.user_prompt,
            content=system_prompt,
            version="optimized",
            is_enabled=True,
            source_type="optimized",
            parent_prompt_id=original.id,
            optimization_note="由优化方案 Agent 强化结构化输出协议。",
        ),
    )


def _plan_to_read(plan: OptimizationPlan) -> OptimizationPlanRead:
    """将 OptimizationPlan 实体转换为 OptimizationPlanRead DTO"""
    # 手动解析 JSON 字符串字段，避免 Pydantic from_attributes 无法处理 Text 类型的 JSON
    def _parse_json_str(value: str, default):
        if not value:
            return default() if callable(default) else default
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default() if callable(default) else default

    return OptimizationPlanRead(
        id=plan.id,
        task_id=plan.task_id,
        source_batch_id=plan.source_batch_id,
        target_batch_id=plan.target_batch_id,
        status=plan.status,
        diagnosis=_parse_json_str(plan.diagnosis_json, dict),
        actions=_parse_json_str(plan.actions_json, list),
        new_prompt_ids=_parse_json_str(plan.new_prompt_ids_json, list),
        new_model_ids=_parse_json_str(plan.new_model_ids_json, list),
        new_parameter_ids=_parse_json_str(plan.new_parameter_ids_json, list),
        agent_name=plan.agent_name,
        agent_model=plan.agent_model,
        summary=plan.summary,
        recommendation=plan.recommendation,
        round_number=plan.round_number,
        stop_optimization=plan.stop_optimization,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


def _safe_json_list(value: str) -> list:
    """安全解析 JSON 列表"""
    if not value or value == "[]":
        return []
    try:
        result = json.loads(value)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def list_optimization_plans(db: Session, task_id: int) -> list[OptimizationPlanRead]:
    """列出任务的所有优化方案"""
    stmt = (
        select(OptimizationPlan)
        .where(OptimizationPlan.task_id == task_id)
        .order_by(OptimizationPlan.created_at.desc())
    )
    plans = list(db.scalars(stmt).all())
    return [_plan_to_read(p) for p in plans]


def get_optimization_plan(db: Session, plan_id: int) -> OptimizationPlanRead:
    """获取单个优化方案"""
    plan = get_or_404(db, OptimizationPlan, plan_id)
    return _plan_to_read(plan)


async def optimize_and_retest(
    db: Session,
    batch_id: int,
    max_rounds: int = 3,
) -> OptimizationPlanRead:
    """一键优化+复测：生成方案→应用→创建新批次→运行→对比
    
    这是一个长运行函数，应该在后台任务中执行。
    """
    from app.services.execution import create_batch_with_combinations, run_batch
    from app.schemas.dto import BatchCreate
    
    current_round = 1
    source_batch_id = batch_id
    
    while current_round <= max_rounds:
        # 1. 生成优化方案
        plan = await generate_optimization_plan(db, source_batch_id, round_number=current_round)
        
        # 2. 检查是否应该停止优化
        if plan.stop_optimization:
            plan.summary += f"\n\n优化在第 {current_round} 轮停止：{plan.recommendation}"
            db.commit()
            return plan
        
        # 3. 应用优化方案
        plan = apply_optimization_plan(db, plan.id)
        
        # 4. 创建新批次（使用新创建的配置）
        new_prompt_ids = _safe_json_list(plan.new_prompt_ids_json)
        new_model_ids = _safe_json_list(plan.new_model_ids_json)
        new_parameter_ids = _safe_json_list(plan.new_parameter_ids_json)
        
        # 如果没有新配置，停止优化
        if not new_prompt_ids and not new_model_ids and not new_parameter_ids:
            plan.summary += "\n\n优化方案未生成新配置，停止迭代。"
            db.commit()
            return plan
        
        # 创建新批次
        batch_name = f"优化轮次 {current_round}"
        batch_payload = BatchCreate(
            name=batch_name,
            prompt_ids=new_prompt_ids if new_prompt_ids else None,
        )
        
        try:
            new_batch = create_batch_with_combinations(db, plan.task_id, batch_payload)
        except Exception as exc:
            plan.summary += f"\n\n创建新批次失败: {exc}"
            db.commit()
            return plan
        
        # 5. 运行新批次
        try:
            new_batch = await run_batch(db, new_batch.id)
        except Exception as exc:
            plan.summary += f"\n\n运行新批次失败: {exc}"
            db.commit()
            return plan
        
        # 6. 更新 plan 的 target_batch_id
        plan.target_batch_id = new_batch.id
        db.commit()
        db.refresh(plan)
        
        # 7. 对比新旧批次评分
        old_batch = _load_batch_for_optimization(db, source_batch_id)
        old_completed = [c for c in old_batch.combinations if c.evaluation]
        new_completed = [c for c in new_batch.combinations if c.evaluation]
        
        if not old_completed or not new_completed:
            plan.summary += "\n\n无法对比评分：缺少已完成的测试组合。"
            db.commit()
            return plan
        
        old_avg_total = sum(c.evaluation.total_score for c in old_completed) / len(old_completed)
        new_avg_total = sum(c.evaluation.total_score for c in new_completed) / len(new_completed)
        
        improvement = new_avg_total - old_avg_total
        
        plan.summary += f"\n\n轮次 {current_round} 对比：旧批次平均分 {old_avg_total:.2f}，新批次平均分 {new_avg_total:.2f}，提升 {improvement:.2f}。"
        db.commit()
        
        # 8. 判断是否继续迭代
        if improvement < 0.5:  # 提升不足 0.5 分，停止
            plan.recommendation = f"优化效果不明显（提升 {improvement:.2f} 分），建议停止迭代。"
            plan.stop_optimization = True
            db.commit()
            return plan
        
        # 继续下一轮
        source_batch_id = new_batch.id
        current_round += 1
    
    # 达到最大轮数
    plan.recommendation = f"已达到最大迭代轮数 {max_rounds}，停止优化。"
    plan.stop_optimization = True
    db.commit()
    return plan
