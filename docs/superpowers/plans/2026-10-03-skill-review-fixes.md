# Aiogram skill review fixes — Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` to implement this plan task-by-task in the current workspace. Steps use checkbox syntax for tracking. Independent tasks do not require subagents; the requested execution target is a less capable model working from explicit instructions.

**Goal:** Исправить четыре воспроизведённые недоработки скилла, добавить регрессионные проверки и сохранить достоверность исторических eval-артефактов.

**Architecture:** Mini App validator остаётся каноническим Python-примером в справочнике; тесты исполняют именно этот пример. Webhook получает отдельный import-safe пример с durable inbox: HTTP 200 означает завершённый durable commit, а обработка через Dispatcher выполняется worker после приёма. Форматы JSON Schema проверяются дополнительными test-зависимостями; dependency-free валидатор реестра сохраняет свой интерфейс.

**Tech Stack:** Python 3.10+, aiogram 3.30.0, aiogram-dialog 2.6.0, aiohttp из зависимостей aiogram, pytest, pytest-asyncio, jsonschema Draft 2020-12, uv, PowerShell.

**Spec:** Раздел «Требования и подтверждённые дефекты» этого документа является спецификацией. Основание — review в текущем чате; исходные файлы проверены 3 октября 2026 года. Не требуется читать старые дизайн-документы про presentation или переосмысливать весь скилл.

## Global Constraints

- Рабочий каталог: `C:\programs-_-\projects\github\aiogram-bot-engineering`.
- Источник устанавливаемого скилла: `skill/aiogram-bot-engineering/`, а не корень репозитория.
- Совместимость остаётся Python 3.10+, aiogram **3.30.0**, aiogram-dialog **2.6.0**, Bot API **10.2**. Не обновлять эти версии ради исправлений.
- В рабочем дереве уже есть изменённые и новые файлы. Сначала прочитать их актуальное содержимое. Не выполнять reset, clean, checkout с перезаписью, stash или перенос в worktree, который исключит текущие изменения.
- Выполнять локальные исправления без запроса approval. Не делать commit, push, PR, deploy или обращения к Telegram в рамках этого плана.
- Тесты используют фиктивный `Bot("42:TEST")`, mocked requests и fake inbox; они не открывают Telegram-соединения, не запускают polling и не читают реальные секреты.
- Не добавлять PostgreSQL, Redis, очередь или production service в этот репозиторий: здесь разрабатывается скилл. Реальный durable adapter предоставляется проектом, использующим пример.
- Не использовать `asyncio.timeout`: он отсутствует в Python 3.10. Использовать `asyncio.wait_for`.
- Скрипт `validate_custom_emoji_registry.py` остаётся dependency-free. `jsonschema` и дополнительные проверки форматов относятся только к repository QA.
- Не переписывать старые ответы модели, retrieval trace, оценки или hashes так, будто новую версию уже оценили.
- Установленная копия вне workspace обновляется только отдельным разрешённым действием после готового и проверенного bundle; это не обязательный этап локального исправления.

## Review Focus

Пять условий, которые должны получить явную проверку в соответствующей задаче:

1. Не-ASCII hash отклоняется как `ValueError`, но корректно подписанные Unicode user data проходят — задача 2.
2. Inbox возвращает ошибку до commit: ответ не 200, Dispatcher не вызывается — задача 5.
3. Commit запаздывает или запрос отменён: успешного подтверждения нет; повтор после неопределённого результата безопасен благодаря ключу `(bot_id, update_id)` — задача 5.
4. Повреждённый `license_url` обрабатывается так же, как `source_url`, а `license_url=null` сохраняет допустимость — задачи 3 и 4.
5. Старый eval должен оставаться проверяемым после изменения текущего bundle; подмена содержимого его снимка обнаруживается — задача 1.

---

## Требования и подтверждённые дефекты

| ID | Где | Воспроизведение | Требуемый результат |
| --- | --- | --- | --- |
| F1 | `references/deployment.md`, webhook example | `SimpleRequestHandler(handle_in_background=False)` возвращает 200 по таймауту `feed_webhook_update`, хотя приём update ещё не завершён | Canonical durable example подтверждает только завершённый inbox commit; timeout/storage failure дают 503 |
| F2 | `references/mini-apps.md`, `validate_init_data` | `auth_date=1&hash=%D1%8F` вызывает `TypeError` внутри `hmac.compare_digest` | Некорректный hash даёт `ValueError`; правильная подпись и проверки возраста сохраняются |
| F3 | `pyproject.toml`, schema QA | В текущем окружении `FormatChecker` не содержит `uri` и `date-time`; malformed strings проходят | Установить format dependencies и доказать отрицательными тестами фактическое отклонение |
| F4 | `scripts/validate_custom_emoji_registry.py`, `_uri` | `source_url="https://[broken"` вызывает неперехваченный `ValueError` из `urlsplit` | Возвращать ошибку конкретного поля; CLI завершается с кодом 1 без traceback |

