# Dialogs and UI

Choose **aiogram-dialog 2.6.0** when the UI is widget-driven or needs
pagination, a dialog stack, or nested flows. It owns that stack and lets each
`Window` describe one state. Having more than one state is not sufficient by
itself: use native FSM or Scenes for the simpler stateful flows in the matrix
below, and keep native keyboards for small actions or screens.

## State and UI choice

| Need | Choose |
| --- | --- |
| One action or screen | Handler with a native keyboard |
| Short, linear input | Native FSM |
| Isolated multi-step flow with lifecycle and history | Native Scenes |
| Rich widget-driven UI, pagination, a dialog stack, or nested flows | aiogram-dialog |
| Complex browser UI | Mini App |

aiogram Scenes support lifecycle hooks, history, `back()`, and `goto()`, but
they are experimental in aiogram 3.30.0 and may change. Prefer them only for
the isolated-flow case above; use aiogram-dialog when the UI itself needs to
own widgets, windows, or a dialog stack.

## Composition and data boundaries

Model a feature as a `StatesGroup`, then compose its `Dialog` from `Window`
objects. Let navigation use `DialogManager` (`start`, `switch_to`, `back`, or
`done`) instead of encoding screen state in callback data. Include dialog
routers before installing the middleware:

```python
from aiogram import Dispatcher
from aiogram.fsm.state import State, StatesGroup
from aiogram_dialog import Dialog, Window, setup_dialogs
from aiogram_dialog.widgets.text import Const


class CatalogSG(StatesGroup):
    browse = State()
    details = State()


catalog_dialog = Dialog(
    Window(Const("Catalog"), state=CatalogSG.browse),
    Window(Const("Catalog details"), state=CatalogSG.details),
)

dp = Dispatcher()
dp.include_router(catalog_dialog)
setup_dialogs(dp)
```

Keep getters pure with respect to dialog state: read the server-side data they
need and return a dictionary for rendering. Do not mutate an order, inventory,
or entitlement from a getter.

```python
PAGE_SIZE = 12


async def catalog_getter(dialog_manager, **_kwargs) -> dict:
    requested_page = int(dialog_manager.dialog_data.get("page", 0))
    total_pages = await catalog.page_count(limit=PAGE_SIZE)
    final_page = max(0, total_pages - 1)
    page = min(max(0, requested_page), final_page)
    result = await catalog.list_page(page=page, limit=PAGE_SIZE)
    return {
        "products": result.items,
        "page": page,
        "has_previous": page > 0,
        "has_next": result.has_next,
    }
```

For dynamic lists, render server-provided items with `Select` (and a
`ScrollingGroup` or pager when needed). Keep callback payloads to compact
action and identifier values. Pagination must have a positive, bounded page
size; derive the final page from server-side data, clamp invalid page values,
and make repeat or out-of-range navigation idempotently render the same final
page.

## Callback trust and navigation

Callback identifiers are untrusted input, not a product snapshot. Parse them
defensively, fetch the object from the server, then authorize the action using
the fetched object. Acknowledge the callback promptly after safe handling
(including malformed and denied cases); do not invent a fixed response-time
deadline.

```python
from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.kbd import Button


async def on_product_click(
    callback: CallbackQuery,
    button: Button,
    manager: DialogManager,
    item_id: str,
) -> None:
    try:
        product_id = int(item_id)
    except (TypeError, ValueError):
        await callback.answer("That selection is no longer valid.", show_alert=True)
        return

    product = await catalog.get_by_id(product_id)
    if product is None or not catalog.can_view(callback.from_user.id, product):
        await callback.answer("This product is unavailable.", show_alert=True)
        return

    await callback.answer()
    await manager.switch_to(CatalogSG.details)
```

Use `StartMode.RESET_STACK` for a top-level entry point when a fresh menu is
intended. Route stale-dialog recovery through centralized dispatcher error
handling, log the exception, and reset to a known safe window rather than
trying to repair arbitrary callback state.

```python
from aiogram.filters import ExceptionTypeFilter
from aiogram_dialog import DialogManager, StartMode
from aiogram_dialog.api.exceptions import UnknownIntent, UnknownState


async def recover_dialog(event, dialog_manager: DialogManager) -> None:
    logger.exception("Stale dialog callback", exc_info=event.exception)
    callback = getattr(event.update, "callback_query", None)
    if callback:
        await callback.answer()
    await dialog_manager.start(CatalogSG.browse, mode=StartMode.RESET_STACK)


dp.errors.register(recover_dialog, ExceptionTypeFilter(UnknownIntent))
dp.errors.register(recover_dialog, ExceptionTypeFilter(UnknownState))
```

## Styled buttons and custom emoji

Use `Style` from the style module, not the keyboard module. `StyleCase` is the
conditional variant when a getter determines the style; use plain `Style` for
one fixed appearance. This construction is version-targeted to aiogram 3.30.0
and aiogram-dialog 2.6.0:

```python
from aiogram.enums import ButtonStyle
from aiogram_dialog.widgets.kbd import Button
from aiogram_dialog.widgets.style import Style
from aiogram_dialog.widgets.text import Const


open_button = Button(
    Const("Open"),
    id="open",
    style=Style(
        style=ButtonStyle.SUCCESS,
        emoji_id="5368324170671202286",
    ),
)
```

For API details, see the [official aiogram documentation](https://docs.aiogram.dev/)
and [official aiogram-dialog documentation](https://aiogram-dialog.readthedocs.io/).
