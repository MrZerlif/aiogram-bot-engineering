# Native Telegram Presentation and Custom Emoji Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the aiogram skill so an agent can design coherent native Telegram screens, resist emoji slop, and select licensed custom emoji through verified semantic IDs and context-aware fallbacks.

**Architecture:** Keep the entrypoint as a small router. Put screen art direction and anti-slop review in `presentation-and-ux.md`; put capability, registry, sourcing, selection, and owned-pack mechanics in `custom-emoji-system.md`. Prove the behavioral change with the repository's existing recorded control/treatment evaluation format.

**Tech Stack:** Markdown Codex skill, Python 3.10+, pytest, repository contract linter, JSON-form YAML evaluation fixtures, aiogram 3.30.0, aiogram-dialog 2.6.0, Telegram Bot API 10.2.

**Spec:** `docs/superpowers/specs/2026-08-19-native-telegram-presentation-design.md`

## Global Constraints

- `skill/aiogram-bot-engineering/` remains the only installable bundle; maintainer evidence stays outside it.
- The compatibility baseline remains Python 3.10+, aiogram 3.30.0, aiogram-dialog 2.6.0, and Telegram Bot API 10.2.
- Agents select semantic tokens and only registry code resolves verified `custom_emoji_id` values.
- A bot never has Premium; capability is `owner_premium`, `fragment_username`, or `unavailable`, combined with target chat type.
- Owner Premium is not documented as channel permission.
- Public pack links are references, not licenses; no third-party pack is downloaded or bundled.
- Decorative emoji default to zero; labels and critical information work without icons, color, or cover art.
- No live Telegram mutation, commit, push, or publication is part of this plan.

---

### Task 1: RED contracts and control evidence

**Files:**
- Modify: `tests/code/test_lint_skill_contract.py`
- Modify: `tests/code/test_skill_evals.py`
- Modify: `tests/skill-evals/cases.yaml`
- Modify: `tests/skill-evals/baseline-without-skill.md`

**Interfaces:**
- Consumes: the current `REQUIRED_REFERENCE_NAMES`, `REQUIRED_CASE_IDS`, `REQUIRED_TOPICS`, and case schema.
- Produces: required routes for `presentation-and-ux.md` and `custom-emoji-system.md`, plus case IDs `native-presentation-anti-slop` and `custom-emoji-capability-selection`.

- [ ] **Step 1: Extend the required reference contract**

Add the two reference names to `REQUIRED_REFERENCE_NAMES`; the fixture builder will then require both direct routes without asserting prose wording.

- [ ] **Step 2: Add two behavioral case contracts**

Add these IDs to `REQUIRED_CASE_IDS` and the topics `presentation`, `custom-emoji`, and `anti-slop` to `REQUIRED_TOPICS`. Add two JSON objects to `cases.yaml` with exact expected references:

```json
["SKILL.md", "references/presentation-and-ux.md", "references/custom-emoji-system.md", "references/dialogs-and-ui.md"]
```

The presentation case asserts one primary action, restrained semantic icons, fallback-safe labels, useful cover boundaries, and explicit error/destructive states. The emoji case asserts the capability correction, no invented IDs, pack-first style lock, deterministic semantic-token fallback, and license/provenance checks.

- [ ] **Step 3: Record the raw unaided responses**

Append the exact control-run responses under matching level-two headings in `baseline-without-skill.md`; do not edit their mistakes.

- [ ] **Step 4: Verify RED**

Run:

```shell
uv run --locked --group test pytest -q tests/code/test_lint_skill_contract.py tests/code/test_skill_evals.py
```

Expected: failures report the two missing required references, absent treatment evidence, incomplete trace/assertion records, and stale manifest hashes. A syntax/import error is not an acceptable RED result.

---

### Task 2: Presentation and anti-slop guidance

**Files:**
- Create: `skill/aiogram-bot-engineering/references/presentation-and-ux.md`
- Modify: `skill/aiogram-bot-engineering/SKILL.md`

**Interfaces:**
- Consumes: existing native UI mechanics in `dialogs-and-ui.md` and the presentation contract in the spec.
- Produces: a directly routed reference with `PresentationBrief`, `ScreenSpec`, screen-state, anti-slop, and visual-QA decision contracts.

- [ ] **Step 1: Add the smallest direct route**

Add one router row for native visual hierarchy, cover art, button composition, copy, screen states, accessibility, and emoji-slop review.

- [ ] **Step 2: Implement the reference**

Document the positive screen recipe first: brief, screen spec, action hierarchy, message lifecycle, states, and visual review. Add a deterministic rejection gate for filler emoji, mixed families, decorative color, redundant copy, image-only information, emoji-only critical actions, and absent error/destructive states.

- [ ] **Step 3: Run the targeted contract test**

Run:

```shell
uv run --locked --group test pytest -q tests/code/test_lint_skill_contract.py
```

Expected: presentation reference routing passes; the custom-emoji reference may remain the only intentional missing-resource failure until Task 3.

---

### Task 3: Custom emoji capability, registry, and selection

