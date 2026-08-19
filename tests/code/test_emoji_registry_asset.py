from __future__ import annotations

import json
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = (
    REPOSITORY_ROOT
    / "skill"
    / "aiogram-bot-engineering"
    / "assets"
    / "custom-emoji-registry.example.json"
)
REFERENCE_PATH = (
    REPOSITORY_ROOT
    / "skill"
    / "aiogram-bot-engineering"
    / "references"
    / "custom-emoji-system.md"
)
RICH_MESSAGES_REFERENCE_PATH = (
    REPOSITORY_ROOT
    / "skill"
    / "aiogram-bot-engineering"
    / "references"
    / "rich-messages.md"
)
REQUIRED_TOKENS = {
    "payment",
    "profile",
    "servers",
    "support",
    "back",
    "warning",
    "delete",
    "connect",
    "devices",
    "locations",
    "retry",
    "settings",
    "success",
    "error",
    "home",
}
EXPECTED_SOURCE_ICONS = {
    "payment": "credit-card",
    "profile": "circle-user-round",
    "servers": "server",
    "support": "headset",
    "back": "arrow-left",
    "warning": "triangle-alert",
    "delete": "trash-2",
    "connect": "shield-check",
    "devices": "monitor-smartphone",
    "locations": "map-pin",
    "retry": "rotate-cw",
    "settings": "settings",
    "success": "circle-check",
    "error": "circle-x",
    "home": "house",
}


def test_starter_registry_is_coherent_licensed_and_unbound() -> None:
    """Catch shipping a mixed, unlicensed, or pre-enabled example catalog."""

    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    packs = {pack["pack_id"]: pack for pack in data["packs"]}
    starter_pack = packs["lucide_ui_adaptive"]

    assert data["schema_version"] == 1
    assert starter_pack["coherence_group"] == "lucide_ui_v1"
    assert starter_pack["source_url"] == "https://github.com/lucide-icons/lucide"
    assert starter_pack["license_spdx"] == "ISC"
    assert starter_pack["needs_repainting"] is True
    assert starter_pack["status"] == "template"
    assert starter_pack["selection_priority"] == 100

    emoji = data["emoji"]
    tokens = [item["token"] for item in emoji]
    source_icons = [item["source_icon"] for item in emoji]
    assert REQUIRED_TOKENS <= set(tokens)
    assert len(tokens) == len(set(tokens))
    assert len(source_icons) == len(set(source_icons))
    assert {item["token"]: item["source_icon"] for item in emoji} == EXPECTED_SOURCE_ICONS

    for item in emoji:
        assert item["pack_id"] in packs
        assert item["custom_emoji_id"] is None
        assert item["enabled"] is False
        assert item["review_status"] == "awaiting_telegram_id"
        assert item["semantic_description"].strip()
        assert item["rich_text_alternative_emoji"] is None
        assert "alternative_text" not in item

    collision_tokens = {
        token
        for group in data["semantic_collision_groups"].values()
        for token in group
    }
    assert {"payment", "warning", "error", "delete", "success"} <= collision_tokens


def test_custom_emoji_reference_keeps_selection_and_provenance_deterministic() -> None:
    """Guard the API-shaped Rich Text fallback and set-membership checks."""

    content = REFERENCE_PATH.read_text(encoding="utf-8")

    for required_contract in (
        "RichTextCustomEmoji.alternative_text",
        "rich_text_alternative_emoji",
        "selection_priority",
        "lexical `pack_id`",
        "whole screen under one compatible pack",
        "atomically replace the exact pack lock",
        "missing, duplicate, or",
        "registry pack's `telegram_set_name`",
    ):
        assert required_contract in content


def test_rich_message_example_uses_registry_values_not_literal_ids_or_words() -> None:
    """Keep RichTextCustomEmoji aligned with the semantic registry contract."""

    content = RICH_MESSAGES_REFERENCE_PATH.read_text(encoding="utf-8")

    assert 'custom_emoji_id="5368324170671202286"' not in content
    assert 'alternative_text="star"' not in content
    assert "reviewed_alternative_emoji" in content
    assert "verified_custom_emoji_id is None or reviewed_alternative_emoji is None" in content
