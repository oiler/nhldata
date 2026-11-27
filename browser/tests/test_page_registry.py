"""Each page registers once, under its package name (D54).

Dash names page modules from the app's name. If a page loads under two names
(pages.notes and browser.pages.notes), its callbacks register twice and the
app fails at startup.
"""
import sys
from pathlib import Path

import dash

from browser import app  # noqa: F401 — registers the pages

PAGES_DIR = Path(app.__file__).parent / "pages"


def test_every_page_registers_once_under_browser_pages():
    modules = [page["module"] for page in dash.page_registry.values()]
    assert len(modules) == len(set(modules))
    assert all(m.startswith("browser.pages.") for m in modules), modules
    files = {p.stem for p in PAGES_DIR.glob("*.py")
             if "register_page" in p.read_text()}
    assert {m.rsplit(".", 1)[1] for m in modules} == files


def test_no_page_loads_under_a_bare_pages_name():
    assert not [m for m in sys.modules if m == "pages" or m.startswith("pages.")]


def test_every_page_layout_accepts_query_parameters():
    # Dash passes ?key=value pairs to layout() as keyword arguments; a layout that
    # can't take them raises, and a link with tracking tags shows an empty page.
    import inspect
    for page in dash.page_registry.values():
        layout = page["layout"]
        if not callable(layout):
            continue
        kinds = {p.kind for p in inspect.signature(layout).parameters.values()}
        assert inspect.Parameter.VAR_KEYWORD in kinds, page["module"]
