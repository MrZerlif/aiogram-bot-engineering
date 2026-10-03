# Baseline without skill — recorded control run

Run `control-20260820-composite-r3` combines retained and fresh isolated control
evidence. Eight unaffected engineering cases retain the historical control,
and the presentation case retains its prior isolated control. The three
affected prompts (`dialog-widget-ui`, `custom-emoji-capability-selection`, and
`webhook-secret`) were freshly rerun in `/root/eval_control_delivery_registry`
without repository, skill, rubric, result-artifact, or web context. The exact
deployed model revision was not exposed. See
[`run-manifest.json`](run-manifest.json) for the recorded protocol and hashes.

## fsm-linear-flow

Model the conversation as a `StatesGroup` with `name`, `email`, and `confirmation` states. The `/register` handler clears any abandoned registration, initializes fresh FSM data, sets `name`, and renders the first prompt. Each state gets its own handler: normalize and validate the name, validate the email syntactically and against any product rules, then accept only an explicit confirm or restart choice. Invalid input must leave the state unchanged and return a specific correction message. Store normalized values in `FSMContext`, not module-level variables.

Register a `/cancel` and cancel-button handler that applies while any registration state is active. It should clear the FSM data, remove or replace obsolete keyboards, and acknowledge callback queries. On confirmation, revalidate the complete payload and persist it atomically before clearing state; if persistence fails, retain enough state to retry and show a recoverable error. Also handle unexpected text and old callback buttons without advancing. Test every valid transition, each validation failure, cancellation from all three states, duplicate confirmation, and simultaneous registrations by different users.

## scenes-isolated-flow

Represent onboarding as a scene or wizard with explicit entry, step, back, completion, and exit handlers. Entry should initialize a fresh, namespaced data object and render the first view. Each forward transition validates the current answer before saving it; back navigation moves to the previous step while preserving already entered values and re-renders them for editing. Completion writes the final model atomically, while cancel and exit clear transient scene data and remove obsolete controls.

Isolation depends on storage keys, not merely on scene code. Configure FSM storage so the key includes at least bot, chat, and user identifiers; this is especially important in group chats where several users share one chat. Use Redis or another durable FSM backend in a multi-process deployment, with an appropriate TTL, and never store current-user data in globals or singleton scene objects. If two updates for one user can execute concurrently, serialize them or use a version check. Tests should interleave two users in one chat and one user in two chats, verify back/exit behavior, restart the application mid-flow, and assert that no answers cross storage keys.

## dialog-widget-ui

Use `aiogram-dialog` as one router inside the native aiogram application. Keep edits in `dialog_data`; write them to storage only when the user confirms.

```python
class SettingsSG(StatesGroup):
    main = State()

async def getter(dialog_manager: DialogManager, **_):
    selected = dialog_manager.dialog_data.get("server", "eu-1")
    return {
        "servers": [
            {"id": key, "title": f"{'✓ ' if key == selected else ''}{name}"}
            for key, name in SERVERS
        ]
    }

async def select_server(
    query: CallbackQuery, widget, manager: DialogManager, item_id: str
):
    manager.dialog_data["server"] = item_id

async def confirm(query: CallbackQuery, button, manager: DialogManager):
    settings = {
        "notifications": manager.find("notifications").is_checked(),
        "server": manager.dialog_data.get("server", "eu-1"),
    }
    await repository.save(query.from_user.id, settings)
    await query.answer("Settings saved")

settings_dialog = Dialog(
    Window(
        Const("Settings"),
        Checkbox(
            Const("🔔 Notifications: on"),
            Const("🔕 Notifications: off"),
            id="notifications",
            on_state_changed=lambda e, w, m:
                m.dialog_data.__setitem__("notifications", w.is_checked()),
        ),
        ScrollingGroup(
            Select(
                Format("{item[title]}"),
                id="server",
                item_id_getter=lambda item: item["id"],
                items="servers",
                on_click=select_server,
            ),
            id="pages",
            width=1,
            height=3,
        ),
        Group(
            PrevPage(scroll="pages", text=Const("◀")),
            CurrentPage(scroll="pages", text=Format("{current_page1}/{pages}")),
            NextPage(scroll="pages", text=Const("▶")),
            width=3,
        ),
        Button(Const("✅ Confirm"), id="confirm", on_click=confirm),
        getter=getter,
        state=SettingsSG.main,
    )
)
```

