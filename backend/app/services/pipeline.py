import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.agents.pipeline_prompts import (
    PIPELINE_PLANNER_AGENT_KEY,
    PIPELINE_PLANNER_PROMPT_LOCATION,
    PIPELINE_PLANNER_SYSTEM_PROMPT,
)
from app.core.model_adapters import get_agent_model
from app.schemas.dto import (
    EvaluationTargetCreate,
    ModelConfigCreate,
    ParameterConfigCreate,
    PipelineCandidateDraft,
    PipelineCommitRead,
    PipelineDraftRead,
    PipelineModelDraft,
    PipelineParameterDraft,
    PipelinePromptDraft,
    PipelineTaskDraft,
    PromptCreate,
    TaskCreate,
)
from app.services.crud import (
    create_evaluation_target,
    create_model_config,
    create_parameter_config,
    create_prompt,
    create_task,
)
from app.services.output_contracts import STRUCTURED_OUTPUT_INSTRUCTIONS
from app.tools.model_client import ModelClient


async def generate_pipeline_draft(requirement: str) -> PipelineDraftRead:
    requirement = requirement.strip()
    agent_model = get_agent_model(PIPELINE_PLANNER_AGENT_KEY)
    payload = json.dumps({"requirement": requirement}, ensure_ascii=False, indent=2)
    model_result = await ModelClient().complete_for_agent(
        PIPELINE_PLANNER_AGENT_KEY,
        PIPELINE_PLANNER_SYSTEM_PROMPT,
        payload,
    )
    parsed = _parse_json_object(model_result.output) if model_result.success else None
    if parsed:
        return _normalize_draft(requirement, parsed, f"{agent_model.provider}/{agent_model.model}")
    fallback = _fallback_draft(requirement)
    fallback.agent_model = "rule_fallback"
    fallback.agent_name = "rule_fallback"
    return fallback


def commit_pipeline_draft(db: Session, draft: PipelineDraftRead) -> PipelineCommitRead:
    task = create_task(
        db,
        TaskCreate(
            name=draft.task.name,
            description=draft.task.description,
            task_type="web_search",
            background=draft.task.background,
            focus_points=draft.task.focus_points,
            use_default_targets=False,
        ),
    )
    targets = [
        create_evaluation_target(
            db,
            task.id,
            EvaluationTargetCreate(
                name=target.name,
                description=target.description,
                weight=target.weight,
                is_enabled=target.is_enabled,
            ),
        )
        for target in draft.evaluation_targets
    ]
    prompt = create_prompt(
        db,
        task.id,
        PromptCreate(
            name=draft.prompt.name,
            system_prompt=draft.prompt.system_prompt,
            user_prompt=draft.prompt.user_prompt,
            content=draft.prompt.system_prompt,
            version=draft.prompt.version,
            is_enabled=True,
            source_type="pipeline",
        ),
    )
    model = create_model_config(
        db,
        task.id,
        ModelConfigCreate(
            name=draft.model.name,
            provider=draft.model.provider,
            base_url=draft.model.base_url,
            api_key_ref=draft.model.api_key_ref,
            is_enabled=draft.model.is_enabled,
        ),
    )
    parameter = create_parameter_config(
        db,
        task.id,
        ParameterConfigCreate(
            name=draft.parameter.name,
            temperature=draft.parameter.temperature,
            top_p=draft.parameter.top_p,
            max_tokens=draft.parameter.max_tokens,
            search_limit=draft.parameter.search_limit,
            search_strategy=draft.parameter.search_strategy,
            force_citations=draft.parameter.force_citations,
            require_structured_output=draft.parameter.require_structured_output,
            enable_evaluator=draft.parameter.enable_evaluator,
            enable_secondary_verification=draft.parameter.enable_secondary_verification,
            allow_model_memory=draft.parameter.allow_model_memory,
            is_enabled=draft.parameter.is_enabled,
        ),
    )
    return PipelineCommitRead(task=task, prompt=prompt, model=model, parameter=parameter, evaluation_targets=targets)


