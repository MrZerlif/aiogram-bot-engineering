# Results with skill — recorded treatment run

Run `treatment-20260820-composite-r8` combines eight unaffected engineering
cases from the historical runner `/root/eval_treatment_round3`, the prior
presentation case from `/root/final_treatment_native_r2`, and three freshly
rerun affected cases from `/root/final_treatment_delivery_registry_r4` on
2026-08-19 and 2026-08-20. Each runner received prompt text directly, read
`SKILL.md` and only locally routed resources, and confirmed it did not read eval
rubrics, tests, README, prior results, git history, or web content. The exact
deployed model revision was not exposed. The fresh affected-case runner was
given frozen bundle SHA-256
`03b1002d0efd7c878fd189ff74bc101db078ff62848473d56cde91f23bde4ba2`.
See [`retrieval-trace.json`](retrieval-trace.json)
for each case's self-reported read set and [`run-manifest.json`](run-manifest.json)
for protocol and hashes.

## fsm-linear-flow

Use a native aiogram FSM because this is a short linear form. Define a `Registration` `StatesGroup` with `name`, `email`, and `age` states, and put its handlers in a feature `Router`. Each handler should normalize and validate only the answer for its current state: reject a blank or oversized name, parse and validate the email, and parse age with explicit bounds. On invalid input, answer with a specific correction and leave the state unchanged. On valid input, save the normalized value with `FSMContext.update_data()` and advance with `set_state()`.

Register a `/cancel` handler, plus a cancel callback if buttons are shown, so it matches every registration state. It should acknowledge callbacks, clear the FSM, and return a neutral confirmation; cancellation must not create a user record. At the final step, read all state data, persist the registration through a service/repository transaction, and clear state only after success. Use persistent production FSM storage and event isolation, not module-level dictionaries, so restarts and concurrent answers do not corrupt progress.

## scenes-isolated-flow

Model onboarding as an aiogram Scene because it needs an isolated lifecycle and navigation history, while noting that Scenes are experimental in aiogram 3.30.0. Give entry, profile, and review steps explicit scene states. An entry hook may initialize onboarding metadata; navigation should use the scene wizard’s `goto()` and `back()` operations rather than encoding the current screen in callback data. An exit hook should perform bounded cleanup, while successful completion should call the application service first and then leave the scene. A cancel action should be available in every step.

Store draft answers only in the user’s `FSMContext` through a persistent `BaseStorage`. Configure the storage key strategy so the intended user/chat pair owns the session, and never keep drafts in a mutable global, router singleton, or shared getter. Durable profile and authorization data still belong in the database. On every callback, treat identifiers as untrusted, acknowledge denied or malformed input, and reject stale scene history by resetting to a known entry state. Add same-user concurrency isolation and verify separately that two users and two chats cannot observe one another’s drafts.

## dialog-widget-ui

Use native routers for ordinary commands and let `aiogram-dialog` exclusively own the settings flow and its stack.