Дополнительный результат: установленная копия `C:\Users\lfyzer\.codex\skills\aiogram-bot-engineering` сейчас отличается от bundle и не содержит новой schema и validator. Порядок её обновления описан после обязательных задач.

### Решение для F1: durable inbox вместо ожидания бизнес-обработки

Последовательность HTTP boundary:

```text
secret verification -> parse/validate Update -> durable inbox accept -> HTTP 200
                                                   |
                                      failure/timeout -> HTTP 503

committed inbox -> project-owned worker -> Dispatcher.feed_raw_update
```

`accept()` возвращается только после durable commit или подтверждённого существования ранее committed записи. Ключ уникальности — `(bot_id, update_id)`. Worker никогда не зависит от in-memory task, запущенной HTTP request handler.

Интеграция остаётся через официальный `SimpleRequestHandler`: новый класс наследует его secret verification, routing и shutdown hooks, но переопределяет `_handle_request`. Это private extension point, поэтому пример явно привязан к aiogram 3.30.0 и проверяется исполняемыми тестами. HTTP path не вызывает `feed_webhook_update` и не зависит от его 55-секундного механизма.

### Карта файлов

| Файл | Действие и ответственность |
| --- | --- |
| `tests/skill-evals/snapshots/03b1002d0efd7c878fd189ff74bc101db078ff62848473d56cde91f23bde4ba2.zip` | Создать архив именно старого evaluated bundle до изменений |
| `tests/skill-evals/run-manifest.json` | Добавить ссылку и hash архива, сохранив исторические run data |
| `tests/code/test_skill_evals.py` | Проверять исторический hash по архиву, не по текущему изменяемому bundle |
| `skill/aiogram-bot-engineering/references/mini-apps.md` | Проверка формы hash перед `compare_digest` |
| `tests/code/test_mini_app_init_data.py` | Новый тест исполняемого canonical fence |
| `pyproject.toml`, `uv.lock` | Format dependencies без обновления frameworks |
| `tests/code/test_emoji_registry_asset.py` | Отрицательные schema tests, validator и CLI regressions |
| `skill/aiogram-bot-engineering/scripts/validate_custom_emoji_registry.py` | Безопасная обработка `urlsplit` |
| `skill/aiogram-bot-engineering/examples/durable_webhook.py` | Новый import-safe HTTP acceptance example и Protocol |
| `tests/code/test_durable_webhook.py` | Новый executable acceptance/timeout/authentication test boundary |
| `skill/aiogram-bot-engineering/references/deployment.md` | Canonical wiring и объяснение inbox/worker границы |
| `skill/aiogram-bot-engineering/references/testing.md` | Уточнить webhook acceptance assertions |
| `skill/aiogram-bot-engineering/SKILL.md` | Прямая условная ссылка на новый example |
| `scripts/lint_skill_contract.py`, `tests/code/test_lint_skill_contract.py` | Canonical durable example вместо признания одного флага достаточным |
| `README.md` | Команды точечных проверок и статус исторических eval |

## Task 0: Зафиксировать исходное состояние

**Files:** Читать только перечисленные выше файлы по мере соответствующей задачи.

**Interfaces:** Consumes: актуальный working tree. Produces: список уже существующих изменений и подтверждённый исходный bundle hash.

- [x] Выполнить `git status --short` и прочитать текущие версии затрагиваемых файлов. Нельзя считать все обнаруженные изменения результатом своей работы.
- [x] Проверить наличие Python 3.10-compatible окружения и `uv`; использовать текущий `.venv`, если он исправен.
- [x] Вычислить bundle hash по алгоритму `bundle_sha256()` из `tests/code/test_skill_evals.py`: сортировать POSIX relative paths, исключать `__pycache__`, `.pyc`, `.pyo`, для каждого файла добавлять `path_utf8 + b"\0" + original_bytes + b"\0"` в SHA-256.
- [x] Сравнить его с `run-manifest.json -> skill_snapshot.bundle_sha256`. На момент планирования оба значения равны `03b1002d0efd7c878fd189ff74bc101db078ff62848473d56cde91f23bde4ba2`.

