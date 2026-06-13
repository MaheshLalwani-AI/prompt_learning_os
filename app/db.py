from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv
from sqlmodel import Session, SQLModel, create_engine

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")

if DATABASE_URL.startswith("sqlite:///"):
    db_path = DATABASE_URL.replace("sqlite:///", "", 1)
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)


def migrate_existing_sqlite_schema() -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return

    with engine.begin() as connection:
        tables = {
            row[0]
            for row in connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if "promptrun" not in tables:
            return

        columns = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(promptrun)")
        }
        prompt_run_columns = {
            "learning_session_id": "INTEGER",
            "prompt_template_id": "INTEGER",
            "provider_id": "INTEGER",
            "system_prompt": "VARCHAR DEFAULT ''",
            "provider_name": "VARCHAR DEFAULT ''",
            "model_name": "VARCHAR DEFAULT ''",
            "routing_reason": "VARCHAR DEFAULT ''",
            "input_token_estimate": "INTEGER DEFAULT 0",
            "output_token_estimate": "INTEGER DEFAULT 0",
            "estimated_cost_usd": "FLOAT DEFAULT 0.0",
            "response_status": "VARCHAR DEFAULT 'prompt_created'",
        }
        for column_name, column_type in prompt_run_columns.items():
            if column_name not in columns:
                connection.exec_driver_sql(
                    f"ALTER TABLE promptrun ADD COLUMN {column_name} {column_type}"
                )


def init_db() -> None:
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    migrate_existing_sqlite_schema()


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
