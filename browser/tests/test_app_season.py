
from browser import app
def _find(node, pred, out=None):
    out = [] if out is None else out
    if pred(node):
        out.append(node)
    kids = getattr(node, "children", None)
    for k in kids if isinstance(kids, list) else [kids]:
        if k is not None and not isinstance(k, str):
            _find(k, pred, out)
    return out


def _by_id(node, id_):
    return _find(node, lambda n: getattr(n, "id", None) == id_)


def test_season_bar_shows_on_season_aware_pages():
    for p in ["/games", "/teams", "/team/EDM", "/skaters", "/player/8478402", "/goalies"]:
        assert app.toggle_season_bar(p) == {}, p


def test_season_bar_hidden_elsewhere():
    for p in ["/", "/game/2026020001", "/goalie/8478406", "/elites", "/notes", None]:
        assert app.toggle_season_bar(p) == {"display": "none"}, p


def test_sync_season_normalizes():
    assert app.sync_season("2026") == "2026"
    assert app.sync_season("2019") == "2026"
    assert app.sync_season(None) == "2026"


def test_filter_labels_and_persistence():
    (r,) = _by_id(app.app.layout, "filter-season")
    assert [o["label"] for o in r.options] == ["2025-26", "2026-27"]
    assert r.value == "2026"
    assert r.persistence is True and r.persistence_type == "session"


def test_season_group_has_accessible_name():
    (bar,) = _by_id(app.app.layout, "season-bar")
    (fieldset,) = _find(bar, lambda n: type(n).__name__ == "Fieldset")
    legends = _find(fieldset, lambda n: type(n).__name__ == "Legend")
    assert [legend.children for legend in legends] == ["Season"]
    assert _by_id(fieldset, "filter-season")
