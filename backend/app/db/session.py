from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, echo=settings.sql_echo, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models import entities  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_prompt_columns()
    _ensure_parameter_columns()
    _ensure_evaluation_columns()


def _ensure_prompt_columns() -> None:
    inspector = inspect(engine)
    if "prompts" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("prompts")}
    statements: list[str] = []
    dialect = engine.dialect.name
    if "system_prompt" not in existing:
        if dialect == "mysql":
            statements.append("ALTER TABLE prompts ADD COLUMN system_prompt TEXT NULL")
        else:
            statements.append("ALTER TABLE prompts ADD COLUMN system_prompt TEXT NOT NULL DEFAULT ''")
    if "user_prompt" not in existing:
        if dialect == "mysql":
            statements.append("ALTER TABLE prompts ADD COLUMN user_prompt TEXT NULL")
        else:
            statements.append("ALTER TABLE prompts ADD COLUMN user_prompt TEXT NOT NULL DEFAULT ''")
    if "parent_prompt_id" not in existing:
        if dialect == "mysql":
            statements.append("ALTER TABLE prompts ADD COLUMN parent_prompt_id INT NULL")
        else:
            statements.append("ALTER TABLE prompts ADD COLUMN parent_prompt_id INTEGER NULL")
    if "source_type" not in existing:
        if dialect == "mysql":
            statements.append("ALTER TABLE prompts ADD COLUMN source_type VARCHAR(50) NOT NULL DEFAULT 'manual'")
        else:
            statements.append("ALTER TABLE prompts ADD COLUMN source_type VARCHAR(50) NOT NULL DEFAULT 'manual'")
    if "optimization_note" not in existing:
        if dialect == "mysql":
            statements.append("ALTER TABLE prompts ADD COLUMN optimization_note TEXT NULL")
        else:
            statements.append("ALTER TABLE prompts ADD COLUMN optimization_note TEXT NOT NULL DEFAULT ''")
    if not statements:
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
        connection.execute(text("UPDATE prompts SET system_prompt = content WHERE system_prompt = ''"))


def _ensure_parameter_columns() -> None:
    inspector = inspect(engine)
    if "parameter_configs" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("parameter_configs")}
    if "search_strategy" in existing:
        return
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE parameter_configs ADD COLUMN search_strategy VARCHAR(50) NOT NULL DEFAULT 'default'")
        )


def _ensure_evaluation_columns() -> None:
    inspector = inspect(engine)
    if "evaluation_results" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("evaluation_results")}
    if "rule_metrics_json" in existing:
        return
    with engine.begin() as connection:
        if engine.dialect.name == "mysql":
            connection.execute(text("ALTER TABLE evaluation_results ADD COLUMN rule_metrics_json TEXT NULL"))
        else:
            connection.execute(text("ALTER TABLE evaluation_results ADD COLUMN rule_metrics_json TEXT NOT NULL DEFAULT '{}'"))
