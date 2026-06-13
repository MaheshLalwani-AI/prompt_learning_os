from __future__ import annotations

import json
import os

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from .bootstrap import (
    ensure_default_profile,
    ensure_learning_foundation,
    ensure_model_provider,
    ensure_prompt_templates,
    get_template_by_slug,
    get_templates,
)
from .db import engine, get_session, init_db
from .learning import (
    add_evidence_source,
    build_syllabus_version,
    create_daily_plan,
    decide_next_topic,
    grouped_syllabus,
    loads_list,
    progress_to_dict,
    recommendation_history_to_dict,
    recommendation_to_dict,
    record_feedback,
    seed_syllabus,
    syllabus_to_dict,
    syllabus_to_markdown,
    update_mastery,
)
from .llm import estimate_cost_usd, estimate_tokens, get_llm_config, stream_chat_completion
from .models import (
    CostRecord,
    EvidenceSource,
    LearningRoadmap,
    LearningSession,
    MasteryRecord,
    PromptRun,
    RecommendationRun,
    SyllabusItem,
    TopicFeedback,
    UserProfile,
    utcnow,
)
from .prompt_builder import build_prompt

APP_TITLE = os.getenv("APP_TITLE", "Prompt Learning OS")

app = FastAPI(title=APP_TITLE)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    with Session(engine) as session:
        ensure_default_profile(session)
        ensure_prompt_templates(session)
        ensure_model_provider(session, get_llm_config())
        ensure_learning_foundation(session)


def get_profile(session: Session) -> UserProfile:
    return ensure_default_profile(session)


@app.get("/", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(get_session)):
    profile = get_profile(session)
    roadmap = seed_syllabus(session, profile, reason="index")
    templates_list = get_templates(session)
    runs = session.exec(
        select(PromptRun).order_by(PromptRun.created_at.desc()).limit(12)
    ).all()
    latest_recommendation = session.exec(
        select(RecommendationRun).order_by(RecommendationRun.created_at.desc())
    ).first()
    deferred_items = session.exec(
        select(SyllabusItem).where(SyllabusItem.status == "deferred").order_by(SyllabusItem.title)
    ).all()
    skipped_items = session.exec(
        select(SyllabusItem).where(SyllabusItem.status == "skip_for_now").order_by(SyllabusItem.title)
    ).all()
    evidence_sources = session.exec(
        select(EvidenceSource).order_by(EvidenceSource.captured_at.desc()).limit(6)
    ).all()
    feedback_count = len(session.exec(select(TopicFeedback)).all())
    mastery_count = len(
        session.exec(select(MasteryRecord).where(MasteryRecord.confidence >= 0.8)).all()
    )
    cost_records = session.exec(select(CostRecord)).all()
    total_cost = sum(record.estimated_cost_usd for record in cost_records)
    total_input_tokens = sum(record.input_tokens for record in cost_records)
    total_output_tokens = sum(record.output_tokens for record in cost_records)
    llm_config = get_llm_config()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "profile": profile,
            "roadmap": roadmap,
            "syllabus_groups": grouped_syllabus(session, roadmap.id),
            "latest_recommendation": latest_recommendation,
            "latest_recommendation_steps": loads_list(
                latest_recommendation.suggested_next_steps_json
            )
            if latest_recommendation
            else [],
            "latest_recommendation_alternatives": loads_list(
                latest_recommendation.alternatives_json
            )
            if latest_recommendation
            else [],
            "deferred_items": deferred_items,
            "skipped_items": skipped_items,
            "evidence_sources": evidence_sources,
            "feedback_count": feedback_count,
            "mastery_count": mastery_count,
            "prompt_templates": templates_list,
            "runs": runs,
            "llm_config": llm_config,
            "llm_enabled": llm_config.enabled,
            "cost_total": total_cost,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "api_call_count": len(cost_records),
        },
    )


@app.post("/profile", response_class=HTMLResponse)
def update_profile(
    request: Request,
    primary_goal: str = Form(""),
    current_level: str = Form(""),
    learning_preferences: str = Form(""),
    optimization_mode: str = Form("balanced"),
    default_mode: str = Form("teach"),
    session: Session = Depends(get_session),
):
    profile = get_profile(session)
    profile.primary_goal = primary_goal.strip()
    profile.current_level = current_level.strip()
    profile.learning_preferences = learning_preferences.strip()
    profile.optimization_mode = optimization_mode.strip()
    profile.default_mode = default_mode.strip()
    profile.updated_at = utcnow()
    session.add(profile)
    session.commit()
    session.refresh(profile)

    return templates.TemplateResponse(
        request=request,
        name="partials/profile_saved.html",
        context={"profile": profile},
    )


