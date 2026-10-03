from __future__ import annotations

import ast
from collections.abc import Callable
from datetime import timedelta
import hashlib
import hmac
import json
from pathlib import Path
import re
import time
from urllib.parse import parse_qsl, urlencode

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MINI_APPS_PATH = (
    REPOSITORY_ROOT
    / "skill"
    / "aiogram-bot-engineering"
    / "references"
    / "mini-apps.md"
)
BOT_TOKEN = "test-token"


def load_canonical_validator() -> Callable[[str, str, timedelta], dict[str, str]]:
    content = MINI_APPS_PATH.read_text(encoding="utf-8")
    blocks = re.findall(r"```python\s*\n(.*?)```", content, re.DOTALL)
    matches: list[str] = []
    for block in blocks:
        tree = ast.parse(block)
        if any(
            isinstance(node, ast.FunctionDef) and node.name == "validate_init_data"
            for node in ast.walk(tree)
        ):
            matches.append(block)

    assert len(matches) == 1, "expected exactly one canonical validate_init_data fence"
    tree = ast.parse(matches[0])
    functions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "validate_init_data"
    ]
    assert len(functions) == 1, "expected exactly one canonical validate_init_data function"

    namespace: dict[str, object] = {}
    exec(compile(matches[0], str(MINI_APPS_PATH), "exec"), namespace)
    validator = namespace.get("validate_init_data")
    assert callable(validator)
    return validator


def sign_init_data(fields: dict[str, str], bot_token: str) -> str:
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode([*fields.items(), ("hash", signature)])


@pytest.mark.parametrize(
    "malformed_hash",
    ["я", "", "a" * 63, "a" * 65, "g" * 64, " " * 64],
)
def test_malformed_hash_raises_value_error(malformed_hash: str) -> None:
    validator = load_canonical_validator()
    raw = urlencode({"auth_date": "1", "hash": malformed_hash})

    with pytest.raises(ValueError) as error:
        validator(raw, BOT_TOKEN, timedelta(minutes=5))

    assert not isinstance(error.value, TypeError)


def test_valid_signed_unicode_data_is_accepted() -> None:
    validator = load_canonical_validator()
    fields = {
        "auth_date": str(int(time.time()) - 2),
        "user": json.dumps({"id": 123, "first_name": "Иван"}, ensure_ascii=False),
    }

    result = validator(sign_init_data(fields, BOT_TOKEN), BOT_TOKEN, timedelta(minutes=5))

    assert result == fields


def test_tampered_hash_is_rejected() -> None:
    validator = load_canonical_validator()
    fields = {"auth_date": str(int(time.time()) - 2)}
    signed_pairs = parse_qsl(sign_init_data(fields, BOT_TOKEN), keep_blank_values=True)
    tampered_pairs = [
        (key, ("0" if value[0] != "0" else "1") + value[1:] if key == "hash" else value)
        for key, value in signed_pairs
    ]

    with pytest.raises(ValueError, match="invalid hash"):
        validator(urlencode(tampered_pairs), BOT_TOKEN, timedelta(minutes=5))


def test_duplicate_init_data_fields_are_rejected() -> None:
    validator = load_canonical_validator()

    with pytest.raises(ValueError, match="duplicate initData field"):
        validator("auth_date=1&auth_date=2&hash=abc", BOT_TOKEN, timedelta(minutes=5))


def test_missing_hash_is_rejected() -> None:
    validator = load_canonical_validator()

    with pytest.raises(ValueError, match="missing hash"):
        validator("auth_date=1", BOT_TOKEN, timedelta(minutes=5))


@pytest.mark.parametrize("offset", [-600, 600], ids=["expired", "future-dated"])
def test_signed_expired_or_future_init_data_is_rejected(offset: int) -> None:
    validator = load_canonical_validator()
    fields = {"auth_date": str(int(time.time()) + offset)}

    with pytest.raises(ValueError, match="expired initData"):
        validator(sign_init_data(fields, BOT_TOKEN), BOT_TOKEN, timedelta(minutes=5))
