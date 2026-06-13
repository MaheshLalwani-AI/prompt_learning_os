from __future__ import annotations

import json
import os

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from .bootstrap import (
    ensure_default_profile,
    ensure_model_provider,
    ensure_prompt_templates,
    get_template_by_slug,
    get_templates,
)
from .db import engine, get_session, init_db
from .llm import estimate_cost_usd, estimate_tokens, get_llm_config, stream_chat_completion
from .models import CostRecord, LearningSession, PromptRun, UserProfile, utcnow
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


def get_profile(session: Session) -> UserProfile:
    return ensure_default_profile(session)


@app.get("/", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(get_session)):
    profile = get_profile(session)
    templates_list = get_templates(session)
    runs = session.exec(
        select(PromptRun).order_by(PromptRun.created_at.desc()).limit(12)
    ).all()
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
