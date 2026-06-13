from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .learning import CATEGORIES, FRESHNESS_LEVELS, STATUSES


RECOMMENDATION_REQUIRED_FIELDS = {
    "next_topic",
    "next_subtopic",
    "decision",
    "why_this_now",
    "why_not_other_options",
    "prerequisites_missing",
    "roi_score",
    "effort_score",
    "urgency_score",
    "confidence",
    "alternatives",
    "recommended_depth",
    "suggested_next_steps",
    "source_basis",
    "freshness_note",
    "freshness_level",
}

SYLLABUS_ITEM_REQUIRED_FIELDS = {
    "title",
    "subtopic",
    "status",
    "category",
    "source_basis",
    "freshness_note",
    "freshness_level",
    "confidence",
    "why_this_now",
    "prerequisites",
    "effort_score",
    "roi_score",
    "urgency_score",
}

VALID_DECISIONS = {"learn_now", "defer", "skip"}


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]


def load_json_object(raw_output: str | dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    if isinstance(raw_output, dict):
        return raw_output, []
    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        return None, [f"Invalid JSON: {exc}"]
    if not isinstance(parsed, dict):
        return None, ["Output must be a JSON object."]
    return parsed, []


def validate_recommendation_output(raw_output: str | dict[str, Any]) -> ValidationResult:
    payload, errors = load_json_object(raw_output)
    if payload is None:
        return ValidationResult(valid=False, errors=errors)

    missing = sorted(RECOMMENDATION_REQUIRED_FIELDS - set(payload))
    errors.extend(f"Missing field: {field}" for field in missing)

    if payload.get("decision") not in VALID_DECISIONS:
        errors.append("decision must be learn_now, defer, or skip.")
    if payload.get("freshness_level") not in FRESHNESS_LEVELS:
        errors.append("freshness_level is invalid.")
    if not payload.get("source_basis"):
        errors.append("source_basis is required and cannot be empty.")
    if not payload.get("freshness_note"):
        errors.append("freshness_note is required and cannot be empty.")

    confidence = payload.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        errors.append("confidence must be a number between 0 and 1.")

    return ValidationResult(valid=not errors, errors=errors)


def validate_syllabus_output(raw_output: str | dict[str, Any]) -> ValidationResult:
    payload, errors = load_json_object(raw_output)
    if payload is None:
        return ValidationResult(valid=False, errors=errors)

    modules = payload.get("modules")
    if not isinstance(modules, list) or not modules:
        errors.append("modules must be a non-empty list.")
        return ValidationResult(valid=False, errors=errors)

    for module_index, module in enumerate(modules):
        if not isinstance(module, dict):
            errors.append(f"module {module_index} must be an object.")
            continue
        items = module.get("items")
        if not isinstance(items, list) or not items:
            errors.append(f"module {module_index} must contain items.")
            continue
        for item_index, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"module {module_index} item {item_index} must be an object.")
                continue
            missing = sorted(SYLLABUS_ITEM_REQUIRED_FIELDS - set(item))
            errors.extend(
                f"module {module_index} item {item_index} missing field: {field}"
                for field in missing
            )
            if item.get("status") not in STATUSES:
                errors.append(f"module {module_index} item {item_index} has invalid status.")
            if item.get("category") not in CATEGORIES:
                errors.append(f"module {module_index} item {item_index} has invalid category.")
            if item.get("freshness_level") not in FRESHNESS_LEVELS:
                errors.append(f"module {module_index} item {item_index} has invalid freshness_level.")
            if not item.get("source_basis"):
                errors.append(f"module {module_index} item {item_index} needs source_basis.")
            if not item.get("freshness_note"):
                errors.append(f"module {module_index} item {item_index} needs freshness_note.")

    return ValidationResult(valid=not errors, errors=errors)


def build_repair_prompt(raw_output: str, errors: list[str]) -> str:
    return f"""
Repair the following model output so it is valid JSON and satisfies the required schema.
Do not add unsupported evidence. If evidence is missing, set freshness_level to "unknown",
source_basis to "No current source supplied", and confidence to 0.35 or lower.

Validation errors:
{json.dumps(errors, indent=2)}

Raw output:
{raw_output}
""".strip()