def _normalize_draft(requirement: str, payload: dict[str, Any], agent_model: str) -> PipelineDraftRead:
    fallback = _fallback_draft(requirement)
    high_accuracy = any(word in requirement for word in ["背调", "核验", "准确", "风险", "招投标", "处罚", "监管", "舆情"])
    task_payload = payload.get("task") if isinstance(payload.get("task"), dict) else {}

    targets = _targets_from_payload(payload.get("evaluation_targets")) or fallback.evaluation_targets

    # 解析多候选配置
    candidates_payload = payload.get("candidates")
    if isinstance(candidates_payload, list) and len(candidates_payload) > 0:
        candidates = []
        for i, cand in enumerate(candidates_payload[:5]):  # 最多 5 个候选
            if not isinstance(cand, dict):
                continue
            cand_fallback = fallback.candidates[i] if i < len(fallback.candidates) else fallback.candidates[0]
            candidates.append(_candidate_from_payload(cand, cand_fallback, high_accuracy))
        if not candidates:
            candidates = fallback.candidates
    else:
        # 向后兼容：如果 Agent 返回旧格式（单 prompt/model/parameter），包装为单候选
        prompt_payload = payload.get("prompt") if isinstance(payload.get("prompt"), dict) else {}
        model_payload = payload.get("model") if isinstance(payload.get("model"), dict) else {}
        parameter_payload = payload.get("parameter") if isinstance(payload.get("parameter"), dict) else {}
        fb = fallback.candidates[0]
        candidates = [
            PipelineCandidateDraft(
                label="推荐方案",
                prompt=PipelinePromptDraft(
                    name=str(prompt_payload.get("name") or fb.prompt.name)[:200],
                    version=str(prompt_payload.get("version") or "v1"),
                    system_prompt=_ensure_contract_prompt(str(prompt_payload.get("system_prompt") or fb.prompt.system_prompt)),
                    user_prompt=str(prompt_payload.get("user_prompt") or ""),
                ),
                model=PipelineModelDraft(
                    provider=str(model_payload.get("provider") or fb.model.provider),
                    name=str(model_payload.get("name") or fb.model.name),
                    rationale=str(model_payload.get("rationale") or fb.model.rationale),
                ),
                parameter=PipelineParameterDraft(
                    name=str(parameter_payload.get("name") or fb.parameter.name)[:200],
                    temperature=min(
                        _number(parameter_payload.get("temperature"), fb.parameter.temperature, 0, 2),
                        0.2 if high_accuracy else 2,
                    ),
                    top_p=_number(parameter_payload.get("top_p"), fb.parameter.top_p, 0, 1),
                    max_tokens=int(_number(parameter_payload.get("max_tokens"), fb.parameter.max_tokens, 256, 12000)),
                    search_limit=int(_number(parameter_payload.get("search_limit"), fb.parameter.search_limit, 1, 10)),
                    search_strategy=_search_strategy(
                        parameter_payload.get("search_strategy"),
                        "agent" if high_accuracy else fb.parameter.search_strategy,
                    ),
                    force_citations=True if high_accuracy else bool(parameter_payload.get("force_citations", fb.parameter.force_citations)),
                    require_structured_output=bool(
                        True if high_accuracy else parameter_payload.get("require_structured_output", fb.parameter.require_structured_output)
                    ),
                    enable_evaluator=bool(parameter_payload.get("enable_evaluator", fb.parameter.enable_evaluator)),
                    enable_secondary_verification=bool(
                        True if high_accuracy else parameter_payload.get("enable_secondary_verification", fb.parameter.enable_secondary_verification)
                    ),
                    allow_model_memory=bool(parameter_payload.get("allow_model_memory", False)),
                    rationale=str(parameter_payload.get("rationale") or fb.parameter.rationale),
                ),
                rationale="从旧格式兼容的单候选方案",
            )
        ]

    return PipelineDraftRead(
        requirement=requirement,
        task=PipelineTaskDraft(
            name=str(task_payload.get("name") or fallback.task.name)[:200],
            description=str(task_payload.get("description") or fallback.task.description),
            background=str(task_payload.get("background") or fallback.task.background),
            focus_points=str(task_payload.get("focus_points") or fallback.task.focus_points),
        ),
        evaluation_targets=targets,
        candidates=candidates,
        selected_candidate_index=0,
        assumptions=_string_list(payload.get("assumptions")),
        review_notes=_string_list(payload.get("review_notes")) or fallback.review_notes,
        agent_name=PIPELINE_PLANNER_AGENT_KEY,
        agent_model=agent_model,
        prompt_location=PIPELINE_PLANNER_PROMPT_LOCATION,
    )


