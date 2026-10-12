"""The framework's own wiring in a browser — on about:blank or a page set by the test, no app
needed. A project drops tests/framework once its TMS cases cover these layers."""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page, expect
from pytest_check import check

from autotests.support import artifacts


def test_a_test_starts_with_a_fresh_context(page: Page) -> None:
    page.goto("about:blank")
    # only what this test's `authenticate` put there — never the cookie the test before left
    # (a check for "no cookies at all" breaks as soon as the login is injected; lab10 2026-10-12)
    leftover = [c for c in page.context.cookies() if c.get("name") == "left"]

    page.context.add_cookies([{"name": "left", "value": "behind", "url": "https://example.org"}])
    page.context.new_page()  # left open: the next test must not see it

    assert leftover == [], "no cookie of another test"


def test_another_test_starts_with_a_fresh_context_too(page: Page) -> None:
    page.goto("about:blank")

    with check:
        assert all(c.get("name") != "left" for c in page.context.cookies()), (
            "no cookie of the test before"
        )
    with check:
        assert len(page.context.pages) == 1, "no page of the test before"


def test_locators_wait_for_what_the_action_produces(page: Page) -> None:
    page.set_content(
        """<button id="next">Next</button><div id="step">Define</div>
        <script>document.getElementById('next').onclick = () =>
          setTimeout(() => document.getElementById('step').textContent = 'Specifications', 500)
        </script>"""
    )

    page.get_by_role("button", name="Next").click()

    expect(page.locator("#step")).to_have_text("Specifications")


def test_failure_artifacts_capture_the_page(page: Page, tmp_path: Path) -> None:
    page.set_content("<h1>evidence</h1>")
    console = ["error boom"]

    folder = artifacts.save(page, console, tmp_path / "case", "tests/x.py::test_y", "it failed")

    with check:
        assert (folder / "screenshot.png").stat().st_size > 0, "screenshot"
    with check:
        assert "evidence" in (folder / "page.html").read_text(), "the DOM"
    with check:
        assert "boom" in (folder / "console.log").read_text(), "the console"
    with check:
        assert "failure:  it failed" in (folder / "info.txt").read_text(), "info"


def test_the_page_keeps_its_console(page: Page, request) -> None:
    page.set_content("<script>console.error('kept')</script>")
    _, console = request.node._autotests_page

    expect(page.locator("body")).to_be_attached()

    assert any("kept" in line for line in console), "the console of the test's page"
