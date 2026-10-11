"""Example pages — Selenium's public test form (base.url in resources/env/dev.yml): how a page is
written, and what the example tests and CI run until the project has its own pages. Template repo
only: onboarding deletes tests/example/ and resources/data/web-form-data.json right after cloning.

Page conventions shown: the URL path for open(); locators created once in `__init__` (lazy —
resolved on every use); the test talks to the page, never to its locators — a fluent method per
user action, a read per value; an action that leads to another page returns it, loaded. The app's
pages go to src/autotests/pages/<area>/.
"""

from __future__ import annotations

from pathlib import Path
from typing import Self

from playwright.sync_api import Locator, Page

from autotests.config.settings import Settings
from autotests.pages.base_page import BasePage


class SubmittedPage(BasePage):
    """Where WebFormPage.submit() lands — "Form submitted" with its message."""

    path = "submitted-form.html"

    def __init__(self, page: Page, settings: Settings) -> None:
        super().__init__(page, settings)
        self._message = page.locator("#message")

    def ready(self) -> Locator:
        return self._message

    def message(self) -> str:
        return self._message.inner_text()


class WebFormPage(BasePage):
    path = "web-form.html"

    def __init__(self, page: Page, settings: Settings) -> None:
        super().__init__(page, settings)
        # the form's controls have names, not labels Playwright can use — by name
        self._text = page.locator("[name=my-text]")
        self._textarea = page.locator("[name=my-textarea]")
        self._disabled_input = page.locator("[name=my-disabled]")
        self._readonly_input = page.locator("[name=my-readonly]")
        self._options = page.locator("[name=my-select]")
        self._file = page.locator("[name=my-file]")
        self._default_checkbox = page.locator("#my-check-2")
        self._radios = page.get_by_role("radio")
        self._submit = page.get_by_role("button", name="Submit")

    def ready(self) -> Locator:
        return self._submit

    def type_text(self, value: str) -> Self:
        self._text.fill(value)
        return self

    def type_textarea(self, value: str) -> Self:
        self._textarea.fill(value)
        return self

    def choose_option(self, text: str) -> Self:
        """By the visible text — refused at once when the select doesn't have it (Playwright would
        wait for it to appear)."""
        if text not in self.options():
            raise ValueError(f"No option '{text}' in {self._options}, options: {self.options()}")
        self._options.select_option(label=text)
        return self

    def set_default_checked(self, checked: bool) -> Self:
        self._default_checkbox.set_checked(checked)
        return self

    def choose_radio(self, label: str) -> Self:
        self.page.get_by_label(label, exact=True).check()
        return self

    def upload(self, file: Path) -> Self:
        self._file.set_input_files(file)
        return self

    def submit(self) -> SubmittedPage:
        self._submit.click()
        return SubmittedPage(self.page, self.settings).wait_loaded()

    def text(self) -> str:
        return self._text.input_value()

    def textarea(self) -> str:
        return self._textarea.input_value()

    def is_disabled_input_enabled(self) -> bool:
        return self._disabled_input.is_enabled()

    def is_readonly_input_read_only(self) -> bool:
        return self._readonly_input.get_attribute("readonly") is not None

    def options(self) -> list[str]:
        return [o.strip() for o in self._options.locator("option").all_inner_texts()]

    def option(self) -> str:
        return self._options.locator("option:checked").inner_text().strip()

    def option_value(self) -> str:
        return self._options.input_value()

    def is_default_checked(self) -> bool:
        return self._default_checkbox.is_checked()

    def radio(self) -> str:
        checked = self._radios.and_(self.page.locator(":checked"))
        return self.page.locator(f"label:has(#{checked.get_attribute('id')})").inner_text().strip()

    def radio_options(self) -> list[str]:
        return [
            label.strip()
            for label in self.page.locator("label:has(input[type=radio])").all_inner_texts()
        ]

    def uploaded_files(self) -> list[str]:
        return self._file.evaluate("input => [...input.files].map(f => f.name)")