A native command opens it:

```python
@native_router.message(Command("settings"))
async def open_settings(message: Message, dialog_manager: DialogManager):
    current = await repository.load(message.from_user.id)
    await dialog_manager.start(
        SettingsSG.main,
        data=current,
        mode=StartMode.RESET_STACK,
    )
```

Use Redis rather than `MemoryStorage`, but still handle expired stacks and states removed by a deployment. Central recovery should answer the stale callback and reset the whole dialog stack:

```python
@dp.error(ExceptionTypeFilter(UnknownIntent))
async def stale_dialog(event: ErrorEvent, dialog_manager: DialogManager):
    query = event.update.callback_query
    if query is None:
        raise event.exception

    await query.answer("This screen expired; opening a fresh one.", show_alert=True)
    current = await repository.load(query.from_user.id)
    await dialog_manager.start(
        SettingsSG.main,
        data=current,
        mode=StartMode.RESET_STACK,
    )
    return True
```

Add the pinned library version’s specific unknown-window/state exception to that filter. Register a final catch-all callback router after all legitimate callback routers for stale callbacks that become merely unhandled. Do not catch arbitrary exceptions, because database and programming errors must remain observable.

## mini-app-launch-security

Send an inline keyboard button containing `WebAppInfo` with an HTTPS dashboard URL. The Mini App should pass Telegram’s initialization data to its backend immediately. On the server, validate the `initData` signature according to Telegram’s HMAC procedure using the bot token, compare the computed hash in constant time, reject an old `auth_date`, and optionally track a nonce or data hash briefly to reduce replay. Parse the user identity only after successful validation; never accept a user ID, role, or account ID merely because JavaScript supplied it.

After validation, issue a short-lived application session scoped to that Telegram user. Use secure, `HttpOnly`, `SameSite` cookies with CSRF protection, or a short-lived bearer token kept in memory. Every dashboard endpoint must authorize access to the requested account independently. Keep the bot token exclusively server-side, enforce HTTPS through the proxy and application, restrict CORS to the Mini App origin, rate-limit authentication, and avoid logging raw initialization data or credentials. Test modified fields, invalid hashes, expired data, replay, cross-account requests, and a legitimate launch on both Telegram clients and browser-like test clients.

## callback-authorization

Encode only a report identifier and expected version in a structured callback payload; do not encode “is moderator” or approval state as trusted facts. When clicked, always answer the callback promptly, then obtain the actor’s moderator status from an authoritative source such as current chat membership or the application role table. Hiding the button from ordinary users improves UX but is not authorization. Reject unauthorized actors with a neutral alert and record the attempt without exposing sensitive report details.

Load the report in a transaction using a row lock or conditional update such as `WHERE status = 'pending' AND version = :expected`. If no row changes, the button is stale, the report is missing, or another moderator already acted; return an “already handled” response and refresh the message. On success, record approver, timestamp, and the new version, commit, and then edit the UI. Use an idempotency key based on report and action so duplicate deliveries are harmless. Test ordinary users, removed moderators, forged payloads, malformed IDs, old versions, two simultaneous moderators, duplicate updates, and failures between database commit and message editing.

## payment-lifecycle

Create a pending order before sending the invoice and place an opaque, unique order reference in the invoice payload. In the `pre_checkout_query` handler, reload that order and verify product, price, currency, buyer eligibility, and pending status; answer within Telegram’s deadline. Do not grant access at pre-checkout, because it is only permission to attempt payment. Fulfillment begins from `successful_payment`, after verifying its invoice payload and monetary fields against the stored order.

