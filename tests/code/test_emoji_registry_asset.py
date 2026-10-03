from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import re
from types import ModuleType

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.validators import validator_for


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = (
    REPOSITORY_ROOT
    / "skill"
    / "aiogram-bot-engineering"
    / "assets"
    / "custom-emoji-registry.example.json"
)
SCHEMA_PATH = REGISTRY_PATH.with_name("custom-emoji-registry.schema.json")
VALIDATOR_PATH = (
    REPOSITORY_ROOT
    / "skill"
    / "aiogram-bot-engineering"
    / "scripts"
    / "validate_custom_emoji_registry.py"
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


def load_starter_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def errors_with_context(errors) -> list:
    nested = []
    for error in errors:
        nested.append(error)
        nested.extend(errors_with_context(error.context))
    return nested


def load_registry_validator() -> ModuleType:
    assert VALIDATOR_PATH.is_file(), "the installable bundle must ship its offline validator"
    spec = importlib.util.spec_from_file_location("custom_emoji_registry_validator", VALIDATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    assert starter_pack["telegram_set_origin"] == "unpublished_template"
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


def test_registry_schema_is_valid_draft_2020_12_and_accepts_the_starter() -> None:
    """Catch a missing, malformed, or starter-incompatible JSON Schema."""

    assert SCHEMA_PATH.is_file(), "the installable bundle must ship its registry schema"
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    schema_validator = validator_for(schema)
    schema_validator.check_schema(schema)

    errors = list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(
            load_starter_registry()
        )
    )

    assert errors == []


def test_registry_schema_rejects_a_pack_without_an_identity() -> None:
    """Catch a schema that accepts structurally unusable pack records."""

    assert SCHEMA_PATH.is_file(), "the installable bundle must ship its registry schema"
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    document = load_starter_registry()
    del document["packs"][0]["pack_id"]

    errors = list(Draft202012Validator(schema).iter_errors(document))

    assert errors


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_url", "https://[broken"),
        ("source_url", "not an absolute URI"),
        ("license_url", "https://[broken"),
        ("license_url", "not an absolute URI"),
    ],
)
def test_schema_rejects_malformed_uri_fields(field: str, value: str) -> None:
    document = load_starter_registry()
    document["packs"][0][field] = value
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    errors = list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document)
    )

    assert any(
        error.validator == "format"
        and list(error.absolute_path) == ["packs", 0, field]
        for error in errors_with_context(errors)
    )


@pytest.mark.parametrize(
    "value",
    [
        "not-a-date",
        "2026-13-40T00:00:00Z",
        "2026-08-20T00:00:00",
    ],
)
def test_schema_rejects_malformed_verified_at(value: str) -> None:
    document = load_starter_registry()
    document["emoji"][0]["verified_at"] = value
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    errors = list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document)
    )

    assert any(
        error.validator == "format"
        and list(error.absolute_path) == ["emoji", 0, "verified_at"]
        for error in errors_with_context(errors)
    )


def test_schema_rejects_malformed_schema_uri_reference() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    malformed = load_starter_registry()
    malformed["$schema"] = "http://[broken"
    malformed_errors = list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(malformed)
    )
    assert any(
        error.validator == "format" and list(error.absolute_path) == ["$schema"]
        for error in errors_with_context(malformed_errors)
    )

    relative = load_starter_registry()
    relative["$schema"] = "./custom-emoji-registry.schema.json"
    relative_errors = list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(relative)
    )
    assert relative_errors == []


def test_schema_accepts_valid_uri_and_date_time_formats() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    document = load_starter_registry()
    document["$schema"] = "./custom-emoji-registry.schema.json"
    document["packs"][0]["source_url"] = "https://[::1]/icons"
    document["packs"][0]["license_url"] = None

    for verified_at in ("2026-08-20T00:00:00Z", "2026-08-20T00:00:00+03:00"):
        document["emoji"][0]["verified_at"] = verified_at
        errors = list(
            Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document)
        )
        assert errors == []