Если bundle уже изменился, нельзя объявить его архив старым evaluated input. Сообщить расхождение, попытаться найти существующий точный снимок read-only; без него не менять исторические hashes. Независимые задачи 2–5 можно продолжать, но ограничение eval verification отметить в итоговом отчёте.

## Task 1: Сохранить исторические eval до изменения bundle

**Files:** Create: ZIP из карты файлов. Modify/Test: `tests/skill-evals/run-manifest.json`, `tests/code/test_skill_evals.py`.

**Interfaces:**
- Consumes: старый bundle и прежний алгоритм SHA-256 из задачи 0.
- Produces: `archived_bundle_sha256(archive_path: Path) -> str` в test module и `skill_snapshot.archive: {path: str, sha256: str}` в manifest.

- [x] Сохранить ZIP старого bundle **до любых изменений внутри `skill/aiogram-bot-engineering/`**. Archive entry names — пути относительно bundle с `/`, без enclosing directory. Сохранять исходные bytes без нормализации переносов. Использовать стандартный `zipfile`; архив не извлекать на файловую систему.
- [x] Написать тест `test_archived_bundle_hash_matches_recorded_snapshot`: архивный helper должен воспроизвести прежний алгоритм, и результат равен историческому `skill_snapshot.bundle_sha256`.
- [x] Написать тест `test_archived_bundle_hash_detects_changed_content`: создать два маленьких ZIP в `tmp_path`, изменить bytes одного entry, проверить различие hashes. В архивном helper отклонять duplicate names и paths с `..`, абсолютные paths или backslash; добавить параметризованный тест этих случаев. Сортировка entry names — POSIX lexical.
- [x] Запустить эти тесты и получить ожидаемый FAIL из-за отсутствующего helper/metadata.
- [x] Реализовать `archived_bundle_sha256`, затем добавить `skill_snapshot.archive.path` относительно repository root и SHA-256 **самого ZIP файла**. Не смешивать archive-file hash и semantic bundle hash.

Ключевые assertions test fixture:

```python
assert sha256_file(archive_path) == manifest["skill_snapshot"]["archive"]["sha256"]
assert archived_bundle_sha256(archive_path) == manifest["skill_snapshot"]["bundle_sha256"]
assert archived_bundle_sha256(original_zip) != archived_bundle_sha256(modified_zip)
```

- [x] В `test_run_manifest_binds_inputs_outputs_and_runner_conditions` заменить только сравнение исторического hash с текущим `bundle_sha256()` на проверку archive bytes hash и `archived_bundle_sha256`. Сохранить существующие проверки пяти recorded artifact hashes, run IDs, excerpts и score arithmetic.
- [x] При необходимости дополнить только описательную metadata manifest: архив добавлен после run для сохранения original input; новая версия ещё не прошла model eval. Не менять `collected_on`, `frozen_at`, commit, runner identities, оценки, ответы и retrieval paths.
- [x] Проверить:

```powershell
uv run --locked --group test pytest -q tests/code/test_skill_evals.py
```

Ожидается PASS. Последующее изменение текущего bundle больше не должно подменять или ломать проверку исторических результатов.

## Task 2: Исправить форму hash в Mini App validator

**Files:** Modify: `skill/aiogram-bot-engineering/references/mini-apps.md`. Create/Test: `tests/code/test_mini_app_init_data.py`.

**Interfaces:**
- Consumes: canonical fenced Python example из `mini-apps.md`.
- Produces: прежний `validate_init_data(init_data: str, bot_token: str, max_age: timedelta) -> dict[str, str]`, который для malformed hash выбрасывает `ValueError`.
- Test helpers: `load_canonical_validator() -> Callable[[str, str, timedelta], dict[str, str]]`; `sign_init_data(fields: dict[str, str], bot_token: str) -> str` для построения подписанных inputs. Signing helper использует сортировку key/value, HMAC-SHA-256 с ключом `WebAppData`, затем `urlencode`; поля fixture задаются в самих тестах.

