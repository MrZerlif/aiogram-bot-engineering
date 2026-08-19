# Aiogram Bot Engineering

## Repository and installed bundle

This repository contains two distinct layers:

- `skill/aiogram-bot-engineering/` is the complete installable Codex skill
  bundle. It contains `SKILL.md`, UI metadata, focused references, and the
  import-safe example.
- The repository root contains maintainer tooling: this README, contract
  scripts, code tests, CI configuration, and behavioral evaluation evidence.
  Those files support development and are not part of the installed skill.

## Compatibility

The bundle targets Python 3.10 or newer, aiogram 3.30.0, aiogram-dialog 2.6.0,
and Telegram Bot API 10.2. These are dated compatibility targets rather than a
claim that each dependency is the newest release. Verify upstream documentation
before version-sensitive work.

The repository's test dependency group pins the two framework versions used by
the guidance and example:

```shell
uv sync --locked --group test
```

## Install the bundle

Copy the bundle directory into the Codex skills directory:

```shell
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R skill/aiogram-bot-engineering "${CODEX_HOME:-$HOME/.codex}/skills/"
```

For a development checkout, link it instead so local bundle edits are available
immediately:

```shell
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
ln -s "$PWD/skill/aiogram-bot-engineering" "${CODEX_HOME:-$HOME/.codex}/skills/aiogram-bot-engineering"
```

Only copy or link `skill/aiogram-bot-engineering/`; installing the repository
root would expose QA artifacts as though they were skill content.

## Invoke the skill

Ask Codex to use `$aiogram-bot-engineering` while designing, implementing,
reviewing, or deploying an aiogram bot. For example:

```text
Use $aiogram-bot-engineering to design a two-window aiogram-dialog flow.
```

## Repository QA

From the repository root, synchronize the test group and run the same checks as
CI:

```shell
uv sync --locked --group test
uv run --locked --group test python scripts/lint_skill_contract.py .
uv run --locked --group test pytest -q
uv run --locked --group test mypy scripts skill/aiogram-bot-engineering/examples
```

The example-specific smoke check can also be run directly:

```shell
uv run --locked --group test pytest -q tests/code/test_dialog_bot.py
```

It imports `skill/aiogram-bot-engineering/examples/dialog-bot.py` by file path
and constructs its rich message, dialog, router, and dispatcher without reading
a bot token, creating a `Bot`, polling, or making a network request.

## Behavioral evaluation evidence

[`tests/skill-evals/cases.yaml`](tests/skill-evals/cases.yaml) defines the
deterministic evaluation cases. Separate Codex subagent conditions produced the
recorded [`baseline-without-skill.md`](tests/skill-evals/baseline-without-skill.md)
control and [`results-with-skill.md`](tests/skill-evals/results-with-skill.md)
treatment. The exact deployed model revision was not exposed, so the repository
does not claim byte-for-byte reproducibility or platform-signed independence.
[`run-manifest.json`](tests/skill-evals/run-manifest.json) records runner task
identities, allowed context, the base commit, the exact evaluated working-bundle
hash, and artifact hashes;
[`retrieval-trace.json`](tests/skill-evals/retrieval-trace.json) discloses the
self-reported shared-batch and isolated-runner read sets. Assertion-level scores
and literal output evidence live in
[`assertion-results.json`](tests/skill-evals/assertion-results.json), with the
derived human-readable comparison in
[`evaluation-summary.md`](tests/skill-evals/evaluation-summary.md).

Pytest validates the artifacts' structure and bundle-reference reachability.
CI does not invoke a model or regenerate the recorded runs.
