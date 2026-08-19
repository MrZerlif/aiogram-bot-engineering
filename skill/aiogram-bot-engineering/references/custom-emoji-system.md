# Custom Emoji System

Read this reference when a bot needs custom emoji in button icons, message
entities, or Rich Messages; when an agent must curate or create a pack; or when
runtime code must choose an icon safely. Read [presentation and UX](presentation-and-ux.md)
first when the larger screen has not yet been composed.

## Separate meaning, asset, and capability

The model chooses a semantic token. A reviewed registry maps that token to a
verified Telegram `custom_emoji_id`. A capability check decides whether that
ID may be sent in the target context. Keep these three decisions separate.

Never ask whether the bot has Telegram Premium: a bot is not a Premium user.
Do not let an LLM invent or autocomplete a numeric ID, scrape a random catalog
at runtime, or choose a new visual family for each button.

## Button capability

Telegram Bot API 10.2 exposes `icon_custom_emoji_id` on both `KeyboardButton`
and `InlineKeyboardButton`. The field is available under either official path:

| Capability | Eligible context |
| --- | --- |
| `fragment_username` | Bot purchased the required additional username on Fragment |
| `owner_premium` | Messages directly sent by the bot to private, group, or supergroup chats while its owner has Premium |
| `unavailable` | Omit the icon and keep the complete text label |

The owner-Premium path does not include channel posts. Channel administrator
rights do not extend it. If channel support is required, use the Fragment path
or an icon-free fallback after verifying the current official documentation.
Reply keyboards have their own channel limitations independently of the icon
field.

Treat capability as deployment configuration plus target chat type; do not
infer it from the viewing user's Premium status:

```yaml
custom_emoji_capability:
  mode: owner_premium  # owner_premium | fragment_username | unavailable
  owner_user_id: 123456789
  target_chat_types: [private, group, supergroup]
```

If the configuration is absent, invalid, or outside its allowed targets,
resolve the screen without custom icons. A failed send caused by a stale
capability must degrade to the same fallback and produce an observable warning,
not a retry loop that keeps sending an invalid payload.

## Semantic registry

Keep pack metadata and individual emoji records distinct. The following is a
minimum decision schema; use a database or versioned data file appropriate to
the project:

```yaml
packs:
  - pack_id: brand_ui_adaptive
    telegram_set_name: brand_ui_adaptive_by_example_bot
    coherence_group: brand_ui_v1
    status: active
    selection_priority: 100
    trust: owned_reviewed
    source_kind: licensed_source
    source_url: https://github.com/lucide-icons/lucide
    license_spdx: ISC
    notice_path: licenses/LUCIDE.txt
    redistribution: allowed_with_notice
    allowed_roles: [action, navigation, status]
    brand_safe: true
    style:
      family: outline
      palette: adaptive_monochrome
      line_weight: regular
      detail: low
      animation: none
      mood: calm
      density: compact

emoji:
  - pack_id: brand_ui_adaptive
    token: payment
    aliases: [billing, subscription, renew]
    polarity: neutral
    state: default
    roles: [action]
    custom_emoji_id: null
    semantic_description: payment or subscription action
    rich_text_alternative_emoji: null
    fallback_unicode: null
    needs_repainting: true
    enabled: false
    verified_at: null
    review_status: awaiting_telegram_id
```

Enable a record only after Telegram returns the ID and the preview has passed
human visual/semantic review. IDs are not secrets, but they are operational
data: record when and from which set they were verified.

Keep `semantic_description` as curator metadata. Telegram
`RichTextCustomEmoji.alternative_text` is not a prose accessibility label: the
Bot API requires an alternative Unicode emoji. Populate
`rich_text_alternative_emoji` only from the reviewed sticker's `emoji` value
or another explicitly reviewed emoji, and pass that value as
`alternative_text`. Never pass a token such as `payment` or `profile`. If it is
still null, render ordinary text instead of constructing a Rich Text custom
emoji. Button labels remain the accessible, authoritative description.

For a concrete starting point, copy
[the disabled Lucide/ISC starter registry](../assets/custom-emoji-registry.example.json).
It maps common bot UI tokens to one licensed source family without bundling
SVG artwork or pretending Telegram IDs already exist. Pin `source_revision`,
retain the ISC notice, create the owned set, then populate and verify IDs in
the copied project registry; do not enable the bundled template itself.

### Tokens, roles, and collisions

Use product semantics such as `payment`, `profile`, `servers`, `support`,
`back`, `warning`, and `delete`, not visual descriptions such as `blue_gem`.
The request to the selector includes:

- token and aliases;
- UI role: action, navigation, status, category, or brand accent;
- state and polarity;
- target chat type and capability mode;
- the current screen or flow's `coherence_group` and exact `pack_id` lock.

Define collision groups for meanings that must not substitute for one another:

- warning versus error;
- payment versus refund or free;
- delete versus archive or remove-from-view;
- consent versus completion;
- connection status versus subscription status.

An approximate visual match never overrides a semantic collision. The visible
label and confirmation copy remain the authority.

## Deterministic selection

Resolve an icon pack-first rather than asking a model to compare the whole
catalog:

1. Hard-filter packs by enabled status, capability, target, UI role, license,
   redistribution policy, brand safety, and operational verification.
2. Reuse the screen or flow's exact `pack_id` lock. If none exists, filter to
   the brief's reviewed `coherence_group`, choose the smallest explicit
   `selection_priority`, break a remaining tie by lexical `pack_id`, and store
   that exact pack lock for the rest of the flow. Never iterate an unordered
   set of eligible packs.
3. Within the locked pack, prefer exact token, exact state, and exact role matches;
   aliases are a lower-priority match.