def _candidate_from_payload(
    cand: dict[str, Any],
    fallback_candidate: PipelineCandidateDraft,
    high_accuracy: bool,
) -> PipelineCandidateDraft:
    """从 JSON payload 解析单个候选配置"""
    prompt_payload = cand.get("prompt") if isinstance(cand.get("prompt"), dict) else {}
    model_payload = cand.get("model") if isinstance(cand.get("model"), dict) else {}
    parameter_payload = cand.get("parameter") if isinstance(cand.get("parameter"), dict) else {}
    fb = fallback_candidate

    return PipelineCandidateDraft(
        label=str(cand.get("label") or fb.label)[:200],
        prompt=PipelinePromptDraft(
            name=str(prompt_payload.get("name") or fb.prompt.name)[:200],
            version=str(prompt_payload.get("version") or "v1"),
            system_prompt=_ensure_contract_prompt(str(prompt_payload.get("system_prompt") or fb.prompt.system_prompt)),
            user_prompt=str(prompt_payload.get("user_prompt") or ""),
        ),
        model=PipelineModelDraft(
            provider=str(model_payload.get("provider") or fb.model.provider),
            name=str(model_payload.get("name") or fb.model.name),
            rationale=str(model_payload.get("rationale") or fb.model.rationale),
        ),
        parameter=PipelineParameterDraft(
            name=str(parameter_payload.get("name") or fb.parameter.name)[:200],
            temperature=min(
                _number(parameter_payload.get("temperature"), fb.parameter.temperature, 0, 2),
                0.2 if high_accuracy else 2,
            ),
            top_p=_number(parameter_payload.get("top_p"), fb.parameter.top_p, 0, 1),
            max_tokens=int(_number(parameter_payload.get("max_tokens"), fb.parameter.max_tokens, 256, 12000)),
            search_limit=int(_number(parameter_payload.get("search_limit"), fb.parameter.search_limit, 1, 10)),
            search_strategy=_search_strategy(
                parameter_payload.get("search_strategy"),
                "agent" if high_accuracy else fb.parameter.search_strategy,
            ),
            force_citations=True if high_accuracy else bool(parameter_payload.get("force_citations", fb.parameter.force_citations)),
            require_structured_output=bool(
                True if high_accuracy else parameter_payload.get("require_structured_output", fb.parameter.require_structured_output)
            ),
            enable_evaluator=bool(parameter_payload.get("enable_evaluator", fb.parameter.enable_evaluator)),
            enable_secondary_verification=bool(
                True if high_accuracy else parameter_payload.get("enable_secondary_verification", fb.parameter.enable_secondary_verification)
            ),
            allow_model_memory=bool(parameter_payload.get("allow_model_memory", False)),
            rationale=str(parameter_payload.get("rationale") or fb.parameter.rationale),
        ),
        rationale=str(cand.get("rationale") or fb.rationale),
    )


def _ensure_contract_prompt(system_prompt: str) -> str:
    if all(keyword in system_prompt for keyword in ["claims", "sources", "unverified_items", "search_queries_used"]):
        return system_prompt
    return f"{system_prompt.rstrip()}\n\n{STRUCTURED_OUTPUT_INSTRUCTIONS}"