```python
import logging
from aiogram import Dispatcher, Router
from aiogram.enums import ButtonStyle
from aiogram.filters import Command, ExceptionTypeFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import BaseStorage
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import (
    Dialog, DialogManager, ShowMode, StartMode, Window, setup_dialogs,
)
from aiogram_dialog.api.exceptions import UnknownIntent, UnknownState
from aiogram_dialog.widgets.kbd import Button, Column, Row, Select, SwitchTo
from aiogram_dialog.widgets.style import Style
from aiogram_dialog.widgets.text import Const, Format

log = logging.getLogger(__name__)
PAGE_SIZE = 5
native_router = Router(name="native")


class SettingsSG(StatesGroup):
    edit = State()
    confirm = State()


async def load_draft(_start_data, manager: DialogManager):
    repo = manager.middleware_data["settings_repo"]
    current = await repo.get(manager.event.from_user.id)
    manager.dialog_data.update(
        alerts=current.alerts,
        server_id=str(current.server_id),
        version=current.version,
        page=0,
    )


async def settings_getter(dialog_manager: DialogManager, **_):
    catalog = dialog_manager.middleware_data["server_catalog"]
    requested = int(dialog_manager.dialog_data.get("page", 0))
    total_pages = await catalog.page_count(limit=PAGE_SIZE)
    final_page = max(0, total_pages - 1)
    page = min(max(0, requested), final_page)
    result = await catalog.list_page(page=page, limit=PAGE_SIZE)
    selected = await catalog.get(dialog_manager.dialog_data["server_id"])
    return {
        "alerts_label": "On" if dialog_manager.dialog_data["alerts"] else "Off",
        "selected_name": selected.name,
        "items": [{"id": str(x.id), "name": x.name} for x in result.items],
        "page_label": f"{page + 1}/{max(1, total_pages)}",
        "has_previous": page > 0,
        "has_next": result.has_next,
    }


async def toggle_alerts(
    callback: CallbackQuery, _button: Button, manager: DialogManager
):
    manager.dialog_data["alerts"] = not manager.dialog_data["alerts"]
    await callback.answer()


async def move_page(callback, _button, manager: DialogManager, delta: int):
    catalog = manager.middleware_data["server_catalog"]
    total_pages = await catalog.page_count(limit=PAGE_SIZE)
    final_page = max(0, total_pages - 1)
    current = int(manager.dialog_data.get("page", 0))
    manager.dialog_data["page"] = min(max(0, current + delta), final_page)
    await callback.answer()


async def previous_page(c, b, m):
    await move_page(c, b, m, -1)


async def next_page(c, b, m):
    await move_page(c, b, m, 1)


async def select_server(
    callback: CallbackQuery, _select: Select, manager: DialogManager, item_id: str
):
    try:
        server_id = int(item_id)
    except (TypeError, ValueError):
        await callback.answer("This server is no longer valid.", show_alert=True)
        return
    catalog = manager.middleware_data["server_catalog"]
    server = await catalog.get_visible(server_id, callback.from_user.id)
    if server is None:
        await callback.answer("This server is unavailable.", show_alert=True)
        return
    manager.dialog_data["server_id"] = str(server.id)
    await callback.answer()


async def confirm_settings(
    callback: CallbackQuery, _button: Button, manager: DialogManager
):
    await callback.answer()
    catalog = manager.middleware_data["server_catalog"]
    server_id = int(manager.dialog_data["server_id"])
    if await catalog.get_visible(server_id, callback.from_user.id) is None:
        raise ValueError("selected server became unavailable")

    repo = manager.middleware_data["settings_repo"]
    await repo.save(
        user_id=callback.from_user.id,
        alerts=manager.dialog_data["alerts"],
        server_id=server_id,
        expected_version=manager.dialog_data["version"],
    )
    await manager.done()


settings_dialog = Dialog(
    Window(
        Format(
            "Settings\n\nNotifications: {alerts_label}\n"
            "Selected server: {selected_name}"
        ),
        Button(
            Format("Notifications: {alerts_label}"),
            id="toggle_alerts",
            on_click=toggle_alerts,
        ),
        Column(
            Select(
                Format("{item[name]}"),
                id="server",
                item_id_getter=lambda item: item["id"],
                items="items",
                on_click=select_server,
            )
        ),
        Row(
            Button(Const("Previous"), id="prev", on_click=previous_page,
                   when="has_previous"),
            Button(Const("Next"), id="next", on_click=next_page,
                   when="has_next"),
        ),
        Format("Page {page_label}"),
        SwitchTo(Const("Review changes"), id="review", state=SettingsSG.confirm),
        getter=settings_getter,
        state=SettingsSG.edit,
    ),
    Window(
        Format(
            "Confirm settings\n\nNotifications: {alerts_label}\n"
            "Server: {selected_name}"
        ),
        SwitchTo(Const("Back"), id="back", state=SettingsSG.edit),
        Button(
            Const("Confirm and save"),
            id="confirm",
            on_click=confirm_settings,
            style=Style(style=ButtonStyle.SUCCESS),
        ),
        getter=settings_getter,
        state=SettingsSG.confirm,
    ),
    on_start=load_draft,
)


@native_router.message(Command("settings"))
async def open_settings(_message: Message, manager: DialogManager):
    await manager.start(SettingsSG.edit, mode=StartMode.RESET_STACK)


async def recover_stale_dialog(event, dialog_manager: DialogManager):
    log.exception("Stale dialog callback", exc_info=event.exception)
    callback = getattr(event.update, "callback_query", None)
    if callback:
        await callback.answer()
    await dialog_manager.start(
        SettingsSG.edit,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.SEND,
    )


def build_dispatcher(
    storage: BaseStorage, settings_repo, server_catalog
) -> Dispatcher:
    dp = Dispatcher(
        storage=storage,
        settings_repo=settings_repo,
        server_catalog=server_catalog,
    )
    dp.include_router(native_router)
    dp.include_router(settings_dialog)
    dp.errors.register(recover_stale_dialog, ExceptionTypeFilter(UnknownIntent))
    dp.errors.register(recover_stale_dialog, ExceptionTypeFilter(UnknownState))
    setup_dialogs(dp)
    return dp
```

