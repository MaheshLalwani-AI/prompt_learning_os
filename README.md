# Prompt Learning OS

Prompt Learning OS is a local-first FastAPI app for deciding what to learn next, maintaining a personalized AI automation syllabus, and turning that plan into prompt-driven learning sessions.

The app is intentionally small: Python backend, SQLite via SQLModel, HTMX/Jinja templates, and Server-Sent Events for streaming model responses.

## What It Does

- Builds optimized learning prompts from your profile.
- Decides the next best topic and subtopic to study.
- Maintains a full grouped syllabus with roadmap versions.
- Tracks source evidence, freshness, confidence, and reasons for recommendations.
- Accepts feedback such as `too early`, `skip`, `defer`, `interested`, and `already know`.
- Tracks mastery evidence separately from passive reading.
- Produces a compact daily plan.
- Exports syllabus, recommendation history, and progress as JSON or Markdown.

## How Next-Topic Selection Works

The recommendation engine is deterministic and testable before any runtime LLM is connected. It scores syllabus items using:

- learner goal and current profile
- missing prerequisites
- syllabus priority
- ROI, effort, and urgency
- stable-core vs adaptive-current vs experimental category
- source evidence and freshness level
- feedback and mastery records

It returns:

- `next_topic`
- `next_subtopic`
- `decision`: `learn_now`, `defer`, or `skip`
- missing prerequisites
- ROI, effort, urgency, and confidence
- alternatives
- recommended depth
- source basis and freshness note
- suggested next steps

## Full Syllabus

The syllabus is a structured curriculum map, not a flat list. It is grouped into modules such as:

- Automation Foundations
- AI Workflow Core
- Automation Tools and Orchestration
- Advanced and Deferred Topics

Each item includes:

- status: `learn_next`, `recommended_soon`, `later`, `deferred`, `skip_for_now`, `mastered`
- category: `stable_core`, `adaptive_current`, `experimental`, `skip_for_now`
- prerequisites
- ROI, effort, urgency, and confidence
- source basis
- freshness note and freshness level
- reason for inclusion

Every syllabus update creates a roadmap version.

## Evidence And Freshness

Recommendations should not pretend to be current without evidence. Evidence sources can be added from the UI with:

- source title
- URL or manual note
- source type
- related topic
- freshness level
- summary
- reliability score

Freshness levels:

- `verified_current`: current evidence is available
- `probably_stable`: stable foundational topic
- `needs_checking`: likely useful but should be checked against current sources
- `stale_risk`: may be outdated
- `unknown`: no current evidence

Unknown or stale freshness caps confidence. Date-sensitive topics need evidence before they can receive high confidence.

## Feedback Loop

Feedback changes future recommendations:

- `interested`: raises priority slightly
- `too_early`: signals missing prerequisites
- `not_useful`: lowers priority
- `defer`: moves an item to deferred
- `skip`: moves an item to skip-for-now
- `already_know`: marks the item mastered
- `learned`: records learning feedback but does not automatically mark mastery

## Mastery Tracking

The app does not mark a topic complete just because you viewed it. Mastery evidence tracks whether you can:

- explain it
- build with it
- debug it
- apply it

An item becomes mastered when all mastery evidence is recorded or when you explicitly mark it `already_know`.

## Daily Plan

The daily plan returns:

- one primary study item
- one practice item
- one optional review item

It uses the current recommendation, time budget, syllabus status, feedback, and mastery state.

## Runtime Model Selection

Runtime model choice is external and configured through `.env`.

Example:

```env
LLM_PROVIDER_NAME=Generic API
LLM_BASE_URL=https://example.com/v1
LLM_API_KEY=your_key_here
LLM_MODEL=your_model
LLM_TEMPERATURE=0.2
LLM_INPUT_COST_PER_1M_TOKENS=0
LLM_OUTPUT_COST_PER_1M_TOKENS=0
```

The core recommendation and syllabus engine works without an LLM. A configured API is only needed for streaming model answers to generated prompts.

## Exports

Available export routes:

- `/exports/syllabus.json`
- `/exports/syllabus.md`
- `/exports/recommendations.json`
- `/exports/progress.json`

## Example Flow

1. Save profile: goal is “Become an AI Automation Engineer”.
2. Add evidence for a current topic, such as provider API docs.
3. Click “Decide next”.
4. Review the next topic, confidence, source basis, and freshness note.
5. Generate or update the full syllabus.
6. Click “Plan today”.
7. Generate a learning prompt for the selected topic.
8. Record feedback or mastery evidence after studying.

## Run

```bash
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

## Test

```bash
python3 -m unittest
```
