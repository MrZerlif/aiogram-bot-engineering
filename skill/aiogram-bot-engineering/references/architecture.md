# Architecture choices for an aiogram bot

Choose a layout that keeps responsibility boundaries visible; do not replace an
already coherent project layout merely to follow a folder template. The useful
boundary is between Telegram transport, application composition, and feature
behaviour.

## Compose the application explicitly

`Bot` is the Telegram API client. `Dispatcher` owns update processing and
middleware, while a feature-level `Router` owns handlers and filters for one
area of behaviour. Build the dispatcher at the composition root and include
feature routers there, rather than importing the application dispatcher from
feature modules.

```python
from aiogram import Bot, Dispatcher, Router
from aiogram.fsm.storage.base import BaseStorage

orders_router = Router(name="orders")

def create_dispatcher(storage: BaseStorage) -> Dispatcher:
    dispatcher = Dispatcher(storage=storage)
    dispatcher.include_router(orders_router)
    return dispatcher
```

Make settings and dependencies explicit at that root: load configuration once,
construct the `Bot`, storage, services, and repositories there, then pass what
handlers need through dependency injection or dispatcher context. Keep bot
tokens, database addresses, and webhook secrets outside source code, in
environment variables or a secret manager.

## State and persistence

Use the FSM for short-lived conversational progress (for example, a multi-step
form). It is not the source of truth for orders, permissions, or other business
records; persist those in the domain's durable store. FSM storage records the
conversation's transient state, while durable business state has its own
repository, schema, and transaction boundary. See [production engineering](production-engineering.md)
when that boundary needs PostgreSQL, concurrency, or lifecycle guidance.
Keep per-user progress in `FSMContext` through the configured storage; never
track it in module-level dictionaries, mutable handler globals, or singleton
objects shared by multiple updates.

Code should depend on the `BaseStorage` abstraction. `MemoryStorage` is useful
only for local development and tests: it loses state when a process restarts
and cannot coordinate multiple instances. Production needs persistent storage,
such as a supported Redis-backed `BaseStorage` implementation, sized and
operated according to the deployment's reliability needs.

## Errors and update delivery

Put unexpected-error handling at a central boundary, log enough structured
context to diagnose the failing update, and re-raise or otherwise propagate
the exception. Do not silently convert unknown failures into a successful
update; feature handlers should handle only errors they understand.

Select exactly one delivery mode for a running instance: polling is a simple
choice for local or modest operation, while webhooks are an HTTPS endpoint
operated by a web server. They are mutually exclusive for the same bot update
stream, so deployment configuration must choose one and keep the other off.
