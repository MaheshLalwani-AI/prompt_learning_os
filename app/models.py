from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserProfile(SQLModel, table=True):
    __tablename__ = "userprofile"

    id: Optional[int] = Field(default=1, primary_key=True)
    primary_goal: str = ""
    current_level: str = ""
    learning_preferences: str = ""
    optimization_mode: str = "balanced"  # token_saver | balanced | quality_first
    default_mode: str = "teach"  # teach | plan | verify | summarize | practice | debug
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)


class LearningSession(SQLModel, table=True):
    __tablename__ = "learning_session"

    id: Optional[int] = Field(default=None, primary_key=True)
    topic: str = Field(index=True)
    goal: str = ""
    current_level: str = ""
    mode: str = Field(default="teach", index=True)
    status: str = Field(default="prompt_created", index=True)
    summary: str = ""
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)


class PromptTemplate(SQLModel, table=True):
    __tablename__ = "prompt_template"

    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(index=True)
    name: str
    mode: str = Field(default="teach", index=True)
    description: str = ""
    instruction_text: str = ""
    output_format: str = ""
    next_step: str = ""
    sort_order: int = 0
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)


class ModelProvider(SQLModel, table=True):
    __tablename__ = "model_provider"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    base_url: str = ""
    default_model: str = Field(default="", index=True)
    input_cost_per_1m_tokens: float = 0.0
    output_cost_per_1m_tokens: float = 0.0
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)


class PromptRun(SQLModel, table=True):
    __tablename__ = "promptrun"

    id: Optional[int] = Field(default=None, primary_key=True)
    learning_session_id: Optional[int] = Field(default=None, foreign_key="learning_session.id", index=True)
    prompt_template_id: Optional[int] = Field(default=None, foreign_key="prompt_template.id", index=True)
    provider_id: Optional[int] = Field(default=None, foreign_key="model_provider.id", index=True)
    topic: str
    goal: str = ""
    current_level: str = ""
    mode: str = "teach"
    time_budget: str = ""
    extra_context: str = ""
    system_prompt: str = ""
    prompt_text: str
    llm_response: str = ""
    next_step: str = ""
    provider_name: str = ""
    model_name: str = ""
    routing_reason: str = ""
    input_token_estimate: int = 0
    output_token_estimate: int = 0
    estimated_cost_usd: float = 0.0
    response_status: str = Field(default="prompt_created", index=True)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)


class CostRecord(SQLModel, table=True):
    __tablename__ = "cost_record"

    id: Optional[int] = Field(default=None, primary_key=True)
    prompt_run_id: Optional[int] = Field(default=None, foreign_key="promptrun.id", index=True)
    learning_session_id: Optional[int] = Field(default=None, foreign_key="learning_session.id", index=True)
    provider_id: Optional[int] = Field(default=None, foreign_key="model_provider.id", index=True)
    provider_name: str = ""
    model_name: str = Field(default="", index=True)
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    currency: str = "USD"
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
