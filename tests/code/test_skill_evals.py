from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

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


@dataclass(frozen=True)
class EvidenceSection:
    case_id: str
    body: str


def load_cases(path: Path) -> list[dict[str, object]]:
    """Load the JSON-form YAML fixture without adding a YAML dependency."""
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, list), "cases.yaml must contain a JSON list"
    assert all(isinstance(case, dict) for case in data), "each case must be an object"
    return data


def parse_evidence_sections(path: Path) -> list[EvidenceSection]:
    """Parse each level-two case heading and the evidence body it owns."""
    content = path.read_text(encoding="utf-8")
    headings = list(re.finditer(r"^## ([a-z0-9-]+)\s*$", content, re.MULTILINE))
    return [
        EvidenceSection(
            heading.group(1),
            content[heading.end() : headings[index + 1].start() if index + 1 < len(headings) else len(content)].strip(),
        )
        for index, heading in enumerate(headings)
    ]


def resolve_bundle_reference(reference: str) -> Path:
    """Resolve a bundle-relative reference without allowing it to escape the bundle."""
    bundle_root = BUNDLE_ROOT.resolve()
    reference_path = (bundle_root / reference).resolve()
    try:
        reference_path.relative_to(bundle_root)
    except ValueError as error:
        raise ValueError(f"reference escapes the skill bundle: {reference}") from error
    return reference_path


def test_evidence_sections_have_substantive_case_specific_bodies() -> None:
    for evidence_path in (BASELINE_PATH, RESULTS_PATH):
        sections = parse_evidence_sections(evidence_path)
        assert all(len(section.body.split()) >= 20 for section in sections)
        assert all(len(re.findall(r"[.!?](?:\s|$)", section.body)) >= 2 for section in sections)
        assert len({section.body for section in sections}) == len(sections)


def test_bundle_reference_rejects_a_parent_directory_escape() -> None:
    with pytest.raises(ValueError, match="escapes the skill bundle"):
        resolve_bundle_reference("../outside.md")


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
            reference_path = resolve_bundle_reference(reference)
            assert reference_path.is_file(), f"{case['id']} references missing bundle file: {reference}"

    assert REQUIRED_TOPICS <= covered_topics
    for evidence_path in (BASELINE_PATH, RESULTS_PATH):
        section_ids = [section.case_id for section in parse_evidence_sections(evidence_path)]
        assert len(section_ids) == len(set(section_ids)), f"duplicate case section in {evidence_path}"
        assert set(section_ids) == case_ids
