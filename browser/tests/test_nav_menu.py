"""The phone menu carries the same links as the desktop nav.

Closing it after a link is followed happens in browser/assets/menu.js, checked by hand.
"""

from dash import html

import browser.app as app_module


def _find(node, pred):
    if pred(node):
        return node
    children = getattr(node, "children", None)
    for child in children if isinstance(children, list) else [children]:
        if child is not None and not isinstance(child, str):
            found = _find(child, pred)
            if found is not None:
                return found
    return None


def _hrefs(node):
    return [link.href for link in node.children]


def test_phone_menu_has_the_desktop_links():
    layout = app_module.app.layout
    wide = _find(layout, lambda n: "app-nav-wide" in (getattr(n, "className", "") or ""))
    menu = _find(layout, lambda n: isinstance(n, html.Details) and getattr(n, "id", None) == "app-menu")
    assert wide is not None and menu is not None
    menu_nav = _find(menu, lambda n: "app-menu-list" in (getattr(n, "className", "") or ""))
    assert _hrefs(menu_nav) == _hrefs(wide)
    assert "/skaters" in _hrefs(wide)
