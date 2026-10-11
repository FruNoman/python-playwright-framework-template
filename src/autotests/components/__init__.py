"""Components: a widget the app repeats that one Playwright locator call doesn't cover (a table read
into records, a react-select, a date picker) — a small class around the widget's root `Locator`.
Not a wrapper per control: an input is `locator.fill`, a select `locator.select_option`. A new
component only when a second page needs the same widget code; screen-specific reading stays in the
page."""

from autotests.components.table import Table

__all__ = ["Table"]
