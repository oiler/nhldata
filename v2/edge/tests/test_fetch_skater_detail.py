"""Tests for v2/edge/fetch_skater_detail.py — pure-function helpers only.

Network-touching code (fetch_one) is exercised by the end-to-end run, not unit tests.
"""

from pathlib import Path


def test_build_url_uses_documented_pattern():
    from v2.edge.fetch_skater_detail import build_url

    url = build_url(player_id=8478402, season="20252026", game_type=2)
    assert url == (
        "https://api-web.nhle.com/v1/edge/skater-detail/8478402/20252026/2"
    )


def test_target_path_lives_under_player_id(tmp_path):
    from v2.edge.fetch_skater_detail import target_path

    p = target_path(tmp_path, player_id=8478402)
    assert p == tmp_path / "8478402.json"


def test_already_fetched_true_when_file_exists(tmp_path):
    from v2.edge.fetch_skater_detail import already_fetched

    f = tmp_path / "1.json"
    assert already_fetched(f) is False
    f.write_text("{}")
    assert already_fetched(f) is True
