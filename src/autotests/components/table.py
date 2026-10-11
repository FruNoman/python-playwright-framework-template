"""A table read as text — `<table>` or a div grid — for the page to map into its own records
(a page never returns dict rows: `list[OrderRow]`)."""

from __future__ import annotations

from playwright.sync_api import Locator


class Table:
    def __init__(
        self, root: Locator, row_selector: str = "tbody tr", cell_selector: str = "td"
    ) -> None:
        self.root = root
        self.row_selector = row_selector
        self.cell_selector = cell_selector

    def headers(self) -> list[str]:
        return [h.strip() for h in self.root.locator("thead th").all_inner_texts()]

    def rows(self) -> list[list[str]]:
        """Every row's cell texts, as shown."""
        return [
            [c.strip() for c in row.locator(self.cell_selector).all_inner_texts()]
            for row in self.root.locator(self.row_selector).all()
        ]

    def row(self, text: str) -> Locator:
        """The row holding `text` — for an action in it (its menu, its checkbox)."""
        return self.root.locator(self.row_selector).filter(has_text=text)
