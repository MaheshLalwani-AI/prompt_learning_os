from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from .models import (
    EvidenceSource,
    LearnerState,
    LearningRoadmap,
    MasteryRecord,
    RecommendationOption,
    RecommendationRun,
    RoadmapVersion,
    SyllabusItem,
    SyllabusModule,
    TopicFeedback,
    UserProfile,
    utcnow,
)


STATUSES = {
    "learn_next",
    "recommended_soon",
    "later",
    "deferred",
    "skip_for_now",
    "mastered",
}
CATEGORIES = {"stable_core", "adaptive_current", "experimental", "skip_for_now"}
FRESHNESS_LEVELS = {
    "verified_current",
    "probably_stable",
    "needs_checking",
    "stale_risk",
    "unknown",
}
FEEDBACK_ACTIONS = {
    "learned",
    "too_early",
    "not_useful",
    "skip",
    "defer",
    "already_know",
    "interested",
}

FRESHNESS_CONFIDENCE_CAP = {
    "verified_current": 0.95,
    "probably_stable": 0.78,
    "needs_checking": 0.62,
    "stale_risk": 0.42,
    "unknown": 0.45,
}
FRESHNESS_SCORE_BONUS = {
    "verified_current": 3.0,
    "probably_stable": 1.5,
    "needs_checking": -1.0,
    "stale_risk": -4.0,
    "unknown": -2.5,
}
CATEGORY_BONUS = {
    "stable_core": 2.0,
    "adaptive_current": 0.5,
    "experimental": -2.0,
    "skip_for_now": -8.0,
}
FEEDBACK_BONUS = {
    "interested": 2.0,
    "not_useful": -4.0,
    "too_early": -3.0,
    "learned": -2.0,
    "skip": -12.0,
    "defer": -8.0,
    "already_know": -20.0,
}


