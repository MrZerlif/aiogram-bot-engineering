"""Offline structural and semantic validation for a custom emoji registry."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


ROOT_REQUIRED = {
    "schema_version",
    "catalog_kind",
    "packs",
    "semantic_collision_groups",
    "emoji",
}
ROOT_ALLOWED = ROOT_REQUIRED | {"$schema"}
PACK_REQUIRED = {
    "pack_id",
    "telegram_set_name",
    "telegram_set_origin",
    "coherence_group",
    "status",
    "selection_priority",
    "trust",
    "source_kind",
    "source_url",
    "source_revision",
    "license_spdx",
    "license_url",
    "notice_required",
    "redistribution",
    "allowed_roles",
    "brand_safe",
    "needs_repainting",
    "style",
}
STYLE_REQUIRED = {
    "family",
    "palette",
    "line_weight",
    "detail",
    "animation",
    "mood",
    "density",
}
EMOJI_REQUIRED = {
    "pack_id",
    "token",
    "aliases",
    "source_icon",
    "polarity",
    "state",
    "roles",
    "custom_emoji_id",
    "semantic_description",
    "rich_text_alternative_emoji",
    "fallback_unicode",
    "needs_repainting",
    "enabled",
    "verified_at",
    "review_status",
}
ROLES = {"action", "navigation", "status", "category", "brand_accent"}
PACK_STATUSES = {"template", "active", "disabled", "reference_only"}
TELEGRAM_SET_ORIGINS = {"owned", "public_reference", "unpublished_template"}
SEMANTIC_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
TELEGRAM_SET_NAME = re.compile(
    r"^(?!.*__)[A-Za-z][A-Za-z0-9_]*$"
)
OWNED_TELEGRAM_SET_NAME = re.compile(
    r"^(?!.*__)[A-Za-z][A-Za-z0-9_]*_by_"
    r"[A-Za-z][A-Za-z0-9_]{1,28}[Bb][Oo][Tt]$"
)
CUSTOM_EMOJI_ID = re.compile(r"^[0-9]+$")


def _location(path: str, field: str) -> str:
    return f"{path}.{field}" if path else field


def _check_keys(
    record: dict[str, Any],
    required: set[str],
    allowed: set[str],
    path: str,
    errors: list[str],
) -> None:
    for key in sorted(required - record.keys()):
        errors.append(f"{path}: missing required field {key!r}")
    for key in sorted(record.keys() - allowed):
        errors.append(f"{path}: unknown field {key!r}")


def _nonempty_string(value: Any, path: str, errors: list[str]) -> str | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path}: expected a non-empty string")
        return None
    return value


def _semantic_name(value: Any, path: str, errors: list[str]) -> str | None:
    text = _nonempty_string(value, path, errors)
    if text is not None and SEMANTIC_NAME.fullmatch(text) is None:
        errors.append(f"{path}: expected lowercase semantic name")
        return None
    return text


def _boolean(value: Any, path: str, errors: list[str]) -> bool | None:
    if not isinstance(value, bool):
        errors.append(f"{path}: expected a boolean")
        return None
    return value


def _nullable_string(value: Any, path: str, errors: list[str]) -> str | None:
    if value is None:
        return None
    return _nonempty_string(value, path, errors)


def _uri(value: Any, path: str, errors: list[str], *, nullable: bool = False) -> None:
    if value is None and nullable:
        return
    text = _nonempty_string(value, path, errors)
    if text is None:
        return
    try:
        parsed = urlsplit(text)
    except ValueError:
        errors.append(f"{path}: expected an absolute URI")
        return
    if not parsed.scheme or not parsed.netloc:
        errors.append(f"{path}: expected an absolute URI")


def _timestamp(value: Any, path: str, errors: list[str], *, nullable: bool = True) -> bool:
    if value is None and nullable:
        return True
    text = _nonempty_string(value, path, errors)
    if text is None:
        return False
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{path}: expected an RFC 3339 timestamp")
        return False
    if parsed.tzinfo is None:
        errors.append(f"{path}: timestamp must include a UTC offset")
        return False
    return True


def _semantic_list(
    value: Any,
    path: str,
    errors: list[str],
    *,
    allow_empty: bool,
) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{path}: expected an array")
        return []
    if not value and not allow_empty:
        errors.append(f"{path}: expected at least one item")
    result: list[str] = []
    for index, item in enumerate(value):
        semantic = _semantic_name(item, f"{path}[{index}]", errors)
        if semantic is not None:
            result.append(semantic)
    if len(result) != len(set(result)):
        errors.append(f"{path}: duplicate values are not allowed")
    return result


def _validate_style(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{path}: expected an object")
        return
    _check_keys(value, STYLE_REQUIRED, STYLE_REQUIRED, path, errors)
    for field in sorted(STYLE_REQUIRED & value.keys()):
        _nonempty_string(value[field], _location(path, field), errors)


def _validate_pack_shape(pack: dict[str, Any], path: str, errors: list[str]) -> None:
    _check_keys(pack, PACK_REQUIRED, PACK_REQUIRED, path, errors)
    for field in ("pack_id", "coherence_group"):
        if field in pack:
            _semantic_name(pack[field], _location(path, field), errors)
    for field in ("trust", "source_kind", "redistribution"):
        if field in pack:
            _nonempty_string(pack[field], _location(path, field), errors)
    if "telegram_set_name" in pack and pack["telegram_set_name"] is not None:
        name = _nonempty_string(
            pack["telegram_set_name"],
            _location(path, "telegram_set_name"),
            errors,
        )
        if name is not None and (
            len(name) > 64 or TELEGRAM_SET_NAME.fullmatch(name) is None
        ):
            errors.append(f"{path}.telegram_set_name: invalid Telegram set name")
    origin = pack.get("telegram_set_origin")
    if not isinstance(origin, str) or origin not in TELEGRAM_SET_ORIGINS:
        errors.append(f"{path}.telegram_set_origin: unsupported set origin")
    if origin == "owned":
        name = pack.get("telegram_set_name")
        if (
            not isinstance(name, str)
            or len(name) > 64
            or OWNED_TELEGRAM_SET_NAME.fullmatch(name) is None
        ):
            errors.append(
                f"{path}.telegram_set_name: owned set must end in _by_<bot_username>"
            )
    if origin == "public_reference" and not isinstance(
        pack.get("telegram_set_name"), str
    ):
        errors.append(f"{path}: public_reference requires telegram_set_name")
    if origin == "unpublished_template" and (
        pack.get("telegram_set_name") is not None or pack.get("status") != "template"
    ):
        errors.append(
            f"{path}: unpublished_template requires a null set name and template status"
        )
    if "status" in pack:
        status = pack["status"]
        if not isinstance(status, str) or status not in PACK_STATUSES:
            errors.append(f"{path}.status: unsupported pack status")
    if "selection_priority" in pack:
        priority = pack["selection_priority"]
        if isinstance(priority, bool) or not isinstance(priority, int) or priority < 0:
            errors.append(f"{path}.selection_priority: expected a non-negative integer")
    if "source_url" in pack:
        _uri(pack["source_url"], _location(path, "source_url"), errors)
    if "license_url" in pack:
        _uri(pack["license_url"], _location(path, "license_url"), errors, nullable=True)
    for field in ("source_revision", "license_spdx"):
        if field in pack:
            _nullable_string(pack[field], _location(path, field), errors)
    for field in ("notice_required", "brand_safe", "needs_repainting"):
        if field in pack:
            _boolean(pack[field], _location(path, field), errors)
    if "allowed_roles" in pack:
        roles = _semantic_list(
            pack["allowed_roles"],
            _location(path, "allowed_roles"),
            errors,
            allow_empty=False,
        )
        unknown = sorted(set(roles) - ROLES)
        if unknown:
            errors.append(f"{path}.allowed_roles: unsupported roles {unknown}")
    if "style" in pack:
        _validate_style(pack["style"], _location(path, "style"), errors)


def _validate_emoji_shape(record: dict[str, Any], path: str, errors: list[str]) -> None:
    _check_keys(record, EMOJI_REQUIRED, EMOJI_REQUIRED, path, errors)
    for field in ("pack_id", "token", "source_icon", "state"):
        if field in record:
            _semantic_name(record[field], _location(path, field), errors)
    for field in ("polarity", "semantic_description", "review_status"):
        if field in record:
            _nonempty_string(record[field], _location(path, field), errors)
    if "aliases" in record:
        aliases = _semantic_list(
            record["aliases"],
            _location(path, "aliases"),
            errors,
            allow_empty=True,
        )
        if record.get("token") in aliases:
            errors.append(f"{path}.aliases: token must not repeat as an alias")
    if "roles" in record:
        roles = _semantic_list(
            record["roles"],
            _location(path, "roles"),
            errors,
            allow_empty=False,
        )
        unknown = sorted(set(roles) - ROLES)
        if unknown:
            errors.append(f"{path}.roles: unsupported roles {unknown}")
    if "custom_emoji_id" in record and record["custom_emoji_id"] is not None:
        custom_emoji_id = _nonempty_string(
            record["custom_emoji_id"],
            _location(path, "custom_emoji_id"),
            errors,
        )
        if custom_emoji_id is not None and CUSTOM_EMOJI_ID.fullmatch(custom_emoji_id) is None:
            errors.append(f"{path}.custom_emoji_id: expected a decimal string")
    for field in ("rich_text_alternative_emoji", "fallback_unicode"):
        if field in record:
            _nullable_string(record[field], _location(path, field), errors)
    for field in ("needs_repainting", "enabled"):
        if field in record:
            _boolean(record[field], _location(path, field), errors)
    if "verified_at" in record:
        _timestamp(record["verified_at"], _location(path, "verified_at"), errors)


def validate_registry(document: object) -> list[str]:
    """Return deterministic offline validation errors for ``document``."""

    errors: list[str] = []
    if not isinstance(document, dict):
        return ["registry: expected an object"]
    _check_keys(document, ROOT_REQUIRED, ROOT_ALLOWED, "registry", errors)
    if document.get("schema_version") != 1 or isinstance(document.get("schema_version"), bool):
        errors.append("registry.schema_version: only version 1 is supported")
    if "$schema" in document:
        _nonempty_string(document["$schema"], "registry.$schema", errors)
    if "catalog_kind" in document:
        _nonempty_string(document["catalog_kind"], "registry.catalog_kind", errors)

    raw_packs = document.get("packs")
    if not isinstance(raw_packs, list) or not raw_packs:
        errors.append("registry.packs: expected a non-empty array")
        raw_packs = []
    packs: dict[str, dict[str, Any]] = {}
    for index, pack in enumerate(raw_packs):
        path = f"registry.packs[{index}]"
        if not isinstance(pack, dict):
            errors.append(f"{path}: expected an object")
            continue
        _validate_pack_shape(pack, path, errors)
        pack_id = pack.get("pack_id")
        if isinstance(pack_id, str):
            if pack_id in packs:
                errors.append(f"{path}: duplicate pack_id {pack_id!r}")
            else:
                packs[pack_id] = pack
        if pack.get("status") == "active":
            if not isinstance(pack.get("telegram_set_name"), str) or not pack["telegram_set_name"]:
                errors.append(f"{path}: active pack requires telegram_set_name")
            if (
                not isinstance(pack.get("source_revision"), str)
                or not pack["source_revision"].strip()
            ):
                errors.append(f"{path}: active pack requires a pinned source_revision")

    collision_groups = document.get("semantic_collision_groups")
    if not isinstance(collision_groups, dict):
        errors.append("registry.semantic_collision_groups: expected an object")
    else:
        for group, members in collision_groups.items():
            group_path = f"registry.semantic_collision_groups.{group}"
            _semantic_name(group, group_path, errors)
            values = _semantic_list(members, group_path, errors, allow_empty=False)
            if len(values) < 2:
                errors.append(f"{group_path}: expected at least two distinct meanings")

    raw_emoji = document.get("emoji")
    if not isinstance(raw_emoji, list) or not raw_emoji:
        errors.append("registry.emoji: expected a non-empty array")
        raw_emoji = []
    identities: set[tuple[str, str, str, tuple[str, ...]]] = set()
    role_matches: set[tuple[str, str, str, str]] = set()
    custom_ids: dict[str, int] = {}
    alias_matches: dict[tuple[str, str, str, str], str] = {}
    for index, record in enumerate(raw_emoji):
        path = f"registry.emoji[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{path}: expected an object")
            continue
        _validate_emoji_shape(record, path, errors)
        pack_id = record.get("pack_id")
        token = record.get("token")
        state = record.get("state")
        roles = record.get("roles")
        aliases = record.get("aliases")
        pack = packs.get(pack_id) if isinstance(pack_id, str) else None
        if isinstance(pack_id, str) and pack is None:
            errors.append(f"{path}: unknown pack_id {pack_id!r}")
        if (
            isinstance(pack_id, str)
            and isinstance(token, str)
            and isinstance(state, str)
            and isinstance(roles, list)
            and all(isinstance(role, str) for role in roles)
        ):
            string_roles = [role for role in roles if isinstance(role, str)]
            role_tuple = tuple(sorted(string_roles))
            identity = (pack_id, token, state, role_tuple)
            if identity in identities:
                errors.append(f"{path}: duplicate emoji identity {identity!r}")
            identities.add(identity)
            for role in string_roles:
                role_match = (pack_id, token, state, role)
                if role_match in role_matches:
                    errors.append(f"{path}: duplicate emoji identity for role {role!r}")
                role_matches.add(role_match)
            if isinstance(aliases, list):
                for alias in aliases:
                    if not isinstance(alias, str):
                        continue
                    for role in string_roles:
                        alias_key = (pack_id, state, role, alias)
                        previous = alias_matches.get(alias_key)
                        if previous is not None and previous != token:
                            errors.append(
                                f"{path}: ambiguous alias {alias!r} for role {role!r}; "
                                f"already maps to {previous!r}"
                            )
                        alias_matches[alias_key] = token
        custom_emoji_id = record.get("custom_emoji_id")
        if isinstance(custom_emoji_id, str) and CUSTOM_EMOJI_ID.fullmatch(custom_emoji_id):
            previous_index = custom_ids.get(custom_emoji_id)
            if previous_index is not None:
                errors.append(
                    f"{path}: duplicate custom_emoji_id {custom_emoji_id!r}; "
                    f"already used by registry.emoji[{previous_index}]"
                )
            else:
                custom_ids[custom_emoji_id] = index
        if pack is not None:
            allowed_roles = pack.get("allowed_roles")
            if isinstance(roles, list) and isinstance(allowed_roles, list):
                record_role_names = {role for role in roles if isinstance(role, str)}
                allowed_role_names = {
                    role for role in allowed_roles if isinstance(role, str)
                }
                disallowed = sorted(record_role_names - allowed_role_names)
                if disallowed:
                    errors.append(f"{path}: roles {disallowed} are not allowed by pack {pack_id!r}")
            if (
                isinstance(record.get("needs_repainting"), bool)
                and isinstance(pack.get("needs_repainting"), bool)
                and record["needs_repainting"] is not pack["needs_repainting"]
            ):
                errors.append(f"{path}: needs_repainting does not match pack {pack_id!r}")
        if record.get("enabled") is True:
            if not isinstance(custom_emoji_id, str) or CUSTOM_EMOJI_ID.fullmatch(custom_emoji_id) is None:
                errors.append(f"{path}: enabled record requires a verified custom_emoji_id")
            if record.get("review_status") != "verified":
                errors.append(f"{path}: enabled record requires review_status='verified'")
            if not _timestamp(record.get("verified_at"), f"{path}.verified_at", errors, nullable=False):
                errors.append(f"{path}: enabled record requires verified_at")
            if pack is None or pack.get("status") != "active":
                errors.append(f"{path}: enabled record requires an active pack")
    return errors


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        print(
            "usage: python validate_custom_emoji_registry.py <registry.json>",
            file=sys.stderr,
        )
        return 2
    path = Path(arguments[0])
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"{path}: invalid JSON: {exc.msg} (line {exc.lineno})", file=sys.stderr)
        return 1
    except (OSError, UnicodeDecodeError) as exc:
        print(f"{path}: cannot read registry: {exc}", file=sys.stderr)
        return 1
    errors = validate_registry(document)
    if errors:
        print(f"{path}: registry validation failed", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"{path}: valid custom emoji registry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