Use shared persistent FSM storage in production. Persistence reduces restart loss, but it cannot make a removed state name valid after a deployment. The centralized recovery acknowledges the stale callback, discards the arbitrary stack with `RESET_STACK`, and uses `ShowMode.SEND` so recovery does not try to edit the stale message again.

## mini-app-launch-security

Launch the dashboard from an inline `WebAppInfo` button, which supports the signed `initData` flow. The URL only locates the Mini App; it is not proof of identity. The frontend should send the raw `Telegram.WebApp.initData` to the HTTPS backend. One server-side validator should parse it strictly, reject duplicate or missing fields, remove `hash`, sort the remaining `key=value` lines, and verify the documented HMAC using a secret derived from the bot token. Use `hmac.compare_digest`, enforce an application-chosen short maximum age, and reject both expired and future `auth_date` values.

Only after validation should the backend parse the validated `user` JSON and use that Telegram ID to find an application account. Bind a server session to that identity and authorize every dashboard operation against server-side account, role, and ownership data. Never accept `initDataUnsafe`, a client-provided user ID, role, price, or account ID as authority. Keep the bot token server-side, redact `initData` and secrets from logs, apply normal session expiry and rotation, and reject malformed requests before any account lookup or business action.

## callback-authorization

Use a native inline keyboard for this single action. Encode only a compact action plus `report_id` and, if useful, an expected report version in typed `CallbackData`; do not encode the moderator role, approval state, or trusted snapshot. The callback handler should parse defensively, load the report from durable storage, resolve the actor’s current moderator permission server-side, and check that the report is still pending and the version belongs to the displayed action.

Perform approval in one transaction with a conditional update or row lock. The invariant should require both “actor is authorized” and “status is pending”; a uniqueness/idempotency key should make a retried callback return the existing outcome rather than approve twice. A missing report, ordinary user, revoked moderator, mismatched version, or already-resolved report is denied without mutation. Acknowledge every callback promptly: use a concise alert for malformed, unauthorized, or stale buttons, and edit the message/remove the button only after the transaction commits. Record safe audit fields such as report ID, actor ID, decision, and correlation ID, but never treat Telegram callback payloads as authorization evidence.

## payment-lifecycle

Treat an in-Telegram subscription as a digital service and route it through Telegram Stars with `currency="XTR"`, subject to a current policy check before shipping. Create a durable order first with the product, amount, payer/recipient policy, and opaque public reference; the invoice payload should only correlate to that order. In `pre_checkout_query`, reload it and compare status, payer policy, currency, and total, denying invalid requests within Telegram’s documented ten-second window.

Fulfillment belongs only in `successful_payment`, never in pre-checkout or a client return. Reload and revalidate the order, then in one database transaction record the unique `telegram_payment_charge_id`, advance payment state, and grant the subscription. Persist a provider charge ID only when nonempty. Replayed success updates must return the recorded result. Model paid, fulfilled, renewed, canceled, refunded, reversed, and disputed transitions explicitly; key each external event by its stable ID so late or out-of-order events are either applied legally or retained for reconciliation. Publish post-payment work through a transactional outbox. Define the policy for duplicate valid payments and investigate contract mismatches rather than silently granting access.

## webhook-secret

Provision the webhook secret once with `secrets.token_urlsafe(32)`, store it outside source control, and reuse it across restarts. Configure the same value in Telegram and aiogram’s request handler:

```python
import os, re
from urllib.parse import urlsplit
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

PATH = "/telegram/webhook"


def load_config():
    url = os.environ["WEBHOOK_URL"]
    secret = os.environ["TELEGRAM_WEBHOOK_SECRET"]
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError("WEBHOOK_URL must be absolute HTTPS")
    if (
        not re.fullmatch(r"[A-Za-z0-9_-]{43,256}", secret)
        or secret.casefold() in {"change-me", "example-secret", "placeholder"}
    ):
        raise RuntimeError("weak webhook secret")
    return url, secret


async def build_app(bot: Bot, dp: Dispatcher) -> web.Application:
    url, secret = load_config()
    app = web.Application()

    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        handle_in_background=False,
        secret_token=secret,
    ).register(app, path=PATH)
    setup_application(app, dp, bot=bot)

    await bot.set_webhook(
        url=url,
        secret_token=secret,
        allowed_updates=dp.resolve_used_update_types(),
    )
    return app
```

`SimpleRequestHandler` rejects a missing or incorrect secret header before dispatch. Do not log the token, secret/header, or unredacted update. Add ingress rate limits, but treat them as defense in depth rather than authentication.

`handle_in_background=False` means HTTP success waits for dispatcher completion. For a loss-sensitive update, keep that handler short and make its success boundary a committed database transaction:

```python
async def accept_loss_sensitive(message, event_update, uow_factory):
    normalized = {
        "chat_id": message.chat.id,
        "message_id": message.message_id,
        "user_id": message.from_user.id,
    }
    async with uow_factory() as uow:
        inserted = await uow.inbox.try_insert(
            update_id=event_update.update_id,   # UNIQUE / PRIMARY KEY
            normalized_payload=normalized,
        )
        if inserted:
            await uow.outbox.add(
                job_key=f"telegram:{event_update.update_id}",  # UNIQUE
                kind="process_loss_sensitive_update",
                payload=normalized,
            )
        await uow.commit()
```

The inbox row and outbox job must commit in the same transaction. A duplicate Telegram delivery becomes an idempotent no-op. If the commit fails, propagate the error so the endpoint does not acknowledge success and Telegram can retry. A bounded worker publishes/drains the outbox, retries only transient failures with capped backoff and jitter, and sends exhausted jobs to a dead-letter store. Do not use one `asyncio.create_task()` per update: it is neither durable nor bounded. Finish the commit comfortably inside aiogram’s roughly 55-second webhook wait window.

Readiness should remain false until the database and essential worker/queue dependencies are usable. During shutdown: stop intake, mark unready, drain bounded in-flight acceptance work, then close workers, pools, and bot sessions.

A production polling alternative with bounded update tasks is:

```python
async def run_polling(bot: Bot, dp: Dispatcher, limit: int = 64):
    if limit <= 0:
        raise ValueError("limit must be positive")
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types(),
        handle_as_tasks=True,
        tasks_concurrency_limit=limit,
    )
```

Size the limit against the DB pool, outbound limits, and handler cost. Multiple bots multiply the bound. A strictly sequential deployment can use `handle_as_tasks=False`; either way, own shutdown draining and keep slow work behind the same durable, bounded outbox workers.

## background-jobs

Keep the successful-order handler short by committing the order transition and durable outbox records in the same database transaction. Create separate job records for customer/admin notifications and report generation, each with a stable idempotency key derived from the order and job type. A publisher can move committed outbox entries to a durable queue; acknowledging the update after this durable acceptance point avoids losing work if the process exits immediately afterward.

Workers should claim jobs with bounded concurrency and backpressure. Before each side effect, check or atomically record its deduplication key so redelivery cannot send the same notification or publish the same report twice. Retry only classified transient failures with bounded exponential backoff and jitter. Permanent validation failures and exhausted retries belong in a dead-letter store with alerts, diagnostic context, and a controlled replay procedure. Persist job status rather than relying on `asyncio.create_task`, so restart recovery can resume outstanding work. Propagate the incoming correlation and trace context through outbox metadata, and monitor queue depth, oldest-job age, retry counts, dead letters, and end-to-end completion latency.

## testing-strategy