CURRICULUM_SEED = [
    {
        "title": "Automation Foundations",
        "domain": "foundation",
        "summary": "Core software skills needed before API and AI workflow work.",
        "items": [
            {
                "title": "Python Automation Basics",
                "subtopic": "scripts, functions, files, environment variables",
                "prerequisites": [],
                "roi": 9,
                "effort": 3,
                "urgency": 9,
                "why": "It is the lowest-friction base for API automation, local tooling, and learning scripts.",
            },
            {
                "title": "HTTP APIs and JSON",
                "subtopic": "requests, responses, auth headers, payloads",
                "prerequisites": ["Python Automation Basics"],
                "roi": 9,
                "effort": 4,
                "urgency": 9,
                "why": "Most AI automation work depends on calling APIs and handling JSON reliably.",
            },
            {
                "title": "FastAPI Foundations",
                "subtopic": "routes, forms, responses, templates, dependency injection",
                "prerequisites": ["HTTP APIs and JSON"],
                "roi": 8,
                "effort": 5,
                "urgency": 8,
                "why": "This project uses FastAPI, and building with it creates immediate portfolio value.",
            },
            {
                "title": "SQLite and SQLModel",
                "subtopic": "schemas, sessions, persistence, migrations",
                "prerequisites": ["Python Automation Basics"],
                "roi": 8,
                "effort": 4,
                "urgency": 8,
                "why": "Local-first storage is required for memory, progress, cost, and syllabus tracking.",
            },
        ],
    },
    {
        "title": "AI Workflow Core",
        "domain": "ai_workflow",
        "summary": "The practical layer that connects prompts, models, routing, and app behavior.",
        "items": [
            {
                "title": "Prompt Design for Learning Workflows",
                "subtopic": "roles, output contracts, evaluation prompts",
                "prerequisites": ["Python Automation Basics"],
                "roi": 8,
                "effort": 3,
                "urgency": 8,
                "why": "The app depends on reliable prompts that produce structured learning outputs.",
            },
            {
                "title": "LLM Provider APIs",
                "subtopic": "OpenAI-compatible chat, streaming, errors, model config",
                "prerequisites": ["HTTP APIs and JSON"],
                "roi": 9,
                "effort": 5,
                "urgency": 9,
                "category": "adaptive_current",
                "freshness_level": "needs_checking",
                "why": "Provider APIs change over time, but API literacy is essential for AI automation.",
            },
            {
                "title": "Model Routing and Cost Tracking",
                "subtopic": "cheap defaults, escalation, token estimates, budget signals",
                "prerequisites": ["LLM Provider APIs", "SQLite and SQLModel"],
                "roi": 8,
                "effort": 5,
                "urgency": 8,
                "why": "The project goal is low-cost AI learning, so routing and cost visibility matter early.",
            },
            {
                "title": "SSE Streaming Interfaces",
                "subtopic": "server-sent events, incremental UI updates, persistence",
                "prerequisites": ["FastAPI Foundations"],
                "roi": 7,
                "effort": 4,
                "urgency": 7,
                "why": "Streaming improves tutor responsiveness without adding a heavy frontend framework.",
            },
        ],
    },
    {
        "title": "Automation Tools and Orchestration",
        "domain": "automation",
        "summary": "Useful current tools and workflow patterns, gated by freshness evidence.",
        "items": [
            {
                "title": "MCP Fundamentals",
                "subtopic": "tool context, connectors, server/client responsibilities",
                "prerequisites": ["LLM Provider APIs"],
                "roi": 8,
                "effort": 5,
                "urgency": 7,
                "category": "adaptive_current",
                "freshness_level": "needs_checking",
                "why": "It may be high-leverage for tool-using AI systems, but it needs current source evidence.",
            },
            {
                "title": "LangGraph Workflow Basics",
                "subtopic": "state graphs, nodes, edges, durable workflows",
                "prerequisites": ["Python Automation Basics", "LLM Provider APIs"],
                "roi": 7,
                "effort": 6,
                "urgency": 6,
                "category": "adaptive_current",
                "freshness_level": "needs_checking",
                "why": "Graph workflows can help with multi-step agents, but should come after provider API basics.",
            },
            {
                "title": "n8n Automation Patterns",
                "subtopic": "webhooks, API actions, human review, handoff patterns",
                "prerequisites": ["HTTP APIs and JSON"],
                "roi": 7,
                "effort": 4,
                "urgency": 6,
                "category": "adaptive_current",
                "freshness_level": "needs_checking",
                "why": "It is useful for practical automation delivery when validated against current docs.",
            },
        ],
    },
    {
        "title": "Advanced and Deferred Topics",
        "domain": "advanced",
        "summary": "Useful later, risky, or low-return topics that should not block the core path.",
        "items": [
            {
                "title": "Multi-Agent Workflow Design",
                "subtopic": "coordination, handoffs, evaluation loops",
                "prerequisites": ["Model Routing and Cost Tracking", "LangGraph Workflow Basics"],
                "roi": 6,
                "effort": 8,
                "urgency": 4,
                "category": "experimental",
                "freshness_level": "needs_checking",
                "why": "It can be powerful later, but it is easy to overbuild before core workflows are solid.",
            },
            {
                "title": "Local GPU Fine-Tuning",
                "subtopic": "local training, datasets, GPU workflows",
                "prerequisites": ["Python Automation Basics"],
                "roi": 3,
                "effort": 10,
                "urgency": 2,
                "category": "skip_for_now",
                "status": "skip_for_now",
                "freshness_level": "stale_risk",
                "why": "It conflicts with the project goal of cloud API learning without local GPU requirements.",
            },
        ],
    },
]


@dataclass
class ScoredItem:
    item: SyllabusItem
    score: float
    decision: str
    prerequisites_missing: list[str]
    confidence: float
    source_basis: str
    freshness_note: str
    freshness_level: str
    why: str


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True)


def loads_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [str(item) for item in data]
    return []


def ensure_learner_state(session: Session) -> LearnerState:
    state = session.get(LearnerState, 1)
    if state is None:
        state = LearnerState(id=1, updated_at=utcnow())
        session.add(state)
        session.commit()
        session.refresh(state)
    return state


