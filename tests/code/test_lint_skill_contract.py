from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPOSITORY_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

from lint_skill_contract import (  # noqa: E402
    BUNDLE_RELATIVE,
    inspect_skill_routes,
    lint_repository,
    lint_skill_bundle,
)


REQUIRED_REFERENCE_NAMES = (
    "architecture.md",
    "custom-emoji-system.md",
    "deployment.md",
    "dialogs-and-ui.md",
    "mini-apps.md",
    "payments.md",
    "presentation-and-ux.md",
    "production-engineering.md",
    "rich-messages.md",
    "testing.md",
)
REQUIRED_BUNDLE_RESOURCES = (
    "assets/custom-emoji-registry.example.json",
    "assets/custom-emoji-registry.schema.json",
    "scripts/validate_custom_emoji_registry.py",
)


def make_valid_repository(tmp_path: Path) -> Path:
    repo = tmp_path / "repository"
    bundle = repo / BUNDLE_RELATIVE
    (bundle / "agents").mkdir(parents=True)
    (bundle / "references").mkdir()
    (bundle / "examples").mkdir()
    (bundle / "assets").mkdir()
    (bundle / "scripts").mkdir()
    (bundle / "agents" / "openai.yaml").write_text("interface: {}\n", encoding="utf-8")
    for name in REQUIRED_REFERENCE_NAMES:
        (bundle / "references" / name).write_text(f"# {name}\n", encoding="utf-8")
    (bundle / "references" / "deployment.md").write_text(
        "# deployment.md\n\n"
        "```python\n"
        "SimpleRequestHandler(\n"
        "    dispatcher=dispatcher, bot=bot, handle_in_background=False\n"
        ")\n"
        "DurableWebhookRequestHandler(\n"
        "    dispatcher=dispatcher, bot=bot, inbox=inbox, secret_token=secret_token\n"
        ")\n"
        "await dispatcher.start_polling(\n"
        "    bot, tasks_concurrency_limit=max_concurrent_updates\n"
        ")\n"
        "```\n",
        encoding="utf-8",
    )
    (bundle / "references" / "dialogs-and-ui.md").write_text(
        "# dialogs-and-ui.md\n\n"
        "```python\n"
        "async def recover_dialog(dialog_manager):\n"
        "    await dialog_manager.start(\n"
        "        CatalogSG.browse, show_mode=ShowMode.SEND\n"
        "    )\n"
        "```\n",
        encoding="utf-8",
    )
    (bundle / "examples" / "dialog-bot.py").write_text("print('ok')\n", encoding="utf-8")
    (bundle / "examples" / "durable_webhook.py").write_text(
        "class DurableWebhookRequestHandler:\n    pass\n",
        encoding="utf-8",
    )
    (bundle / "assets" / "custom-emoji-registry.example.json").write_text(
        "{}\n",
        encoding="utf-8",
    )
    (bundle / "assets" / "custom-emoji-registry.schema.json").write_text(
        "{}\n",
        encoding="utf-8",
    )
    (bundle / "scripts" / "validate_custom_emoji_registry.py").write_text(
        "def validate_registry(document):\n    return []\n",
        encoding="utf-8",
    )
    reference_routes = "\n".join(
        f"[{name}](references/{name})" for name in REQUIRED_REFERENCE_NAMES
    )
    (bundle / "SKILL.md").write_text(
        f"""---
name: test-skill
description: Test fixture
---

{reference_routes}
[full example](examples/dialog-bot.py)
[durable webhook acceptance](examples/durable_webhook.py)
""",
        encoding="utf-8",
    )
    return repo


def bundle_path(repo: Path) -> Path:
    return repo / BUNDLE_RELATIVE


def append_skill(repo: Path, text: str) -> None:
    skill = bundle_path(repo) / "SKILL.md"
    skill.write_text(skill.read_text(encoding="utf-8") + "\n" + text + "\n", encoding="utf-8")


def append_reference(repo: Path, name: str, text: str) -> None:
    reference = bundle_path(repo) / "references" / name
    reference.write_text(
        reference.read_text(encoding="utf-8") + "\n" + text + "\n",
        encoding="utf-8",
    )


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


