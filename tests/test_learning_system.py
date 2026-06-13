from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select

from app.bootstrap import ensure_default_profile
from app.learning import (
    add_evidence_source,
    build_syllabus_version,
    create_daily_plan,
    decide_next_topic,
    get_syllabus_items,
    grouped_syllabus,
    record_feedback,
    score_item,
    seed_syllabus,
    syllabus_to_dict,
    syllabus_to_markdown,
)
from app.models import EvidenceSource, SyllabusItem, TopicFeedback
from app.validation import validate_recommendation_output, validate_syllabus_output


class LearningEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        SQLModel.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.profile = ensure_default_profile(self.session)
        self.roadmap = seed_syllabus(self.session, self.profile, reason="test")

    def tearDown(self) -> None:
        self.session.close()

    def item(self, title: str) -> SyllabusItem:
        item = self.session.exec(select(SyllabusItem).where(SyllabusItem.title == title)).one()
        return item

    def test_next_topic_and_subtopic_selection(self) -> None:
        run = decide_next_topic(self.session, self.profile)
        self.assertEqual(run.next_topic, "Python Automation Basics")
        self.assertTrue(run.next_subtopic)
        self.assertEqual(run.decision, "learn_now")

    def test_missing_prerequisites_defer_advanced_item(self) -> None:
        item = self.item("LLM Provider APIs")
        scored = score_item(item, set(), {}, [], [])
        self.assertEqual(scored.decision, "defer")
        self.assertIn("HTTP APIs and JSON", scored.prerequisites_missing)

    def test_high_roi_current_topic_wins_with_fresh_evidence_and_prereqs(self) -> None:
        record_feedback(self.session, "Python Automation Basics", "already_know")
        record_feedback(self.session, "HTTP APIs and JSON", "already_know")
        add_evidence_source(
            self.session,
            source_title="Provider API docs",
            related_topic="LLM Provider APIs",
            source_type="official_docs",
            freshness_level="verified_current",
            summary="Current API behavior verified from docs.",
            reliability_score=0.9,
        )
        run = decide_next_topic(self.session, self.profile)
        self.assertEqual(run.next_topic, "LLM Provider APIs")
        self.assertGreater(run.confidence, 0.5)
        self.assertEqual(run.freshness_level, "verified_current")

    def test_stable_core_topic_has_probably_stable_freshness(self) -> None:
        run = decide_next_topic(self.session, self.profile)
        self.assertEqual(run.freshness_level, "probably_stable")
        self.assertLessEqual(run.confidence, 0.78)

    def test_experimental_topic_is_not_selected_before_prerequisites(self) -> None:
        item = self.item("Multi-Agent Workflow Design")
        scored = score_item(item, set(), {}, [], [])
        self.assertEqual(scored.decision, "defer")
        self.assertLess(scored.confidence, 0.5)

    def test_skip_for_now_topic_stays_skipped(self) -> None:
        item = self.item("Local GPU Fine-Tuning")
        scored = score_item(item, set(), {}, [], [])
        self.assertEqual(scored.decision, "skip")
        self.assertLess(scored.score, 0)

    def test_stale_or_unknown_freshness_caps_confidence(self) -> None:
        item = self.item("MCP Fundamentals")
        scored = score_item(item, {"LLM Provider APIs"}, {}, [], [])
        self.assertLessEqual(scored.confidence, 0.55)

    def test_feedback_changes_future_priority(self) -> None:
        item = self.item("Python Automation Basics")
        before = score_item(item, set(), {}, [], [])
        feedback = TopicFeedback(topic_title=item.title, action="not_useful")
        after = score_item(item, set(), {item.title: [feedback]}, [], [feedback])
        self.assertLess(after.score, before.score)

    def test_mastery_is_not_automatic_from_learned_feedback(self) -> None:
        record_feedback(self.session, "Python Automation Basics", "learned")
        item = self.item("Python Automation Basics")
        self.assertNotEqual(item.status, "mastered")

    def test_daily_plan_selection(self) -> None:
        plan = create_daily_plan(self.session, self.profile, time_budget="20 minutes")
        self.assertIn("primary", plan)
        self.assertIn("practice", plan)
        self.assertEqual(plan["time_budget"], "20 minutes")

    def test_roadmap_version_creation(self) -> None:
        current_version = self.roadmap.current_version
        version = build_syllabus_version(self.session, self.profile, reason="test update")
        self.session.refresh(self.roadmap)
        self.assertEqual(version.version_number, current_version + 1)
        self.assertEqual(self.roadmap.current_version, current_version + 1)

    def test_syllabus_grouping_and_rendering(self) -> None:
        groups = grouped_syllabus(self.session, self.roadmap.id)
        self.assertGreaterEqual(len(groups), 2)
        data = syllabus_to_dict(self.session, self.roadmap)
        self.assertIn("modules", data)
        markdown = syllabus_to_markdown(self.session, self.roadmap)
        self.assertIn("# AI Automation Learning Roadmap", markdown)
        self.assertIn("## Automation Foundations", markdown)

    def test_structured_output_validation(self) -> None:
        valid_recommendation = {
            "next_topic": "Python",
            "next_subtopic": "files",
            "decision": "learn_now",
            "why_this_now": "Prerequisite",
            "why_not_other_options": "Lower priority",
            "prerequisites_missing": [],
            "roi_score": 9,
            "effort_score": 3,
            "urgency_score": 9,
            "confidence": 0.7,
            "alternatives": [],
            "recommended_depth": "working_knowledge",
            "suggested_next_steps": [],
            "source_basis": "Stored syllabus",
            "freshness_note": "Stable",
            "freshness_level": "probably_stable",
        }
        self.assertTrue(validate_recommendation_output(valid_recommendation).valid)
        self.assertFalse(validate_recommendation_output({"next_topic": "Python"}).valid)

        valid_syllabus = {
            "modules": [
                {
                    "title": "Foundation",
                    "items": [
                        {
                            "title": "Python",
                            "subtopic": "files",
                            "status": "learn_next",
                            "category": "stable_core",
                            "source_basis": "Stored syllabus",
                            "freshness_note": "Stable",
                            "freshness_level": "probably_stable",
                            "confidence": 0.7,
                            "why_this_now": "Prerequisite",
                            "prerequisites": [],
                            "effort_score": 3,
                            "roi_score": 9,
                            "urgency_score": 9,
                        }
                    ],
                }
            ]
        }
        self.assertTrue(validate_syllabus_output(valid_syllabus).valid)
        self.assertFalse(validate_syllabus_output({"modules": []}).valid)


class RouteSmokeTests(unittest.TestCase):
    def test_fastapi_recommendation_and_export_routes(self) -> None:
        db_path = Path(tempfile.gettempdir()) / "prompt_learning_os_route_test.db"
        if db_path.exists():
            db_path.unlink()
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
        os.environ["LLM_BASE_URL"] = ""
        os.environ["LLM_API_KEY"] = ""
        os.environ["LLM_MODEL"] = ""

        from fastapi.testclient import TestClient

        from app.main import app, on_startup

        on_startup()
        client = TestClient(app)
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Next learning decision", response.text)

        response = client.post("/recommendations/next")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Python Automation Basics", response.text)

        response = client.get("/exports/syllabus.json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("modules", response.json())

        response = client.get("/exports/syllabus.md")
        self.assertEqual(response.status_code, 200)
        self.assertIn("AI Automation Learning Roadmap", response.text)


if __name__ == "__main__":
    unittest.main()