Test application behavior at the smallest useful boundary. Directly call the callback handler with `AsyncMock` callback events for malformed payloads, missing orders, ordinary users, revoked permissions, wrong ownership, stale versions, repeated clicks, and the authorized transition. Assert both repository state and callback acknowledgement; a denied path must make no mutation. Use `Dispatcher.feed_raw_update()` with a fake token when filters, router selection, middleware, or dependency injection matter, without polling or Telegram network access.

For payments, feed the same successful-payment update twice and assert one charge row and one entitlement in the database transaction. Repeat after recreating storage to simulate restart, and cover success arriving around duplicated/stale UI updates, plus payer, order, currency, and amount mismatches. Controlled clocks and barriers should exercise timeout and concurrent-delivery races. For UI behavior, assert the rendered button identifiers, page clamping, disabled/absent actions for terminal states, safe stale-button alerts, and message edits only after commit. Keep service validation real where practical, use disposable repositories for transactional assertions, and ensure test configuration contains no usable Telegram or provider credentials.

## production-uow-observability

Give the order-confirmation handler an injected Unit of Work containing repositories, an outbox, and one explicit transaction. After defensively parsing the callback, load and lock the order, resolve current authorization server-side, and enforce the expected version and confirmable state. Insert an update/callback idempotency key under a unique constraint in the same transaction as the state transition and outbox event. A duplicate should return the previously recorded outcome; expected denial should not mutate, and unexpected failure should roll back and reach centralized error handling. Acknowledge success only after commit.

Retry transient database failures at the application boundary with bounded backoff and jitter, starting a fresh Unit of Work each attempt. Do not retry authorization or validation failures, and rely on the idempotency constraint to prevent duplicate effects. Emit structured logs with correlation ID, safe order/user identifiers, attempt, decision, duration, and error class while redacting callback contents and secrets. Create trace spans around update handling, authorization/query, transaction commit, outbox publication, and worker processing; persist trace context with the outbox record. Track latency, rollback/error classes, retry counts, idempotency conflicts, outbox age, and confirmation outcomes, with alerts tied to service objectives.

## native-presentation-anti-slop

Ниже — готовый нативный экран: спокойный premium-визуал, один очевидный CTA, без Mini App и перегруза эмодзи.

## PresentationBrief

| Параметр | Решение |
|---|---|
| Аудитория | Пользователи VPN без необходимости разбираться в технических деталях |
| Главная задача | Быстро подключить новое устройство |
| Тон | Спокойный, уверенный, технологичный |
| Поверхность | Нативное сообщение: фото-баннер, HTML-caption и inline-клавиатура |
| Роль баннера | Бренд и атмосфера; никаких тарифов, дат или кнопок внутри изображения |
| Иерархия | `Подключить VPN` — primary; остальные действия — обычные |
| Навигация | Внутренние экраны редактируют текущее сообщение; возврат ведёт в главное меню |
| Иконки | Один набор монохромных custom emoji; при недоступности весь экран показывается без иконок |

## Система иконок

Стиль-лок: `vpn_ui_adaptive_v1` — тонкие монохромные контурные пиктограммы, одинаковая толщина линий, без анимации, с адаптивной перекраской Telegram.

| Токен | Образ | Назначение |
|---|---|---|
| `status_secure` | щит с галочкой | Состояние аккаунта |
| `connect` | штекер или защищённое соединение | Подключение VPN |
| `payment` | банковская карта | Подписка |
| `devices` | телефон и ноутбук | Устройства |
| `servers` | метка локации | Серверы |
| `support` | гарнитура | Поддержка |

В реализации токены разрешаются только в проверенные `custom_emoji_id`. Числовые ID нельзя придумывать. Если бот не имеет подходящей capability через дополнительный Fragment username либо Premium владельца в поддерживаемом типе чата, `icon_custom_emoji_id` убирается сразу у всех кнопок. Текстовые подписи остаются полными.

## Карта экрана

```text
/start
  └─ Обновление статуса
       ├─ Главное меню: подписка активна
       │    ├─ Подключить VPN → выбор устройства / инструкция
       │    ├─ Подписка → сведения и продление
       │    ├─ Устройства → список устройств
       │    ├─ Локации → список серверов
       │    └─ Поддержка → обращение
       ├─ Главное меню: подписка закончилась
       │    └─ Выбрать тариф → тарифы
       └─ Ошибка загрузки
            ├─ Повторить
            └─ Поддержка
```