@pytest.mark.parametrize(
    "relative",
    [
        *(f"references/{name}" for name in REQUIRED_REFERENCE_NAMES),
        "examples/dialog-bot.py",
        *REQUIRED_BUNDLE_RESOURCES,
    ],
)
def test_rejects_removing_a_required_routed_resource(
    tmp_path: Path,
    relative: str,
) -> None:
    repo = make_valid_repository(tmp_path)
    bundle = bundle_path(repo)
    (bundle / relative).unlink()
    skill = bundle / "SKILL.md"
    skill.write_text(
        "\n".join(
            line for line in skill.read_text(encoding="utf-8").splitlines()
            if f"({relative})" not in line
        )
        + "\n",
        encoding="utf-8",
    )

    errors = lint_repository(repo)

    assert any(f"missing required file: {relative}" in error for error in errors)


def test_allows_unrelated_repository_files(tmp_path: Path) -> None:
    repo = make_valid_repository(tmp_path)
    (repo / "README.md").write_text("Repository documentation\n", encoding="utf-8")

    assert lint_repository(repo) == []


def test_allows_additional_direct_skill_references_beyond_the_required_subset(
    tmp_path: Path,
) -> None:
    repo = make_valid_repository(tmp_path)
    for number in range(1, 7):
        add_reference(repo, f"topic-{number}.md", routed=True)

    routes = inspect_skill_routes(bundle_path(repo))

    assert len(routes.references) == len(REQUIRED_REFERENCE_NAMES) + 6
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


def test_rejects_webhook_example_that_acknowledges_in_background(tmp_path: Path) -> None:
    repo = make_valid_repository(tmp_path)
    append_reference(
        repo,
        "deployment.md",
        "```python\nSimpleRequestHandler(dispatcher=dispatcher, bot=bot)\n```",
    )

    assert any("handle_in_background=False" in error for error in lint_repository(repo))


def test_accepts_webhook_example_that_awaits_dispatch(tmp_path: Path) -> None:
    repo = make_valid_repository(tmp_path)
    append_reference(
        repo,
        "deployment.md",
        "```python\nSimpleRequestHandler(\n"
        "    dispatcher=dispatcher, bot=bot, handle_in_background=False\n"
        ")\n```",
    )

    assert lint_repository(repo) == []


def test_rejects_simple_handler_as_only_durable_webhook_example(tmp_path: Path) -> None:
    repo = make_valid_repository(tmp_path)
    deployment = bundle_path(repo) / "references" / "deployment.md"
    content = deployment.read_text(encoding="utf-8")
    durable_call = (
        "DurableWebhookRequestHandler(\n"
        "    dispatcher=dispatcher, bot=bot, inbox=inbox, secret_token=secret_token\n"
        ")\n"
    )
    assert durable_call in content
    deployment.write_text(content.replace(durable_call, ""), encoding="utf-8")

    errors = lint_repository(repo)

    assert any(
        "missing durable webhook acceptance example in references/deployment.md" in error
        for error in errors
    )


@pytest.mark.parametrize(
    "polling_call",
    [
        "await dispatcher.start_polling(bot)",
        "await dispatcher.start_polling(bot, tasks_concurrency_limit=None)",
        "await dispatcher.start_polling(bot, tasks_concurrency_limit=0)",
        "await dispatcher.start_polling(bot, tasks_concurrency_limit='64')",
        "await dispatcher.start_polling(bot, tasks_concurrency_limit=1.5)",
        "await dispatcher.start_polling(bot, tasks_concurrency_limit=-max_updates)",
    ],
)
def test_rejects_unbounded_or_nonpositive_polling_policy(
    tmp_path: Path,
    polling_call: str,
) -> None:
    repo = make_valid_repository(tmp_path)
    append_reference(repo, "deployment.md", f"```python\n{polling_call}\n```")

    assert any("bounded polling concurrency" in error for error in lint_repository(repo))


@pytest.mark.parametrize(
    "polling_call",
    [
        "await dispatcher.start_polling(bot, tasks_concurrency_limit=max_updates)",
        "await dispatcher.start_polling(bot, handle_as_tasks=False)",
    ],
)
def test_accepts_explicit_bounded_or_sequential_polling_policy(
    tmp_path: Path,
    polling_call: str,
) -> None:
    repo = make_valid_repository(tmp_path)
    append_reference(repo, "deployment.md", f"```python\n{polling_call}\n```")

    assert lint_repository(repo) == []


def test_rejects_stale_dialog_recovery_that_edits_the_stale_message(tmp_path: Path) -> None:
    repo = make_valid_repository(tmp_path)
    append_reference(
        repo,
        "dialogs-and-ui.md",
        "```python\n"
        "async def recover_dialog(dialog_manager):\n"
        "    await dialog_manager.start(CatalogSG.browse, mode=StartMode.RESET_STACK)\n"
        "```",
    )

    assert any("show_mode=ShowMode.SEND" in error for error in lint_repository(repo))