Process payment in a database transaction with a lock or conditional state transition. Store both Telegram and provider charge IDs under unique constraints, mark the order paid once, extend the subscription deterministically, and insert an outbox event in the same transaction. Duplicate successful-payment updates then return the existing result. If payment arrives without a recorded pre-checkout event, reconcile it from the trusted invoice payload rather than discarding paid money; if events arrive late, state transitions must never move a paid order backward. Workers consume the outbox idempotently for receipts and notifications. Test duplicate and reordered updates, concurrent handlers, amount mismatch, declined checkout, crash after commit, subscription extension rules, refunds, and reconciliation of ambiguous payments.

## webhook-secret

Terminate TLS at a trusted HTTPS proxy and configure Telegram’s standard secret header:

```python
await bot.set_webhook(
    url="https://bot.example.com/telegram/update",
    secret_token=settings.webhook_secret,
    allowed_updates=dispatcher.resolve_used_update_types(),
    drop_pending_updates=False,
)
```

Generate the secret independently of the bot token, keep it in a secret manager, and preserve `X-Telegram-Bot-Api-Secret-Token` through the proxy. Authenticate before reading or parsing the request body, using constant-time comparison:

```python
async def webhook(request: web.Request):
    supplied = request.headers.get(
        "X-Telegram-Bot-Api-Secret-Token", ""
    )
    if not supplied or not secrets.compare_digest(
        supplied, request.app["webhook_secret"]
    ):
        return web.Response(status=404)

    try:
        raw = await request.json()
        update_id = int(raw["update_id"])
        Update.model_validate(raw, context={"bot": request.app["bot"]})
    except (ValueError, TypeError, KeyError):
        return web.Response(status=400)

    try:
        async with request.app["pool"].acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    INSERT INTO telegram_update_inbox
                        (bot_id, update_id, payload, state)
                    VALUES ($1, $2, $3::jsonb, 'pending')
                    ON CONFLICT (bot_id, update_id) DO NOTHING
                    """,
                    request.app["bot"].id,
                    update_id,
                    json.dumps(raw),
                )
    except Exception:
        return web.Response(status=503)

    return web.Response(status=200, text="ok")
```

The `(bot_id, update_id)` primary key makes Telegram retries idempotent. Return success only after the transaction has committed to storage configured for durable synchronous commits. An in-memory `asyncio.Queue` or background handler is not acceptance; if storage is unavailable, return `503` so Telegram retries.

Run a fixed worker pool. Workers claim rows atomically with `FOR UPDATE SKIP LOCKED` and a lease, call `dispatcher.feed_raw_update`, then mark the row complete. On failure they schedule a bounded retry and eventually dead-letter it. Processing remains at-least-once: a crash after an external side effect but before `mark_done` can repeat that side effect. Use an idempotency key such as `(bot_id, update_id, operation)` or a transactional outbox for payments and other loss-sensitive actions.

The safest polling alternative creates no handler tasks:

```python
await dispatcher.start_polling(
    bot,
    handle_as_tasks=False,
    allowed_updates=dispatcher.resolve_used_update_types(),
)
```

Where supported, bounded parallelism can use `handle_as_tasks=True, tasks_concurrency_limit=32`. A semaphore inside already-created handlers does not prevent an unbounded number of waiting tasks. For webhook-equivalent durability, let sequential polling only insert into the same durable inbox while the fixed workers perform slow work.

## background-jobs

Use a transactional outbox. In the same database transaction that changes the order to `paid`, insert separate durable jobs for customer notification and report generation, each with a stable idempotency key such as `order_id + job_type`. The update handler commits this small transaction and responds; it does not render reports or call slow downstream services. A dispatcher publishes committed outbox rows to a durable broker, or workers can lease rows directly from the database with `SKIP LOCKED` semantics.

Workers acknowledge a job only after its side effect is complete. They should use bounded exponential backoff with jitter, lease expiry for crashed workers, maximum attempts, and a dead-letter state with alerting. Notification delivery records and generated-report records need unique constraints so redelivery cannot send or create twice; store reports in durable object storage and save their location atomically. Propagate order, update, job, and trace identifiers into job metadata. On restart, expired leases and unpublished outbox rows are picked up again. Test crashes before and after each commit, duplicate delivery, transient Telegram/storage failures, poison jobs, concurrent workers, shutdown while processing, and replay from the dead-letter queue.