- [x] В новом test module написать loader, который находит ровно один fenced `python` block с AST `FunctionDef` по имени `validate_init_data`, компилирует и исполняет этот block в отдельном namespace. Не копировать validator в тест и не создавать второй production implementation. Проверять, что найден ровно один canonical function.
- [x] Добавить `test_malformed_hash_raises_value_error` с `pytest.mark.parametrize`: `я`, пустой hash, 63 символа `a`, 65 символов `a`, 64 символа `g`, пробелы. Assertions: `pytest.raises(ValueError)`; ошибка не `TypeError`. Unicode случай использовать через `urlencode`, чтобы тест не зависел от ручного URL escaping.
- [x] Добавить positive test `test_valid_signed_unicode_data_is_accepted`: fixture подписывает `auth_date` и JSON `user` с Unicode именем `Иван`, `ensure_ascii=False`; `auth_date` брать как `int(time.time()) - 2`, `max_age=timedelta(minutes=5)`. Результат содержит исходный user JSON и auth_date, без поля hash.
- [x] Добавить `test_tampered_hash_is_rejected`: правильный 64-char hex hash с изменённой первой цифрой даёт `ValueError("invalid hash")`.
- [x] Добавить проверки duplicate fields, missing hash, expired и future-dated подписанных данных. Для timestamps брать отклонение ±600 секунд, чтобы избежать пограничной зависимости от длительности теста. Неподписанный старый timestamp не доказывает age validation.
- [x] Запустить `uv run --locked --group test pytest -q tests/code/test_mini_app_init_data.py`. Unicode malformed case должен воспроизвести FAIL с текущим `TypeError`.

Минимальный regression test:

```python
def test_non_ascii_hash_raises_value_error() -> None:
    validator = load_canonical_validator()
    raw = urlencode({"auth_date": "1", "hash": "я"})
    with pytest.raises(ValueError):
        validator(raw, "test-token", timedelta(minutes=5))
```

- [x] В canonical fence добавить `import re` и перед HMAC comparison проверить `re.fullmatch(r"[0-9a-f]{64}", received_hash)`. Отсутствующий hash продолжает давать `ValueError("missing hash")`; malformed — `ValueError("invalid hash")`. Остальной HMAC алгоритм, сортировку полей и authorization boundary не менять.
- [x] Повторить команду: все случаи PASS. Проверить `python scripts/lint_skill_contract.py .` через `uv run --locked --group test` — fence остаётся valid Python.

## Task 3: Включить реальные проверки schema formats

**Files:** Modify: `pyproject.toml`, `uv.lock`, `tests/code/test_emoji_registry_asset.py`.

**Interfaces:**
- Consumes: существующая Draft 2020-12 schema.
- Produces: repository environment, в котором `FormatChecker` реально отклоняет malformed `uri`, `uri-reference` и `date-time`.

- [x] Добавить `test_schema_rejects_malformed_uri_fields` для `packs[0].source_url` и `packs[0].license_url`, значения `https://[broken` и `not an absolute URI`. Проверять реальный `Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document)`: должна существовать ошибка с `validator == "format"` и нужным `absolute_path`.
- [x] Добавить `test_schema_rejects_malformed_verified_at`: значения `not-a-date`, `2026-13-40T00:00:00Z`, `2026-08-20T00:00:00` без timezone. Остальные поля fixture допустимы. Проверять format error на `emoji[0].verified_at`, а не наличие произвольной другой ошибки.
- [x] Добавить `test_schema_rejects_malformed_schema_uri_reference`: `$schema="http://[broken"` должен дать format error; относительная ссылка `./custom-emoji-registry.schema.json` остаётся допустимой.
- [x] Добавить positive cases: HTTPS URI, IPv6 URI `https://[::1]/icons`, timestamp `2026-08-20T00:00:00Z`, timestamp с `+03:00`, nullable license URL, disabled starter registry.
- [x] Запустить новые negative tests до изменения зависимостей: ожидать FAIL, поскольку optional format checkers сейчас отсутствуют.

Пример точного assertion, который исключает случайный PASS из-за другой ошибки fixture:

```python
document = load_starter_registry()
document["packs"][0]["source_url"] = "https://[broken"
errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document))
assert any(
    error.validator == "format" and list(error.absolute_path) == ["packs", 0, "source_url"]
    for error in errors
)
```

- [x] Заменить ровно dependency `jsonschema>=4.23,<5` на `jsonschema[format-nongpl]>=4.23,<5`. Этот extra подтверждён metadata установленной jsonschema и включает URI/date-time validators. Не переносить его в production dependencies.
- [x] Выполнить `uv lock`, затем `uv sync --locked --group test`. Проверить diff lockfile: frameworks остаются 3.30.0 и 2.6.0; изменения обусловлены добавленным extra. Не выполнять `uv lock --upgrade`.
- [x] Проверить:

```powershell
uv run --locked --group test pytest -q tests/code/test_emoji_registry_asset.py
```

Ожидается PASS, включая отрицательные проверки реального поведения. Проверка одного списка `FormatChecker.checkers` сама по себе недостаточна.

## Task 4: Обрабатывать повреждённые URL в dependency-free validator

**Files:** Modify: `skill/aiogram-bot-engineering/scripts/validate_custom_emoji_registry.py`, `tests/code/test_emoji_registry_asset.py`.

**Interfaces:**
- Consumes: `_uri(value: Any, path: str, errors: list[str], *, nullable: bool = False) -> None`.
- Produces: тот же интерфейс; malformed URL добавляет `f"{path}: expected an absolute URI"` вместо исключения. CLI exit codes сохраняются: 0 valid, 1 invalid, 2 incorrect usage.

- [x] Добавить `test_validator_reports_malformed_url_without_raising`, параметризованный по `source_url` и `license_url`, со значениями `https://[broken` и строкой `https://example.com\uff1a443/icons` с символом, который нарушает NFKC parsing netloc. Проверять returned errors с полным path конкретного поля.
- [x] Добавить `test_validator_cli_rejects_malformed_url_without_traceback`: записать изменённый registry в `tmp_path`; вызвать `main([str(path)])`; assert exit code 1, field path присутствует в stderr, `Traceback` отсутствует.
- [x] Positive checks: `license_url=None`, обычный HTTPS URL и `https://[::1]/icons` не дают URI ошибок; disabled starter остаётся valid.
- [x] Запустить новые tests до исправления: ожидать FAIL с `ValueError` из `urlsplit`.

Минимальный regression assertion:

```python
document = load_starter_registry()
document["packs"][0]["source_url"] = "https://[broken"
errors = load_registry_validator().validate_registry(document)
assert "registry.packs[0].source_url: expected an absolute URI" in errors
```

- [x] В `_uri` обернуть только `urlsplit(text)` в `try/except ValueError`. В except добавить указанную ошибку в `errors` и `return`. После успешного parsing сохранить проверки scheme/netloc. Не ловить все `Exception` и не скрывать программные ошибки.
- [x] Проверить:

```powershell
uv run --locked --group test pytest -q tests/code/test_emoji_registry_asset.py
uv run --locked --group test python skill/aiogram-bot-engineering/scripts/validate_custom_emoji_registry.py skill/aiogram-bot-engineering/assets/custom-emoji-registry.example.json
```

Ожидается PASS; CLI сообщает valid для starter. Не добавлять новые требования к лицензиям, semantic aliases или production IDs в эту задачу.

## Task 5: Добавить исполняемый durable webhook example

**Files:** Create: `skill/aiogram-bot-engineering/examples/durable_webhook.py`, `tests/code/test_durable_webhook.py`. Modify: `skill/aiogram-bot-engineering/references/deployment.md`, `skill/aiogram-bot-engineering/references/testing.md`, `skill/aiogram-bot-engineering/SKILL.md`, `scripts/lint_skill_contract.py`, `tests/code/test_lint_skill_contract.py`.

**Interfaces:**
- `class DurableInbox(Protocol)` с методом `async def accept(self, *, bot_id: int, update_id: int, payload: dict[str, Any]) -> None`.
- `class DurableWebhookRequestHandler(SimpleRequestHandler)` с `def __init__(self, dispatcher: Dispatcher, bot: Bot, *, inbox: DurableInbox, secret_token: str, acceptance_timeout: float = 10.0) -> None`.
- Override: `async def _handle_request(self, bot: Bot, request: web.Request) -> web.Response`.
- Canonical wiring: `async def start_webhook(bot: Bot, dispatcher: Dispatcher, inbox: DurableInbox) -> web.Application` в справочнике; real Bot API вызовы находятся только в явно вызываемой runtime function, не при импорте example.
- Worker принадлежит проекту: читает committed inbox, вызывает `dispatcher.feed_raw_update(bot, update=payload)`, помечает запись обработанной после успеха, повторяет ошибки согласно durable retry policy.

### 5.1. Сначала доказать acceptance contract тестами