4. Reject candidates in a semantic collision group or with incompatible
   polarity, animation, density, or repainting behavior.
5. Break remaining ties by stable registry order or an explicit curator rank,
   never by an unconstrained LLM choice.

Runtime vision embeddings are unnecessary. They may help an offline ingestion
tool flag near-duplicates or style outliers, but a human reviews the result and
the runtime selector stays deterministic.

### Fallback ladder

Use the first safe option:

1. exact token in the locked pack;
2. re-resolve the whole screen under one compatible pack from the same
   `coherence_group`, but only when that pack safely resolves every requested
   icon; atomically replace the exact pack lock before rendering anything;
3. an approved screen-wide Unicode family when every displayed icon has a
   coherent Unicode mapping;
4. no icon.

Never fall back to another pack for a single icon while retaining the old
lock. Do not insert one default Unicode emoji among custom icons merely to fill
a gap. When a full screen-wide Unicode switch is not coherent, omit the
missing icon. The button label must still work. No icon is preferable to a
misleading, unlicensed, unverified, or visually inconsistent one.

## Aiogram integration boundary

Resolve the icon before constructing a widget. The UI layer receives either a
verified ID or `None`:

```python
from aiogram.enums import ButtonStyle
from aiogram_dialog.widgets.kbd import Button
from aiogram_dialog.widgets.style import Style
from aiogram_dialog.widgets.text import Const


def payment_button(verified_custom_emoji_id: str | None) -> Button:
    return Button(
        Const("Pay"),
        id="pay",
        style=Style(
            style=ButtonStyle.PRIMARY,
            emoji_id=verified_custom_emoji_id,
        ),
    )
```

The model may request `payment`; it never supplies the function argument. Keep
button text complete and authorize the callback action server-side. For custom
emoji inside Rich Message text, use the reviewed
`rich_text_alternative_emoji` as the API's required `alternative_text`; never
substitute `semantic_description`. Apply the same registry/capability decision
before constructing the rich text node, and fall back to ordinary text while
the alternative emoji is unreviewed.

## Public sets and provenance

A public `t.me/addemoji/<slug>` link is a deep link for opening or importing a
set. It is not a copyright license. Telegram grants only limited platform data
access needed to operate a legitimate bot and requires compliance with the
rightful owner's copyright terms. Therefore:

- store a public set only as a reviewed reference with its known set name and
  verified IDs needed by the bot;
- record creator/source, review date, permitted use, and evidence of permission;
- do not bundle previews, extract artwork, republish the set, or claim
  commercial rights without an explicit license or authorization;
- mark unknown rights as `reference_only` and exclude the asset from owned-pack
  generation and redistribution.

The Bot API can retrieve a known set by name and validate known IDs; it does not
provide a global semantic search for custom emoji. Manual curation is the safe
ingestion path inside this skill. MTProto search remains outside this skill's
implementation boundary.

## Owned production packs

For durable product UI, prefer a small owned pack built from assets with an
explicit license. Suitable coherent source families include
[Fluent UI System Icons (MIT)](https://github.com/microsoft/fluentui-system-icons),
[Lucide (ISC)](https://github.com/lucide-icons/lucide), and
[Phosphor Icons (MIT)](https://github.com/phosphor-icons/core). Retain license
notices and source provenance, and review trademarks or brand-specific artwork
separately.

Split packs by rendering contract because `needs_repainting` applies to the
whole custom emoji set:

- `brand_ui_adaptive`: simple monochrome action/navigation/status icons with
  repainting enabled;
- `brand_accent`: a very small colored or animated brand set with repainting
  disabled.

They may share a coherence group after visual review. Do not mix them merely
for variety, and do not use an accent icon as a substitute for a missing
destructive or status meaning.

## Creation and verification lifecycle

Publishing a Telegram set changes external state. Prepare files and a manifest
locally, but obtain explicit authorization immediately before upload or set
creation.

For Bot API 10.2:

- call `createNewStickerSet` with the explicit human owner's `user_id`, a name
  ending in `_by_<bot_username>`, `sticker_type="custom_emoji"`, 1–50 initial
  `InputSticker` items, and the intended set-wide `needs_repainting` value;
- the method returns `True`; call `getStickerSet(expected_name)` afterward,
  require the returned set name to match, and build the authoritative set of
  its unique `custom_emoji_id` values before mapping them to the manifest;
- custom emoji sets can contain up to 200 items; validate known IDs with
  `getCustomEmojiStickers` in batches of at most 200 before enabling records.
  Require one unique response per requested ID, reject missing, duplicate, or
  unexpected IDs, and require each returned sticker's `set_name` to equal the
  registry pack's `telegram_set_name`; merely proving that an ID exists is not
  sufficient provenance;
- a set created by the bot is owned by the specified user and can then be
  edited by the bot.

Official format boundaries:

| Format | Custom emoji requirements |
| --- | --- |
| Static PNG/WEBP | Exactly 100×100 pixels |
| Video WEBM | Exactly 100×100, VP9, no audio, at most 3 seconds, at most 30 FPS, at most 256 KB |
| Animated TGS | 512×512 canvas, looped, at most 3 seconds, 60 FPS, at most 64 KB, within Telegram's supported feature set |

Run a visual review after Telegram processing: check light/dark themes,
adaptive repainting, button scale, animation distraction, and meaning at small
size. Store the final set name, IDs, verification timestamp, source revision,
license notice, and reviewer decision together.

Primary sources: [Telegram button fields](https://core.telegram.org/bots/api#inlinekeyboardbutton),
[sticker-set methods](https://core.telegram.org/bots/api#createnewstickerset),
[format requirements](https://core.telegram.org/stickers), and
[Telegram Content Licensing Terms](https://telegram.org/tos/content-licensing).
