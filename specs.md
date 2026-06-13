# AI-Powered Personal Learning System — Build Specification

## Purpose

Build a personal AI-powered learning system focused on helping me learn AI automation
efficiently through cloud AI APIs without requiring local LLMs or a GPU.

---

## Architecture

**1.** Use a Python-first architecture (FastAPI backend + minimal web UI) to maximize
development speed and minimize frontend complexity. The UI should use HTMX or a
lightweight single-page approach with server-sent events for streaming. Avoid full SPA
frameworks.

**2.** Use an API-only architecture optimized for ultra-low cost through smart model
routing (cheap models by default, stronger models on escalation), token-efficient context
management, prompt caching, response summarization, and selective memory injection —
without significantly degrading learning quality.

**3.** Automate interaction with AI APIs (DeepSeek, OpenAI, Gemini, Claude, etc.) by
sending prompts, collecting responses, and organizing them into structured learning
workflows.

**4.** Use local-first storage (SQLite initially) with clearly defined structured entities:
Sessions, Concepts, Tasks, Evaluations, PromptTemplates, LearningPaths, MemoryRecords,
SkillMaps, CostRecords, and WorkflowChains. These entities must be locked down as a
schema before any other implementation begins.

**5.** Support streaming AI responses via Server-Sent Events for a responsive
conversational experience.

**6.** Support modular feature expansion through a plugin-style provider interface for AI
models, a registry pattern for workflows and study modes, and clearly separated service
layers for memory, routing, evaluation, and session management — so new workflows, AI
providers, and learning systems can be added without major rewrites.

---

## Cost and Token Efficiency

**7.** Prioritize ultra-low-cost learning by defaulting to highly economical models (such
as DeepSeek or smaller variants) and selectively escalating to stronger models only when
task complexity, evaluation depth, or quality thresholds require it.

**8.** Track estimated token usage and API cost per session, per model, and as a
cumulative total. Support configurable daily and monthly budget alerts to prevent
unexpected spend.

---

## Adaptive AI Tutor

**9.** Act as an adaptive AI tutor that explains concepts, generates tasks, evaluates
performance, and dynamically adjusts difficulty, pacing, and focus based on the learner's
weaknesses, goals, and progress over time.

**10.** Support reusable prompt templates and configurable AI workflows for distinct roles:
teacher, interviewer, debugger, architect, reviewer, planner, and evaluator. Each role
should have its own default prompt structure and escalation behavior.

**11.** Support automated prompt chaining where outputs from one AI interaction can be
refined, critiqued, summarized, expanded, or reused automatically. Chains are defined as
structured workflow records with named steps, explicit input/output bindings, and
conditional routing — stored as editable database records, not hardcoded logic.

**12.** Minimize manual work by automating prompt management, context injection, response
organization, and learning session tracking throughout each session.

---

## Memory and Knowledge System

**13.** Maintain persistent learning memory including conversations, explanations,
mistakes, revisions, solved problems, bookmarks, ratings, and progress across all
sessions. Sessions are summarized on close and stored; semantic search is used to inject
only the top-k most relevant memories per new query rather than the full history.

**14.** Maintain organized searchable knowledge using projects, topics, tags, timelines,
skill maps, and contextual memory.

**15.** Support conversational learning sessions with full session persistence and
recovery, so interrupted sessions can be resumed from the exact previous context.

**16.** Maintain a continuously evolving skill map showing relationships between
technologies, concepts, tools, and real-world workflows. The skill map updates
automatically when new concepts are learned, tasks are completed, or evaluations are
scored, and is manually editable by the user.

---

## Learning Structure and Paths

**17.** Use curated learning roadmaps and skill graphs as the foundation for syllabus
generation, while allowing AI to personalize sequencing, pacing, difficulty, and focus
areas dynamically. Learning paths are stored as structured database records generated
once and kept editable — not regenerated from scratch on each session.

**18.** Break complex topics into structured step-by-step learning paths with checkpoints,
revision cycles, practical exercises, and dynamically generated daily study sessions.

