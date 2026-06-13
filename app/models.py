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


class LearnerState(SQLModel, table=True):
    __tablename__ = "learner_state"

    id: Optional[int] = Field(default=1, primary_key=True)
    user_profile_id: int = Field(default=1, foreign_key="userprofile.id", index=True)
    mastered_topics_json: str = "[]"
    deferred_topics_json: str = "[]"
    skipped_topics_json: str = "[]"
    interests_json: str = "[]"
    daily_time_budget: str = "30 minutes"
    energy_level: str = "medium"
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)


class LearningRoadmap(SQLModel, table=True):
    __tablename__ = "learning_roadmap"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    goal: str = ""
    status: str = Field(default="active", index=True)
    current_version: int = 1
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)


class RoadmapVersion(SQLModel, table=True):
    __tablename__ = "roadmap_version"

    id: Optional[int] = Field(default=None, primary_key=True)
    roadmap_id: int = Field(foreign_key="learning_roadmap.id", index=True)
    version_number: int = Field(default=1, index=True)
    summary: str = ""
    reason: str = ""
    previous_version_id: Optional[int] = Field(default=None, foreign_key="roadmap_version.id")
    created_at: datetime = Field(default_factory=utcnow, nullable=False)


class SyllabusModule(SQLModel, table=True):
    __tablename__ = "syllabus_module"

    id: Optional[int] = Field(default=None, primary_key=True)
    roadmap_id: int = Field(foreign_key="learning_roadmap.id", index=True)
    title: str = Field(index=True)
    domain: str = ""
    summary: str = ""
    sort_order: int = 0
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)


class SyllabusItem(SQLModel, table=True):
    __tablename__ = "syllabus_item"

    id: Optional[int] = Field(default=None, primary_key=True)
    roadmap_id: int = Field(foreign_key="learning_roadmap.id", index=True)
    module_id: int = Field(foreign_key="syllabus_module.id", index=True)
    parent_item_id: Optional[int] = Field(default=None, foreign_key="syllabus_item.id", index=True)
    title: str = Field(index=True)
    subtopic: str = ""
    status: str = Field(default="later", index=True)
    category: str = Field(default="stable_core", index=True)
    source_basis: str = ""
    freshness_note: str = ""
    freshness_level: str = Field(default="unknown", index=True)
    freshness_checked_at: Optional[datetime] = None
    confidence: float = 0.0
    why_this_now: str = ""
    prerequisites_json: str = "[]"
    effort_score: int = 5
    roi_score: int = 5
    urgency_score: int = 5
    sort_order: int = 0
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)


class EvidenceSource(SQLModel, table=True):
    __tablename__ = "evidence_source"

    id: Optional[int] = Field(default=None, primary_key=True)
    source_title: str = Field(index=True)
    url: str = ""
    manual_note: str = ""
    source_type: str = Field(default="user_note", index=True)
    related_topic: str = Field(index=True)
    captured_at: datetime = Field(default_factory=utcnow, nullable=False)
    freshness_checked_at: Optional[datetime] = None
    freshness_level: str = Field(default="unknown", index=True)
    summary: str = ""
    reliability_score: float = 0.5


class RecommendationRun(SQLModel, table=True):
    __tablename__ = "recommendation_run"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_profile_id: int = Field(default=1, foreign_key="userprofile.id", index=True)
    roadmap_id: Optional[int] = Field(default=None, foreign_key="learning_roadmap.id", index=True)
    next_topic: str = Field(index=True)
    next_subtopic: str = ""
    decision: str = Field(default="learn_now", index=True)
    why_this_now: str = ""
    why_not_other_options: str = ""
    prerequisites_missing_json: str = "[]"
    roi_score: int = 0
    effort_score: int = 0
    urgency_score: int = 0
    confidence: float = 0.0
    alternatives_json: str = "[]"
    recommended_depth: str = "working_knowledge"
    suggested_next_steps_json: str = "[]"
    source_basis: str = ""
    freshness_note: str = ""
    freshness_level: str = Field(default="unknown", index=True)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)


class RecommendationOption(SQLModel, table=True):
    __tablename__ = "recommendation_option"

    id: Optional[int] = Field(default=None, primary_key=True)
    recommendation_run_id: int = Field(foreign_key="recommendation_run.id", index=True)
    syllabus_item_id: Optional[int] = Field(default=None, foreign_key="syllabus_item.id", index=True)
    title: str = Field(index=True)
    subtopic: str = ""
    decision: str = Field(default="learn_now", index=True)
    status: str = Field(default="later", index=True)
    score: float = 0.0
    why: str = ""
    source_basis: str = ""
    freshness_level: str = "unknown"
    confidence: float = 0.0


class TopicFeedback(SQLModel, table=True):
    __tablename__ = "topic_feedback"

    id: Optional[int] = Field(default=None, primary_key=True)
    syllabus_item_id: Optional[int] = Field(default=None, foreign_key="syllabus_item.id", index=True)
    topic_title: str = Field(index=True)
    action: str = Field(index=True)
    note: str = ""
    created_at: datetime = Field(default_factory=utcnow, nullable=False)


class MasteryRecord(SQLModel, table=True):
    __tablename__ = "mastery_record"

    id: Optional[int] = Field(default=None, primary_key=True)
    syllabus_item_id: Optional[int] = Field(default=None, foreign_key="syllabus_item.id", index=True)
    topic_title: str = Field(index=True)
    can_explain: bool = False
    can_build: bool = False
    can_debug: bool = False
    can_apply: bool = False
    evidence_note: str = ""
    confidence: float = 0.0
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)


class ValidationErrorRecord(SQLModel, table=True):
    __tablename__ = "validation_error_record"

    id: Optional[int] = Field(default=None, primary_key=True)
    output_type: str = Field(index=True)
    source: str = ""
    errors_json: str = "[]"
    raw_output: str = ""
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
