---
name: framework-core
description: The rules of this Python + Playwright + pytest framework core — pytest-playwright's browser per worker and a fresh context per test, pages over Playwright locators created in __init__ and returned by the actions that lead to them, expect() for every wait (no sleeps), components only for widgets a locator call doesn't cover, JSON test data and typed UI texts reaching tests as fixtures, API preconditions as yield fixtures, failure evidence and traces, known bugs as xfail(strict=True), settings in layers (YAML, env file, env vars, options), local browsers or a playwright run-server. Use whenever writing or changing pages, components, tests, test data, browser config or settings.
---

# Framework core — the rules (python-playwright)

A pytest framework, written the Python way, with Playwright's own idioms: the browser comes from
`pytest-playwright` (adapted in `autotests/browser.py`), pages hold lazy locators, `expect` waits.
The invariants come from the `qa-core` plugin (`qa-core:test-rules`); the workflow (writing and
running tests, login, onboarding, site map) from `qa-core` + `qa-python` (its skills' Playwright
reference: `references/playwright.md`), both enabled in `.claude/settings.json`.

## Which skill when — load it before the work, not after

The routing table lives in the plugin: **`qa-core:which-skill`**. This file holds the framework's
**rules**; the plugins the **workflow**. **Writing or changing a test, or its data → load
`qa-python:test-data` first, always.**

## Browser

- pytest-playwright's fixtures, adapted (`autotests/browser.py`, registered after it): a
  **browser per xdist worker** — launched locally (`runner: local`; browsers by `make browsers`)
  or connected to a `playwright run-server` (`runner: server`, `PLAYWRIGHT_SERVER_URL`;
  `docker-compose.playwright.yml`, its version = the `playwright` package's) — and **a fresh
  context per test** (`context`): no cookies, storage or pages leak between tests, at a fraction of
  a new browser's cost. Tests and page fixtures take **`page`** (this test's, on its context).
- `page` sets the context's timeouts from the settings (`timeouts.action`, `.navigation`) and keeps
  the browser console for the failure artifacts. `expect`'s timeout = `timeouts.action`.
- Browser choice: `browser.name` (chromium | firefox | webkit) or pytest-playwright's
  `--browser`; headed: `--headed` (with `-n 0` to watch). `--tracing retain-on-failure` is on
  (`pyproject.toml`), traces in `build/reports/traces/`.
- Logged in before the test starts: the `authenticate(context, user)` fixture (ONBOARD —
  `qa-python:login-strategies`): the session cookie (`context.add_cookies`, host-only: `url`, no
  `domain`) or a saved storage state — never the login form outside the login-flow tests. The
  user: `@pytest.mark.as_user(User.ADMIN)`, default the least privileged `User.USER`.

## Settings

Layers, later wins: `config/application.yml` → `config/application-ci.yml` (`CI=true`) →
`resources/env/<env>.yml` (`--env` / `TEST_ENV`, default `dev`) → env vars (`BASE_URL`, `RUNNER`,
`BROWSER`, `HEADLESS`, `PLAYWRIGHT_SERVER_URL`, `TIMEOUT`) → options (`--env`, `--runner`;
pytest-playwright's `--browser`, `--headed`). One frozen `Settings` per run (the `settings`
fixture); nothing else reads `os.environ`. An env file holds URLs and non-secret per-env settings;
logins are test data.

## Pages

- `BasePage(page, settings)`: `path` (relative to `base.url`), `ready()` (the locator that shows
  the page is usable — override when the URL isn't enough), `open()`, `wait_loaded()` (the URL,
  then `ready()` visible), `title()`.
- **Locators are created once in `__init__`** (`self._save = page.get_by_role("button",
  name="Save")`) — lazy, resolved on every use, never stale; a locator built from data at run time
  is a method (`self._row(name)`). Order: `get_by_test_id`, `get_by_role` + name, `get_by_label`,
  `get_by_placeholder`, `get_by_text` (only for the text that *is* the thing), CSS last.
  **Strict mode**: a locator matching two elements fails the action — fix the locator, never
  `.first` as a fix.
- **The test talks to the page, never to its locators**: locators are `_private`; one method per
  user action **whatever its outcome** — fluent (`return self`) when it stays, the next page when
  it leads there (`submit() -> SubmittedPage`, returned `wait_loaded()`), nothing when the landing
  depends on the data; reads return values or page records (`list[Order]`), never `dict` rows.
- **Pages come from the actions that lead to them**: a test takes its entry page from a fixture
  (`web_form_page`, opened) and every other page as a local from the action. A page variable is
  named after its class (`web_form_page`), never `page` — that name is Playwright's `Page`.
- **A page object lives for one test**, on the test's `page`: no state in class attributes.

## Components

`autotests/components/`: a small class around a widget's root `Locator` when one locator call
doesn't cover it and a second page needs the same code (`Table` reads rows as text for the page's
records; a react-select, a date picker when the app has them). Not a wrapper per control — an input
is `fill`, a select `select_option`, a checkbox `set_checked`. **No new component without the
user's yes** when an existing one could be extended.