@app.post("/generate", response_class=HTMLResponse)
def generate_prompt(
    request: Request,
    topic: str = Form(...),
    mode: str = Form("teach"),
    goal_override: str = Form(""),
    current_level: str = Form(""),
    time_budget: str = Form(""),
    extra_context: str = Form(""),
    session: Session = Depends(get_session),
):
    profile = get_profile(session)
    template = get_template_by_slug(session, mode)
    config = get_llm_config()
    provider = ensure_model_provider(session, config)
    package = build_prompt(
        profile=profile,
        template=template,
        topic=topic,
        goal_override=goal_override,
        current_level=current_level,
        time_budget=time_budget,
        extra_context=extra_context,
    )
    input_tokens = estimate_tokens(package.system_prompt) + estimate_tokens(package.prompt)
    learning_session = LearningSession(
        topic=topic.strip(),
        goal=goal_override.strip() or profile.primary_goal.strip(),
        current_level=current_level.strip() or profile.current_level.strip(),
        mode=template.slug,
        status="prompt_created",
        updated_at=utcnow(),
    )
    session.add(learning_session)
    session.flush()

    run = PromptRun(
        learning_session_id=learning_session.id,
        prompt_template_id=template.id,
        provider_id=provider.id,
        topic=topic.strip(),
        goal=goal_override.strip(),
        current_level=current_level.strip(),
        mode=template.slug,
        time_budget=time_budget.strip(),
        extra_context=extra_context.strip(),
        system_prompt=package.system_prompt,
        prompt_text=package.prompt,
        next_step=package.next_step,
        provider_name=config.provider_name,
        model_name=config.model,
        routing_reason=config.routing_reason,
        input_token_estimate=input_tokens,
        response_status="prompt_created",
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    return templates.TemplateResponse(
        request=request,
        name="partials/prompt_result.html",
        context={
            "run": run,
            "package": package,
            "template": template,
            "llm_enabled": get_llm_config().enabled,
        },
    )


@app.post("/recommendations/next", response_class=HTMLResponse)
def recommend_next(request: Request, session: Session = Depends(get_session)):
    profile = get_profile(session)
    run = decide_next_topic(session, profile)
    return templates.TemplateResponse(
        request=request,
        name="partials/recommendation_result.html",
        context={
            "recommendation": run,
            "suggested_steps": loads_list(run.suggested_next_steps_json),
            "alternatives": loads_list(run.alternatives_json),
        },
    )


@app.post("/syllabus/generate", response_class=HTMLResponse)
def generate_syllabus(
    request: Request,
    reason: str = Form("manual update"),
    session: Session = Depends(get_session),
):
    profile = get_profile(session)
    roadmap = seed_syllabus(session, profile, reason=reason)
    version = build_syllabus_version(session, profile, reason=reason)
    return templates.TemplateResponse(
        request=request,
        name="partials/syllabus.html",
        context={
            "roadmap": roadmap,
            "roadmap_version": version,
            "syllabus_groups": grouped_syllabus(session, roadmap.id),
        },
    )


@app.post("/daily-plan", response_class=HTMLResponse)
def daily_plan(
    request: Request,
    time_budget: str = Form("30 minutes"),
    session: Session = Depends(get_session),
):
    profile = get_profile(session)
    plan = create_daily_plan(session, profile, time_budget=time_budget)
    return templates.TemplateResponse(
        request=request,
        name="partials/daily_plan.html",
        context={"daily_plan": plan},
    )


@app.post("/evidence", response_class=HTMLResponse)
def add_evidence(
    request: Request,
    source_title: str = Form(...),
    related_topic: str = Form(...),
    source_type: str = Form("user_note"),
    freshness_level: str = Form("unknown"),
    summary: str = Form(""),
    url: str = Form(""),
    manual_note: str = Form(""),
    reliability_score: float = Form(0.7),
    session: Session = Depends(get_session),
):
    source = add_evidence_source(
        session,
        source_title=source_title,
        related_topic=related_topic,
        source_type=source_type,
        freshness_level=freshness_level,
        summary=summary,
        url=url,
        manual_note=manual_note,
        reliability_score=reliability_score,
    )
    return templates.TemplateResponse(
        request=request,
        name="partials/evidence_saved.html",
        context={"source": source},
    )


@app.post("/feedback", response_class=HTMLResponse)
def submit_feedback(
    request: Request,
    topic_title: str = Form(...),
    action: str = Form(...),
    syllabus_item_id: int | None = Form(None),
    note: str = Form(""),
    session: Session = Depends(get_session),
):
    feedback = record_feedback(
        session,
        topic_title=topic_title,
        action=action,
        syllabus_item_id=syllabus_item_id,
        note=note,
    )
    return templates.TemplateResponse(
        request=request,
        name="partials/feedback_saved.html",
        context={"feedback": feedback},
    )


@app.post("/mastery", response_class=HTMLResponse)
def submit_mastery(
    request: Request,
    topic_title: str = Form(...),
    can_explain: bool = Form(False),
    can_build: bool = Form(False),
    can_debug: bool = Form(False),
    can_apply: bool = Form(False),
    evidence_note: str = Form(""),
    confidence: float = Form(0.5),
    session: Session = Depends(get_session),
):
    try:
        record = update_mastery(
            session,
            topic_title=topic_title,
            can_explain=can_explain,
            can_build=can_build,
            can_debug=can_debug,
            can_apply=can_apply,
            evidence_note=evidence_note,
            confidence=confidence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return templates.TemplateResponse(
        request=request,
        name="partials/mastery_saved.html",
        context={"mastery": record},
    )


@app.get("/exports/syllabus.json")
def export_syllabus_json(session: Session = Depends(get_session)):
    profile = get_profile(session)
    roadmap = seed_syllabus(session, profile, reason="export")
    return JSONResponse(syllabus_to_dict(session, roadmap))


@app.get("/exports/syllabus.md", response_class=PlainTextResponse)
def export_syllabus_markdown(session: Session = Depends(get_session)):
    profile = get_profile(session)
    roadmap = seed_syllabus(session, profile, reason="export")
    return PlainTextResponse(syllabus_to_markdown(session, roadmap), media_type="text/markdown")


@app.get("/exports/recommendations.json")
def export_recommendations_json(session: Session = Depends(get_session)):
    return JSONResponse({"recommendations": recommendation_history_to_dict(session)})


@app.get("/exports/progress.json")
def export_progress_json(session: Session = Depends(get_session)):
    return JSONResponse(progress_to_dict(session))


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def run_detail(request: Request, run_id: int, session: Session = Depends(get_session)):
    run = session.get(PromptRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Prompt run not found")
    return templates.TemplateResponse(
        request=request,
        name="run_detail.html",
        context={
            "run": run,
            "llm_enabled": get_llm_config().enabled,
        },
    )


def sse_text(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


def sse_json(event: str, data: str) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.get("/runs/{run_id}/stream")
async def stream_run(run_id: int):
    with Session(engine) as session:
        run = session.get(PromptRun, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Prompt run not found")
        prompt_text = run.prompt_text
        system_prompt = run.system_prompt or (
            "You are a concise, high-signal tutor. "
            "Answer with practical teaching, strong accuracy, and no fluff."
        )
        learning_session_id = run.learning_session_id

    config = get_llm_config()

    async def event_stream():
        if not config.enabled:
            message = (
                "API is not configured. Use the optimized prompt manually in ChatGPT, Claude, or DeepSeek."
            )
            with Session(engine) as session:
                stored = session.get(PromptRun, run_id)
                if stored is not None:
                    stored.response_status = "not_configured"
                    session.add(stored)
                    session.commit()
            yield sse_text("status", message)
            yield sse_json("done", {})
            return

        full_response: list[str] = []
        yield sse_text("status", "Streaming response...")
        try:
            async for token in stream_chat_completion(prompt_text, system_prompt, config):
                full_response.append(token)
                yield sse_json("token", token)
        except Exception as exc:
            with Session(engine) as session:
                stored = session.get(PromptRun, run_id)
                if stored is not None:
                    stored.response_status = "error"
                    session.add(stored)
                    session.commit()
            yield sse_text("error", str(exc).replace(chr(10), " "))
            return

        response_text = "".join(full_response)
        input_tokens = estimate_tokens(system_prompt) + estimate_tokens(prompt_text)
        output_tokens = estimate_tokens(response_text)
        estimated_cost = estimate_cost_usd(input_tokens, output_tokens, config)

        with Session(engine) as session:
            provider = ensure_model_provider(session, config)
            stored = session.get(PromptRun, run_id)
            if stored is not None:
                stored.llm_response = response_text
                stored.provider_id = provider.id
                stored.provider_name = config.provider_name
                stored.model_name = config.model
                stored.routing_reason = config.routing_reason
                stored.input_token_estimate = input_tokens
                stored.output_token_estimate = output_tokens
                stored.estimated_cost_usd = estimated_cost
                stored.response_status = "completed"
                session.add(stored)

            if learning_session_id is not None:
                learning_session = session.get(LearningSession, learning_session_id)
                if learning_session is not None:
                    learning_session.status = "answered"
                    learning_session.updated_at = utcnow()
                    session.add(learning_session)

            session.add(
                CostRecord(
                    prompt_run_id=run_id,
                    learning_session_id=learning_session_id,
                    provider_id=provider.id,
                    provider_name=config.provider_name,
                    model_name=config.model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost_usd=estimated_cost,
                )
            )
            session.commit()

        yield sse_json("done", {})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
