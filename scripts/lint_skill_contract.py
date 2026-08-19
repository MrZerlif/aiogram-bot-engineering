"""Static contract checks for the installable aiogram skill bundle."""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit


BUNDLE_RELATIVE = Path("skill/aiogram-bot-engineering")
REQUIRED_BUNDLE_FILES = {
    Path("SKILL.md"),
    Path("agents/openai.yaml"),
    Path("examples/dialog-bot.py"),
    Path("references/architecture.md"),
    Path("references/custom-emoji-system.md"),
    Path("references/deployment.md"),
    Path("references/dialogs-and-ui.md"),
    Path("references/mini-apps.md"),
    Path("references/payments.md"),
    Path("references/presentation-and-ux.md"),
    Path("references/production-engineering.md"),
    Path("references/rich-messages.md"),
    Path("references/testing.md"),
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
PROHIBITED_CALL_NAMES = {"TelegramClient", "TeleBot", "Pyrogram"}
RAW_API_HOST = "api.telegram" + ".org"
PYTHON_FENCE_LANGUAGES = {"python", "py", "python3"}
SCRIPT_FENCE_LANGUAGES = {"js", "javascript", "ts", "typescript"}
EXECUTABLE_FENCE_LANGUAGES = PYTHON_FENCE_LANGUAGES | SCRIPT_FENCE_LANGUAGES | {
    "shell",
    "sh",
    "bash",
    "powershell",
    "ps1",
    "http",
}
PROHIBITED_SCRIPT_FRAMEWORK = re.compile(
    r"(?is)(?:from\s*|require\s*\(\s*|import\s*\(\s*)"
    r"['\"](?:@grammyjs/[^'\"]+|grammy|telegraf|node-telegram-bot-api)(?:/[^'\"]*)?['\"]"
    r"|\bnew\s+Telegraf\s*\("
)


@dataclass(frozen=True)
class SkillRoutes:
    references: set[Path]
    examples: set[Path]


def _read(path: Path, errors: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"cannot read {path}: {exc}")
        return ""


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


def _fenced_blocks(text: str) -> tuple[list[tuple[str, str]], str]:
    lines = text.splitlines(keepends=True)
    blocks: list[tuple[str, str]] = []
    prose = lines[:]
    index = 0
    opener = re.compile(r"^\s{0,3}([`~])\1{2,}([^\n]*)$")
    while index < len(lines):
        match = opener.match(lines[index].rstrip("\r\n"))
        if match is None:
            index += 1
            continue
        marker = match.group(1)
        marker_length = len(lines[index].lstrip()) - len(lines[index].lstrip(marker))
        language = match.group(2).strip()
        closer = re.compile(rf"^\s{{0,3}}{re.escape(marker)}{{{marker_length},}}\s*$")
        end = index + 1
        while end < len(lines) and closer.match(lines[end].rstrip("\r\n")) is None:
            end += 1
        if end == len(lines):
            index += 1
            continue
        blocks.append((language, "".join(lines[index + 1:end])))
        for position in range(index, end + 1):
            prose[position] = "\n" if lines[position].endswith(("\n", "\r")) else ""
        index = end + 1
    return blocks, "".join(prose)


def _reference_definitions(text: str) -> dict[str, str]:
    definitions: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}\[([^\]]+)\]:\s*(<[^>]+>|\S+)", line)
        if match:
            definitions[match.group(1).casefold()] = match.group(2)
    return definitions


def _strip_inline_code(text: str) -> str:
    stripped = list(text)
    index = 0
    while index < len(text):
        if text[index] != "`":
            index += 1
            continue
        opening_end = index
        while opening_end < len(text) and text[opening_end] == "`":
            opening_end += 1
        marker_length = opening_end - index
        closing_start = opening_end
        while closing_start < len(text):
            closing_start = text.find("`", closing_start)
            if closing_start < 0:
                break
            closing_end = closing_start
            while closing_end < len(text) and text[closing_end] == "`":
                closing_end += 1
            if closing_end - closing_start == marker_length:
                for position in range(index, closing_end):
                    if text[position] != "\n":
                        stripped[position] = " "
                index = closing_end
                break
            closing_start = closing_end
        else:
            index = opening_end
        if closing_start < 0:
            index = opening_end
    return "".join(stripped)


def _markdown_destinations(text: str) -> tuple[list[str], list[str]]:
    text = _strip_inline_code(text)
    definitions = _reference_definitions(text)
    destinations: list[str] = []
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
                destination = definitions.get(reference_id)
                if destination is None:
                    unresolved_references.append(reference_id)
                else:
                    destinations.append(destination)
                index = reference[1]
                continue
        index = after_label
    return destinations, unresolved_references


def _local_destination(destination: str) -> str | None:
    destination = destination.strip()
    if destination.startswith("<") and destination.endswith(">"):
        destination = destination[1:-1].strip()
    destination = destination.split(maxsplit=1)[0] if destination else destination
    parsed = urlsplit(destination)
    if not destination or destination.startswith("#") or parsed.scheme or destination.startswith("//"):
        return None
    return unquote(parsed.path)


def _relative_local_destination(bundle_root: Path, source: Path, destination: str) -> Path | None:
    local = _local_destination(destination)
    if local is None:
        return None
    resolved = (source.parent / local).resolve()
    try:
        return resolved.relative_to(bundle_root.resolve())
    except ValueError:
        return Path("..") / local