## Waits

- **Playwright waits before every action** (attached, visible, stable, enabled, receives events):
  no explicit wait before a click or a fill.
- **A state is awaited with `expect(...)`** (`to_have_text`, `to_be_visible`, `to_have_count`,
  `to_have_url`) — it retries until the timeout; the failure names the locator and what it got.
  Reading a value for a check: `expect` when the value arrives async, `inner_text()` /
  `input_value()` when it is already there.
- **No `time.sleep`, no `wait_for_timeout`** in pages or tests. Wait for what *your* action
  produces: a response (`page.expect_response(...)`), a new page (`context.expect_page()`), a
  download (`page.expect_download()`), an element's state — never "network idle".

## Package layout — the framework in `autotests/`, the app by area

```
src/autotests/          config/ browser.py support/ components/ pages/base_page.py data/
                        api/client.py auth/ plugin.py              ← the framework
src/autotests/pages/<area>/        the app's pages              (orders/order_page.py)
src/autotests/api/<area>/          the app's API clients + dto.py
src/autotests/testdata/<area>.py   functions building what tests create through the API
tests/<tms-suite>/…/test_<leaf>.py  tests, mirroring the TMS tree
tests/steps/<area>.py              flows several tests need as preconditions
tests/conftest.py                  page, data, texts and precondition fixtures; authenticate
resources/env/ resources/data/ resources/files/
```

A package past ~10 modules splits by area; a module past ~500 lines splits by screen.

## Test data, API, cleanup

- Data: `resources/data/<model>.json` (`OrderData` ← `order-data.json`), variants by name; the
  main one is `"default"`; `resources/data/<env>/<file>` replaces the shared file whole.
  Placeholders (`{{uniqueTimestamp}}`, `{{inDays:3}}` = an ISO date, `{{inDays:3:%m/%d/%Y}}`
  strftime, `{{text:N}}`, Faker…) — re-resolved on every load. Models extend `TestData` (pydantic:
  frozen, unknown keys refused, camelCase JSON keys → snake_case fields, repr = the class name
  only; secrets `SecretStr`).
- In tests: `order_data = data_fixture(OrderData)` in conftest → `def test_x(..., order_data)`;
  another variant: `@pytest.mark.parametrize("order_data", ["prn"], indirect=True)`; a data table:
  `parametrize(..., variant_names(OrderData), indirect=True)` — the test id carries the variant
  name. The app's texts: `ui-texts.json`, one typed model per area in `data/texts.py`
  (`class OrdersTexts(UiTexts)`, its `area` key) → `orders_texts = texts_fixture(OrdersTexts)`; a
  test annotates `orders_texts: OrdersTexts` — pyright checks every name.
- **What goes to data files**: what varies — per environment, per variant, per user, generated
  (unique, dates) — and the app's texts. A value one test uses once and that changes with nothing
  (a count, a fixed option of the case) may stay a named constant or a literal in the test.
- Logins: `resources/data/user-data.json` (row per `User`, lower case) through `credentials(user)`
  — never env vars, CI secrets or YAML. Tooling tokens (TMS, CI) only in a git-ignored
  `.env.local`.
- API: `api/<area>/<x>_api.py` takes the request DTO (pydantic, `model_dump(by_alias=True)`) and
  returns parsed responses (`ApiResponse.expect_status(201).as_model(OrderResponse)`) — never a
  dict built field by field; bodies logged with secrets masked. `api.as_user(user)` — ONBOARD
  the app's auth. `WebClient` for plain HTTP to the web app (redirects are answers).
- Preconditions through the API, not through other screens: a fixture creates, `yield`s, and
  deletes in `finally` — also when the test fails. Keep the id as soon as the app hands it out
  (a callback, before the save completes), so a save failing midway is cleaned up too. Building
  a record is a plain function (`testdata/orders.py: create_order(...)`), not a class. Never
  delete by hand in a test. A run killed midway leaves records: sweep them at the next run's
  start in a session fixture only when the app's names tell ours apart.

## Failures

`build/reports/failures/<test>/`: `screenshot.png`, `page.html`, `console.log`, `info.txt` — for
a failed test **and for a known bug failing as expected** (xfail): the proof it fails *because of*
the bug, not a locator. Playwright's **trace** of a failed test (every action with the DOM before
and after, the network, the console): `build/reports/traces/<test>/trace.zip` →
`uv run playwright show-trace <it>` — read it before changing a locator or a wait. `build/logs/tests/<test>.log` — one log per test; `build/test-results/
junit.xml` for CI and the TMS.

## Tests

- Test code mirrors the TMS tree: top-level suite → package, leaf suite → `test_<leaf>.py`, case →
  `def test_<id>_<title>` — **TestRail** `test_C123_…` (trcli `parse_junit --case-matcher name`
  reads it from junit.xml), **Qase** read-only `test_LS83_add_new_diagnosis` (+ the id in the
  docstring), a writable Qase: its pytest reporter. A test without a case has no id; never invent
  one.