def ensure_roadmap(session: Session, profile: UserProfile) -> LearningRoadmap:
    roadmap = session.exec(
        select(LearningRoadmap)
        .where(LearningRoadmap.status == "active")
        .order_by(LearningRoadmap.id)
    ).first()
    if roadmap is None:
        roadmap = LearningRoadmap(
            title="AI Automation Learning Roadmap",
            goal=profile.primary_goal,
            status="active",
            current_version=1,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        session.add(roadmap)
        session.commit()
        session.refresh(roadmap)
    return roadmap


def create_roadmap_version(
    session: Session,
    roadmap: LearningRoadmap,
    reason: str,
    summary: str,
) -> RoadmapVersion:
    previous = session.exec(
        select(RoadmapVersion)
        .where(RoadmapVersion.roadmap_id == roadmap.id)
        .order_by(RoadmapVersion.version_number.desc())
    ).first()
    version_number = 1 if previous is None else previous.version_number + 1
    version = RoadmapVersion(
        roadmap_id=roadmap.id or 0,
        version_number=version_number,
        summary=summary,
        reason=reason,
        previous_version_id=previous.id if previous else None,
        created_at=utcnow(),
    )
    roadmap.current_version = version_number
    roadmap.updated_at = utcnow()
    session.add(roadmap)
    session.add(version)
    session.commit()
    session.refresh(version)
    return version


def seed_syllabus(session: Session, profile: UserProfile, reason: str = "initial seed") -> LearningRoadmap:
    ensure_learner_state(session)
    roadmap = ensure_roadmap(session, profile)
    existing = session.exec(select(SyllabusItem).where(SyllabusItem.roadmap_id == roadmap.id)).first()
    if existing is not None:
        return roadmap

    for module_index, module_definition in enumerate(CURRICULUM_SEED, start=1):
        module = SyllabusModule(
            roadmap_id=roadmap.id or 0,
            title=module_definition["title"],
            domain=module_definition["domain"],
            summary=module_definition["summary"],
            sort_order=module_index * 10,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        session.add(module)
        session.flush()
        for item_index, item_definition in enumerate(module_definition["items"], start=1):
            category = item_definition.get("category", "stable_core")
            freshness_level = item_definition.get("freshness_level", "probably_stable")
            source_basis = (
                "Built-in curriculum seed. Add evidence sources to raise freshness confidence."
            )
            freshness_note = (
                "Stable foundation; current implementation details should still be checked."
                if category == "stable_core"
                else "Current or fast-moving topic; add recent source evidence before trusting high confidence."
            )
            item = SyllabusItem(
                roadmap_id=roadmap.id or 0,
                module_id=module.id or 0,
                title=item_definition["title"],
                subtopic=item_definition["subtopic"],
                status=item_definition.get("status", "later"),
                category=category,
                source_basis=source_basis,
                freshness_note=freshness_note,
                freshness_level=freshness_level,
                freshness_checked_at=None,
                confidence=0.58 if category == "stable_core" else 0.42,
                why_this_now=item_definition["why"],
                prerequisites_json=dumps(item_definition["prerequisites"]),
                effort_score=item_definition["effort"],
                roi_score=item_definition["roi"],
                urgency_score=item_definition["urgency"],
                sort_order=(module_index * 100) + item_index,
                is_active=True,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            session.add(item)

    session.commit()
    create_roadmap_version(
        session,
        roadmap,
        reason=reason,
        summary="Seeded the first structured AI automation syllabus.",
    )
    return roadmap


def latest_roadmap_version(session: Session, roadmap_id: int | None) -> RoadmapVersion | None:
    if roadmap_id is None:
        return None
    return session.exec(
        select(RoadmapVersion)
        .where(RoadmapVersion.roadmap_id == roadmap_id)
        .order_by(RoadmapVersion.version_number.desc())
    ).first()


def get_syllabus_items(session: Session, roadmap_id: int | None = None) -> list[SyllabusItem]:
    statement = select(SyllabusItem).where(SyllabusItem.is_active == True)  # noqa: E712
    if roadmap_id is not None:
        statement = statement.where(SyllabusItem.roadmap_id == roadmap_id)
    return session.exec(statement.order_by(SyllabusItem.sort_order, SyllabusItem.title)).all()


def get_syllabus_modules(session: Session, roadmap_id: int | None = None) -> list[SyllabusModule]:
    statement = select(SyllabusModule)
    if roadmap_id is not None:
        statement = statement.where(SyllabusModule.roadmap_id == roadmap_id)
    return session.exec(statement.order_by(SyllabusModule.sort_order, SyllabusModule.title)).all()


def get_feedback(session: Session) -> list[TopicFeedback]:
    return session.exec(select(TopicFeedback).order_by(TopicFeedback.created_at.desc())).all()


def get_mastered_topics(session: Session) -> set[str]:
    mastered = {
        item.title
        for item in session.exec(select(SyllabusItem).where(SyllabusItem.status == "mastered")).all()
    }
    for record in session.exec(select(MasteryRecord)).all():
        if record.can_explain and record.can_build and record.can_debug and record.can_apply:
            mastered.add(record.topic_title)
    return mastered


def evidence_for_item(evidence_sources: list[EvidenceSource], item: SyllabusItem) -> EvidenceSource | None:
    item_terms = f"{item.title} {item.subtopic}".lower()
    matches = [
        source
        for source in evidence_sources
        if source.related_topic.lower() in item_terms
        or item.title.lower() in source.related_topic.lower()
    ]
    if not matches:
        return None
    return sorted(
        matches,
        key=lambda source: (
            FRESHNESS_CONFIDENCE_CAP.get(source.freshness_level, 0.45),
            source.reliability_score,
            source.captured_at,
        ),
        reverse=True,
    )[0]


def feedback_by_topic(feedback: list[TopicFeedback]) -> dict[str, list[TopicFeedback]]:
    grouped: dict[str, list[TopicFeedback]] = {}
    for entry in feedback:
        grouped.setdefault(entry.topic_title, []).append(entry)
    return grouped


def prerequisite_priority_bonus(item: SyllabusItem, feedback: list[TopicFeedback]) -> float:
    bonus = 0.0
    for entry in feedback:
        if entry.action != "too_early":
            continue
        if item.title == entry.topic_title:
            continue
        bonus += 1.5
    return min(bonus, 4.5)


def score_item(
    item: SyllabusItem,
    mastered_topics: set[str],
    feedback_map: dict[str, list[TopicFeedback]],
    evidence_sources: list[EvidenceSource],
    all_feedback: list[TopicFeedback],
) -> ScoredItem:
    prerequisites = loads_list(item.prerequisites_json)
    prerequisites_missing = [topic for topic in prerequisites if topic not in mastered_topics]
    best_evidence = evidence_for_item(evidence_sources, item)

    source_basis = item.source_basis
    freshness_note = item.freshness_note
    freshness_level = item.freshness_level
    evidence_bonus = 0.0
    if best_evidence is not None:
        freshness_level = best_evidence.freshness_level
        source_basis = best_evidence.url or best_evidence.source_title or best_evidence.manual_note
        freshness_note = best_evidence.summary or "Evidence source supplied by the learner."
        evidence_bonus = max(0.0, best_evidence.reliability_score * 2.0)

    direct_feedback = feedback_map.get(item.title, [])
    feedback_bonus = sum(FEEDBACK_BONUS.get(entry.action, 0.0) for entry in direct_feedback)
    feedback_bonus += prerequisite_priority_bonus(item, all_feedback)

    decision = "learn_now"
    if item.status == "skip_for_now" or item.category == "skip_for_now":
        decision = "skip"
    elif item.status == "deferred":
        decision = "defer"
    elif item.status == "mastered" or item.title in mastered_topics:
        decision = "skip"
    elif prerequisites_missing:
        decision = "defer"

    score = (
        item.roi_score * 1.5
        + item.urgency_score * 1.1
        - item.effort_score * 0.7
        + CATEGORY_BONUS.get(item.category, 0.0)
        + FRESHNESS_SCORE_BONUS.get(freshness_level, -2.5)
        + feedback_bonus
        + evidence_bonus
        - (len(prerequisites_missing) * 7.0)
    )
    if item.category in {"adaptive_current", "experimental"} and best_evidence is None:
        score -= 2.0
    if decision == "skip":
        score -= 20.0
    elif decision == "defer":
        score -= 8.0

    confidence = item.confidence + evidence_bonus / 10 + (score / 100)
    if not source_basis.strip():
        confidence = min(confidence, 0.35)
    cap = FRESHNESS_CONFIDENCE_CAP.get(freshness_level, 0.45)
    if item.category == "adaptive_current" and best_evidence is None:
        cap = min(cap, 0.55)
    if item.category == "experimental" and best_evidence is None:
        cap = min(cap, 0.45)
    confidence = round(max(0.15, min(cap, confidence)), 2)

    if prerequisites_missing:
        why = "Prerequisites are missing: " + ", ".join(prerequisites_missing)
    elif decision == "skip":
        why = "This item is skipped or already mastered for the current roadmap."
    else:
        why = item.why_this_now

    return ScoredItem(
        item=item,
        score=round(score, 2),
        decision=decision,
        prerequisites_missing=prerequisites_missing,
        confidence=confidence,
        source_basis=source_basis,
        freshness_note=freshness_note,
        freshness_level=freshness_level,
        why=why,
    )


def decide_next_topic(session: Session, profile: UserProfile) -> RecommendationRun:
    roadmap = seed_syllabus(session, profile, reason="recommendation run")
    items = get_syllabus_items(session, roadmap.id)
    evidence_sources = session.exec(select(EvidenceSource)).all()
    feedback = get_feedback(session)
    feedback_map = feedback_by_topic(feedback)
    mastered_topics = get_mastered_topics(session)

    scored = [
        score_item(item, mastered_topics, feedback_map, evidence_sources, feedback)
        for item in items
    ]
    learnable = [item for item in scored if item.decision == "learn_now"]
    selected = max(learnable or scored, key=lambda item: item.score)
    alternatives = sorted(
        [item for item in scored if item.item.id != selected.item.id],
        key=lambda item: item.score,
        reverse=True,
    )[:4]

    for item in items:
        if item.status == "learn_next":
            item.status = "recommended_soon"
            item.updated_at = utcnow()
            session.add(item)
    if selected.decision == "learn_now" and selected.item.status not in {"mastered", "skip_for_now"}:
        selected.item.status = "learn_next"
        selected.item.updated_at = utcnow()
        session.add(selected.item)

    run = RecommendationRun(
        user_profile_id=profile.id or 1,
        roadmap_id=roadmap.id,
        next_topic=selected.item.title,
        next_subtopic=selected.item.subtopic,
        decision=selected.decision,
        why_this_now=selected.why,
        why_not_other_options=build_why_not_other_options(alternatives),
        prerequisites_missing_json=dumps(selected.prerequisites_missing),
        roi_score=selected.item.roi_score,
        effort_score=selected.item.effort_score,
        urgency_score=selected.item.urgency_score,
        confidence=selected.confidence,
        alternatives_json=dumps([option.item.title for option in alternatives]),
        recommended_depth=recommended_depth(selected.item),
        suggested_next_steps_json=dumps(suggest_next_steps(selected)),
        source_basis=selected.source_basis,
        freshness_note=selected.freshness_note,
        freshness_level=selected.freshness_level,
        created_at=utcnow(),
    )
    session.add(run)
    session.flush()

    for option in [selected, *alternatives]:
        session.add(
            RecommendationOption(
                recommendation_run_id=run.id or 0,
                syllabus_item_id=option.item.id,
                title=option.item.title,
                subtopic=option.item.subtopic,
                decision=option.decision,
                status=option.item.status,
                score=option.score,
                why=option.why,
                source_basis=option.source_basis,
                freshness_level=option.freshness_level,
                confidence=option.confidence,
            )
        )
    session.commit()
    session.refresh(run)
    return run


def build_why_not_other_options(alternatives: list[ScoredItem]) -> str:
    if not alternatives:
        return "No comparable alternatives are available yet."
    reasons = []
    for option in alternatives[:3]:
        if option.prerequisites_missing:
            reasons.append(f"{option.item.title}: missing prerequisites")
        elif option.decision != "learn_now":
            reasons.append(f"{option.item.title}: {option.decision}")
        else:
            reasons.append(f"{option.item.title}: lower combined ROI/urgency/evidence score")
    return "; ".join(reasons)


def recommended_depth(item: SyllabusItem) -> str:
    if item.category == "stable_core":
        return "working_knowledge"
    if item.category == "adaptive_current":
        return "practical_overview_until_sources_are_verified"
    if item.category == "experimental":
        return "awareness_only"
    return "skip_for_now"


def suggest_next_steps(scored: ScoredItem) -> list[str]:
    if scored.prerequisites_missing:
        return [f"Learn prerequisite first: {scored.prerequisites_missing[0]}"]
    if scored.decision == "skip":
        return ["Keep this out of the current learning plan."]
    return [
        f"Generate a teach prompt for {scored.item.title}.",
        "Complete one small practical exercise.",
        "Record feedback after studying.",
    ]


def add_evidence_source(
    session: Session,
    source_title: str,
    related_topic: str,
    source_type: str,
    freshness_level: str,
    summary: str,
    url: str = "",
    manual_note: str = "",
    reliability_score: float = 0.7,
) -> EvidenceSource:
    source = EvidenceSource(
        source_title=source_title.strip(),
        url=url.strip(),
        manual_note=manual_note.strip(),
        source_type=source_type if source_type in SOURCE_TYPES else "other",
        related_topic=related_topic.strip(),
        captured_at=utcnow(),
        freshness_checked_at=utcnow(),
        freshness_level=freshness_level if freshness_level in FRESHNESS_LEVELS else "unknown",
        summary=summary.strip(),
        reliability_score=max(0.0, min(1.0, reliability_score)),
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


SOURCE_TYPES = {"official_docs", "article", "user_note", "changelog", "repo", "other"}


def record_feedback(
    session: Session,
    topic_title: str,
    action: str,
    syllabus_item_id: int | None = None,
    note: str = "",
) -> TopicFeedback:
    action = action if action in FEEDBACK_ACTIONS else "not_useful"
    item = session.get(SyllabusItem, syllabus_item_id) if syllabus_item_id else None
    if item is None:
        item = session.exec(select(SyllabusItem).where(SyllabusItem.title == topic_title)).first()
    topic = item.title if item else topic_title
    feedback = TopicFeedback(
        syllabus_item_id=item.id if item else None,
        topic_title=topic,
        action=action,
        note=note.strip(),
        created_at=utcnow(),
    )
    session.add(feedback)

    if item is not None:
        if action == "skip":
            item.status = "skip_for_now"
        elif action == "defer":
            item.status = "deferred"
        elif action == "already_know":
            item.status = "mastered"
            ensure_mastery_record(
                session,
                item,
                can_explain=True,
                can_build=True,
                can_debug=True,
                can_apply=True,
                evidence_note="User marked this topic as already known.",
                confidence=1.0,
            )
        elif action == "interested" and item.status == "later":
            item.status = "recommended_soon"
        item.updated_at = utcnow()
        session.add(item)

    session.commit()
    session.refresh(feedback)
    return feedback


def ensure_mastery_record(
    session: Session,
    item: SyllabusItem,
    can_explain: bool,
    can_build: bool,
    can_debug: bool,
    can_apply: bool,
    evidence_note: str,
    confidence: float,
) -> MasteryRecord:
    record = session.exec(
        select(MasteryRecord).where(MasteryRecord.syllabus_item_id == item.id)
    ).first()
    if record is None:
        record = MasteryRecord(
            syllabus_item_id=item.id,
            topic_title=item.title,
            created_at=utcnow(),
        )
    record.can_explain = can_explain
    record.can_build = can_build
    record.can_debug = can_debug
    record.can_apply = can_apply
    record.evidence_note = evidence_note
    record.confidence = max(0.0, min(1.0, confidence))
    record.updated_at = utcnow()
    session.add(record)
    return record


def update_mastery(
    session: Session,
    topic_title: str,
    can_explain: bool,
    can_build: bool,
    can_debug: bool,
    can_apply: bool,
    evidence_note: str,
    confidence: float,
) -> MasteryRecord:
    item = session.exec(select(SyllabusItem).where(SyllabusItem.title == topic_title)).first()
    if item is None:
        raise ValueError(f"Unknown syllabus item: {topic_title}")
    record = ensure_mastery_record(
        session,
        item,
        can_explain=can_explain,
        can_build=can_build,
        can_debug=can_debug,
        can_apply=can_apply,
        evidence_note=evidence_note,
        confidence=confidence,
    )
    if can_explain and can_build and can_debug and can_apply:
        item.status = "mastered"
        item.updated_at = utcnow()
        session.add(item)
    session.commit()
    session.refresh(record)
    return record


def grouped_syllabus(session: Session, roadmap_id: int | None = None) -> list[dict[str, Any]]:
    modules = get_syllabus_modules(session, roadmap_id)
    items = get_syllabus_items(session, roadmap_id)
    items_by_module: dict[int, list[SyllabusItem]] = {}
    for item in items:
        items_by_module.setdefault(item.module_id, []).append(item)

    grouped: list[dict[str, Any]] = []
    for module in modules:
        module_items = items_by_module.get(module.id or 0, [])
        grouped.append(
            {
                "module": module,
                "items": module_items,
            }
        )
    return grouped


def syllabus_to_dict(session: Session, roadmap: LearningRoadmap) -> dict[str, Any]:
    version = latest_roadmap_version(session, roadmap.id)
    return {
        "roadmap": {
            "id": roadmap.id,
            "title": roadmap.title,
            "goal": roadmap.goal,
            "current_version": roadmap.current_version,
            "version_summary": version.summary if version else "",
        },
        "modules": [
            {
                "title": group["module"].title,
                "domain": group["module"].domain,
                "summary": group["module"].summary,
                "items": [
                    {
                        "id": item.id,
                        "title": item.title,
                        "subtopic": item.subtopic,
                        "status": item.status,
                        "category": item.category,
                        "source_basis": item.source_basis,
                        "freshness_note": item.freshness_note,
                        "freshness_level": item.freshness_level,
                        "freshness_checked_at": item.freshness_checked_at.isoformat()
                        if item.freshness_checked_at
                        else None,
                        "confidence": item.confidence,
                        "why_this_now": item.why_this_now,
                        "prerequisites": loads_list(item.prerequisites_json),
                        "effort_score": item.effort_score,
                        "roi_score": item.roi_score,
                        "urgency_score": item.urgency_score,
                    }
                    for item in group["items"]
                ],
            }
            for group in grouped_syllabus(session, roadmap.id)
        ],
    }


def syllabus_to_markdown(session: Session, roadmap: LearningRoadmap) -> str:
    data = syllabus_to_dict(session, roadmap)
    lines = [
        f"# {data['roadmap']['title']}",
        "",
        f"Goal: {data['roadmap']['goal']}",
        f"Version: {data['roadmap']['current_version']}",
        "",
    ]
    for module in data["modules"]:
        lines.append(f"## {module['title']}")
        lines.append(module["summary"])
        lines.append("")
        for item in module["items"]:
            prerequisites = ", ".join(item["prerequisites"]) or "None"
            lines.extend(
                [
                    f"- **{item['title']}** - {item['subtopic']}",
                    f"  - Status: {item['status']} | Category: {item['category']}",
                    f"  - Scores: ROI {item['roi_score']}, effort {item['effort_score']}, urgency {item['urgency_score']}, confidence {item['confidence']}",
                    f"  - Freshness: {item['freshness_level']} - {item['freshness_note']}",
                    f"  - Prerequisites: {prerequisites}",
                    f"  - Why: {item['why_this_now']}",
                ]
            )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def create_daily_plan(session: Session, profile: UserProfile, time_budget: str = "") -> dict[str, Any]:
    latest_run = session.exec(
        select(RecommendationRun).order_by(RecommendationRun.created_at.desc())
    ).first()
    if latest_run is None:
        latest_run = decide_next_topic(session, profile)
    items = get_syllabus_items(session, latest_run.roadmap_id)
    mastered_topics = get_mastered_topics(session)
    primary = next((item for item in items if item.title == latest_run.next_topic), None)
    practice = next(
        (
            item
            for item in items
            if item.status in {"recommended_soon", "later"}
            and item.category != "skip_for_now"
            and not set(loads_list(item.prerequisites_json)) - mastered_topics
        ),
        primary,
    )
    review = next((item for item in items if item.status == "mastered"), None)
    return {
        "time_budget": time_budget.strip() or "30 minutes",
        "primary": {
            "title": primary.title if primary else latest_run.next_topic,
            "subtopic": primary.subtopic if primary else latest_run.next_subtopic,
            "why": latest_run.why_this_now,
        },
        "practice": {
            "title": practice.title if practice else latest_run.next_topic,
            "subtopic": practice.subtopic if practice else latest_run.next_subtopic,
            "why": "Practice reinforces the next eligible roadmap item without adding overload.",
        },
        "review": {
            "title": review.title if review else "No mastered review item yet",
            "subtopic": review.subtopic if review else "",
            "why": "Review is optional until mastery records exist.",
        },
    }


def recommendation_to_dict(run: RecommendationRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "next_topic": run.next_topic,
        "next_subtopic": run.next_subtopic,
        "decision": run.decision,
        "why_this_now": run.why_this_now,
        "why_not_other_options": run.why_not_other_options,
        "prerequisites_missing": loads_list(run.prerequisites_missing_json),
        "roi_score": run.roi_score,
        "effort_score": run.effort_score,
        "urgency_score": run.urgency_score,
        "confidence": run.confidence,
        "alternatives": loads_list(run.alternatives_json),
        "recommended_depth": run.recommended_depth,
        "suggested_next_steps": loads_list(run.suggested_next_steps_json),
        "source_basis": run.source_basis,
        "freshness_note": run.freshness_note,
        "freshness_level": run.freshness_level,
        "created_at": run.created_at.isoformat(),
    }


def recommendation_history_to_dict(session: Session) -> list[dict[str, Any]]:
    runs = session.exec(select(RecommendationRun).order_by(RecommendationRun.created_at.desc())).all()
    return [recommendation_to_dict(run) for run in runs]


def progress_to_dict(session: Session) -> dict[str, Any]:
    feedback = session.exec(select(TopicFeedback).order_by(TopicFeedback.created_at.desc())).all()
    mastery = session.exec(select(MasteryRecord).order_by(MasteryRecord.updated_at.desc())).all()
    return {
        "feedback": [
            {
                "topic_title": item.topic_title,
                "action": item.action,
                "note": item.note,
                "created_at": item.created_at.isoformat(),
            }
            for item in feedback
        ],
        "mastery": [
            {
                "topic_title": item.topic_title,
                "can_explain": item.can_explain,
                "can_build": item.can_build,
                "can_debug": item.can_debug,
                "can_apply": item.can_apply,
                "confidence": item.confidence,
                "evidence_note": item.evidence_note,
                "updated_at": item.updated_at.isoformat(),
            }
            for item in mastery
        ],
    }


def build_syllabus_version(session: Session, profile: UserProfile, reason: str) -> RoadmapVersion:
    roadmap = seed_syllabus(session, profile, reason=reason)
    return create_roadmap_version(
        session,
        roadmap,
        reason=reason,
        summary="Updated syllabus ordering, statuses, feedback, and evidence signals.",
    )