**Files:**
- Create: `skill/aiogram-bot-engineering/references/custom-emoji-system.md`
- Create: `skill/aiogram-bot-engineering/assets/custom-emoji-registry.example.json`
- Modify: `skill/aiogram-bot-engineering/SKILL.md`
- Modify: `skill/aiogram-bot-engineering/references/dialogs-and-ui.md`
- Test: `tests/code/test_emoji_registry_asset.py`

**Interfaces:**
- Consumes: the compatibility baseline and aiogram `Style` mechanics already documented in `dialogs-and-ui.md`.
- Produces: capability input, pack and emoji registry schemas, semantic selection algorithm, fallback ladder, source-license policy, and owned-pack lifecycle.

- [ ] **Step 1: Add the direct route and mechanics handoff**

Route custom emoji system design from `SKILL.md`. Keep the `Style` example in `dialogs-and-ui.md`, but state that its ID must come from the verified registry and route selection/provenance decisions to the new reference.

- [ ] **Step 2: Implement capability and selection contracts**

Document `owner_premium | fragment_username | unavailable`, target-chat checks, semantic tokens, hard filtering, coherence-group lock, collision groups, deterministic ranking, and the fallback ladder ending in no icon.

- [ ] **Step 3: Implement source and owned-pack contracts**

Document license/provenance fields, public-link limits, recommended licensed icon sources, separate adaptive/accent packs, official format boundaries, creation ownership, `getStickerSet` ID retrieval, and bounded ID validation.

- [ ] **Step 4: Add a disabled licensed starter registry**

Map common UI tokens to exact Lucide source icon names in one adaptive
coherence group. Keep every `custom_emoji_id` null, every item disabled, and
the ISC source/license metadata explicit until the owning project creates and
verifies its Telegram set.

- [ ] **Step 5: Verify GREEN for static contracts**

Run:

```shell
uv run --locked --group test python scripts/lint_skill_contract.py .
uv run --locked --group test pytest -q tests/code/test_lint_skill_contract.py
```

Expected: both commands exit zero.

---

### Task 4: Treatment runs and auditable evaluation artifacts

**Files:**
- Modify: `tests/skill-evals/results-with-skill.md`
- Modify: `tests/skill-evals/retrieval-trace.json`
- Modify: `tests/skill-evals/assertion-results.json`
- Modify: `tests/skill-evals/evaluation-summary.md`
- Modify: `tests/skill-evals/run-manifest.json`

**Interfaces:**
- Consumes: the twelve case prompts, the completed installable bundle, and raw control responses.
- Produces: twelve treatment sections, reference traces, assertion judgments tied to literal evidence, derived score summary, and SHA-256 bindings.

- [ ] **Step 1: Run fresh treatment scenarios**

Give a fresh agent only each new prompt, `SKILL.md`, and locally routed resources. Preserve the raw answers under their case IDs and record every reference read.

- [ ] **Step 2: Refactor guidance if treatment exposes a loophole**

If the answer invents an ID, claims universal Premium/channel support, mixes packs for variety, or adds decorative emoji by quota, tighten the positive recipe or conditional contract and rerun the same case.

- [ ] **Step 3: Score all assertions from evidence**

For every new assertion, use either a retrieval-path record, a normalized literal output excerpt, or an explicit missing-evidence reason. Recalculate per-case and aggregate control/treatment scores from these booleans.

- [ ] **Step 4: Bind the completed run**

Update the manifest's bundle hash, artifact hashes, run IDs, dates, allowed context, and limitations after all other artifacts have their final bytes.

- [ ] **Step 5: Verify the evaluation contract**

Run:

```shell
uv run --locked --group test pytest -q tests/code/test_skill_evals.py
```

Expected: every artifact, reference, excerpt, score, and hash check passes.

---

### Task 5: Repository documentation, review, and final verification

**Files:**
- Modify: `README.md` only if routing or evaluation counts need maintainer documentation.
- Review: every file changed since the starting `HEAD`.

**Interfaces:**
- Consumes: the completed bundle and evaluation artifacts.
- Produces: an independently reviewed, validated working tree with no external side effects.

- [ ] **Step 1: Review the final diff against the spec**

Check every acceptance criterion, confirm sources are authoritative, and verify no downloaded emoji asset or fabricated ID entered the bundle.

- [ ] **Step 2: Request independent review**

Give a fresh reviewer the spec, plan, starting SHA, current diff, and test evidence. Resolve every Critical or Important finding and re-review fixes.

- [ ] **Step 3: Run the complete repository checks**

Run:

```shell
uv run --locked --group test python scripts/lint_skill_contract.py .
uv run --locked --group test pytest -q
uv run --locked --group test mypy scripts skill/aiogram-bot-engineering/examples
```

Run the bundled `skill-creator` quick validator against `skill/aiogram-bot-engineering`, then inspect `git diff --check`, `git status --short`, and the complete diff.

- [ ] **Step 4: Report without publishing**

Leave the verified changes in the current working tree. Report changed files, behavioral improvements, test counts, independent review outcome, and any documented limitations; do not commit or push.
