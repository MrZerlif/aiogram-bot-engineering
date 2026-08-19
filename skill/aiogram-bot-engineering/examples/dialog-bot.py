"""A compact, import-safe aiogram and aiogram-dialog polling example.

Set BOT_TOKEN only when running this module.  MemoryStorage is deliberately
used here for a demo/development bot; production deployments need persistent
shared storage.
"""

from __future__ import annotations

import asyncio
import os

from aiogram import Bot, Dispatcher, Router
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, InputRichBlockParagraph, InputRichMessage, Message
from aiogram_dialog import Dialog, DialogManager, StartMode, Window, setup_dialogs
from aiogram_dialog.widgets.kbd import Back, Button, SwitchTo
from aiogram_dialog.widgets.style import Style
from aiogram_dialog.widgets.text import Const


class ExampleSG(StatesGroup):
    welcome = State()
    details = State()


def build_welcome_rich_message() -> InputRichMessage:
    """Build outgoing rich content for the /rich command."""
    return InputRichMessage(
        blocks=[
            InputRichBlockParagraph(
                text="Welcome! This message uses a structured Telegram rich block."
            )
        ]
    )


def build_primary_style(custom_emoji_id: str | None) -> Style:
    """Create the fixed style used by the dialog's primary action."""
    return Style(style=ButtonStyle.SUCCESS, emoji_id=custom_emoji_id)


async def acknowledge_primary(
    callback: CallbackQuery,
    button: Button,
    manager: DialogManager,
) -> None:
    """Give the demo primary button a small, safe acknowledgement."""
    del button, manager
    await callback.answer("Use Continue to see the next window.")


def build_main_dialog(custom_emoji_id: str | None) -> Dialog:
    """Build the two-window dialog without creating a bot or reading settings."""
    return Dialog(
        Window(
            Const("Welcome to the dialog example."),
            Button(
                Const("Primary action"),
                id="primary",
                on_click=acknowledge_primary,
                style=build_primary_style(custom_emoji_id),
            ),
            SwitchTo(Const("Continue"), id="continue", state=ExampleSG.details),
            state=ExampleSG.welcome,
        ),
        Window(
            Const("This is the second window."),
            Back(Const("Back"), id="back"),
            state=ExampleSG.details,
        ),
    )


async def start_dialog(message: Message, dialog_manager: DialogManager) -> None:
    """Open the top-level dialog flow from /start."""
    await dialog_manager.start(ExampleSG.welcome, mode=StartMode.RESET_STACK)


async def send_rich_message(message: Message, bot: Bot) -> None:
    """Send native Telegram rich content from /rich."""
    await bot.send_rich_message(
        chat_id=message.chat.id,
        rich_message=build_welcome_rich_message(),
    )


def build_router() -> Router:
    """Create a fresh feature router for each dispatcher construction."""
    feature_router = Router(name="dialog_example")
    feature_router.message.register(start_dialog, Command("start"))
    feature_router.message.register(send_rich_message, Command("rich"))
    return feature_router


def build_dispatcher(custom_emoji_id: str | None) -> Dispatcher:
    """Compose a network-free dispatcher for this demo/development example."""
    # MemoryStorage is demo/development-only: production requires shared persistence.
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(build_router())
    dispatcher.include_router(build_main_dialog(custom_emoji_id))
    setup_dialogs(dispatcher)
    return dispatcher


async def main() -> None:
    """Read runtime settings and start polling only when executed as a script."""
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN environment variable is required to run this example.")

    custom_emoji_id = os.getenv("BOT_BUTTON_EMOJI_ID")
    bot = Bot(token=token)
    try:
        await build_dispatcher(custom_emoji_id).start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
