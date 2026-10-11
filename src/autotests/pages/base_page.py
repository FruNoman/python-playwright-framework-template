"""Pages: the test talks to a page, never to its locators.

A page declares its URL path, the locators it needs (Playwright locators are lazy — created in
`__init__`, resolved on every use, so they never go stale), and one method per user action: fluent
(`return self`) when the action stays on the page, returning the next page when it leads there.
Playwright waits for a locator to be actionable before every action; reads that must wait for a
state use `expect(...)`, which retries until the timeout:

    class LoginPage(BasePage):
        path = "login"

        def __init__(self, page: Page, settings: Settings) -> None:
            super().__init__(page, settings)
            self._email = page.get_by_label("Email")
            self._sign_in = page.get_by_role("button", name="Sign in")

        def sign_in(self, email: str) -> HomePage:
            self._email.fill(email)
            self._sign_in.click()
            return HomePage(self.page, self.settings).wait_loaded()

Locators in the project's order: `get_by_test_id`, `get_by_role` + name, `get_by_label`,
`get_by_placeholder`, `get_by_text` (only for the text that *is* the thing), CSS last. A page object
lives for one test, on the test's `page` (a fresh browser context per test): no state between tests.
"""

from __future__ import annotations

import re
from typing import Self

from playwright.sync_api import Locator, Page, expect

from autotests.config.settings import Settings


class BasePage:
    path: str = ""
    """The page's URL relative to base.url (no leading slash); "" for the root."""

    def __init__(self, page: Page, settings: Settings) -> None:
        self.page = page
        self.settings = settings

    def url(self) -> str:
        return self.settings.base.url + self.path

    def ready(self) -> Locator | None:
        """What shows once the page is usable — override when the URL isn't enough (a SPA)."""
        return None

    def open(self) -> Self:
        """Navigates to the page and returns once it is loaded."""
        self.page.goto(self.url())
        return self.wait_loaded()

    def wait_loaded(self) -> Self:
        expect(self.page).to_have_url(re.compile("^" + re.escape(self.url())))
        ready = self.ready()
        if ready is not None:
            expect(ready).to_be_visible()
        return self

    def title(self) -> str:
        return self.page.title()
