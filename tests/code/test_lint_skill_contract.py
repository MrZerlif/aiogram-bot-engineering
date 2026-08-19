from __future__ import annotations

import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPOSITORY_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

from lint_skill_contract import (  # noqa: E402
    BUNDLE_RELATIVE,
    inspect_skill_routes,
    lint_repository,
    lint_skill_bundle,
)


def make_valid_repository(tmp_path: Path) -> Path:
    repo = tmp_path / "repository"
    bundle = repo / BUNDLE_RELATIVE
    (bundle / "agents").mkdir(parents=True)
    (bundle / "references").mkdir()
    (bundle / "examples").mkdir()
    (bundle / "agents" / "openai.yaml").write_text("interface: {}\n", encoding="utf-8")
    (bundle / "references" / "architecture.md").write_text("# Architecture\n", encoding="utf-8")
    (bundle / "examples" / "dialog-bot.py").write_text("print('ok')\n", encoding="utf-8")
    (bundle / "SKILL.md").write_text(
        """---
name: test-skill
description: Test fixture
---

[architecture](references/architecture.md)
[full example](examples/dialog-bot.py)
""",
        encoding="utf-8",
    )
    return repo


def bundle_path(repo: Path) -> Path:
    return repo / BUNDLE_RELATIVE


def append_skill(repo: Path, text: str) -> None:
    skill = bundle_path(repo) / "SKILL.md"
    skill.write_text(skill.read_text(encoding="utf-8") + "\n" + text + "\n", encoding="utf-8")


def add_reference(repo: Path, name: str, *, routed: bool) -> None:
    reference = bundle_path(repo) / "references" / name
    reference.write_text("# Additional guidance\n", encoding="utf-8")
    if routed:
        append_skill(repo, f"[extra reference](references/{name})")


def add_example(repo: Path, name: str, *, routed: bool) -> None:
    example = bundle_path(repo) / "examples" / name
    example.write_text("print('ok')\n", encoding="utf-8")
    if routed:
        append_skill(repo, f"[extra example](examples/{name})")


def test_allows_an_additional_routed_reference(tmp_path: Path) -> None:
    repo = make_valid_repository(tmp_path)
    add_reference(repo, "database.md", routed=True)

    assert lint_repository(repo) == []


def test_rejects_an_orphan_reference(tmp_path: Path) -> None:
    repo = make_valid_repository(tmp_path)
    add_reference(repo, "orphan.md", routed=False)

    assert any("orphan reference" in error for error in lint_repository(repo))


def test_rejects_reference_hidden_in_an_unused_reference_definition(tmp_path: Path) -> None:
    repo = make_valid_repository(tmp_path)
    add_reference(repo, "orphan.md", routed=False)
    append_skill(repo, "[fake]: references/orphan.md")

    assert any("orphan reference" in error for error in lint_repository(repo))


def test_rejects_reference_hidden_in_inline_code(tmp_path: Path) -> None:
    repo = make_valid_repository(tmp_path)
    add_reference(repo, "orphan.md", routed=False)
    append_skill(repo, "`[fake](references/orphan.md)`")

    assert any("orphan reference" in error for error in lint_repository(repo))


def test_rejects_invalid_python_fence(tmp_path: Path) -> None:
    repo = make_valid_repository(tmp_path)
    append_skill(repo, "```python\nif True print('broken')\n```")

    assert any("invalid Python fence" in error for error in lint_repository(repo))


def test_rejects_missing_required_bundle_files(tmp_path: Path) -> None:
    repo = make_valid_repository(tmp_path)
    (bundle_path(repo) / "agents" / "openai.yaml").unlink()

    errors = lint_repository(repo)

    assert any("missing required file: agents/openai.yaml" in error for error in errors)


def test_allows_unrelated_repository_files(tmp_path: Path) -> None:
    repo = make_valid_repository(tmp_path)
    (repo / "README.md").write_text("Repository documentation\n", encoding="utf-8")

    assert lint_repository(repo) == []


def test_allows_a_seventh_direct_skill_reference(tmp_path: Path) -> None:
    repo = make_valid_repository(tmp_path)
    for number in range(1, 7):
        add_reference(repo, f"topic-{number}.md", routed=True)

    routes = inspect_skill_routes(bundle_path(repo))

    assert len(routes.references) == 7
    assert lint_repository(repo) == []


def test_rejects_broken_direct_skill_reference(tmp_path: Path) -> None:
    repo = make_valid_repository(tmp_path)
    append_skill(repo, "[missing reference](references/missing.md)")

    assert any("unresolved local link" in error for error in lint_repository(repo))


def test_accepts_valid_python_fences_including_top_level_await(tmp_path: Path) -> None:
    repo = make_valid_repository(tmp_path)
    append_skill(repo, "```python\nawait bot.send_message(chat_id=1, text='hello')\n```")

    assert lint_repository(repo) == []


def test_rejects_prohibited_telegram_framework_and_raw_bot_api_http(tmp_path: Path) -> None:
    repo = make_valid_repository(tmp_path)
    append_skill(
        repo,
        "```python\nfrom telebot import TeleBot\nurl = 'https://api.telegram.org/botTOKEN/getMe'\n```",
    )

    errors = lint_repository(repo)

    assert any("prohibited executable framework" in error for error in errors)
    assert any("prohibited executable raw Bot API HTTP" in error for error in errors)


def test_rejects_an_unrouted_bundle_example(tmp_path: Path) -> None:
    repo = make_valid_repository(tmp_path)
    add_example(repo, "orphan.py", routed=False)

    assert any("orphan example" in error for error in lint_repository(repo))


def test_real_repository_has_no_orphan_resources() -> None:
    assert lint_skill_bundle(REPOSITORY_ROOT / BUNDLE_RELATIVE) == []
