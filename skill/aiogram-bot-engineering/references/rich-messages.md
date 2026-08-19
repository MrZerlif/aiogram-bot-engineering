# Native Rich Messages

Use aiogram's native Rich Message bindings when a Bot API rich message is the
right transport. This reference targets aiogram 3.30.0 and the corresponding
Bot API 10.2 models.

## Author and receive different models

For content the bot authors, construct `InputRichMessage` with **exactly one**
content source: `html`, `markdown`, or `blocks`. Do not combine those sources
in one authored message. Its structured blocks are `InputRichBlock*` models.
For a message received from Telegram, inspect the returned `RichMessage` and
its `RichBlock*` models instead; received blocks are not outgoing input
objects.

Keep user-provided text and IDs separate from construction, validate the
business action before sending, and select the simple source (`html` or
`markdown`) unless the layout needs structured `blocks`. Resolve IDs and their
alternative emoji through [the custom emoji system](custom-emoji-system.md)
before construction. This is a minimal structured custom-emoji text node:

```python
from aiogram import Bot
from aiogram.types import (
    InputRichBlockParagraph,
    InputRichMessage,
    RichTextCustomEmoji,
)


def build_status_message(
    verified_custom_emoji_id: str | None,
    reviewed_alternative_emoji: str | None,
) -> InputRichMessage:
    if verified_custom_emoji_id is None or reviewed_alternative_emoji is None:
        return InputRichMessage(html="Status")

    return InputRichMessage(
        blocks=[
            InputRichBlockParagraph(
                text=RichTextCustomEmoji(
                    custom_emoji_id=verified_custom_emoji_id,
                    alternative_text=reviewed_alternative_emoji,
                )
            )
        ]
    )


rich_message = build_status_message(
    verified_custom_emoji_id=registry_entry.custom_emoji_id,
    reviewed_alternative_emoji=registry_entry.rich_text_alternative_emoji,
)
await bot.send_rich_message(chat_id=chat_id, rich_message=rich_message)
```

The guard narrows both optional registry values before constructing
`RichTextCustomEmoji`. The API field named `alternative_text` expects an
alternative Unicode emoji, not a prose description such as `star` or
`payment`. When either value is unavailable, the example sends ordinary text.

Escape untrusted text for the exact selected context: HTML escaping is not
Markdown escaping, and neither is safe to interpolate into URLs, attributes,
or a structured block model. When the correct escaping rule is unclear, prefer
plain text or construct typed structured blocks instead of assembling markup.

## Media and limits

The media shape depends on the selected content source. For `html` or
`markdown`, put each `InputRichMessageMedia` binding in `InputRichMessage.media`
and refer to its ID with `tg://photo?id=...`, `tg://video?id=...`, or
`tg://audio?id=...`. For structured `blocks`, do not use those ID bindings:
media blocks such as `InputRichBlockPhoto` contain their `InputMediaPhoto`
directly inside the block. The video and audio block variants likewise contain
their matching `InputMediaVideo` and `InputMediaAudio` objects.

```python
from aiogram.types import (
    InputMediaPhoto,
    InputRichBlockPhoto,
    InputRichMessage,
    InputRichMessageMedia,
)


html_media_message = InputRichMessage(
    html='<img src="tg://photo?id=cover">',
    media=[
        InputRichMessageMedia(
            id="cover",
            media=InputMediaPhoto(media="telegram-file-id"),
        )
    ],
)
structured_media_message = InputRichMessage(
    blocks=[
        InputRichBlockPhoto(
            photo=InputMediaPhoto(media="telegram-file-id"),
        )
    ]
)
```

Where uploads are supported, pass aiogram file objects such as `FSInputFile`
or `BufferedInputFile` to the appropriate `InputMedia*`; do not substitute a
hand-written HTTP request for the client API.

Apply the Bot API limits before creating the request: at most 32768 characters,
500 blocks, nesting depth 16, 50 media items, and 20 table columns. An outgoing
`InputRichBlockMap` has a zoom value from 0–24 inclusive. Treat these as input
validation boundaries, not as a reason to truncate silently.

## Draft lifecycle and editing

`Bot.send_rich_message_draft` targets a private chat. Its `draft_id` must be
non-zero, and each streamed draft is an ephemeral 30-second preview. Direct upload
of new files isn't supported by this method. Build a complete
`InputRichMessage` for each update, then call `Bot.send_rich_message_draft`.
When the output is final, create the persistent message with
`Bot.send_rich_message`; a draft update is not the final message send.

```python
draft_content = InputRichMessage(markdown="Preparing your order…")
await bot.send_rich_message_draft(
    chat_id=chat_id,
    draft_id=draft_id,
    rich_message=draft_content,
)

final_content = InputRichMessage(markdown="Your order is ready.")
await bot.send_rich_message(chat_id=chat_id, rich_message=final_content)
```

`Bot.edit_message_text` also accepts `rich_message`. When editing, provide the
intended text or rich-message content (normally one), rather than contradictory
payloads that describe different final content.

For field definitions and all supported block variants, consult the [official
aiogram InputRichMessage API reference](https://docs.aiogram.dev/en/latest/api/types/input_rich_message.html)
and the [official Telegram Bot API Rich Message reference](https://core.telegram.org/bots/api#inputrichmessage).
