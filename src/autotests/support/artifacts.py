"""Evidence of a failed test, as plain files any CI can publish — no reporter needed:
<artifacts.dir>/<test>/screenshot.png, page.html, console.log, info.txt. Playwright's own trace
(every action, DOM snapshots, network) of a failed test is in build/reports/traces/<test>/trace.zip
(`--tracing retain-on-failure`): `uv run playwright show-trace <it>`."""

from __future__ import annotations

import datetime as dt
import logging
import re
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Page

log = logging.getLogger(__name__)


def folder_name(nodeid: str) -> str:
    """tests/example/test_web_form.py::test_submit[x] → test_web_form.test_submit[x]"""
    path, _, name = nodeid.partition("::")
    return re.sub(r"[^\w.\[\]-]+", "_", f"{Path(path).stem}.{name.replace('::', '.')}")


def save(page: Page, console: list[str], folder: Path, nodeid: str, failure: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    _try("screenshot", lambda: page.screenshot(path=folder / "screenshot.png", full_page=True))
    _try("page.html", lambda: (folder / "page.html").write_text(page.content()))
    (folder / "console.log").write_text("".join(f"{line}\n" for line in console) or "(empty)\n")
    info = [f"test:     {nodeid}", f"failure:  {failure}"]
    _try("url", lambda: info.append(f"url:      {page.url}"))
    _try("title", lambda: info.append(f"title:    {page.title()}"))
    _try(
        "browser",
        lambda: info.append(
            f"browser:  {page.context.browser.browser_type.name} {page.context.browser.version}"
            if page.context.browser
            else "browser:  ?"
        ),
    )
    info.append(f"time:     {dt.datetime.now().isoformat(timespec='seconds')}")
    (folder / "info.txt").write_text("\n".join(info) + "\n")
    log.info("failure artifacts → %s", folder)
    return folder


def _try(what: str, action: Callable[[], object]) -> None:
    try:
        action()
    except Exception as e:
        log.warning("failure artifact %s not saved: %s", what, e)


__all__ = ["folder_name", "save"]