Все переходы внутри меню редактируют исходное сообщение. Новый отдельный message нужен только для долговечных событий, например чека об оплате или ответа оператора.

## Состояния

| Состояние | Текст и поведение |
|---|---|
| Loading | `Обновляем статус VPN…` Повторные действия временно не показываются; доступна только поддержка |
| Empty | `Устройств пока нет` и основная кнопка `Подключить VPN` |
| Error | `Не удалось обновить статус. Подписка и настройки не изменены.` Кнопки `Повторить` и `Поддержка` |
| Confirmation | N/A — главное меню только открывает другие экраны и ничего необратимого не выполняет |
| Success | После подготовки подключения: `Данные подключения готовы` и кнопка `Открыть инструкцию` |
| Destructive | N/A — удаление устройства выполняется на отдельном экране с явным подтверждением |

## ScreenSpec

```yaml
id: home_active
purpose: показать состояние подписки и дать быстро подключить VPN
content:
  heading: VPN готов к работе
  status: Подписка активна до 24 сентября
  supporting: Устройств: 2 из 5
primary_action:
  label: Подключить VPN
  intent: connection_setup
  icon_token: connect
secondary_actions:
  - label: Подписка
    intent: subscription_details
    icon_token: payment
  - label: Устройства
    intent: device_list
    icon_token: devices
  - label: Локации
    intent: server_list
    icon_token: servers
  - label: Поддержка
    intent: support_start
    icon_token: support
navigation:
  back: false
  home: false
  edit_in_place: true
```

Для истёкшей подписки заголовок меняется на `Доступ приостановлен`, статус — на `Подписка закончилась 24 сентября`, а primary-кнопка — на `Выбрать тариф`.

## Баннер

Формат: `1280 × 720`, 16:9.

Композиция:

- фон — мягкий градиент от `#070B16` к `#101B34`;
- справа — объёмный полупрозрачный щит и две тонкие дуги маршрута;
- акценты — холодный cyan `#6EE7F9` и приглушённый violet `#8B5CF6`;
- слева — небольшой логотип и название продукта;
- не менее 40% свободного пространства;
- без людей, устройств, дат, тарифов, слоганов и нарисованных кнопок.

Готовый промпт для генерации:

> Premium minimalist VPN brand banner, 16:9, deep midnight navy gradient, elegant translucent glass shield on the right, two subtle encrypted routing arcs, restrained cyan and violet highlights, fine soft grain, generous negative space, calm commercial SaaS aesthetic, no people, no devices, no UI buttons, no pricing, no status text, no stock-photo look.

Баннер декоративный: вся важная информация остаётся в Telegram-тексте.

## Готовый экран

Caption с `parse_mode=HTML`:

```html
[icon: status_secure] <b>VPN готов к работе</b>

Подписка активна до <b>24 сентября</b>
Устройств: <b>2 из 5</b>

Выберите действие.
```

Обозначения `[icon: …]` — семантические токены для реализации, а не видимый пользователю текст.

Inline-клавиатура:

```text
┌──────────────────────────────────┐
│ [connect] Подключить VPN         │  primary
├─────────────────┬────────────────┤
│ [payment]       │ [devices]      │
│ Подписка        │ Устройства     │
├─────────────────┼────────────────┤
│ [servers]       │ [support]      │
│ Локации         │ Поддержка      │
└─────────────────┴────────────────┘
```

Конкретные callback-идентификаторы:

```text
home:connect
home:subscription
home:devices
home:servers
home:support
```

Идентификаторы считаются недоверенным вводом: обработчик заново получает данные пользователя, проверяет доступ и подтверждает callback через `answer()`.

Для этого экрана достаточно обычного aiogram-handler с нативным `InlineKeyboardMarkup`. Цветовой стиль `primary` получает только `Подключить VPN`; остальные кнопки остаются стандартными.

Статическая anti-slop проверка пройдена: один главный CTA, один набор иконок, нет повторения текста в баннере, кнопки понятны без цвета и эмодзи. Перед релизом остаётся проверить Telegram на iOS/Android, светлую и тёмную темы, узкий экран, длинные даты и полностью отключённые custom emoji.