- [x] Импортировать example по file path через `importlib.util`, как сделано в `test_dialog_bot.py`. Добавить модуль в `sys.modules` на время импорта при необходимости. Не читать `BOT_TOKEN` и не запускать event loop при импорте.
- [x] Написать fixtures: local fake inbox, `Bot("42:TEST")`, Dispatcher и mocked aiohttp request. У request методы `json` — `AsyncMock`; у Bot реальная session не выполняет запросов. В teardown закрыть bot session и dispatcher storage.
- [x] Fake inbox имеет per-test dictionary с ключом `(bot_id, update_id)`, сохраняет исходный payload после разрешения test Event и возвращает существующую запись на duplicate. Это test double, а не предлагаемый production storage.
- [x] Вызывать именно `await handler.handle(request)`, чтобы проверить inherited authentication до parse/accept. Не ограничиваться прямым вызовом `_handle_request`.
- [x] Написать следующие assertions:

| Test | Input/action | Assertions |
| --- | --- | --- |
| `test_invalid_secret_rejected_before_parsing` | missing header / неправильный ASCII secret | 401; `request.json` не awaited; inbox не вызван |
| `test_success_waits_for_committed_inbox` | accept блокируется на Event | HTTP task не завершён до release; после release 200 и payload сохранён |
| `test_inbox_failure_is_not_acknowledged` | accept raises RuntimeError | 503; успешной записи нет; секрет и payload отсутствуют в captured logs |
| `test_acceptance_timeout_is_not_acknowledged` | accept ожидает Event; timeout 0.01 | 503; fake accept получает cancellation; записи нет |
| `test_request_cancellation_propagates` | cancel HTTP task во время accept | `CancelledError` propagates; записи нет; нет оставленной accept task |
| `test_duplicate_update_uses_same_inbox_key` | два запроса с одинаковым update | два 200; один persisted key в fake; одинаковые `(bot_id, update_id)` переданы adapter |
| `test_update_ids_are_scoped_by_bot` | update_id тот же, Bot IDs 42 и 43 | два разных inbox keys; данные не смешиваются |
| `test_invalid_json_or_update_is_rejected` | json decode error / payload без update_id | 400; inbox не вызван |
| `test_http_path_never_dispatches` | valid request | `feed_webhook_update`, `feed_update`, `feed_raw_update` dispatcher mocks не awaited |
| `test_acceptance_timeout_configuration` | 0, -1, NaN, infinity | constructor raises ValueError; positive finite default принят |

- [x] Для pending assertion использовать `entered` и `release` Events, а не большие sleep. Оборачивать ожидания событий в test-side `asyncio.wait_for(..., timeout=1.0)` для защиты от зависания.

Главный acceptance test использует fixtures `handler`, `http_request`, `inbox`; у fake inbox есть `entered`, `release` и `records`, у HTTP input update_id равен 1. Не называть fixture `request`: это зарезервированная встроенная pytest fixture.

```python
@pytest.mark.asyncio
async def test_success_waits_for_committed_inbox(handler, http_request, inbox):
    response_task = asyncio.create_task(handler.handle(http_request))
    await asyncio.wait_for(inbox.entered.wait(), timeout=1.0)
    assert not response_task.done()
    assert inbox.records == {}
    inbox.release.set()
    response = await asyncio.wait_for(response_task, timeout=1.0)
    assert response.status == 200
    assert (42, 1) in inbox.records
```

Закрывать/отменять `response_task` в `finally` при падении assertion, чтобы regression не оставлял pending tasks.

- [x] Запустить новый test module и получить ожидаемый FAIL из-за отсутствующего example. При реализации tests не должны требовать реальных aiohttp listener sockets.

### 5.2. Реализовать минимальный example

- [x] Создать Protocol и класс с указанными интерфейсами. Module-level разрешены imports, logger и определения; не разрешены env reads, Bot creation или запуск сервера.
- [x] Constructor: проверить positive finite `acceptance_timeout` и непустой secret с официальными ASCII символами `[A-Za-z0-9_-]`, длина 1–256. Документированный production config loader сохраняет более строгий минимум 43 символа. Вызвать `super().__init__(dispatcher=dispatcher, bot=bot, handle_in_background=False, secret_token=secret_token)`; не давать caller возможность включить background acknowledgement.
- [x] `_handle_request`: прочитать JSON через `request.json(loads=bot.session.json_loads)`; `json.JSONDecodeError` и `UnicodeDecodeError` дают 400. Если parsed value не `dict`, вернуть 400. Проверить `Update.model_validate(raw_payload, context={"bot": bot})`; `pydantic.ValidationError` даёт 400. Не ловить все ошибки parse stage как malformed user input.
- [x] Передать original JSON payload в `inbox.accept(bot_id=bot.id, update_id=validated_update.update_id, payload=raw_payload)`, ожидая через `asyncio.wait_for` с configured timeout.
- [x] Вернуть 200 с пустым body только после успешного завершения accept. Timeout и storage exception дают 503. Не запускать fallback task, не продолжать бизнес-обработку внутри HTTP path, не отправлять Bot API method в response body.
- [x] Не перехватывать `asyncio.CancelledError`. Для storage failures логировать безопасные bot_id/update_id/error type, без secret header, token, original payload и полного exception message, который adapter может сформировать из этих данных.
- [x] В docstring Protocol зафиксировать: atomic durable commit; unique `(bot_id, update_id)`; duplicate success только для committed записи; cancellation cooperative; ambiguous commit outcome разрешается idempotent retry. In-memory implementation не удовлетворяет production contract.
- [x] Запустить `uv run --locked --group test pytest -q tests/code/test_durable_webhook.py`: PASS.

