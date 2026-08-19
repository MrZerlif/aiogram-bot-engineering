from __future__ import annotations

import json
import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EVALS_ROOT = REPOSITORY_ROOT / "tests" / "skill-evals"
CASES_PATH = EVALS_ROOT / "cases.yaml"
BASELINE_PATH = EVALS_ROOT / "baseline-without-skill.md"
RESULTS_PATH = EVALS_ROOT / "results-with-skill.md"
BUNDLE_ROOT = REPOSITORY_ROOT / "skill" / "aiogram-bot-engineering"

REQUIRED_CASE_IDS = {
    "fsm-linear-flow",
    "scenes-isolated-flow",
    "dialog-widget-ui",
    "mini-app-launch-security",
    "callback-authorization",
    "payment-lifecycle",
    "webhook-secret",
    "background-jobs",
    "testing-strategy",
    "production-uow-observability",
}
REQUIRED_TOPICS = {
    "fsm",
    "scenes",
    "dialogs",
    "mini-apps",
    "callback-authorization",
    "payments",
    "webhook",
    "background-jobs",
    "testing",
}
REQUIRED_CASE_FIELDS = {
    "id",
    "prompt",
    "topics",
    "expected_references",
    "retrieval_assertions",
    "application_assertions",
    "gap_assertions",
}


def load_cases(path: Path) -> list[dict[str, object]]:
    """Load the JSON-form YAML fixture without adding a YAML dependency."""
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, list), "cases.yaml must contain a JSON list"
    assert all(isinstance(case, dict) for case in data), "each case must be an object"
    return data


def markdown_case_section_ids(path: Path) -> list[str]:
    """Return the level-two case identifiers in an evidence artifact."""
    return re.findall(r"^## ([a-z0-9-]+)\s*$", path.read_text(encoding="utf-8"), re.MULTILINE)


def test_skill_eval_artifacts_are_complete_and_reachable() -> None:
    assert CASES_PATH.is_file(), f"missing eval cases fixture: {CASES_PATH}"
    assert BASELINE_PATH.is_file(), f"missing baseline evidence: {BASELINE_PATH}"
    assert RESULTS_PATH.is_file(), f"missing with-skill evidence: {RESULTS_PATH}"

    cases = load_cases(CASES_PATH)
    assert 8 <= len(cases) <= 12

    case_ids = {case.get("id") for case in cases}
    assert all(isinstance(case_id, str) for case_id in case_ids)
    assert len(case_ids) == len(cases), "case IDs must be unique"
    assert case_ids == REQUIRED_CASE_IDS

    covered_topics: set[str] = set()
    for case in cases:
        assert REQUIRED_CASE_FIELDS <= case.keys(), f"case is missing required fields: {case}"
        assert isinstance(case["prompt"], str) and case["prompt"].strip()
        for field in (
            "topics",
            "expected_references",
            "retrieval_assertions",
            "application_assertions",
            "gap_assertions",
        ):
            value = case[field]
            assert isinstance(value, list) and value, f"{case['id']} has an empty {field} rubric"
            assert all(isinstance(item, str) and item.strip() for item in value)

        covered_topics.update(case["topics"])
        for reference in case["expected_references"]:
            reference_path = BUNDLE_ROOT / reference
            assert reference_path.is_file(), f"{case['id']} references missing bundle file: {reference}"

    assert REQUIRED_TOPICS <= covered_topics
    for evidence_path in (BASELINE_PATH, RESULTS_PATH):
        section_ids = markdown_case_section_ids(evidence_path)
        assert len(section_ids) == len(set(section_ids)), f"duplicate case section in {evidence_path}"
        assert set(section_ids) == case_ids