def test_documented_minimum_registry_example_matches_the_bundled_schema() -> None:
    """Catch documentation that produces a registry the shipped schema rejects."""

    content = REFERENCE_PATH.read_text(encoding="utf-8")
    match = re.search(r"```yaml\n(packs:\n.*?\nemoji:\n.*?)(?:\n```)" , content, re.DOTALL)
    assert match is not None
    excerpt = yaml.safe_load(match.group(1))
    document = {
        "schema_version": 1,
        "catalog_kind": "documentation_example",
        "semantic_collision_groups": {},
        **excerpt,
    }
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    errors = list(Draft202012Validator(schema).iter_errors(document))

    assert errors == []


def test_offline_registry_validator_accepts_the_disabled_starter() -> None:
    """Catch semantic validation that rejects the known-safe starter fixture."""

    validator = load_registry_validator()

    assert validator.validate_registry(load_starter_registry()) == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_url", "https://[broken"),
        ("source_url", "https://example.com\uff1a443/icons"),
        ("license_url", "https://[broken"),
        ("license_url", "https://example.com\uff1a443/icons"),
    ],
)
def test_validator_reports_malformed_url_without_raising(field: str, value: str) -> None:
    validator = load_registry_validator()
    document = load_starter_registry()
    document["packs"][0][field] = value

    errors = validator.validate_registry(document)

    assert f"registry.packs[0].{field}: expected an absolute URI" in errors


@pytest.mark.parametrize("field", ["source_url", "license_url"])
def test_validator_cli_rejects_malformed_url_without_traceback(
    tmp_path: Path,
    capsys,
    field: str,
) -> None:
    validator = load_registry_validator()
    document = load_starter_registry()
    document["packs"][0][field] = "https://[broken"
    registry_path = tmp_path / "malformed-url.json"
    registry_path.write_text(json.dumps(document), encoding="utf-8")

    exit_code = validator.main([str(registry_path)])
    output = capsys.readouterr()

    assert exit_code == 1
    assert f"registry.packs[0].{field}: expected an absolute URI" in output.err
    assert "Traceback" not in output.err


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_url", "https://example.com/icons"),
        ("source_url", "https://[::1]/icons"),
        ("license_url", None),
        ("license_url", "https://example.com/license"),
        ("license_url", "https://[::1]/icons"),
    ],
)
def test_validator_accepts_valid_uri_fields(field: str, value: str | None) -> None:
    validator = load_registry_validator()
    document = load_starter_registry()
    document["packs"][0][field] = value

    errors = validator.validate_registry(document)

    expected_error = f"registry.packs[0].{field}: expected an absolute URI"
    assert expected_error not in errors


def set_unknown_pack(document: dict) -> None:
    document["emoji"][0]["pack_id"] = "missing_pack"


def duplicate_pack(document: dict) -> None:
    document["packs"].append(copy.deepcopy(document["packs"][0]))


def duplicate_emoji_identity(document: dict) -> None:
    document["emoji"].append(copy.deepcopy(document["emoji"][0]))


def duplicate_custom_emoji_id(document: dict) -> None:
    document["emoji"][0]["custom_emoji_id"] = "123456789"
    document["emoji"][1]["custom_emoji_id"] = "123456789"


def enable_unverified_record(document: dict) -> None:
    document["emoji"][0]["enabled"] = True


def mismatch_repainting_contract(document: dict) -> None:
    document["emoji"][0]["needs_repainting"] = False


def use_role_outside_pack_allowlist(document: dict) -> None:
    document["emoji"][0]["roles"] = ["brand_accent"]


def create_ambiguous_alias(document: dict) -> None:
    document["emoji"][1]["aliases"].append("billing")


def use_non_string_pack_role(document: dict) -> None:
    document["packs"][0]["allowed_roles"] = [{"unexpected": "object"}]


