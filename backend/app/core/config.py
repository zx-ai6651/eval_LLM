import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote

from pydantic import BaseModel, ConfigDict, Field

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


BACKEND_DIR = Path(__file__).resolve().parents[2]


def _load_env() -> None:
    if not load_dotenv:
        return
    load_dotenv(BACKEND_DIR / ".env")
    load_dotenv()


_load_env()


class Settings(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    app_name: str = "Agent Eval Platform"
    app_env: str = "development"
    database_url: str = "sqlite:///./agent_eval.db"
    sql_echo: bool = False
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    cors_origin_regex: str = (
        r"https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|10\.\d+\.\d+\.\d+|"
        r"192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?"
    )
    model_adapter_config: str = "../config/model_adapters.json"
    pricing_config: str = "../config/pricing.json"
    default_llm_provider: str = "deepseek"
    deepseek_api_key: str = ""
    bailian_api_key: str = ""
    search_provider: str = "bailian_builtin"
    tavily_api_key: str = ""
    serper_api_key: str = ""
    max_test_combinations: int = Field(default=48, ge=1, le=500)
    model_call_timeout_seconds: int = Field(default=900, ge=30, le=3600)
    evaluator_call_timeout_seconds: int = Field(default=240, ge=30, le=1800)
    prompt_optimizer_timeout_seconds: int = Field(default=120, ge=30, le=1800)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "Agent Eval Platform"),
        app_env=os.getenv("APP_ENV", "development"),
        database_url=_normalize_database_url(os.getenv("DATABASE_URL", "sqlite:///./agent_eval.db")),
        sql_echo=os.getenv("SQL_ECHO", "false").lower() == "true",
        cors_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"),
        cors_origin_regex=os.getenv(
            "CORS_ORIGIN_REGEX",
            r"https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|10\.\d+\.\d+\.\d+|"
            r"192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?",
        ),
        model_adapter_config=os.getenv("MODEL_ADAPTER_CONFIG", "../config/model_adapters.json"),
        pricing_config=os.getenv("PRICING_CONFIG", "../config/pricing.json"),
        default_llm_provider=os.getenv("DEFAULT_LLM_PROVIDER", "deepseek"),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        bailian_api_key=os.getenv("BAILIAN_API_KEY", ""),
        search_provider=os.getenv("SEARCH_PROVIDER", "bailian_builtin"),
        tavily_api_key=os.getenv("TAVILY_API_KEY", ""),
        serper_api_key=os.getenv("SERPER_API_KEY", ""),
        max_test_combinations=int(os.getenv("MAX_TEST_COMBINATIONS", "48")),
        model_call_timeout_seconds=int(os.getenv("MODEL_CALL_TIMEOUT_SECONDS", "900")),
        evaluator_call_timeout_seconds=int(os.getenv("EVALUATOR_CALL_TIMEOUT_SECONDS", "240")),
        prompt_optimizer_timeout_seconds=int(os.getenv("PROMPT_OPTIMIZER_TIMEOUT_SECONDS", "120")),
    )


def _normalize_database_url(database_url: str) -> str:
    if not database_url.startswith("sqlite:///") or database_url.startswith("sqlite:////"):
        return database_url

    path_text = unquote(database_url.removeprefix("sqlite:///"))
    path = Path(path_text)
    if path.is_absolute():
        return database_url

    resolved = (BACKEND_DIR / path).resolve()
    return f"sqlite:///{resolved.as_posix()}"