## custom-emoji-capability-selection

Telegram ID нельзя корректно «выбрать» или сгенерировать: это значение возвращает Telegram для конкретного custom-emoji sticker. Поэтому я не буду подставлять правдоподобные числа. До live-проверки все ID должны быть `null`, а записи — `enabled: false`.

Для единого интерфейса я выбрал бы собственный адаптивный набор на базе Lucide (ISC, outline, monochrome, `needs_repainting: true`):

| token | Lucide source icon | role |
|---|---|---|
| `payment` | `credit-card` | action/category |
| `profile` | `circle-user-round` | action/category |
| `servers` | `server` | action/category |
| `support` | `headset` | action/category |
| `back` | `arrow-left` | navigation |
| `warning` | `triangle-alert` | status |
| `delete` | `trash-2` | action, destructive |

«Популярный публичный набор» не гарантирует ни лицензию, ни стабильность, ни полный семантический ряд. Ссылку `t.me/addemoji/...` можно хранить только как `public_reference` после проверки автора, прав, точного имени set и ID; сама ссылка не разрешает копирование. Для долговечного UI лучше owned-set с именем вида `brand_ui_v1_by_MyBot`.

Registry хранить как `registry/custom-emoji.v1.json`:

```json
{
  "$schema": "./custom-emoji-registry.schema.json",
  "schema_version": 1,
  "catalog_kind": "production",
  "packs": [{
    "pack_id": "lucide_ui_adaptive",
    "telegram_set_name": null,
    "telegram_set_origin": "unpublished_template",
    "coherence_group": "lucide_ui_v1",
    "status": "template",
    "selection_priority": 100,
    "trust": "licensed_source",
    "source_kind": "licensed_source",
    "source_url": "https://github.com/lucide-icons/lucide",
    "source_revision": null,
    "license_spdx": "ISC",
    "license_url": "https://github.com/lucide-icons/lucide/blob/main/LICENSE",
    "notice_required": true,
    "redistribution": "allowed_with_notice",
    "allowed_roles": ["action", "navigation", "status", "category"],
    "brand_safe": true,
    "needs_repainting": true,
    "style": {
      "family": "lucide_outline",
      "palette": "adaptive_monochrome",
      "line_weight": "regular",
      "detail": "low",
      "animation": "none",
      "mood": "calm",
      "density": "compact"
    }
  }],
  "semantic_collision_groups": {
    "severity": ["warning", "error"],
    "commerce": ["payment", "refund"],
    "destructive": ["delete", "archive"]
  },
  "emoji": []
}
```

В `emoji` добавляются семь записей из таблицы со всеми полями схемы: aliases, polarity, state, roles, source_icon, semantic_description, `custom_emoji_id: null`, `verified_at: null`, `review_status: "awaiting_telegram_id"` и `enabled: false`.

ИИ выбирает только `{token, role, state, polarity}`. Детерминированный resolver затем:

1. отфильтровывает pack по capability, chat type, лицензии, роли и верификации;
2. фиксирует один `pack_id` на весь экран;
3. выбирает exact token, затем alias;
4. исключает semantic collisions;
5. разрешает ничью по `selection_priority`, затем лексически;
6. переключает весь экран на совместимый pack, единую Unicode-схему либо на режим без иконок.

Premium владельца покрывает сообщения бота в private/group/supergroup, но не публикации в канале. Для канала нужен режим `fragment_username` с подходящим дополнительным username; иначе кнопки канала должны оставаться без custom icon. Premium зрителя и права администратора канала этого не меняют.

Offline-этап: JSON Schema Draft 2020-12 плюс семантический validator:

```shell
python validate_custom_emoji_registry.py registry/custom-emoji.v1.json
```

После явного разрешения live-этап вызывает `getStickerSet(expected_name)`, затем `getCustomEmojiStickers` партиями до 200 ID. Каждый ответ должен быть уникальным, иметь ожидаемый `set_name`, пройти визуальную проверку в светлой/тёмной теме и только затем получить `verified_at`, `review_status: "verified"` и `enabled: true`.
