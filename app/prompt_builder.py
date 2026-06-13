from __future__ import annotations

from dataclasses import dataclass

from .models import PromptTemplate, UserProfile


OUTPUT_FORMAT = """
Return exactly these sections:
1. Decision
2. Prerequisites
3. Shortest useful path
4. One practical exercise
5. One verification question
6. What to ignore
7. Next step
""".strip()


DEFAULT_TEMPLATE_DEFINITIONS = [
    {
        "slug": "teach",
        "name": "Teach",
        "description": "Learn a topic through the shortest practical explanation.",
        "instruction_text": (
            "Teach the topic using the shortest useful path. Start with prerequisites "
            "only if they are missing. Prefer practical examples over theory."
        ),
        "next_step": "Study the answer, complete the exercise, then answer the verification question.",
        "sort_order": 10,
    },
    {
        "slug": "plan",
        "name": "Plan",
        "description": "Create a minimal learning path for a topic.",
        "instruction_text": (
            "Create a minimal learning plan. Focus on the best sequence, the smallest "
            "necessary prerequisite set, and the fastest path to a working result."
        ),
        "next_step": "Review the minimal plan, then expand only the first step when needed.",
        "sort_order": 20,
    },
    {
        "slug": "verify",
        "name": "Verify",
        "description": "Check whether the learner understands the topic.",
        "instruction_text": (
            "Test whether the learner really understands the topic. Ask targeted "
            "questions, include one small practical task, and flag gaps clearly."
        ),
        "next_step": "Answer the verification question without notes, then compare against the model's critique.",
        "sort_order": 30,
    },
    {
        "slug": "summarize",
        "name": "Summarize",
        "description": "Compress a topic into a reusable cheat sheet.",
        "instruction_text": (
            "Compress the topic into a compact cheat sheet. Keep only the most reusable "
            "concepts, commands, pitfalls, and next steps."
        ),
        "next_step": "Save the useful parts as notes, then schedule a quick review.",
        "sort_order": 40,
    },
    {
        "slug": "practice",
        "name": "Practice",
        "description": "Generate a small practical exercise for the current level.",
        "instruction_text": (
            "Create a hands-on practice task that proves the learner can use the topic. "
            "Keep the task small, include success criteria, and avoid unnecessary setup."
        ),
        "next_step": "Complete the exercise, then paste your result back for review.",
        "sort_order": 50,
    },
    {
        "slug": "debug",
        "name": "Debug",
        "description": "Learn through troubleshooting and common failure modes.",
        "instruction_text": (
            "Teach the topic through debugging. Focus on common mistakes, symptoms, "
            "root causes, and a minimal troubleshooting checklist."
        ),
        "next_step": "Use the checklist on a real or sample failure, then record what fixed it.",
        "sort_order": 60,
    },
]


QUALITY_RULES = {
    "token_saver": (
        "Optimize for minimal tokens. Be concise, avoid repetition, and keep the answer tightly scoped."
    ),
    "balanced": (
        "Optimize for a strong balance of brevity and completeness. Avoid fluff."
    ),
    "quality_first": (
        "Prioritize correctness and completeness, but still avoid unnecessary verbosity."
    ),
}


@dataclass
class PromptPackage:
    prompt: str
    next_step: str
    title: str
    system_prompt: str
    template_slug: str
    template_name: str


def build_prompt(
    profile: UserProfile,
    template: PromptTemplate,
    topic: str,
    goal_override: str,
    current_level: str,
    time_budget: str,
    extra_context: str,
) -> PromptPackage:
    optimization_mode = (profile.optimization_mode or "balanced").strip().lower()
    quality_rule = QUALITY_RULES.get(optimization_mode, QUALITY_RULES["balanced"])

    primary_goal = goal_override.strip() or profile.primary_goal.strip() or "Learn efficiently with maximum practical return."
    level = current_level.strip() or profile.current_level.strip() or "Not specified"
    time_budget = time_budget.strip() or "Not specified"
    preferences = profile.learning_preferences.strip() or "Not specified"
    extra_context = extra_context.strip() or "None"
    output_format = template.output_format.strip() or OUTPUT_FORMAT

    system_prompt = (
        "You are a concise, high-signal AI tutor and curriculum designer. "
        "Answer with practical teaching, strong accuracy, and no fluff."
    )
    title = f"{template.name}: {topic.strip() or 'Untitled topic'}"

    prompt = f"""
Mission:
Help the learner master the topic with the shortest useful path and the highest practical return.

User goal:
{primary_goal}

Topic:
{topic.strip() or "Not specified"}

Current level:
{level}

Time budget:
{time_budget}

Learning preferences:
{preferences}

Learning mode:
{template.name}

Optimization mode:
{optimization_mode}

Core rules:
- {template.instruction_text.strip()}
- {quality_rule}
- Prefer current stable documentation and established best practices.
- If a method is outdated, say so clearly.
- If something depends on version or environment, state that dependency.
- If the topic is not worth learning now, say so directly and explain why.
- If prerequisites are missing, list only the missing ones.
- Do not give a full course unless explicitly necessary.
- Use practical examples, not abstract explanation.
- Keep the answer focused on the learner's immediate next step.

Extra context:
{extra_context}

Required output format:
{output_format}

Answer in a concise but complete way.
""".strip()

    return PromptPackage(
        prompt=prompt,
        next_step=template.next_step,
        title=title,
        system_prompt=system_prompt,
        template_slug=template.slug,
        template_name=template.name,
    )
