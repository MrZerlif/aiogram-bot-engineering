# Native Telegram Presentation and Custom Emoji Design

## Status and intent

This design extends the existing `aiogram-bot-engineering` skill with the
judgment needed to make native Telegram bot screens feel deliberate rather
than generated. The user approved autonomous implementation and asked for no
further questions. The work stays inside the skill and its repository QA; it
does not publish sticker sets, mutate a live bot, or push repository changes.

## Problem

The skill already explains aiogram-dialog widgets, button styles, and how to
place a known custom emoji ID in a button. It does not yet tell an agent how to
compose a coherent screen, when an icon is useful, how to avoid emoji-heavy AI
slop, how to source a compatible icon family, or what to do when Telegram does
not permit a custom emoji in the current send context.

That gap produces four predictable failures:

1. decoration replaces information hierarchy;
2. unrelated emoji families are mixed on one screen;
3. agents invent IDs or treat a public pack link as a redistribution license;
4. agents assume that a bot itself has Premium, or that an owner's Premium
   entitlement makes button icons work in every chat type.

## Architecture

Keep `SKILL.md` as a concise router and add two focused references:

- `presentation-and-ux.md` owns art direction, screen composition, native
  navigation, copy density, semantic button emphasis, screen states, the
  anti-slop contract, and visual QA.
- `custom-emoji-system.md` owns Telegram capability checks, semantic tokens,
  pack/style locking, deterministic selection, fallback behavior, provenance,
  licensing, owned-pack creation, and ID validation.
- `assets/custom-emoji-registry.example.json` is a copyable, disabled starter
  catalog that maps common UI tokens to one coherent Lucide/ISC source family.
  It contains source icon names and no Telegram IDs or redistributed artwork.

`dialogs-and-ui.md` remains the mechanics reference. It will route readers to
the two new references for presentation decisions instead of duplicating that
policy. The example may demonstrate safe optional icon fallback, but it must
remain import-safe and network-free.

## Presentation contract

Before proposing a styled native screen, the agent creates a compact
presentation brief with these decisions:

- product, audience, top user task, and tone;
- native message/dialog versus Mini App boundary;
- role of the cover image, if any;
- information and action hierarchy;
- icon capability and fallback policy;
- message lifecycle: edit in place, send a new message, or pin;
- loading, empty, error, confirmation, and destructive-action states.

Each screen is then described as a `ScreenSpec`: purpose, content, primary
action, secondary actions, navigation, icon tokens, and state variants. A
cover image may establish brand and context, but critical status or action
instructions must also exist as Telegram text or accessible button labels.

Native menus default to one primary action, a small set of secondary actions,
and explicit Back or Home navigation where needed. Navigation normally edits
the existing message; event/history content may warrant a new message.
Callbacks are acknowledged, stale state has a safe recovery path, and labels
remain understandable without icon shape or button color.

## Anti-slop contract

The output is a restrained design system, not an emoji quota. Decorative emoji
default to zero. An icon earns a place only when it identifies an action,
state, category, or brand accent faster than the label alone.

The gate rejects a screen when any of these conditions hold:

- emoji are used as punctuation, filler, or repeated decoration;
- unrelated visual families appear in one coherence group;
- a critical action is emoji-only or depends on color/icon recognition;
- every button is emphasized, or button colors are decorative rather than
  semantic;
- the same meaning is repeated in cover, heading, body, and button copy;
- a long text wall precedes the action hierarchy;
- critical information exists only inside an image;
- loading, empty, error, confirmation, or destructive states are omitted.

Static review checks the `ScreenSpec` and rendered copy. Visual review checks
light and dark themes, narrow layouts, iOS and Android rendering, longer
localization, and custom emoji enabled and unavailable. The final screen must
still work when every optional icon is removed.

## Custom emoji capability model

Never ask whether the bot has Premium. The runtime capability is configured as
one of:

- `owner_premium`: the bot owner has Telegram Premium; usable only in the
  officially allowed direct-send contexts;
- `fragment_username`: the bot has the required additional username acquired
  through Fragment;
- `unavailable`: render the label without a custom icon.

