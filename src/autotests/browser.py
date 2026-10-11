"""pytest-playwright's browser fixtures, adapted to the settings (registered by the plugin after
pytest-playwright, so these win). A browser per xdist worker — launched, or connected to a
`playwright run-server` — and a **fresh context per test** (pytest-playwright's `context`): no
cookies, storage or pages leak between tests, at a fraction of a new browser's cost."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from playwright.sync_api import BrowserContext, ConsoleMessage, Page

from autotests.auth.users import User
from autotests.config.settings import Settings


@pytest.fixture(scope="session")
def browser_type_launch_args(
    browser_type_launch_args: dict[str, Any], settings: Settings
) -> dict[str, Any]:
    return {**browser_type_launch_args, "headless": settings.browser.headless}


@pytest.fixture(scope="session")
def connect_options(settings: Settings) -> dict[str, Any] | None:
    """`runner: server` → pytest-playwright connects to the `playwright run-server` instead of
    launching (the same version as the `playwright` package — docker-compose.playwright.yml pins
    both); the launch options (headless) travel with the connection."""
    return {"endpoint": settings.server.url} if settings.runner == "server" else None


@pytest.fixture(scope="session")
def browser_context_args(
    browser_context_args: dict[str, Any], settings: Settings
) -> dict[str, Any]:
    width, height = settings.browser.viewport
    return {
        **browser_context_args,
        "base_url": settings.base.url,
        "viewport": {"width": width, "height": height},
    }


@pytest.fixture
def page(
    request: pytest.FixtureRequest,
    context: BrowserContext,
    settings: Settings,
    user: User,
    authenticate: Callable[[BrowserContext, User], None],
) -> Iterator[Page]:
    """This test's page, on its fresh context, logged in as `user`; its console kept for the
    failure artifacts."""
    context.set_default_timeout(settings.timeouts.action * 1000)
    context.set_default_navigation_timeout(settings.timeouts.navigation * 1000)
    authenticate(context, user)
    page = context.new_page()
    console: list[str] = []

    def keep(message: ConsoleMessage) -> None:
        console.append(f"{message.type} {message.text}")

    page.on("console", keep)
    page.on("pageerror", lambda error: console.append(f"pageerror {error}"))
    request.node._autotests_page = (page, console)
    yield page