### 5.3. Связать example со скиллом и static contract

- [x] В `deployment.md` заменить canonical production wiring на импорт и использование `DurableWebhookRequestHandler`. Пояснить: copied example module должен быть доступен как `durable_webhook`; adapter и worker предоставляются приложением. Не добавлять fake durable adapter в production snippet.
- [x] Сохранить config loaders и `setup_application`, runtime `bot.set_webhook`, allowed_updates. При обновлении описания secret verification назвать унаследованный `SimpleRequestHandler` verifier.
- [x] Оставить объяснение 55-секундного поведения обычного `SimpleRequestHandler` как мотивацию и ограничение. Убрать формулировку, что `handle_in_background=False` само определяет durable acceptance policy: новый HTTP path не вызывает `feed_webhook_update`.
- [x] Явно объяснить пределы: commit timeout может иметь неопределённый исход; следующий delivery дедуплицируется; worker retry/idempotency нужны отдельно. Этот example не реализует exactly-once внешние эффекты.
- [x] Добавить **прямую** ссылку на `examples/durable_webhook.py` в routing table `SKILL.md`, с условием чтения для durable webhook acceptance. Одной ссылки из `deployment.md` недостаточно: `inspect_skill_routes` проверяет прямые routes.
- [x] В `testing.md` добавить assertions 200-after-commit и non-2xx-on-timeout/storage-error.
- [x] В `_check_documented_api_contracts` сделать наличие вызова `DurableWebhookRequestHandler` в `deployment.md` требованием canonical example. Прежние проверки любого `SimpleRequestHandler` call без `handle_in_background=False` сохраняются; polling и stale-dialog проверки не меняются. Новое missing сообщение: `missing durable webhook acceptance example in references/deployment.md`.
- [x] Если новый example включён в `REQUIRED_BUNDLE_FILES`, обновить `make_valid_repository` и related resource fixtures: создать минимальный синтаксически корректный stub нового файла, добавить прямую SKILL ссылку и canonical durable call с inbox/secret. Fixture не обязана эмулировать runtime — это отдельно проверяет `test_durable_webhook.py`.
- [x] Добавить `test_rejects_simple_handler_as_only_durable_webhook_example`: обычный handler с False и bounded polling не заменяет canonical durable example. Обновить expected missing сообщение в существующем тесте удаления delivery examples. Не удалять negative tests background acknowledgement.
- [x] Проверить:

```powershell
uv run --locked --group test pytest -q tests/code/test_durable_webhook.py tests/code/test_lint_skill_contract.py
uv run --locked --group test python scripts/lint_skill_contract.py .
uv run --locked --group test mypy skill/aiogram-bot-engineering/examples
```

Ожидается PASS и exit code 0. Static AST checks не должны описываться как доказательство фактического durable commit.

## Task 6: Документация, итоговая проверка и self-review

**Files:** Modify: `README.md`; остальные файлы — только для исправления конкретных обнаруженных несогласованностей.

**Interfaces:** Consumes: результаты задач 1–5. Produces: проверенный локальный bundle и точный итоговый отчёт.

- [x] В README описать новый import-safe durable webhook example и включить команды его tests и Mini App tests. Установленный bundle содержит example, но не test dependencies и не maintainer QA scripts.
- [x] В разделе behavioral evidence явно написать: recorded scores относятся к архивным evaluated inputs; текущий исправленный bundle не получает автоматически старую оценку 57/57. Manifest snapshot проверяется по ZIP. Старые model outputs не перегенерируются этим планом.
- [x] Повторно проверить, что aiogram и aiogram-dialog pins не изменены; sync использует updated lock, а example скопируем в реальный проект без repository-only imports.
- [x] Запустить один раз scoped regression set, покрывающий все затронутые области и существующий dialog example:

```powershell
uv run --locked --group test pytest -q tests/code/test_mini_app_init_data.py tests/code/test_emoji_registry_asset.py tests/code/test_durable_webhook.py tests/code/test_lint_skill_contract.py tests/code/test_skill_evals.py tests/code/test_dialog_bot.py
uv run --locked --group test python scripts/lint_skill_contract.py .
uv run --locked --group test python skill/aiogram-bot-engineering/scripts/validate_custom_emoji_registry.py skill/aiogram-bot-engineering/assets/custom-emoji-registry.example.json
uv run --locked --group test mypy scripts skill/aiogram-bot-engineering/examples skill/aiogram-bot-engineering/scripts
git diff --check
```

Этот набор включает существующие repository code tests, потому что изменения затрагивают schema, examples, contract linter и eval binding. Дополнительные широкие integration/load/network проверки не нужны.

- [x] Проверить новый файл отдельно, если `git diff --check` не видит его как untracked: trailing whitespace, UTF-8, отсутствие runtime side effects. Не staging файлы только ради этой проверки.
- [x] Self-review: traceback из URL parsing исключён; malformed hashes нормализованы; schema реально reject malformed formats; нет раннего 200; timeout/cancellation оставляют retry безопасным; archive показывает оригинальные bytes; logs не раскрывают секреты.
- [x] Итог сообщить конкретно: какие F1–F4 закрыты, точные выполненные проверки и результат, какие файлы добавлены, состояние установленной копии. Не приписывать себе все исходные dirty changes и не сообщать о новом model eval.

## Отдельный этап: обновление установленной копии

Обязательные задачи заканчиваются готовым bundle в workspace. На момент review установленный каталог вне workspace устарел. Его изменение требует отдельного разрешения на запись по этому пути; заранее согласовывать локальные исправления не требуется.

1. После PASS показать пользователю source `C:\programs-_-\projects\github\aiogram-bot-engineering\skill\aiogram-bot-engineering` и destination `C:\Users\lfyzer\.codex\skills\aiogram-bot-engineering`, список различающихся/новых файлов и предложенный backup path рядом с destination.
2. Получить явное разрешение, если пользователь не дал его ранее. Если sandbox escalation отклонена, назвать auto-review отказ и его причину; не обходить его другим shell.
3. С разрешением использовать один PowerShell workflow: проверить абсолютные source/destination paths, создать timestamped backup существующего каталога через `Copy-Item -LiteralPath`, затем скопировать только skill bundle. Не применять `robocopy /MIR`, wildcard deletion, `Remove-Item -Recurse` или shell-built команды удаления.
4. Если destination является symlink/junction, сначала проверить resolved target. При уже корректной ссылке на source повторное копирование не нужно; при чужом target не писать через ссылку вслепую.
5. Сравнить hashes всех bundle files, исключая bytecode; отдельно убедиться, что появились schema, validator и durable example. При обнаружении лишних installed files не удалять их автоматически: показать различие.
6. Без разрешения оставить локальные fixes готовыми и указать, что обновление installed copy осталось отдельным действием.

## Критерии готовности

- [x] Все F1–F4 имеют отрицательный regression test, который воспроизводил исходный дефект, и проходящий positive counterpart.
- [x] Python 3.10 совместимость сохранена; frameworks не обновлены; offline validator не получил dependencies.
- [x] Canonical webhook делает 200 только после durable inbox accept, а timeout/failure не подтверждает update.
- [x] Нет скрытого dispatch/background task внутри HTTP boundary; fake storage не выдаётся за production durability.
- [x] Schema URI/date-time проверки действительно активны в locked test environment.
- [x] Исторические eval outputs/score hashes сохранены; изменение текущего bundle не маскируется под старый run.
- [x] Scoped checks завершились успешно; отсутствие real Telegram/deploy проверок не выдаётся за проведённую validation.
- [x] User changes сохранены; готовый diff ограничен описанной областью; installed-copy stage имеет честный отдельный статус.

## Рекомендуемый способ исполнения

Последовательное исполнение через `superpowers:executing-plans` одной моделью в этом workspace. Порядок: 0 → 1 → 2 → 3 → 4 → 5 → 6. Это сохраняет archive до bundle edits и позволяет исправлять сбои в небольшом локальном контексте. Обычные локальные шаги не требуют паузы для подтверждения; запрос разрешения нужен только для отдельного installed-copy stage, если он будет запрошен.
