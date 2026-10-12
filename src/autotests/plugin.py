"""The framework's pytest plugin (pyproject: `-p autotests.plugin`): options, fixtures, hooks.

The browser comes from pytest-playwright (its `--browser`, `--headed`, `--tracing`, its `browser`,
`context`, `page` fixtures) — `autotests.browser` adapts it to the settings: a browser per worker
(launched here, or connected to a `playwright run-server`), **a fresh context per test**, base URL,
viewport and timeouts from the settings, the user logged in by `authenticate`, the console kept.

Fixtures a test (or a page/data fixture in conftest.py) asks for:
  settings          the run's Settings (session)
  page              this test's page (pytest-playwright's, adapted) — pages take it
  user              who the test runs as (`as_user(User.ADMIN)` mark; default: the first User)
  test_data_loader  JSON test data (session); data reaches tests through `data_fixture(...)`
  ui_texts          the app's fixed texts (session); per area through `texts_fixture(...)`
  api               the app's API client (session)

Overridable in conftest.py: `authenticate` (how a context is logged in as a user — ONBOARD:
login-strategies), `shared_state_setter`. What a test creates is cleaned up by the fixture that
creates it (a `yield` fixture: create, yield, delete).
"""

from __future__ import annotations

import base64
import logging
from collections import Counter
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import BrowserContext, Page, expect
from pytest_check import check_log

from autotests.api.client import ApiClient
from autotests.auth.users import Credentials, User
from autotests.config.settings import Settings, load_settings
from autotests.data.loader import TestDataLoader
from autotests.support import artifacts, shared_state

log = logging.getLogger("autotests")

_FORMAT = "%(asctime)s.%(msecs)03d %(levelname)-5s [%(name)s] %(message)s"


# --- options


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("autotests")
    group.addoption("--env", help="resources/env/<name>.yml (default: TEST_ENV, else dev)")
    group.addoption(
        "--runner",
        choices=["local", "server"],
        help="browsers on this machine, or a playwright run-server (PLAYWRIGHT_SERVER_URL)",
    )


def pytest_configure(config: pytest.Config) -> None:
    cli = {
        "env": config.getoption("--env"),
        "runner": config.getoption("--runner"),
        "browser.name": (config.getoption("--browser") or [None])[0],
        "browser.headless": False if config.getoption("--headed") else None,
    }
    settings = load_settings(cli)
    config._autotests_settings = settings  # type: ignore[attr-defined]
    # pytest-playwright reads --browser to pick the browser: the settings' choice when none given
    if not config.getoption("--browser"):
        config.option.browser = [settings.browser.name]
    expect.set_options(timeout=settings.timeouts.action * 1000)
    # registered now, after pytest-playwright: its browser fixtures are overridden by ours
    from autotests import browser

    config.pluginmanager.register(browser, "autotests.browser")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """The tests of a shared resource's less common state run first, all together: the resource
    is switched once for them and once back, instead of the states taking turns all run long — a
    test waiting for another state waits for every holder of the current one. Every xdist worker
    sorts the same way, and its scheduler follows the order."""
    states: dict[str, Counter[Any]] = {}
    for item in items:
        marker = item.get_closest_marker("shared_state")
        if marker is not None:
            key, state = marker.args
            states.setdefault(key, Counter())[state] += 1

    def rare(item: pytest.Item) -> bool:
        marker = item.get_closest_marker("shared_state")
        if marker is None:
            return False
        key, state = marker.args
        return state != states[key].most_common(1)[0][0]

    items[:] = [i for i in items if rare(i)] + [i for i in items if not rare(i)]


# --- settings, logs


@pytest.fixture(scope="session")
def settings(pytestconfig: pytest.Config) -> Settings:
    return pytestconfig._autotests_settings  # type: ignore[attr-defined]


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item: pytest.Item) -> Iterator[None]:
    """One log file per test: <logs.dir>/tests/<test>.log."""
    settings: Settings = item.config._autotests_settings  # type: ignore[attr-defined]
    folder = settings.path(settings.logs.dir) / "tests"
    folder.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(folder / f"{artifacts.folder_name(item.nodeid)}.log", "w")
    handler.setFormatter(logging.Formatter(_FORMAT, "%H:%M:%S"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)
    item._autotests_log = handler  # type: ignore[attr-defined]
    log.info("▶ %s", item.nodeid)
    yield


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item: pytest.Item) -> None:
    handler = getattr(item, "_autotests_log", None)
    if handler is not None:
        logging.getLogger().removeHandler(handler)
        handler.close()


# --- the user, the login, the evidence


@pytest.fixture
def user(request: pytest.FixtureRequest) -> User:
    marker = request.node.get_closest_marker("as_user")
    return marker.args[0] if marker else next(iter(User))  # the least privileged


@pytest.fixture
def authenticate() -> Callable[[BrowserContext, User], None]:
    """ONBOARD: log the context in as the user without the login form — its session cookie
    (`context.add_cookies`) or a saved storage state (login-strategies); until then tests start
    logged out."""
    return lambda context, user: None


