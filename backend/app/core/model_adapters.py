import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import get_settings


class ProviderConfig(BaseModel):
    label: str
    api_style: str = "openai_compatible"
    base_url: str
    api_key_env: str
    api_key_env_aliases: list[str] = Field(default_factory=list)
    default_model: str
    models: list[str] = Field(default_factory=list)
    builtin_search: dict[str, Any] = Field(default_factory=dict)


class AgentModelConfig(BaseModel):
    label: str
    provider: str
    model: str
    temperature: float = 0.2
    top_p: float = 0.9
    max_tokens: int = 1800


class ModelAdapterConfig(BaseModel):
    default_provider: str = "deepseek"
    providers: dict[str, ProviderConfig]
    agents: dict[str, AgentModelConfig]


def _config_path() -> Path:
    settings = get_settings()
    path = Path(settings.model_adapter_config)
    if path.is_absolute():
        return path
    backend_dir = Path(__file__).resolve().parents[2]
    project_root = backend_dir.parent
    candidates = [backend_dir / path, project_root / path, Path.cwd() / path]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return project_root / path


@lru_cache
def get_model_adapter_config() -> ModelAdapterConfig:
    path = _config_path()
    with path.open("r", encoding="utf-8") as file:
        data: dict[str, Any] = json.load(file)
    settings = get_settings()
    if settings.default_llm_provider:
        data["default_provider"] = settings.default_llm_provider
    return ModelAdapterConfig.model_validate(data)


def get_provider(provider_name: str | None) -> ProviderConfig:
    config = get_model_adapter_config()
    name = provider_name or config.default_provider
    provider = config.providers.get(name)
    if provider is None:
        provider = config.providers[config.default_provider]
    return provider


def get_agent_model(agent_key: str) -> AgentModelConfig:
    config = get_model_adapter_config()
    return config.agents.get(agent_key) or AgentModelConfig(
        label=agent_key,
        provider=config.default_provider,
        model=get_provider(config.default_provider).default_model,
    )


def resolve_api_key(provider: ProviderConfig, api_key_ref: str = "") -> str:
    if api_key_ref and api_key_ref.startswith(("sk-", "ds-", "bailian-")):
        return api_key_ref
    if api_key_ref:
        return os.getenv(api_key_ref, "")
    primary = os.getenv(provider.api_key_env, "")
    if primary:
        return primary
    for alias in provider.api_key_env_aliases:
        value = os.getenv(alias, "")
        if value:
            return value
    return ""


def provider_uses_builtin_search(provider_name: str | None) -> bool:
    provider = get_provider(provider_name)
    return bool(provider.builtin_search.get("enabled"))


def chat_completions_search_extra(provider: ProviderConfig, search_strategy: str | None = None) -> dict[str, Any]:
    builtin_search = provider.builtin_search or {}
    if not builtin_search.get("enabled"):
        return {}
    if builtin_search.get("api_mode") != "chat_completions":
        return {}
    chat_config = builtin_search.get("chat_completions", {})
    extra: dict[str, Any] = {}
    if "enable_search" in chat_config:
        extra["enable_search"] = chat_config["enable_search"]
    if "search_options" in chat_config:
        search_options = dict(chat_config["search_options"])
        if search_strategy and search_strategy != "default":
            if search_strategy in {"agent", "agent_max"}:
                search_options = {"search_strategy": search_strategy}
            else:
                search_options["search_strategy"] = search_strategy
                search_options["enable_source"] = bool(search_options.get("enable_source", True))
        extra["search_options"] = search_options
    return extra


def provider_options() -> list[dict[str, Any]]:
    config = get_model_adapter_config()
    return [
        {
            "name": key,
            "label": provider.label,
            "base_url": provider.base_url,
            "api_key_env": provider.api_key_env,
            "api_key_env_aliases": provider.api_key_env_aliases,
            "default_model": provider.default_model,
            "models": provider.models,
            "builtin_search": provider.builtin_search,
        }
        for key, provider in config.providers.items()
    ]