- **Soft assertions — `pytest-check`**: one `with check: assert …, "what"` per expectation, so a
  run reports every broken one of the case; a plain `assert` only where going on is pointless (a
  precondition failed, a known bug blocking the next steps). The message says what was expected.
- **An assertion only checks**: no action or navigation inside `assert` — the action is its own
  statement before it.
- **Known product bugs**: `@pytest.mark.xfail(strict=True, reason="<the finding>")` (a race that
  shows only at some speeds: `strict=False` with that in the reason, until it is understood) — the test
  runs every time: XFAIL while the bug is there (with failure artifacts as proof), and a fixed bug
  turns the run **red** (XPASS, `xfail_strict = true`) — drop the marker then. Never `skip` it,
  never loosen the assertion. Prove it before marking: run it, read the artifacts — it must fail on
  the bug, not on a locator or data.
- **A test module holds only tests** (and its imports): fixtures in conftest.py, flows tests repeat
  as preconditions in `tests/steps/<area>.py` (complete actions of the positive flow ending in a
  stable state, named verb + object — `create_order`), a step checks with a plain `assert`.
- Steps a case repeats from another automated case are its precondition: done through a fixture
  or a step, not checked again.
- **Parallel = processes** (`-n N`, pytest-xdist): no shared state between tests anyway; a value
  that must be unique across workers: `{{uniqueTimestamp}}` (carries the worker number). A resource
  of the environment several tests switch (a feature flag): a file lock per resource, not a module
  global — ask before adding one.
- A test that hangs fails alone: `timeout = 300` (pytest-timeout, setup included). The HTML
  report `build/reports/report.html` (pytest-html) carries each failure's screenshot and URL.
- A shared resource of the environment (a global switch): `@pytest.mark.shared_state(key, state)`
  — same-state tests run together, another state waits (looking again, never queued behind the
  holders), the rarer state's tests are collected first so a run switches once and back.
- `tests/framework` is scaffolding (the wiring on about:blank / set content + onboarding's layer proofs): it goes
  once the project's TMS cases cover the layers.

## Code style — the formatter's

`ruff format` (Black style, 100 columns) and `ruff check` (pyflakes, isort, bugbear, pyupgrade,
naming) and `pyright` (standard mode: what a compiler would catch — a None where a str goes, a
wrong argument) — `make check` runs all three, CI too. Type hints on public functions; `from __future__ import annotations`; docstrings say *what and why* — the behaviour, briefly; when and
where it was found goes to the site map, not the code. A lint rule a whole folder breaks on purpose
(case ids in test names: N802) is ignored once in `per-file-ignores`, never by a `noqa` per line.
Blank lines between Arrange / Act / Assert and around each `with check:`. Python edits through
the editor (Edit tool), never through sed/heredoc scripts on source files.

## Running locally

```bash
uv run pytest -n 4                                     # all, 4 browsers in parallel
uv run pytest tests/orders/test_orders.py::test_x -n 0 --headed   # watch one
uv run pytest --runner grid -n 4                       # on the Grid (GRID_URL)
uv run pytest --browser firefox
docker compose -f docker-compose.grid.yml -f docker-compose.ci.yml up --build \
  --abort-on-container-exit --exit-code-from tests     # exactly like CI
```

## Shared state of the environment

A case that needs a global switch (a feature flag, a setting every user sees) in a state says
`@pytest.mark.shared_state("<key>", <state>)` — never a switch call in its body. The autouse
`_shared_state` fixture holds a lock file per key (`support/shared_state.py`): same-state tests
run in parallel, another state waits its turn, the state is set once per turn through the
project's `shared_state_setter` (ONBOARD: override it in conftest.py — key → (read, write) over the
app's API). It orders this machine's runs only: another run on the environment can flip it back —
check the page's state before the step that depends on it, and read a failure there as that first.

## CI contract (details: `qa-python:ci-setup`, its Playwright reference)

One command (`uv run pytest -n $TESTS_THREADS`), config by env (`CI=true`, `RUNNER=server`,
`PLAYWRIGHT_SERVER_URL`, `TEST_ENV`, `BASE_URL`), browsers in a `playwright run-server`
(`docker-compose.playwright.yml`, its version = the `playwright` package's — bump together), results
in `build/` (junit.xml, report.html, logs, failure artifacts, traces), exit code = the result,
`Dockerfile` = the runner image (no browsers in it). Locally the same as CI:
`docker compose -f docker-compose.playwright.yml -f docker-compose.ci.yml up --build
--abort-on-container-exit --exit-code-from tests`.

## This project

ONBOARD: the app, its environments, its TMS, the decisions the onboarding records — in
`.claude/project-profile.md`; app facts in `.claude/site-map/`.