def _fallback_draft(requirement: str) -> PipelineDraftRead:
    high_accuracy = any(word in requirement for word in ["背调", "核验", "准确", "风险", "招投标", "处罚", "监管", "舆情"])
    system_prompt = _fallback_system_prompt(requirement)

    # 候选A：保守稳健方案
    candidate_a = PipelineCandidateDraft(
        label="候选A：保守稳健方案",
        prompt=PipelinePromptDraft(
            name="保守稳健 Prompt",
            version="v1",
            system_prompt=system_prompt,
            user_prompt="",
        ),
        model=PipelineModelDraft(
            provider="bailian",
            name="qwen-max" if high_accuracy else "qwen-plus",
            rationale="选择高端模型以确保输出质量，适合高准确性要求场景。",
        ),
        parameter=PipelineParameterDraft(
            name="保守稳健参数",
            temperature=0.1,
            top_p=0.9,
            max_tokens=3600,
            search_limit=5,
            search_strategy="agent",
            force_citations=True,
            require_structured_output=True,
            enable_evaluator=True,
            enable_secondary_verification=True,
            allow_model_memory=False,
            rationale="低温度 + agent 搜索 + 二次核验，最大化准确性和来源可追溯性。",
        ),
        rationale="适合对准确性要求极高的场景，如企业背调、事实核验、风险识别。成本较高但质量最有保障。",
    )

    # 候选B：高性价比方案
    candidate_b = PipelineCandidateDraft(
        label="候选B：高性价比方案",
        prompt=PipelinePromptDraft(
            name="高性价比 Prompt",
            version="v1",
            system_prompt=system_prompt,
            user_prompt="",
        ),
        model=PipelineModelDraft(
            provider="bailian",
            name="qwen-plus",
            rationale="中端模型平衡质量与成本，适合大多数场景。",
        ),
        parameter=PipelineParameterDraft(
            name="高性价比参数",
            temperature=0.2,
            top_p=0.9,
            max_tokens=3000,
            search_limit=5,
            search_strategy="max",
            force_citations=True,
            require_structured_output=True,
            enable_evaluator=True,
            enable_secondary_verification=False,
            allow_model_memory=False,
            rationale="中等温度 + max 搜索，平衡质量与成本。",
        ),
        rationale="适合大多数常规评测场景，在质量和成本之间取得良好平衡。",
    )

    # 候选C：快速探索方案（仅非高精度任务时生成）
    candidates = [candidate_a, candidate_b]
    if not high_accuracy:
        candidate_c = PipelineCandidateDraft(
            label="候选C：快速探索方案",
            prompt=PipelinePromptDraft(
                name="快速探索 Prompt",
                version="v1",
                system_prompt=system_prompt,
                user_prompt="",
            ),
            model=PipelineModelDraft(
                provider="bailian",
                name="qwen-turbo",
                rationale="轻量模型适合快速迭代和初步探索。",
            ),
            parameter=PipelineParameterDraft(
                name="快速探索参数",
                temperature=0.3,
                top_p=0.95,
                max_tokens=2400,
                search_limit=3,
                search_strategy="turbo",
                force_citations=False,
                require_structured_output=True,
                enable_evaluator=False,
                enable_secondary_verification=False,
                allow_model_memory=False,
                rationale="较高温度 + turbo 搜索，快速获得初步结果，适合探索性测试。",
            ),
            rationale="适合初步探索或成本敏感场景，快速获取结果用于方向验证。",
        )
        candidates.append(candidate_c)

    return PipelineDraftRead(
        requirement=requirement,
        task=PipelineTaskDraft(
            name=_short_name(requirement),
            description=f"基于用户需求开展联网搜索评测：{requirement}",
            background=requirement,
            focus_points="真实性、来源可追溯性、时间线准确性、关键风险识别、无法确认事项。",
        ),
        evaluation_targets=[
            EvaluationTargetCreate(name="真实性", description="事实、时间、主体和结论是否有可靠证据支撑。", weight=45),
            EvaluationTargetCreate(name="完整性", description="是否覆盖用户需求中的关键关注点。", weight=20),
            EvaluationTargetCreate(name="来源质量", description="来源是否权威、可追溯，并能绑定关键结论。", weight=15),
            EvaluationTargetCreate(name="风险识别", description="是否识别重要风险、边界和无法确认事项。", weight=10),
            EvaluationTargetCreate(name="结构表达", description="输出是否便于人工复核和后续对比。", weight=5),
            EvaluationTargetCreate(name="成本效率", description="结合成本、耗时和结果质量判断性价比。", weight=5),
        ],
        candidates=candidates,
        selected_candidate_index=0,
        assumptions=["该草稿由规则兜底生成，建议人工重点审核 Prompt 和参数。"],
        review_notes=["确认任务目标是否完整。", "确认搜索策略与成本预算是否匹配。", "确认 Prompt 是否覆盖具体输出格式。"],
        agent_name=PIPELINE_PLANNER_AGENT_KEY,
        agent_model="rule_fallback",
        prompt_location=PIPELINE_PLANNER_PROMPT_LOCATION,
    )


def _fallback_system_prompt(requirement: str) -> str:
    return "\n".join(
        [
            "你是一个联网搜索型事实核验 Agent。",
            f"任务需求：{requirement}",
            "请只基于联网搜索结果和可验证来源回答，不要使用模型记忆补全事实。",
            "每个关键结论必须放入 claims；claim_type=fact 的结论必须绑定 source_ids。",
            "涉及时间、金额、主体、状态、处罚、招投标、舆情等信息时，必须核对发布日期和事件发生时间。",
            "请区分 fact、inference、unknown；无法确认的内容必须写入 unverified_items。",
            STRUCTURED_OUTPUT_INSTRUCTIONS,
        ]
    )


def _parse_json_object(text: str) -> dict[str, Any] | None:
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
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _targets_from_payload(value: Any) -> list[EvaluationTargetCreate]:
    if not isinstance(value, list):
        return []
    targets = []
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        targets.append(
            EvaluationTargetCreate(
                name=str(item.get("name") or "评测目标")[:100],
                description=str(item.get("description") or ""),
                weight=_number(item.get("weight"), 10, 0, 100),
                is_enabled=bool(item.get("is_enabled", True)),
            )
        )
    return targets


def _number(value: Any, default: float, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(low, min(number, high))


def _search_strategy(value: Any, default: str) -> str:
    strategy = str(value or default).lower()
    return strategy if strategy in {"turbo", "max", "agent"} else default


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _short_name(requirement: str) -> str:
    cleaned = re.sub(r"\s+", " ", requirement).strip()
    return (cleaned[:28] or "新评测任务") + ("..." if len(cleaned) > 28 else "")