def agent_model_options() -> dict[str, Any]:
    config = get_model_adapter_config()
    return {
        key: {
            "label": agent.label,
            "provider": agent.provider,
            "model": agent.model,
            "temperature": agent.temperature,
            "top_p": agent.top_p,
            "max_tokens": agent.max_tokens,
        }
        for key, agent in config.agents.items()
    }


# ── 模型库集成（优先从数据库读取，回退到静态 JSON）──────────────────


def get_available_models_from_db(db: Any) -> list[dict[str, Any]]:
    """从数据库获取可用模型列表（包含特点标签和性能统计）

    Args:
        db: SQLAlchemy Session

    Returns:
        模型列表，每个模型包含 provider、name、characteristics、avg_total_score 等字段
        如果数据库为空或查询失败，返回空列表
    """
    try:
        from app.models.entities import ModelProfile
        from sqlalchemy import select

        stmt = (
            select(ModelProfile)
            .where(ModelProfile.is_active == True)
            .order_by(ModelProfile.avg_total_score.desc())
        )
        profiles = list(db.scalars(stmt).all())

        if not profiles:
            return []

        result = []
        for profile in profiles:
            # 解析 characteristics_json
            try:
                characteristics = json.loads(profile.characteristics_json) if profile.characteristics_json else []
            except (json.JSONDecodeError, TypeError):
                characteristics = []

            result.append({
                "id": profile.id,
                "provider": profile.provider,
                "name": profile.name,
                "display_name": profile.display_name or profile.name,
                "supports_search": profile.supports_search,
                "search_mode": profile.search_mode,
                "input_price_per_1k": profile.input_price_per_1k,
                "output_price_per_1k": profile.output_price_per_1k,
                "characteristics": characteristics,
                "avg_total_score": profile.avg_total_score,
                "avg_truthfulness_score": profile.avg_truthfulness_score,
                "avg_cost_efficiency_score": profile.avg_cost_efficiency_score,
                "total_test_count": profile.total_test_count,
            })
        return result
    except Exception:
        # 数据库不可用或表不存在时，返回空列表
        return []


def get_available_models_with_fallback(db: Any) -> list[dict[str, Any]]:
    """获取可用模型列表，优先从数据库读取，回退到静态 JSON

    Args:
        db: SQLAlchemy Session（可为 None）

    Returns:
        模型列表
    """
    # 尝试从数据库读取
    if db is not None:
        db_models = get_available_models_from_db(db)
        if db_models:
            return db_models

    # 回退到静态 JSON
    config = get_model_adapter_config()
    result = []
    for provider_name, provider in config.providers.items():
        for model_name in provider.models:
            result.append({
                "provider": provider_name,
                "name": model_name,
                "display_name": model_name,
                "supports_search": bool(provider.builtin_search.get("enabled")),
                "search_mode": "builtin" if provider.builtin_search.get("enabled") else "none",
                "characteristics": [],
                "avg_total_score": 0,
                "avg_truthfulness_score": 0,
                "avg_cost_efficiency_score": 0,
                "total_test_count": 0,
            })
    return result


def format_models_for_prompt(models: list[dict[str, Any]], limit: int = 5) -> str:
    """将模型列表格式化为可注入到 Agent Prompt 中的文本

    Args:
        models: 模型列表（来自 get_available_models_with_fallback）
        limit: 最多显示多少个模型

    Returns:
        格式化的文本字符串
    """
    if not models:
        return "（无可用模型信息）"

    lines = []
    for model in models[:limit]:
        characteristics = model.get("characteristics", [])
        char_str = ", ".join(characteristics) if characteristics else "无特点标签"
        avg_score = model.get("avg_total_score", 0)
        score_str = f"{avg_score:.1f}" if avg_score > 0 else "暂无评分"

        lines.append(
            f"- {model['name']} ({model['provider']}): "
            f"特点[{char_str}], 平均评分{score_str}"
        )

    return "\n".join(lines)
