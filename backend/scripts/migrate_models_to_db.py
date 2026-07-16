"""
静态配置→数据库迁移脚本

将 config/model_adapters.json 和 config/pricing.json 中的模型信息
迁移到 model_profiles 表中。

此脚本是幂等的：如果模型已存在则跳过，不会重复创建。

使用方法：
    cd backend
    python -m scripts.migrate_models_to_db
"""

import json
import sys
from pathlib import Path

# 添加 backend 目录到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.models.entities import ModelProfile


def load_json_config(file_path: Path) -> dict:
    """加载 JSON 配置文件"""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def migrate_models_to_db():
    """将静态配置中的模型信息迁移到数据库"""
    # 确保数据库表结构已创建
    print("正在初始化数据库表结构...")
    init_db()
    print("数据库表结构初始化完成")
    
    # 加载配置文件
    config_dir = backend_dir.parent / "config"
    adapters_path = config_dir / "model_adapters.json"
    pricing_path = config_dir / "pricing.json"

    if not adapters_path.exists():
        print(f"错误：找不到 {adapters_path}")
        return

    adapters_config = load_json_config(adapters_path)
    pricing_config = load_json_config(pricing_path) if pricing_path.exists() else {}

    providers = adapters_config.get("providers", {})
    pricing_providers = pricing_config.get("providers", {})

    db: Session = SessionLocal()
    created_count = 0
    skipped_count = 0

    try:
        for provider_name, provider_info in providers.items():
            base_url = provider_info.get("base_url", "")
            api_key_env = provider_info.get("api_key_env", "")
            models = provider_info.get("models", [])
            builtin_search = provider_info.get("builtin_search", {})
            supports_search = builtin_search.get("enabled", False)
            search_mode = "builtin" if supports_search else "none"

            # 获取该 provider 的定价信息
            provider_pricing = pricing_providers.get(provider_name, {}).get("models", {})

            for model_name in models:
                # 检查是否已存在
                existing = db.query(ModelProfile).filter(
                    ModelProfile.provider == provider_name,
                    ModelProfile.name == model_name,
                ).first()

                if existing:
                    print(f"跳过已存在的模型：{provider_name}/{model_name}")
                    skipped_count += 1
                    continue

                # 获取定价信息（每百万 token 转换为每千 token）
                model_pricing = provider_pricing.get(model_name, {})
                input_price_per_1k = model_pricing.get("input_per_million_tokens", 0) / 1000
                output_price_per_1k = model_pricing.get("output_per_million_tokens", 0) / 1000

                # 创建 ModelProfile
                profile = ModelProfile(
                    provider=provider_name,
                    name=model_name,
                    display_name=model_name,
                    api_base=base_url,
                    api_key_env=api_key_env,
                    supports_search=supports_search,
                    search_mode=search_mode,
                    input_price_per_1k=input_price_per_1k,
                    output_price_per_1k=output_price_per_1k,
                    currency="CNY",
                    characteristics_json="[]",
                    avg_total_score=0,
                    avg_truthfulness_score=0,
                    avg_cost_efficiency_score=0,
                    total_test_count=0,
                    is_active=True,
                    notes="从静态配置迁移",
                )
                db.add(profile)
                created_count += 1
                print(f"创建模型：{provider_name}/{model_name}")

        db.commit()
        print(f"\n迁移完成：创建 {created_count} 个模型，跳过 {skipped_count} 个已存在的模型")

    except Exception as e:
        db.rollback()
        print(f"迁移失败：{e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate_models_to_db()
