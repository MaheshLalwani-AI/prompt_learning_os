from __future__ import annotations

from sqlmodel import Session, select

from .llm import LLMConfig
from .learning import seed_syllabus
from .models import ModelProvider, PromptTemplate, UserProfile, utcnow
from .operational_prompts import OPERATIONAL_PROMPTS
from .prompt_builder import DEFAULT_TEMPLATE_DEFINITIONS, OUTPUT_FORMAT


DEFAULT_PRIMARY_GOAL = "Become an AI Automation Engineer"
DEFAULT_CURRENT_LEVEL = "Basic Python"
DEFAULT_LEARNING_PREFERENCES = (
    "Current docs, stepwise teaching, complete scripts, Git discipline, "
    "uv workflow, practical outputs."
)


def ensure_default_profile(session: Session) -> UserProfile:
    profile = session.get(UserProfile, 1)
    if profile is None:
        profile = UserProfile(
            id=1,
            primary_goal=DEFAULT_PRIMARY_GOAL,
            current_level=DEFAULT_CURRENT_LEVEL,
            learning_preferences=DEFAULT_LEARNING_PREFERENCES,
            optimization_mode="balanced",
            default_mode="teach",
            updated_at=utcnow(),
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)
    return profile


def ensure_prompt_templates(session: Session) -> None:
    for definition in DEFAULT_TEMPLATE_DEFINITIONS:
        template = session.exec(
            select(PromptTemplate).where(PromptTemplate.slug == definition["slug"])
        ).first()
        if template is None:
            template = PromptTemplate(
                slug=definition["slug"],
                name=definition["name"],
                mode=definition["slug"],
                description=definition["description"],
                instruction_text=definition["instruction_text"],
                output_format=OUTPUT_FORMAT,
                next_step=definition["next_step"],
                sort_order=definition["sort_order"],
                is_active=True,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            session.add(template)
    for slug, prompt_text in OPERATIONAL_PROMPTS.items():
        template = session.exec(
            select(PromptTemplate).where(PromptTemplate.slug == slug)
        ).first()
        if template is None:
            template = PromptTemplate(
                slug=slug,
                name=slug.replace("_", " ").title(),
                mode="operational",
                description="Operational prompt used by recommendation and syllabus flows.",
                instruction_text=prompt_text,
                output_format="JSON object matching the route-specific schema.",
                next_step="Use this prompt through the structured recommendation system.",
                sort_order=1000,
                is_active=False,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            session.add(template)
    session.commit()


def get_templates(session: Session) -> list[PromptTemplate]:
    return session.exec(
        select(PromptTemplate)
        .where(PromptTemplate.is_active == True)  # noqa: E712
        .order_by(PromptTemplate.sort_order, PromptTemplate.name)
    ).all()


def get_template_by_slug(session: Session, slug: str) -> PromptTemplate:
    template = session.exec(
        select(PromptTemplate)
        .where(PromptTemplate.slug == slug)
        .where(PromptTemplate.is_active == True)  # noqa: E712
    ).first()
    if template is not None:
        return template

    fallback = session.exec(
        select(PromptTemplate)
        .where(PromptTemplate.slug == "teach")
        .where(PromptTemplate.is_active == True)  # noqa: E712
    ).first()
    if fallback is None:
        ensure_prompt_templates(session)
        fallback = session.exec(
            select(PromptTemplate).where(PromptTemplate.slug == "teach")
        ).one()
    return fallback


def ensure_model_provider(session: Session, config: LLMConfig) -> ModelProvider:
    provider_name = config.provider_name or "OpenAI-compatible"
    provider = session.exec(
        select(ModelProvider)
        .where(ModelProvider.name == provider_name)
        .where(ModelProvider.default_model == config.model)
    ).first()
    if provider is None:
        provider = ModelProvider(
            name=provider_name,
            base_url=config.base_url,
            default_model=config.model,
            input_cost_per_1m_tokens=config.input_cost_per_1m_tokens,
            output_cost_per_1m_tokens=config.output_cost_per_1m_tokens,
            is_active=True,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
    else:
        provider.base_url = config.base_url
        provider.input_cost_per_1m_tokens = config.input_cost_per_1m_tokens
        provider.output_cost_per_1m_tokens = config.output_cost_per_1m_tokens
        provider.is_active = True
        provider.updated_at = utcnow()

    session.add(provider)
    session.commit()
    session.refresh(provider)
    return provider


def ensure_learning_foundation(session: Session) -> None:
    profile = ensure_default_profile(session)
    seed_syllabus(session, profile, reason="startup")