The selector also receives the target chat type. Owner Premium is not treated
as universal permission and must not be used to claim channel support. Current
Bot API compatibility covers custom icon fields on both reply and inline
keyboard buttons; version-sensitive implementation must still be verified
against official Telegram and aiogram documentation.

## Semantic registry and deterministic selection

Agents output semantic tokens such as `payment`, `profile`, `servers`,
`support`, `back`, `warning`, and `delete`; they never invent a
`custom_emoji_id`. Runtime code resolves a token through a curated registry.

Each pack records identity, Telegram set name, coherence group, status,
stable selection priority, trust/provenance, license, allowed roles, brand safety, and visual style
(family, palette, line weight, detail, animation, mood, density). Each emoji
records its verified ID, token, aliases, polarity/state, allowed roles,
semantic description, reviewed Rich Text alternative Unicode emoji, optional
screen-wide Unicode fallback, repainting behavior, enabled state, verification
time, and review state. The semantic description is never passed as Telegram's
`alternative_text`, whose API contract requires an alternative emoji.

Selection is pack-first:

1. hard-filter packs by capability, target, role, license, brand safety, and
   operational status;
2. retain the screen or flow's exact pack lock, or select one eligible pack by
   explicit priority and stable pack ID within the required coherence group;
3. rank exact token/state matches within that locked pack;
4. resolve collisions conservatively for warning, error, payment, delete, and
   consent meanings;
5. fall back to an exact token in a compatible pack, then a non-mixing Unicode
   fallback, then no icon.

No runtime vision embedding or unconstrained similarity search is required.
Visual models may help during offline ingestion and review, never to improvise
production IDs. No icon is better than an inconsistent or ambiguous icon.

## Catalog strategy and licensing

Use a hybrid catalog:

- public Telegram sets may be stored as reviewed references and verified IDs;
- production-owned adaptive UI packs should be generated from explicitly
  licensed sources, with provenance and license notices retained.

A `t.me/addemoji/<slug>` link proves discoverability, not redistribution or
commercial-use permission. Do not copy or bundle a public set without explicit
rights. Suitable source families include Fluent UI System Icons (MIT), Lucide
(ISC), and Phosphor Icons (MIT), subject to retaining their notices.

Owned packs are split by rendering contract because `needs_repainting` is a
set-level property:

- `brand_ui_adaptive`: monochrome navigation and action icons;
- `brand_accent`: a very small colored or animated brand-accent set.

Both may share a coherence group but must not be mixed merely for variety.

## Telegram pack mechanics

The reference will cover the facts needed for implementation without becoming
an upstream manual:

- create a `custom_emoji` sticker set owned by an explicit human user;
- choose `needs_repainting` per set;
- obey official custom-emoji format and size constraints;
- fetch the created set to obtain Telegram-assigned `custom_emoji_id` values;
- validate known IDs in bounded batches before enabling them in the registry;
- treat set creation and publication as an external mutation requiring
  separate authorization.

## Behavioral evaluation

Extend the repository's recorded evaluation suite with two cases:

1. a native VPN main menu that pressures the agent to “add beautiful emoji”;
2. a custom-emoji catalog request containing false Premium/channel
   assumptions and pressure to choose arbitrary public IDs.

The control condition receives only the prompts. The treatment condition may
read `SKILL.md` and routed references. Assertions measure retrieval plus
observable decisions: coherent hierarchy, restrained icon use, fallback-safe
labels, capability correction, semantic token resolution, style lock,
provenance, and refusal to invent IDs. Raw output evidence, retrieval paths,
assertion judgments, hashes, and arithmetic remain auditable under the current
repository protocol.

## Acceptance criteria

- Both references are directly routed from `SKILL.md` and have no broken local
  links or executable examples.
- The starter registry parses as JSON, preserves source/license provenance,
  covers common UI tokens, and cannot enable an unverified Telegram ID.
- Existing mechanics remain version-targeted and internally consistent.
- The new RED tests fail before the references exist and pass after them are
  implemented.
- Recorded treatment responses satisfy every new application and gap
  assertion; control failures are documented honestly.
- Contract lint, full pytest, mypy, and the skill quick validator pass.
- No live Telegram mutation, downloaded third-party pack, commit, or push is
  performed.
