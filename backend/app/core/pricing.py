import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings


class ModelPricing(BaseModel):
    input_per_million_tokens: float = 0
    cached_input_per_million_tokens: float = 0
    output_per_million_tokens: float = 0


class ToolPricing(BaseModel):
    web_search_per_1000_calls: float = 0
    web_extractor_per_1000_calls: float = 0


class ProviderPricing(BaseModel):
    models: dict[str, ModelPricing] = Field(default_factory=dict)
    tools: ToolPricing = Field(default_factory=ToolPricing)


class PricingConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    currency: str = "CNY"
    default_model_pricing: ModelPricing = Field(default_factory=ModelPricing)
    default_tool_pricing: ToolPricing = Field(default_factory=ToolPricing)
    providers: dict[str, ProviderPricing] = Field(default_factory=dict)


def _config_path() -> Path:
    settings = get_settings()
    path = Path(settings.pricing_config)
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
def get_pricing_config() -> PricingConfig:
    path = _config_path()
    with path.open("r", encoding="utf-8") as file:
        data: dict[str, Any] = json.load(file)
    return PricingConfig.model_validate(data)


def estimate_model_cost(provider: str, model: str, usage: dict[str, Any]) -> dict[str, Any]:
    config = get_pricing_config()
    provider_pricing = config.providers.get(provider)
    pricing = config.default_model_pricing
    if provider_pricing:
        pricing = provider_pricing.models.get(model, config.default_model_pricing)

    prompt_tokens = _int_from_usage(usage, "prompt_tokens", "input_tokens")
    completion_tokens = _int_from_usage(usage, "completion_tokens", "output_tokens")
    cached_input_tokens = _int_from_usage(
        usage,
        "prompt_cache_hit_tokens",
        "cached_tokens",
        "cached_input_tokens",
        "cache_hit_tokens",
    )
    billable_input_tokens = max(prompt_tokens - cached_input_tokens, 0)

    input_cost = billable_input_tokens * pricing.input_per_million_tokens / 1_000_000
    cached_input_cost = cached_input_tokens * pricing.cached_input_per_million_tokens / 1_000_000
    output_cost = completion_tokens * pricing.output_per_million_tokens / 1_000_000
    total_cost = input_cost + cached_input_cost + output_cost

    return {
        "currency": config.currency,
        "provider": provider,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "cached_input_tokens": cached_input_tokens,
        "billable_input_tokens": billable_input_tokens,
        "completion_tokens": completion_tokens,
        "input_cost": round(input_cost, 8),
        "cached_input_cost": round(cached_input_cost, 8),
        "output_cost": round(output_cost, 8),
        "total_cost": round(total_cost, 8),
    }


def estimate_tool_cost(provider: str, tool_calls: dict[str, int]) -> dict[str, Any]:
    config = get_pricing_config()
    provider_pricing = config.providers.get(provider)
    pricing = provider_pricing.tools if provider_pricing else config.default_tool_pricing

    web_search_calls = max(int(tool_calls.get("web_search", 0)), 0)
    web_extractor_calls = max(int(tool_calls.get("web_extractor", 0)), 0)
    web_search_cost = web_search_calls * pricing.web_search_per_1000_calls / 1000
    web_extractor_cost = web_extractor_calls * pricing.web_extractor_per_1000_calls / 1000
    total_cost = web_search_cost + web_extractor_cost

    return {
        "currency": config.currency,
        "provider": provider,
        "tool_calls": {
            "web_search": web_search_calls,
            "web_extractor": web_extractor_calls,
        },
        "web_search_cost": round(web_search_cost, 8),
        "web_extractor_cost": round(web_extractor_cost, 8),
        "total_cost": round(total_cost, 8),
    }


def combine_costs(*parts: dict[str, Any]) -> dict[str, Any]:
    currency = next((part.get("currency") for part in parts if part.get("currency")), "CNY")
    total = sum(float(part.get("total_cost", 0) or 0) for part in parts)
    return {
        "currency": currency,
        "total_cost": round(total, 8),
        "parts": list(parts),
    }


def _int_from_usage(usage: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = usage.get(key)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0
    return 0


# ── 模型库集成（优先从数据库读取，回退到静态 JSON）──────────────────


def get_model_pricing_from_db(db: Any, provider: str, model: str) -> ModelPricing | None:
    """从数据库获取模型定价信息

    Args:
        db: SQLAlchemy Session
        provider: 提供商名称
        model: 模型名称

    Returns:
        ModelPricing 对象，如果数据库中没有或查询失败则返回 None
    """
    if db is None:
        return None

    try:
        from app.models.entities import ModelProfile
        from sqlalchemy import select

        stmt = select(ModelProfile).where(
            ModelProfile.provider == provider,
            ModelProfile.name == model,
            ModelProfile.is_active == True,
        )
        profile = db.scalar(stmt)

        if profile is None:
            return None

        # ModelProfile 存储的是每千 token 的价格，需要转换为每百万 token
        # 1M tokens = 1000 * 1K tokens
        return ModelPricing(
            input_per_million_tokens=profile.input_price_per_1k * 1000,
            cached_input_per_million_tokens=0,  # 数据库暂不存储缓存价格
            output_per_million_tokens=profile.output_price_per_1k * 1000,
        )
    except Exception:
        # 数据库不可用或表不存在时，返回 None
        return None


def estimate_model_cost_with_db(
    db: Any, provider: str, model: str, usage: dict[str, Any]
) -> dict[str, Any]:
    """估算模型调用成本，优先从数据库读取定价，回退到静态 JSON

    Args:
        db: SQLAlchemy Session（可为 None）
        provider: 提供商名称
        model: 模型名称
        usage: 用量信息字典

    Returns:
        成本估算结果
    """
    # 尝试从数据库读取定价
    pricing = get_model_pricing_from_db(db, provider, model)

    if pricing is None:
        # 回退到静态 JSON
        config = get_pricing_config()
        provider_pricing = config.providers.get(provider)
        pricing = config.default_model_pricing
        if provider_pricing:
            pricing = provider_pricing.models.get(model, config.default_model_pricing)
        currency = config.currency
    else:
        # 从数据库读取时，使用默认货币
        currency = "CNY"

    prompt_tokens = _int_from_usage(usage, "prompt_tokens", "input_tokens")
    completion_tokens = _int_from_usage(usage, "completion_tokens", "output_tokens")
    cached_input_tokens = _int_from_usage(
        usage,
        "prompt_cache_hit_tokens",
        "cached_tokens",
        "cached_input_tokens",
        "cache_hit_tokens",
    )
    billable_input_tokens = max(prompt_tokens - cached_input_tokens, 0)

    input_cost = billable_input_tokens * pricing.input_per_million_tokens / 1_000_000
    cached_input_cost = cached_input_tokens * pricing.cached_input_per_million_tokens / 1_000_000
    output_cost = completion_tokens * pricing.output_per_million_tokens / 1_000_000
    total_cost = input_cost + cached_input_cost + output_cost

    return {
        "currency": currency,
        "provider": provider,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "cached_input_tokens": cached_input_tokens,
        "billable_input_tokens": billable_input_tokens,
        "completion_tokens": completion_tokens,
        "input_cost": round(input_cost, 8),
        "cached_input_cost": round(cached_input_cost, 8),
        "output_cost": round(output_cost, 8),
        "total_cost": round(total_cost, 8),
    }