def inspect_skill_routes(bundle_root: Path) -> SkillRoutes:
    """Return direct reference and example routes declared by ``SKILL.md``."""
    skill = bundle_root / "SKILL.md"
    try:
        text = skill.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return SkillRoutes(references=set(), examples=set())
    _, prose = _fenced_blocks(text)
    destinations, _ = _markdown_destinations(prose)
    references: set[Path] = set()
    examples: set[Path] = set()
    for destination in destinations:
        relative = _relative_local_destination(bundle_root, skill, destination)
        if relative is None or not relative.parts:
            continue
        if relative.parts[0] == "references":
            references.add(relative)
        elif relative.parts[0] == "examples":
            examples.add(relative)
    return SkillRoutes(references=references, examples=examples)


def _check_local_markdown_links(bundle_root: Path, source: Path, text: str, errors: list[str]) -> None:
    _, prose = _fenced_blocks(text)
    destinations, unresolved_references = _markdown_destinations(prose)
    source_relative = source.relative_to(bundle_root)
    for reference in unresolved_references:
        errors.append(f"unresolved local link in {source_relative}: reference [{reference}]")
    for destination in destinations:
        local = _local_destination(destination)
        if local is None:
            continue
        resolved = (source.parent / local).resolve()
        try:
            resolved.relative_to(bundle_root.resolve())
        except ValueError:
            errors.append(f"unresolved local link in {source_relative}: {local}")
            continue
        if not resolved.is_file():
            errors.append(f"unresolved local link in {source_relative}: {local}")


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
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
            if any(name.split(".", 1)[0] in PROHIBITED_IMPORT_ROOTS for name in names):
                findings.add("framework")
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".", 1)[0] in PROHIBITED_IMPORT_ROOTS:
            findings.add("framework")
        elif isinstance(node, ast.Call):
            called = _dotted_name(node.func)
            if (
                called.split(".", 1)[0] in PROHIBITED_IMPORT_ROOTS
                or called.rsplit(".", 1)[-1] in PROHIBITED_CALL_NAMES
            ):
                findings.add("framework")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and RAW_API_HOST in node.value.lower():
            findings.add("raw-http")
    return findings


def _append_findings(findings: set[str], relative: Path, errors: list[str], context: str = "") -> None:
    if "framework" in findings:
        errors.append(f"prohibited executable framework or MTProto {context}in {relative}")
    if "raw-http" in findings:
        errors.append(f"prohibited executable raw Bot API HTTP {context}in {relative}")


def _check_python_source(source: str, label: str, relative: Path, errors: list[str], context: str = "") -> None:
    try:
        code = compile(source, label, "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
        tree = ast.parse(source, filename=label)
        del code
    except SyntaxError as exc:
        errors.append(f"invalid Python {context}in {relative}: {exc.msg} (line {exc.lineno})")
        return
    _append_findings(_python_findings(tree), relative, errors, context)


def _check_executable_fences(bundle_root: Path, path: Path, text: str, errors: list[str]) -> None:
    for language, source in _fenced_blocks(text)[0]:
        fence_language = language.lower().split(maxsplit=1)[0] if language else ""
        if fence_language not in EXECUTABLE_FENCE_LANGUAGES:
            continue
        relative = path.relative_to(bundle_root)
        if fence_language in PYTHON_FENCE_LANGUAGES:
            _check_python_source(source, str(path), relative, errors, "fence ")
            continue
        findings: set[str] = set()
        if fence_language in SCRIPT_FENCE_LANGUAGES and PROHIBITED_SCRIPT_FRAMEWORK.search(source):
            findings.add("framework")
        if RAW_API_HOST in source.lower():
            findings.add("raw-http")
        _append_findings(findings, relative, errors, "example ")


def _resource_files(bundle_root: Path, directory: str) -> set[Path]:
    root = bundle_root / directory
    if not root.is_dir():
        return set()
    return {
        path.relative_to(bundle_root)
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix not in {".pyc", ".pyo"}
    }


def lint_skill_bundle(bundle_root: Path) -> list[str]:
    """Return static bundle-contract violations for ``bundle_root``."""
    bundle_root = Path(bundle_root).resolve()
    if not bundle_root.is_dir():
        return [f"bundle does not exist or is not a directory: {bundle_root}"]
    errors: list[str] = []
    for relative in sorted(REQUIRED_BUNDLE_FILES):
        if not (bundle_root / relative).is_file():
            errors.append(f"missing required file: {relative.as_posix()}")

    routes = inspect_skill_routes(bundle_root)
    for resource in sorted(_resource_files(bundle_root, "references") - routes.references):
        errors.append(f"orphan reference: {resource.as_posix()}")
    for resource in sorted(_resource_files(bundle_root, "examples") - routes.examples):
        errors.append(f"orphan example: {resource.as_posix()}")

    for markdown in sorted(bundle_root.rglob("*.md")):
        text = _read(markdown, errors)
        _check_local_markdown_links(bundle_root, markdown, text, errors)
        _check_executable_fences(bundle_root, markdown, text, errors)
    for python_file in sorted(bundle_root.rglob("*.py")):
        _check_python_source(
            _read(python_file, errors),
            str(python_file),
            python_file.relative_to(bundle_root),
            errors,
        )
    return errors


def lint_repository(repo_root: Path) -> list[str]:
    """Return static contract violations for the repository's skill bundle."""
    return lint_skill_bundle(Path(repo_root) / BUNDLE_RELATIVE)


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) > 1:
        print("usage: python scripts/lint_skill_contract.py [repository-root]", file=sys.stderr)
        return 2
    root = Path(arguments[0]) if arguments else Path.cwd()
    errors = lint_repository(root)
    if errors:
        print("Skill contract lint failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Skill contract lint passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