## testing-strategy

Split tests by boundary. Unit-test callback payload encoding/decoding, order state transitions, amount checks, authorization decisions, and keyboard construction with table-driven cases. Handler tests should feed synthetic callback and payment updates through the dispatcher with a fake bot session, then assert callback acknowledgements, message edits, alerts, and database effects. Include malformed and forged callback data, an ordinary user, an active moderator, a moderator whose role was revoked, a missing order, and a stale order version.

Run integration tests against the real database engine used in production so transactions, unique constraints, locks, and rollback behavior are exercised. Deliver the same successful-payment update repeatedly and out of order relative to pre-checkout; assert one charge record, one fulfillment transition, and one outbox event. Race two approval or payment handlers and verify only one wins. For UI behavior, assert semantic properties of the keyboard—button text, callback payload, enabled actions, pagination boundaries, and the refreshed state—rather than brittle serialized snapshots alone. Add tests for Telegram API failures after commit, worker retry/restart, unauthorized audit logs, and property-based fuzzing of callback bytes and state-event sequences.

## production-uow-observability

Make the handler an orchestration layer around a unit of work. Parse and validate the callback, authenticate the actor, then begin a transaction and load the order with a row lock or optimistic version. Apply a domain transition that only permits `pending -> confirmed`, write the confirmation and audit record, and insert an outbox event in the same commit. A unique idempotency key derived from the update/action ensures retries return the previously committed result. Call Telegram to refresh the message after commit; failures there must not roll back the order and can be retried from the outbox.

Retry only classified transient failures such as serialization conflicts, deadlocks, timeouts, and rate limits, using bounded exponential backoff with jitter. Do not retry validation, authorization, or invariant failures. Emit structured logs containing update, callback, order, actor, attempt, state transition, duration, and outcome fields, while excluding secrets and payment data. Start a trace span at update receipt and propagate its context into database and outbox-worker spans; record retry and external-call events. Metrics should cover latency, outcomes, retries, conflicts, outbox lag, and dead letters. Test commit ambiguity, concurrent confirmations, duplicate updates, post-commit API failure, log redaction, and trace-context propagation.

## native-presentation-anti-slop

Ниже — готовый вариант с условным брендом **VELA VPN**.

### Структура экрана

```text
┌──────────────────────────────────┐
│                                  │
│           VELA VPN               │
│     БЫСТРО • ЧАСТНО • ВЕЗДЕ      │
│                                  │
│       абстрактная световая       │
│          сфера / орбита          │
└──────────────────────────────────┘

Добрый вечер, Алексей 👋

🟢 Доступ активен
💎 Premium · до 24 сентября 2026
📱 Подключено устройств: 2 из 5

Управляйте подключением и подпиской прямо здесь 👇

[        ⚡ Подключить VPN        ]
[  💎 Продлить  ] [ 📊 Подписка  ]
[ 📱 Устройства ] [  🎁 Бонусы   ]
[ 📖 Инструкция ] [ 💬 Поддержка ]
```

### Текст сообщения

Для аккуратного оформления можно использовать HTML-разметку Telegram:

```html
<b>Добрый вечер, {first_name} 👋</b>

<blockquote>🟢 <b>Доступ активен</b>
💎 Premium · до 24 сентября 2026
📱 Подключено устройств: 2 из 5</blockquote>

Управляйте подключением и подпиской прямо здесь 👇
```

Важно писать именно «доступ активен», а не «VPN подключён»: бот знает состояние подписки, но не всегда может определить реальное VPN-соединение на устройстве.

### Inline-клавиатура

```text
⚡ Подключить VPN                   → vpn:connect

💎 Продлить                        → subscription:renew
📊 Подписка                        → subscription:details

📱 Устройства                      → devices:list
🎁 Бонусы                          → referral:open

📖 Инструкция                      → help:setup
💬 Поддержка                       → support:open
```

Главная кнопка занимает всю строку. Остальные действия собраны попарно — так меню выглядит спокойнее и визуально дороже.