def use_non_string_emoji_role(document: dict) -> None:
    document["emoji"][0]["roles"] = [{"unexpected": "object"}]


def use_non_string_pack_status(document: dict) -> None:
    document["packs"][0]["status"] = []


def use_non_string_schema_reference(document: dict) -> None:
    document["$schema"] = {"unexpected": "object"}


@pytest.mark.parametrize(
    ("mutate", "expected_error"),
    [
        (set_unknown_pack, "unknown pack_id"),
        (duplicate_pack, "duplicate pack_id"),
        (duplicate_emoji_identity, "duplicate emoji identity"),
        (duplicate_custom_emoji_id, "duplicate custom_emoji_id"),
        (enable_unverified_record, "enabled record"),
        (mismatch_repainting_contract, "needs_repainting"),
        (use_role_outside_pack_allowlist, "not allowed by pack"),
        (create_ambiguous_alias, "ambiguous alias"),
        (use_non_string_pack_role, "expected a non-empty string"),
        (use_non_string_emoji_role, "expected a non-empty string"),
        (use_non_string_pack_status, "unsupported pack status"),
        (use_non_string_schema_reference, "registry.$schema"),
    ],
)
def test_offline_registry_validator_rejects_nondeterministic_or_unsafe_records(
    mutate,
    expected_error: str,
) -> None:
    """Catch registry states that make selection unsafe or nondeterministic."""

    validator = load_registry_validator()
    document = load_starter_registry()
    mutate(document)

    errors = validator.validate_registry(document)

    assert any(expected_error in error for error in errors)


def test_registry_validator_cli_reports_valid_and_invalid_files(
    tmp_path: Path,
    capsys,
) -> None:
    """Catch a validator whose command-line contract cannot gate project CI."""

    validator = load_registry_validator()
    valid_path = tmp_path / "valid.json"
    invalid_path = tmp_path / "invalid.json"
    invalid_registry_path = tmp_path / "invalid-registry.json"
    valid_path.write_text(json.dumps(load_starter_registry()), encoding="utf-8")
    invalid_path.write_text("{not-json", encoding="utf-8")
    invalid_registry = load_starter_registry()
    invalid_registry["packs"][0]["status"] = []
    invalid_registry_path.write_text(json.dumps(invalid_registry), encoding="utf-8")

    assert validator.main([str(valid_path)]) == 0
    assert validator.main([str(invalid_path)]) == 1
    assert validator.main([str(invalid_registry_path)]) == 1
    output = capsys.readouterr()
    assert "valid" in output.out
    assert "invalid JSON" in output.err


@pytest.mark.parametrize(
    "set_name",
    [
        "__bad",
        "double__underscore_by_examplebot",
        "missing_bot_suffix",
        f"{'a' * 60}_by_examplebot",
    ],
)
def test_schema_and_validator_reject_invalid_telegram_set_names(set_name: str) -> None:
    """Catch set names that Telegram will refuse or that lack bot ownership suffix."""

    document = load_starter_registry()
    document["packs"][0]["telegram_set_origin"] = "owned"
    document["packs"][0]["telegram_set_name"] = set_name
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    schema_errors = list(Draft202012Validator(schema).iter_errors(document))
    semantic_errors = load_registry_validator().validate_registry(document)

    assert schema_errors
    assert any("telegram_set_name" in error for error in semantic_errors)


def test_active_pack_requires_a_nonblank_pinned_source_revision() -> None:
    """Catch active packs whose provenance pin contains only whitespace."""

    document = load_starter_registry()
    pack = document["packs"][0]
    pack["status"] = "active"
    pack["telegram_set_origin"] = "owned"
    pack["telegram_set_name"] = "lucide_ui_adaptive_by_examplebot"
    pack["source_revision"] = "   "
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    schema_errors = list(Draft202012Validator(schema).iter_errors(document))
    semantic_errors = load_registry_validator().validate_registry(document)

    assert schema_errors
    assert any("pinned source_revision" in error for error in semantic_errors)


