# python-playwright-framework-template

Starting point for a new UI-automation project: **Python + Playwright + pytest** — pytest-playwright's
browser per worker and **a fresh context per test**, page objects over Playwright locators, `expect`
for every wait, test data from JSON and typed UI texts as fixtures, API preconditions as yield
fixtures, failure evidence with Playwright traces, logs per test, local browsers or a
`playwright run-server`, parallel runs — plus the Claude Code setup that drives onboarding and test
writing: the `qa-core` and `qa-python` plugins from
[qa-automation-toolkit](https://github.com/FruNoman/qa-automation-toolkit) are enabled in
`.claude/settings.json` (the toolkit's design: its `docs/ARCHITECTURE.md`). This repo keeps only
`framework-core` (the framework's rules) and `.claude/site-map/` (the map of the app under test).

The same invariants as every stack of the toolkit, in Python's and Playwright's own idioms — no
element library and no waits layer: Playwright's locators and auto-waiting are the framework there.

## Start a new project

1. Create a repo from this template, open it in Claude Code (accept the plugins).
2. Ask: *"onboard this project"* — `qa-core:onboard-new-project` works in stages and stops for your
   go after each: discovery and interview → skeleton (env files, the example replaced by the app's
   entry page, green locally, on the run-server and like CI) → base architecture (login, API
   client, test data, cleanup, failure artifacts, each proven by one check in `tests/framework`).
3. Then, on request: pages (`qa-python:add-page`), API clients (`qa-python:add-api-client`), TMS
   suites (`qa-core:import-tms-suite`), single tests (`qa-python:new-web-test`), CI
   (`qa-python:ci-setup`). Every place the template expects a change is marked `ONBOARD:`.

## What's inside

| Path | What |
|---|---|
| `autotests/browser.py` | pytest-playwright adapted to the settings: launch or `connect_options` (run-server), base URL, viewport, timeouts, the `page` fixture logged in by `authenticate`, its console kept |
| `autotests/pages/base_page.py` | `BasePage(page, settings)`: `path`, `ready()`, `open()`, `wait_loaded()` |
| `autotests/components/` | `Table` — widgets one locator call doesn't cover; no wrapper per control |
| `autotests/config/` | settings in layers: `config/application.yml` → `application-ci.yml` (CI=true) → `resources/env/<env>.yml` → env vars → options |
| `autotests/data/` | `TestDataLoader` (JSON variants, per-env files, placeholders `{{uniqueTimestamp}}`, `{{inDays:3}}` ISO / `{{inDays:3:%m/%d/%Y}}`, Faker…), `TestData` models (pydantic), `data_fixture`, typed texts (`UiTexts`, `texts_fixture`; `ui-texts.json` and/or one `ui-texts/<area>.json` per area, merged) |
| `autotests/api/` | `ApiClient` (requests + pydantic DTOs, `as_user`), `forms.py` for server-rendered forms |
| `autotests/testdata/` | functions building what tests create through the API; the fixture that calls one yields and deletes |
| `autotests/support/` | failure artifacts, the shared-state lock |
| `autotests/known_bug.py` | `with known_bug("<KEY>: <why>"):` — a known bug scoped to the one check it breaks: XFAIL while it reproduces, red once it doesn't (strict); whole-test `xfail(strict=True)` only when the bug blocks the test's start |
| `autotests/step.py` | `with step("<what the user does>"):` around each case step (or `@step("…")` on a page method) — `STEP <n>: …` in the test's log, the steps in the HTML report, the failed step in the failure's info |
| `autotests/plugin.py` | the pytest plugin: options, settings, user, authenticate, data/texts/api fixtures, the rarer shared state collected first, logs per test, artifacts on failure and xfail (screenshot in the HTML report) |

## Run

```bash
uv sync && make browsers                      # once: dependencies + Chromium
uv run pytest -n 4                            # everything, parallel (make test)
uv run pytest tests/example/test_web_form.py::test_submit -n 0 --headed   # watch one
uv run pytest --browser firefox -n 4          # another browser (uv run playwright install firefox)
docker compose -f docker-compose.playwright.yml up -d && RUNNER=server uv run pytest -n 4
docker compose -f docker-compose.playwright.yml -f docker-compose.ci.yml up --build \
  --abort-on-container-exit --exit-code-from tests                        # exactly what CI runs
make check                                    # ruff + pyright + scripts/audit.py (the framework's own rules)
make hooks                                    # once per clone: style gate before every commit (.githooks/pre-commit)
```

A failed test leaves `build/reports/failures/<test>/` (screenshot, page.html, console, info) and
`build/reports/traces/<test>/trace.zip` (`uv run playwright show-trace <it>`); the run's
`build/reports/report.html` and `build/test-results/junit.xml`.

## Qase

A writable Qase reports through its pytest reporter: add `qase-pytest` to the dependencies, a test of
a case carries `@qase.id(<id>)` (and the id in its name), reporting is off unless
`QASE_MODE=testops` (+ `QASE_TESTOPS_PROJECT`, `QASE_TESTOPS_API_TOKEN` — tooling tokens, never in
the repo). Tests without a case id are never reported: the plugin marks them `qase_ignore` (in
testops mode a result without a case id makes Qase create a new case outside the suite) — so
`tests/framework` and helper tests stay out of the TMS.