### Баннер

Формат: **1280 × 720 px**, PNG или качественный JPEG.

Визуальное направление:

- глубокий тёмно-синий фон: `#07111F → #0B2447`;
- мягкое голубое свечение: `#45B7FF`;
- абстрактная стеклянная сфера или тонкие световые орбиты;
- небольшой фирменный знак и надпись `VELA VPN`;
- подзаголовок: `БЫСТРО • ЧАСТНО • ВЕЗДЕ`;
- много свободного пространства, без замков, флагов, серверов и нарисованных кнопок;
- весь важный контент — в центральных 80% изображения, чтобы превью Telegram ничего не обрезало.

Промпт для генерации:

```text
Premium minimalist banner for a commercial VPN Telegram bot,
deep navy gradient background, elegant translucent glass sphere
with thin cyan light rings, subtle depth and soft reflections,
small refined VELA VPN logo in the center, Russian subtitle
“БЫСТРО • ЧАСТНО • ВЕЗДЕ”, high-end fintech aesthetic,
clean composition, generous negative space, no devices,
no padlock icons, no buttons, no people, 16:9
```

Для пользователя без подписки статус и главная кнопка меняются на:

```text
🟠 Доступ не активирован

[         💎 Выбрать тариф         ]
```

Остальная структура меню остаётся неизменной — экран не прыгает между состояниями и воспринимается как цельный продукт.

## custom-emoji-capability-selection

Числовые `custom_emoji_id` нельзя надёжно придумать или восстановить по виду emoji: это непрозрачные Telegram ID. Кроме того, Bot API не предоставляет рейтинг популярности публичных наборов. Поэтому правильный способ «самому выбрать ID» — взять утверждённый список ссылок `t.me/addemoji/<short_name>`, вызвать `getStickerSet`, выбрать подходящие элементы и зафиксировать реальные ID в lock-файле.

Семантические предпочтения:

- оплата: `💳`, резерв `💰`;
- профиль: `👤`;
- серверы: `🖥️`, резерв `🌐`;
- поддержка: `🛟`, резерв `💬`;
- назад: `⬅️`, резерв `↩️`;
- предупреждение: `⚠️`, резерв `❗`;
- удаление: `🗑️`, резерв `❌`.

Резолвер принимает только наборы типа `custom_emoji`, сопоставляет `Sticker.emoji` с этими базовыми символами и сохраняет `Sticker.custom_emoji_id` строкой, чтобы JavaScript не потерял точность.

```yaml
schema_version: 1
registry_version: 1.0.0
entries:
  payment:
    fallback: "💳"
    variants:
      - custom_emoji_id: "REAL_ID_FROM_GET_STICKER_SET"
        source_set: approved_pack
        tags: [payment, card, neutral]
        capabilities: [inline_button_icon, message_entity]
  profile: {fallback: "👤", variants: []}
  servers: {fallback: "🖥️", variants: []}
  support: {fallback: "🛟", variants: []}
  back: {fallback: "⬅️", variants: []}
  warning: {fallback: "⚠️", variants: []}
  delete: {fallback: "🗑️", variants: []}
```

Сборка должна отклонять заглушки. Офлайн-проверка валидирует схему, наличие семи slots, положительный `int64`, дубликаты, fallback, допустимые tags/capabilities и детерминированность выбора. После неё live-проверка вызывает `getCustomEmojiStickers` пакетами, сверяет возвращённые ID и выполняет canary-отправку inline-кнопок в тестовый чат и тестовый канал.

ИИ не выдаёт сырой ID. Он возвращает, например, `{"slot":"warning","tone":"urgent","surface":"inline_button"}`. Детерминированный селектор оставляет только live-verified варианты с подходящей capability, ранжирует tags и иначе использует Unicode fallback. Для удаления destructive-вариант задаётся политикой, а не настроением модели.

Premium владельца требуется для `icon_custom_emoji_id`, но не гарантирует любую поверхность. В канале боту нужны права публикации; старые клиенты могут не показать icon. Поэтому текст кнопки и обычный Unicode emoji всегда должны оставаться понятными.
