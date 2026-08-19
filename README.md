# Aiogram Bot Engineering

## Purpose

A compact Codex skill for designing, reviewing, and deploying Python Telegram
bots with aiogram, including dialogs, Rich Messages, Mini Apps, payments, and
webhooks. It routes each request to focused guidance instead of duplicating it
here.

## Compatibility

Targets Python 3.10+, aiogram 3.30.0, aiogram-dialog 2.6.0, and Telegram Bot
API 10.2. They are dated compatibility targets; check the [official aiogram
documentation](https://docs.aiogram.dev/) and [Telegram Bot
API](https://core.telegram.org/bots/api) for version-sensitive work.

## Installation

Keep this directory available to Codex as a local skill. Bot projects should
install the pinned libraries appropriate to their environment, for example:

```shell
python -m pip install "aiogram==3.30.0" "aiogram-dialog==2.6.0"
```

## Invocation

Ask Codex to use `$aiogram-bot-engineering` when working on an aiogram bot.
