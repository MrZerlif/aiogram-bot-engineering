"""Deterministic, dependency-free contract validator for this skill package."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


REQUIRED_FILES = (
    "SKILL.md",
    "README.md",
    "LICENSE",
    "agents/openai.yaml",
    "examples/dialog-bot.py",
    "scripts/validate_skill.py",
    "references/architecture.md",
    "references/dialogs-and-ui.md",
    "references/rich-messages.md",
    "references/mini-apps.md",
    "references/payments.md",
    "references/deployment.md",
)
REFERENCE_ROUTES = {
    "references/architecture.md",
    "references/dialogs-and-ui.md",
    "references/rich-messages.md",
    "references/mini-apps.md",
    "references/payments.md",
    "references/deployment.md",
}
PROHIBITED_IMPORT_ROOTS = {
    "telebot",
    "telegram",
    "telethon",
    "pyrogram",
    "hydrogram",
    "pytgcalls",
    "tdlib",
}
PLACEHOLDER = re.compile(
    r"\b(?:TODO|TBD|FIXME|generated placeholder|replace[- ]me|your[-_ ](?:name|token|owner))\b",
    re.IGNORECASE,
)
APPROVED_INTERNAL_DIRECTORIES = {".git", ".superpowers"}
EXECUTABLE_FENCE_LANGUAGES = {
    "python", "py", "python3", "shell", "sh", "bash", "powershell", "ps1",
    "js", "javascript", "ts", "typescript", "http",
}
PYTHON_FENCE_LANGUAGES = {"python", "py", "python3"}
SCRIPT_FENCE_LANGUAGES = {"js", "javascript", "ts", "typescript"}
PROHIBITED_CALL_NAMES = {"TelegramClient", "TeleBot", "Pyrogram"}
RAW_API_HOST = "api.telegram" + ".org"
PROHIBITED_SCRIPT_FRAMEWORK = re.compile(
    r"(?is)(?:from\s*|require\s*\(\s*|import\s*\(\s*)"
    r"['\"](?:@grammyjs/[^'\"]+|grammy|telegraf|node-telegram-bot-api)(?:/[^'\"]*)?['\"]"
    r"|\bnew\s+Telegraf\s*\(",
)


def _is_approved_internal(relative: Path) -> bool:
    return bool(relative.parts) and relative.parts[0] in APPROVED_INTERNAL_DIRECTORIES


def _files(root: Path, suffix: str) -> list[Path]:
    return sorted(
        path
        for path in root.rglob(f"*{suffix}")
        if not _is_approved_internal(path.relative_to(root))
    )


def _read(path: Path, errors: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"cannot read {path}: {exc}")
        return ""


def _frontmatter(skill: str, errors: list[str]) -> tuple[dict[str, str], str]:
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", skill, re.DOTALL)
    if not match:
        errors.append("SKILL.md must begin with YAML frontmatter")
        return {}, skill
    values: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, separator, value = line.partition(":")
        if separator:
            values[key.strip()] = value.strip().strip('"\'')
    return values, match.group(2)


def _local_link(destination: str) -> str | None:
    destination = destination.strip()
    if destination.startswith("<") and destination.endswith(">"):
        destination = destination[1:-1].strip()
    # Markdown permits an optional quoted title after a destination.
    destination = destination.split(maxsplit=1)[0] if destination else destination
    parsed = urlsplit(destination)
    if not destination or destination.startswith("#") or parsed.scheme or destination.startswith("//"):
        return None
    return unquote(parsed.path)


def _fenced_blocks(text: str) -> tuple[list[tuple[str, str]], str]:
    """Return executable fenced blocks and text with those blocks blanked."""
    lines = text.splitlines(keepends=True)
    blocks: list[tuple[str, str]] = []
    stripped = lines[:]
    index = 0
    opener = re.compile(r"^\s{0,3}([`~])\1{2,}([^\n]*)$")
    while index < len(lines):
        match = opener.match(lines[index].rstrip("\r\n"))
        if not match:
            index += 1
            continue
        marker = match.group(1)
        length = len(lines[index].lstrip()) - len(lines[index].lstrip(marker))
        language = match.group(2).strip()
        end = index + 1
        closer = re.compile(rf"^\s{{0,3}}{re.escape(marker)}{{{length},}}\s*$")
        while end < len(lines) and not closer.match(lines[end].rstrip("\r\n")):
            end += 1
        if end == len(lines):
            index += 1
            continue
        blocks.append((language, "".join(lines[index + 1:end])))
        for position in range(index, end + 1):
            stripped[position] = "\n" if lines[position].endswith(("\n", "\r")) else ""
        index = end + 1
    return blocks, "".join(stripped)


def _balanced(text: str, start: int, opening: str, closing: str) -> tuple[str, int] | None:
    if start >= len(text) or text[start] != opening:
        return None
    depth = 1
    index = start + 1
    while index < len(text):
        character = text[index]
        if character == "\\":
            index += 2
            continue
        if character == opening:
            depth += 1
        elif character == closing:
            depth -= 1
            if depth == 0:
                return text[start + 1:index], index + 1
        index += 1
    return None


def _reference_definitions(text: str) -> dict[str, str]:
    definitions: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}\[([^\]]+)\]:\s*(<[^>]+>|\S+)", line)
        if match:
            definitions[match.group(1).casefold()] = match.group(2)
    return definitions


def _markdown_destinations(text: str) -> tuple[list[str], list[str]]:
    """Parse balanced inline links plus reference definitions and uses."""
    definitions = _reference_definitions(text)
    destinations = list(definitions.values())
    unresolved_references: list[str] = []
    index = 0
    while index < len(text):
        if text[index] != "[" or (index and text[index - 1] == "\\"):
            index += 1
            continue
        label = _balanced(text, index, "[", "]")
        if label is None:
            index += 1
            continue
        label_text, after_label = label
        if after_label < len(text) and text[after_label] == "(":
            destination = _balanced(text, after_label, "(", ")")
            if destination is not None:
                destinations.append(destination[0])
                index = destination[1]
                continue
        if after_label < len(text) and text[after_label] == "[":
            reference = _balanced(text, after_label, "[", "]")
            if reference is not None:
                reference_id = (reference[0] or label_text).casefold()
                target = definitions.get(reference_id)
                if target is None:
                    unresolved_references.append(reference_id)
                else:
                    destinations.append(target)
                index = reference[1]
                continue
        index = after_label
    return destinations, unresolved_references


def _check_markdown_links(root: Path, path: Path, text: str, errors: list[str]) -> None:
    _, prose = _fenced_blocks(text)
    destinations, unresolved_references = _markdown_destinations(prose)
    for reference in unresolved_references:
        errors.append(f"unresolved local link in {path.relative_to(root)}: reference [{reference}]")
    for destination in destinations:
        local = _local_link(destination)
        if local is None:
            continue
        resolved = (path.parent / local).resolve()
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            errors.append(f"unresolved local link in {path.relative_to(root)}: {local}")
            continue
        if not resolved.is_file():
            errors.append(f"unresolved local link in {path.relative_to(root)}: {local}")


def _dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _python_findings(tree: ast.AST) -> set[str]:
    findings: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            if any(name.split(".", 1)[0] in PROHIBITED_IMPORT_ROOTS for name in names):
                findings.add("framework")
        if isinstance(node, ast.Call):
            called = _dotted_name(node.func)
            if called.split(".", 1)[0] in PROHIBITED_IMPORT_ROOTS or called.rsplit(".", 1)[-1] in PROHIBITED_CALL_NAMES:
                findings.add("framework")
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and RAW_API_HOST in node.value.lower():
            findings.add("raw-http")
    return findings


def _append_findings(findings: set[str], relative: Path, errors: list[str], suffix: str = "") -> None:
    if "framework" in findings:
        errors.append(f"prohibited executable framework or MTProto {suffix}in {relative}")
    if "raw-http" in findings:
        errors.append(f"prohibited executable raw Bot API HTTP {suffix}in {relative}")


def _check_python(path: Path, root: Path, errors: list[str]) -> None:
    source = _read(path, errors)
    if not source:
        return
    try:
        compile(source, str(path), "exec")
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        errors.append(f"invalid Python in {path.relative_to(root)}: {exc.msg} (line {exc.lineno})")
        return
    _append_findings(_python_findings(tree), path.relative_to(root), errors)


def _check_executable_fences(root: Path, path: Path, text: str, errors: list[str]) -> None:
    blocks, _ = _fenced_blocks(text)
    for language, code in blocks:
        fence_language = language.strip().lower().split(maxsplit=1)[0] if language.strip() else ""
        if fence_language not in EXECUTABLE_FENCE_LANGUAGES:
            continue
        if fence_language in PYTHON_FENCE_LANGUAGES:
            try:
                _append_findings(_python_findings(ast.parse(code)), path.relative_to(root), errors, "example ")
            except SyntaxError:
                if re.search(r"\b(?:from|import)\s+(?:telebot|telegram|telethon|pyrogram|hydrogram|pytgcalls|tdlib)\b", code):
                    errors.append(f"prohibited executable framework or MTProto example in {path.relative_to(root)}")
                if re.search(r"\b(?:TelegramClient|TeleBot|Pyrogram)\s*\(", code):
                    errors.append(f"prohibited executable framework or MTProto example in {path.relative_to(root)}")
                if RAW_API_HOST in code.lower():
                    errors.append(f"prohibited executable raw Bot API HTTP example in {path.relative_to(root)}")
        else:
            findings: set[str] = set()
            if fence_language in SCRIPT_FENCE_LANGUAGES and PROHIBITED_SCRIPT_FRAMEWORK.search(code):
                findings.add("framework")
            if RAW_API_HOST in code.lower():
                findings.add("raw-http")
            _append_findings(findings, path.relative_to(root), errors, "example ")


def _require_fragments(root: Path, relative: str, fragments: tuple[str, ...], errors: list[str]) -> None:
    path = root / relative
    if not path.is_file():
        return
    text = _read(path, errors).lower()
    missing = [fragment for fragment in fragments if fragment.lower() not in text]
    if missing:
        errors.append(f"missing required invariant in {relative}: {', '.join(missing)}")


def _check_invariants(root: Path, errors: list[str]) -> None:
    _require_fragments(root, "SKILL.md", ("3.30.0", "2.6.0", "10.2", "server-side", "idempotently"), errors)
    _require_fragments(root, "references/architecture.md", ("Router", "Dispatcher", "BaseStorage", "MemoryStorage", "persistent", "polling", "webhook"), errors)
    _require_fragments(root, "references/deployment.md", ("SimpleRequestHandler", "setup_application", "secret_token", "allowed_updates", "get_webhook_info"), errors)
    _require_fragments(root, "references/dialogs-and-ui.md", ("Dialog", "Window", "StatesGroup", "setup_dialogs", "emoji_id"), errors)
    _require_fragments(root, "references/rich-messages.md", ("InputRichMessage", "RichBlock", "send_rich_message", "send_rich_message_draft", "32768", "500", "16", "50", "20", "0–24"), errors)
    _require_fragments(root, "references/mini-apps.md", ("parse_qsl", "data_check_string", "hmac.new", "hmac.compare_digest", "auth_date", "server-side authorization"), errors)
    _require_fragments(root, "references/payments.md", ("No payments", "XTR", "physical", "external checkout", "pre_checkout_query", "successful_payment", "idempotent"), errors)


def _check_readme_and_license(root: Path, errors: list[str]) -> None:
    readme_path = root / "README.md"
    if readme_path.is_file():
        headings = re.findall(r"^##\s+(.+?)\s*$", _read(readme_path, errors), re.MULTILINE)
        expected = ["Purpose", "Compatibility", "Installation", "Invocation"]
        if headings != expected:
            errors.append("README.md must contain only Purpose, Compatibility, Installation, and Invocation sections")
        if not re.search(r"https://(?:docs\.aiogram\.dev|core\.telegram\.org)/", _read(readme_path, errors)):
            errors.append("README.md must link to official documentation")
    license_path = root / "LICENSE"
    if license_path.is_file():
        license_text = _read(license_path, errors)
        if "MIT License" not in license_text or "Copyright (c) 2026 aiogram-bot-engineering contributors" not in license_text:
            errors.append("LICENSE must be the required MIT contributors license")


def _check_package_set(root: Path, errors: list[str]) -> None:
    approved = {Path(relative) for relative in REQUIRED_FILES}
    approved_directories = {Path()}
    for path in approved:
        approved_directories.update(path.parents)
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if _is_approved_internal(relative):
            continue
        if path.is_dir() and relative not in approved_directories:
            errors.append(f"unexpected package directory: {relative.as_posix()}")
        elif path.is_file() and relative not in approved:
            errors.append(f"unexpected package file: {relative.as_posix()}")


def _check_placeholders(root: Path, errors: list[str]) -> None:
    text_paths = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and not _is_approved_internal(path.relative_to(root))
        and (path.suffix in {".md", ".py", ".yaml", ".yml", ".txt"} or path.name == "LICENSE")
    ]
    validator = root / "scripts" / "validate_skill.py"
    for path in sorted(text_paths):
        if path.resolve() == validator.resolve():
            continue
        if PLACEHOLDER.search(_read(path, errors)):
            errors.append(f"placeholder marker in {path.relative_to(root)}")


def validate(root: Path) -> list[str]:
    """Return every deterministic package-contract error under *root*."""
    root = Path(root).resolve()
    errors: list[str] = []
    if not root.is_dir():
        return [f"root does not exist or is not a directory: {root}"]

    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            errors.append(f"missing required file: {relative}")
    _check_package_set(root, errors)
    _check_placeholders(root, errors)

    markdown_sources = _files(root, ".md")
    for path in markdown_sources:
        text = _read(path, errors)
        _check_markdown_links(root, path, text, errors)
        _check_executable_fences(root, path, text, errors)

    skill_text = _read(root / "SKILL.md", errors)
    frontmatter, body = _frontmatter(skill_text, errors)
    if frontmatter.get("name") != "aiogram-bot-engineering":
        errors.append("frontmatter name must be aiogram-bot-engineering")
    description = frontmatter.get("description", "").lower()
    for trigger in ("telegram", "bot", "python", "aiogram", "dialog", "rich", "mini app", "payment", "webhook"):
        if trigger not in description:
            errors.append(f"frontmatter description is not trigger-oriented: missing {trigger}")
    if len(re.findall(r"\S+", body)) > 500:
        errors.append("SKILL.md exceeds 500 words")
    routes = set(re.findall(r"references/[A-Za-z0-9_-]+\.md", skill_text))
    if routes != REFERENCE_ROUTES:
        errors.append("SKILL reference routes must be exactly the approved six")

    _check_readme_and_license(root, errors)
    _check_invariants(root, errors)
    for path in _files(root, ".py"):
        _check_python(path, root, errors)
    return errors


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) > 1:
        print("usage: python scripts/validate_skill.py [root]", file=sys.stderr)
        return 2
    root = Path(arguments[0]) if arguments else Path(__file__).resolve().parents[1]
    errors = validate(root)
    if errors:
        print("Skill validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Skill validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