def test_schema_and_validator_accept_a_well_formed_active_pack() -> None:
    """Catch production constraints that make every active pack impossible."""

    document = load_starter_registry()
    pack = document["packs"][0]
    pack["status"] = "active"
    pack["telegram_set_origin"] = "owned"
    pack["telegram_set_name"] = "lucide_ui_adaptive_by_examplebot"
    pack["source_revision"] = "4f82cfe"
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    schema_errors = list(Draft202012Validator(schema).iter_errors(document))
    semantic_errors = load_registry_validator().validate_registry(document)

    assert schema_errors == []
    assert semantic_errors == []


def test_reference_only_public_set_name_does_not_require_bot_suffix() -> None:
    """Catch applying createNewStickerSet naming rules to an external known set."""

    document = load_starter_registry()
    pack = document["packs"][0]
    pack["telegram_set_origin"] = "public_reference"
    pack["telegram_set_name"] = "RestrictedEmoji"
    pack["status"] = "reference_only"
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    schema_errors = list(Draft202012Validator(schema).iter_errors(document))
    semantic_errors = load_registry_validator().validate_registry(document)

    assert schema_errors == []
    assert semantic_errors == []


def test_public_reference_requires_a_known_set_name() -> None:
    """Catch a public reference that cannot be resolved with getStickerSet."""

    document = load_starter_registry()
    pack = document["packs"][0]
    pack["telegram_set_origin"] = "public_reference"
    pack["telegram_set_name"] = None
    pack["status"] = "reference_only"
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    schema_errors = list(Draft202012Validator(schema).iter_errors(document))
    semantic_errors = load_registry_validator().validate_registry(document)

    assert schema_errors
    assert any("public_reference requires telegram_set_name" in error for error in semantic_errors)


def valid_enabled_registry() -> dict:
    document = load_starter_registry()
    pack = document["packs"][0]
    pack["status"] = "active"
    pack["telegram_set_origin"] = "owned"
    pack["telegram_set_name"] = "lucide_ui_adaptive_by_examplebot"
    pack["source_revision"] = "4f82cfe"
    record = document["emoji"][0]
    record["custom_emoji_id"] = "123456789"
    record["enabled"] = True
    record["verified_at"] = "2026-08-20T00:00:00Z"
    record["review_status"] = "verified"
    return document


@pytest.mark.parametrize(
    ("field", "invalid_value", "expected_error"),
    [
        ("custom_emoji_id", None, "verified custom_emoji_id"),
        ("review_status", "awaiting_telegram_id", "review_status='verified'"),
        ("verified_at", None, "requires verified_at"),
    ],
)
def test_enabled_record_requires_each_verification_field_independently(
    field: str,
    invalid_value,
    expected_error: str,
) -> None:
    """Catch removal of one enabled-record gate hidden by other simultaneous errors."""

    document = valid_enabled_registry()
    document["emoji"][0][field] = invalid_value
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    schema_errors = list(Draft202012Validator(schema).iter_errors(document))
    semantic_errors = load_registry_validator().validate_registry(document)

    assert schema_errors
    assert any(expected_error in error for error in semantic_errors)


def test_enabled_record_requires_an_active_pack_independently() -> None:
    """Catch enabling a verified ID from a disabled or template pack."""

    document = valid_enabled_registry()
    document["packs"][0]["status"] = "template"

    semantic_errors = load_registry_validator().validate_registry(document)

    assert any("requires an active pack" in error for error in semantic_errors)


def test_fully_verified_enabled_record_is_valid() -> None:
    """Catch enabled-record gates that reject a complete production record."""

    document = valid_enabled_registry()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    schema_errors = list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document)
    )
    semantic_errors = load_registry_validator().validate_registry(document)

    assert schema_errors == []
    assert semantic_errors == []


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