**19.** Follow an "implement → learn → test → practice → apply" learning architecture
focused on real execution and long-term skill-building.

**20.** Support customizable learning intensity levels based on available daily time,
energy, and short-term objectives.

**21.** Maintain separate learning modes for: studying, practicing, revising,
interviewing, and real-world project execution.

**22.** Support custom study workflows tailored to specific goals: AI automation
engineering, interview preparation, debugging, revision, project building, and real-world
execution.

---

## Tasks, Exercises, and Evaluation

**23.** Generate hands-on coding tasks, debugging exercises, mini-projects, workflow
challenges, and realistic workplace simulations aligned with the current learning stage.

**24.** Evaluate completed work through code reviews, architecture analysis, debugging
evaluation, mock interviews, technical questioning, and timed problem-solving sessions.

**25.** Track learning progress, interview readiness, weak areas, completed topics,
pending skills, and long-term goals as separate structured records.

**26.** Include spaced-repetition-based revision and forgetting-curve management for
long-term retention optimization, using an SM-2 or equivalent algorithm applied to
concept review scheduling.

---

## Multi-LLM and Comparison

**27.** Support multi-LLM comparison by sending the same prompt to different AI models
(via their APIs) and displaying responses side-by-side. This feature operates exclusively
through API access, not browser automation.

---

## Interview Simulation

**28.** Support text-based interview simulations and evaluations as a first-class study
mode. Voice-based interaction is explicitly deferred as an optional future enhancement.

---

## Project Integration

**29.** Support real project integration initially through manual paste or file upload of
code, notes, documentation, and project files. GitHub and local directory sync are
explicitly scoped as a later phase and should not be built upfront.

---

## Currency and Relevance

**30.** Keep learning material modern and production-oriented by remaining aware of
current technological trends, APIs, tools, and industry practices.

**31.** Periodically audit saved learning paths and recommendations using web-search-
enabled AI models via scheduled background jobs to detect deprecated tools, obsolete
workflows, and outdated practices, and flag them for review.

---

## UI Surface

**32.** The web UI should include distinct views for:
- Active learning session (streaming chat + context panel)
- Knowledge browser (searchable concepts, tags, topics)
- Skill map (visual graph of concepts and relationships)
- Study plan (daily sessions, learning path, checkpoints)
- Session history (past sessions, resumable)
- Prompt template manager (create, edit, assign roles)
- Cost and usage dashboard (per-session, per-model, cumulative, budget alerts)

Prioritize clarity, speed, and function over visual polish.

---

## Export and Portability

**33.** Support export of sessions, notes, concepts, prompt templates, and full learning
history to Markdown and JSON formats for portability, backup, and use in external tools
such as Obsidian.

---

## Recommended Build Order

| Phase | Points | Goal |
|-------|--------|------|
| 1 — Foundation | 4, 5, 6, 7, 8 | Schema, routing, cost tracking, streaming, modularity |
| 2 — Core Tutor | 9, 10, 11, 12, 13, 15 | Adaptive tutor, memory, session loop |
| 3 — Learning Structure | 17, 18, 19, 20, 21, 22 | Paths, modes, daily sessions |
| 4 — Tasks and Eval | 23, 24, 25, 26 | Exercises, evaluation, SRS |
| 5 — Knowledge System | 14, 16, 27, 32 | Skill map, search, multi-LLM, full UI |
| 6 — Advanced | 28, 29, 30, 31, 33 | Interviews, project integration, auditing, export |

---

## Codex Prompt Order

When using Codex to build this system, prompt in this sequence:

1. Generate the SQLite schema for all entities defined in Point 4
2. Generate the FastAPI route map grouped by feature area
3. Generate the AI provider interface and model routing logic (Point 2, Point 7)
4. Generate the prompt template and chaining engine (Points 10, 11)
5. Build the adaptive tutor session loop (Points 9, 12, 13, 15)
6. Build remaining features phase by phase per the build order above
