from __future__ import annotations

from collections.abc import Iterable
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePath, PureWindowsPath
from typing import TypeVar

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EVALS_ROOT = REPOSITORY_ROOT / "tests" / "skill-evals"
CASES_PATH = EVALS_ROOT / "cases.yaml"
BASELINE_PATH = EVALS_ROOT / "baseline-without-skill.md"
RESULTS_PATH = EVALS_ROOT / "results-with-skill.md"
ASSESSMENT_PATH = EVALS_ROOT / "evaluation-summary.md"
ASSERTION_RESULTS_PATH = EVALS_ROOT / "assertion-results.json"
RETRIEVAL_TRACE_PATH = EVALS_ROOT / "retrieval-trace.json"
RUN_MANIFEST_PATH = EVALS_ROOT / "run-manifest.json"
BUNDLE_ROOT = REPOSITORY_ROOT / "skill" / "aiogram-bot-engineering"
BundlePath = TypeVar("BundlePath", bound=PurePath)

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


def load_json_object(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{path.name} must contain a JSON object"
    return data


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ordered_bundle_paths(
    paths: Iterable[BundlePath],
    root: PurePath,
) -> list[BundlePath]:
    return sorted(paths, key=lambda item: item.relative_to(root).as_posix())


def bundle_sha256() -> str:
    digest = hashlib.sha256()
    paths = (
        item
        for item in BUNDLE_ROOT.rglob("*")
        if item.is_file()
        and "__pycache__" not in item.relative_to(BUNDLE_ROOT).parts
        and item.suffix not in {".pyc", ".pyo"}
    )
    for path in ordered_bundle_paths(paths, BUNDLE_ROOT):
        relative = path.relative_to(BUNDLE_ROOT).as_posix().encode()
        digest.update(relative + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def test_bundle_paths_use_platform_neutral_posix_order() -> None:
    bundle = PureWindowsPath("C:/bundle")
    paths = [bundle / "agents" / "openai.yaml", bundle / "SKILL.md"]

    ordered = ordered_bundle_paths(paths, bundle)

    assert [path.relative_to(bundle).as_posix() for path in ordered] == [
        "SKILL.md",
        "agents/openai.yaml",
    ]


def normalized_excerpt(text: str) -> str:
    return " ".join(text.split())


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


def test_independent_assessment_covers_every_case_with_numeric_scores() -> None:
    assert ASSESSMENT_PATH.is_file(), f"missing eval assessment: {ASSESSMENT_PATH}"
    sections = parse_evidence_sections(ASSESSMENT_PATH)
    assert {section.case_id for section in sections} == REQUIRED_CASE_IDS
    assert all(len(section.body.split()) >= 20 for section in sections)

    content = ASSESSMENT_PATH.read_text(encoding="utf-8")
    for case_id in REQUIRED_CASE_IDS:
        row = re.search(
            rf"^\|\s*{re.escape(case_id)}\s*\|\s*\d+/\d+\s*\|\s*\d+/\d+\s*\|",
            content,
            re.MULTILINE,
        )
        assert row is not None, f"missing numeric assessment row for {case_id}"


def test_run_manifest_binds_inputs_outputs_and_runner_conditions() -> None:
    manifest = load_json_object(RUN_MANIFEST_PATH)
    assert manifest["schema_version"] == 1
    assert re.fullmatch(r"[0-9a-f]{40}", manifest["skill_snapshot"]["commit"])
    assert manifest["skill_snapshot"]["bundle_sha256"] == bundle_sha256()

    artifact_paths = {
        "cases": CASES_PATH,
        "control_output": BASELINE_PATH,
        "treatment_output": RESULTS_PATH,
        "retrieval_trace": RETRIEVAL_TRACE_PATH,
        "assertion_results": ASSERTION_RESULTS_PATH,
    }
    assert set(manifest["artifacts"]) == set(artifact_paths)
    for name, path in artifact_paths.items():
        artifact = manifest["artifacts"][name]
        assert artifact["path"] == path.relative_to(REPOSITORY_ROOT).as_posix()
        assert artifact["sha256"] == sha256_file(path)

    runs = manifest["runs"]
    assert isinstance(runs, list) and {run["condition"] for run in runs} == {
        "control",
        "treatment",
        "evaluator",
    }
    assert len({run["run_id"] for run in runs}) == len(runs)
    assert len({run["runner"]["canonical_task"] for run in runs}) == len(runs)
    for run in runs:
        assert run["runner"]["system"]
        assert run["runner"]["model_family"]
        assert run["runner"]["exact_model_revision"] is None
        assert run["runner"]["revision_disclosure"]
        assert run["allowed_context"]
        assert run["prohibited_context"]
        assert run["network_access"] is False

    run_by_condition = {run["condition"]: run for run in runs}
    trace = load_json_object(RETRIEVAL_TRACE_PATH)
    assertion_results = load_json_object(ASSERTION_RESULTS_PATH)
    assert run_by_condition["treatment"]["skill_commit"] == manifest["skill_snapshot"]["commit"]
    assert run_by_condition["control"]["run_id"] == trace["control"]["run_id"]
    assert run_by_condition["treatment"]["run_id"] == trace["treatment"]["run_id"]
    assert run_by_condition["evaluator"]["run_id"] == assertion_results["run_id"]


def test_retrieval_trace_is_path_based_and_covers_expected_routes() -> None:
    trace = load_json_object(RETRIEVAL_TRACE_PATH)
    cases = load_cases(CASES_PATH)
    assert trace["schema_version"] == 1
    assert trace["control"]["ordered_paths"] == []
    assert trace["treatment"]["granularity"] == "shared_batch"
    assert trace["treatment"]["attribution_limit"]

    treatment_paths = trace["treatment"]["ordered_paths"]
    assert len(treatment_paths) == len(set(treatment_paths))
    for reference in treatment_paths:
        assert resolve_bundle_reference(reference).is_file()
    for case in cases:
        assert trace["control"]["case_paths"][case["id"]] == []
        assert trace["treatment"]["case_paths"][case["id"]] == treatment_paths
        assert set(case["expected_references"]) <= set(treatment_paths), case["id"]


def test_assertion_results_are_evidence_bound_and_scores_are_derived() -> None:
    cases = {case["id"]: case for case in load_cases(CASES_PATH)}
    outputs = {
        "control": {
            section.case_id: section.body for section in parse_evidence_sections(BASELINE_PATH)
        },
        "treatment": {
            section.case_id: section.body for section in parse_evidence_sections(RESULTS_PATH)
        },
    }
    trace = load_json_object(RETRIEVAL_TRACE_PATH)
    results = load_json_object(ASSERTION_RESULTS_PATH)
    records = results["cases"]
    assert {record["id"] for record in records} == REQUIRED_CASE_IDS
    summary = ASSESSMENT_PATH.read_text(encoding="utf-8")

    aggregate = {"control": [0, 0], "treatment": [0, 0]}
    field_by_category = {
        "retrieval": "retrieval_assertions",
        "application": "application_assertions",
        "gap": "gap_assertions",
    }
    for record in records:
        case_id = record["id"]
        case = cases[case_id]
        per_case_scores: dict[str, tuple[int, int]] = {}
        for condition in ("control", "treatment"):
            condition_result = record["conditions"][condition]
            passed = 0
            total = 0
            for category, case_field in field_by_category.items():
                assertions = condition_result[category]
                assert [item["assertion"] for item in assertions] == case[case_field]
                for item in assertions:
                    total += 1
                    evidence = item["evidence"]
                    if category == "retrieval":
                        assert evidence["kind"] == "retrieval_trace"
                        paths = trace[condition]["ordered_paths"]
                        expected_pass = set(case["expected_references"]) <= set(paths)
                        assert item["passed"] is expected_pass
                        assert evidence["paths"] == paths
                    elif item["passed"]:
                        assert evidence["kind"] == "output_excerpt"
                        excerpt = normalized_excerpt(evidence["excerpt"])
                        assert excerpt
                        assert excerpt in normalized_excerpt(outputs[condition][case_id])
                    else:
                        assert evidence["kind"] == "missing_output_evidence"
                        assert evidence["reason"]
                    passed += int(item["passed"])
            per_case_scores[condition] = (passed, total)
            aggregate[condition][0] += passed
            aggregate[condition][1] += total

        row = re.search(
            rf"^\|\s*{re.escape(case_id)}\s*\|\s*(\d+)/(\d+)\s*\|\s*(\d+)/(\d+)\s*\|",
            summary,
            re.MULTILINE,
        )
        assert row is not None
        assert tuple(map(int, row.groups())) == (
            *per_case_scores["control"],
            *per_case_scores["treatment"],
        )

    for condition, (passed, total) in aggregate.items():
        assert 0 <= passed <= total
        assert re.search(rf"{condition}[^\n]*{passed}/{total}", summary, re.IGNORECASE)


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