@pytest.fixture(scope="session")
def credentials(test_data_loader: TestDataLoader) -> Callable[[User], Credentials]:
    """The login of a User — resources/data/user-data.json."""
    return lambda user: test_data_loader.load(Credentials, user.value, "user-data.json")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item: pytest.Item) -> Iterator[None]:
    """Keeps the soft checks' failures: pytest-check clears them when it builds the report."""
    yield
    item._autotests_checks = list(check_log.get_failures())  # type: ignore[attr-defined]


def _failure_line(item: pytest.Item, call: pytest.CallInfo[Any], report: pytest.TestReport) -> str:
    """The failure's first line. Soft checks failing in an xfail test raise nothing — pytest-check
    marks the report xfailed — so their first failure is taken from what the call phase kept."""
    if call.excinfo is not None:
        lines = str(call.excinfo.value).splitlines()
        return lines[0] if lines else call.excinfo.typename
    checks: list[str] = getattr(item, "_autotests_checks", [])
    if checks:
        log.info("failed checks:\n%s", "\n".join(checks))
        return checks[0].splitlines()[0].removeprefix("FAILURE: ")
    return report.longreprtext.splitlines()[0] if report.longreprtext else "?"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[Any]) -> Iterator[None]:
    """A failed test — and a known bug failing as expected (xfail), the proof that it fails
    because of the bug — leaves its page's evidence (the trace: pytest-playwright's)."""
    outcome = yield
    report: pytest.TestReport = outcome.get_result()
    failed = report.failed and report.when in ("setup", "call")
    expected_failure = report.when == "call" and hasattr(report, "wasxfail") and report.skipped
    held = getattr(item, "_autotests_page", None)
    if (failed or expected_failure) and held is not None:
        page, console = held
        settings: Settings = item.config._autotests_settings  # type: ignore[attr-defined]
        folder = settings.path(settings.artifacts.dir) / artifacts.folder_name(item.nodeid)
        failure = _failure_line(item, call, report)
        saved = artifacts.save(page, console, folder, item.nodeid, failure)
        _attach_to_html_report(item, report, saved / "screenshot.png", page)
    if report.when == "call":
        log.info(
            "%s %s (%.1f s)",
            "✔" if report.passed else "✘ XFAIL" if hasattr(report, "wasxfail") else "✘ FAIL",
            item.nodeid,
            report.duration,
        )


def _attach_to_html_report(
    item: pytest.Item, report: pytest.TestReport, screenshot: Path, page: Page
) -> None:
    """The failure's screenshot and URL in the HTML report (build/reports/report.html)."""
    if item.config.pluginmanager.getplugin("html") is None:
        return
    from pytest_html import extras as html_extras

    extras = getattr(report, "extras", [])
    if not page.is_closed():
        extras.append(html_extras.url(page.url))
    if screenshot.exists():
        extras.append(html_extras.png(base64.b64encode(screenshot.read_bytes()).decode()))
    report.extras = extras  # type: ignore[attr-defined] — pytest-html reads it


# --- test data


@pytest.fixture(scope="session")
def test_data_loader(settings: Settings) -> TestDataLoader:
    return TestDataLoader(settings)


@pytest.fixture(scope="session")
def ui_texts(settings: Settings) -> dict[str, Any]:
    """resources/data/ui-texts.json → its "default" variant: area → texts."""
    import json

    path = settings.path(settings.data.dir) / "ui-texts.json"
    return json.loads(path.read_text())["default"] if path.exists() else {}


# --- shared state


@pytest.fixture(scope="session")
def shared_state_setter() -> Callable[[str], tuple[Callable[[], Any], Callable[[Any], None]]]:
    """ONBOARD (when a case needs a global switch in a state): key → (read, write) through the
    app's API. Override in conftest.py."""

    def setter(key: str) -> tuple[Callable[[], Any], Callable[[Any], None]]:
        raise NotImplementedError(f"shared_state '{key}': override shared_state_setter")

    return setter


@pytest.fixture(autouse=True)
def _shared_state(
    request: pytest.FixtureRequest,
    settings: Settings,
    shared_state_setter: Callable[[str], tuple[Callable[[], Any], Callable[[Any], None]]],
) -> Iterator[None]:
    """`@pytest.mark.shared_state("<key>", <state>)`: the resource in that state for the test,
    ordered against this machine's other tests (`autotests.support.shared_state`)."""
    marker = request.node.get_closest_marker("shared_state")
    if marker is None:
        yield
        return
    key, state = marker.args
    read, write = shared_state_setter(key)
    with shared_state.hold(settings.path("build/locks"), key, state, read, write):
        yield


# --- API


@pytest.fixture(scope="session")
def api(settings: Settings) -> ApiClient:
    """ONBOARD: the API's own base URL when it differs from the web app's (an `api.url` setting)."""
    return ApiClient(settings.base.url)


def artifacts_dir(settings: Settings) -> Path:
    return settings.path(settings.artifacts.dir)