def test_accepts_stale_dialog_recovery_that_sends_a_fresh_message(tmp_path: Path) -> None:
    repo = make_valid_repository(tmp_path)
    append_reference(
        repo,
        "dialogs-and-ui.md",
        "```python\n"
        "async def recover_dialog(dialog_manager):\n"
        "    await dialog_manager.start(\n"
        "        CatalogSG.browse,\n"
        "        mode=StartMode.RESET_STACK,\n"
        "        show_mode=ShowMode.SEND,\n"
        "    )\n"
        "```",
    )

    assert lint_repository(repo) == []


def test_does_not_treat_an_unrelated_recovery_service_as_dialog_navigation(
    tmp_path: Path,
) -> None:
    repo = make_valid_repository(tmp_path)
    append_reference(
        repo,
        "dialogs-and-ui.md",
        "```python\n"
        "async def recover_connection(service):\n"
        "    await service.start()\n"
        "```",
    )

    assert lint_repository(repo) == []


def test_rejects_removing_required_delivery_and_recovery_examples(tmp_path: Path) -> None:
    repo = make_valid_repository(tmp_path)
    for name in ("deployment.md", "dialogs-and-ui.md"):
        reference = bundle_path(repo) / "references" / name
        reference.write_text(f"# {name}\n", encoding="utf-8")

    errors = lint_repository(repo)

    assert any("missing SimpleRequestHandler example" in error for error in errors)
    assert any(
        "missing durable webhook acceptance example in references/deployment.md" in error
        for error in errors
    )
    assert any("missing start_polling example" in error for error in errors)
    assert any("missing stale-dialog recovery example" in error for error in errors)


def test_rejects_stale_recovery_with_neutral_function_and_manager_names(
    tmp_path: Path,
) -> None:
    repo = make_valid_repository(tmp_path)
    reference = bundle_path(repo) / "references" / "dialogs-and-ui.md"
    reference.write_text(
        "# dialogs-and-ui.md\n\n"
        "```python\n"
        "from aiogram_dialog import DialogManager, StartMode\n"
        "from aiogram_dialog.api.exceptions import UnknownIntent\n"
        "async def handle_stale(manager: DialogManager):\n"
        "    await manager.start(\n"
        "        CatalogSG.browse, mode=StartMode.RESET_STACK\n"
        "    )\n"
        "```\n",
        encoding="utf-8",
    )

    assert any("show_mode=ShowMode.SEND" in error for error in lint_repository(repo))


def test_does_not_treat_dialog_metrics_start_as_navigation(tmp_path: Path) -> None:
    repo = make_valid_repository(tmp_path)
    append_reference(
        repo,
        "dialogs-and-ui.md",
        "```python\n"
        "async def recover_metrics(dialog_metrics):\n"
        "    await dialog_metrics.start()\n"
        "```",
    )

    assert lint_repository(repo) == []


def test_rejects_an_unrouted_bundle_example(tmp_path: Path) -> None:
    repo = make_valid_repository(tmp_path)
    add_example(repo, "orphan.py", routed=False)

    assert any("orphan example" in error for error in lint_repository(repo))


def test_ignores_generated_python_cache_artifacts(tmp_path: Path) -> None:
    repo = make_valid_repository(tmp_path)
    cache = bundle_path(repo) / "examples" / "__pycache__"
    cache.mkdir()
    (cache / "dialog-bot.cpython-310.pyc").write_bytes(b"generated")

    assert lint_repository(repo) == []


def test_does_not_hide_source_resources_inside_a_cache_named_directory(
    tmp_path: Path,
) -> None:
    repo = make_valid_repository(tmp_path)
    cache = bundle_path(repo) / "examples" / "__pycache__"
    cache.mkdir()
    (cache / "hidden.py").write_text("print('not routed')\n", encoding="utf-8")

    assert any("orphan example" in error for error in lint_repository(repo))


def test_real_repository_has_no_orphan_resources() -> None:
    assert lint_skill_bundle(REPOSITORY_ROOT / BUNDLE_RELATIVE) == []


def test_real_bundle_directly_routes_specialized_references() -> None:
    routes = inspect_skill_routes(REPOSITORY_ROOT / BUNDLE_RELATIVE)

    assert {
        Path("references/custom-emoji-system.md"),
        Path("references/presentation-and-ux.md"),
        Path("references/testing.md"),
        Path("references/production-engineering.md"),
    } <= routes.references
