from __future__ import annotations

import importlib.util
import os
import socket
import sys
from pathlib import Path
from types import ModuleType

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_PATH = (
    REPOSITORY_ROOT / "skill" / "aiogram-bot-engineering" / "examples" / "dialog-bot.py"
)


def import_dialog_example() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "aiogram_bot_engineering_dialog_example",
        EXAMPLE_PATH,
    )
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot create an import spec for {EXAMPLE_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_example_imports_and_builds_components_without_runtime_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catch import-time runtime access and incompatible example constructors."""

    try:
        import aiogram
        from aiogram import Dispatcher, Router
        from aiogram.types import InputRichMessage
        from aiogram_dialog import Dialog
    except ImportError as exc:
        pytest.fail(f"required smoke-test dependency is unavailable: {exc}", pytrace=False)

    def reject_runtime_access(*_args: object, **_kwargs: object) -> str:
        raise AssertionError(
            "the smoke path must not read a token, construct a Bot, or open a network connection"
        )

    async def reject_polling(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the smoke path must not start polling")

    monkeypatch.setattr(os, "getenv", reject_runtime_access)
    monkeypatch.setattr(aiogram, "Bot", reject_runtime_access)
    monkeypatch.setattr(Dispatcher, "start_polling", reject_polling)
    monkeypatch.setattr(socket, "create_connection", reject_runtime_access)
    monkeypatch.setattr(socket.socket, "connect", reject_runtime_access)
    monkeypatch.setattr(socket.socket, "connect_ex", reject_runtime_access)
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    example = import_dialog_example()

    rich_message = example.build_welcome_rich_message()
    dialog = example.build_main_dialog(custom_emoji_id=None)
    router = example.build_router()
    dispatcher = example.build_dispatcher(custom_emoji_id=None)

    assert isinstance(rich_message, InputRichMessage)
    assert rich_message.blocks
    assert isinstance(dialog, Dialog)
    assert isinstance(router, Router)
    assert isinstance(dispatcher, Dispatcher)


def test_primary_action_style_is_semantic_not_decorative() -> None:
    """Catch using a completion color for an ordinary primary action."""

    from aiogram.enums import ButtonStyle

    example = import_dialog_example()

    style = example.build_primary_style(custom_emoji_id=None)

    assert style.style is ButtonStyle.PRIMARY
