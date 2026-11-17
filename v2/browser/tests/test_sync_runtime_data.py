import os
import sqlite3
import subprocess
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "tools" / "sync-runtime-data.sh"
_OTHER_TABLES = ["games", "points_5v5", "events_5v5", "onice_5v5", "elite_forwards",
                 "elite_defensemen", "player_metrics", "constants"]


def _league_db(path, ids, birth=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE competition (playerId INTEGER, position TEXT)")
    con.executemany("INSERT INTO competition VALUES (?, 'F')", [(i,) for i in ids])
    con.execute("CREATE TABLE players (playerId INTEGER, birthDate TEXT)")
    con.executemany("INSERT INTO players VALUES (?, ?)",
                    [(i, "2000-01-01" if birth else None) for i in ids])
    for t in _OTHER_TABLES:
        con.execute(f"CREATE TABLE {t} (x INTEGER)")
    con.commit()
    con.close()


def _bursts(path, ids):
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"playerId": ids, "bursts_per_60": 1.0, "speed_max_mph": 20.0,
                  "birth_date": "2000-01-01"}).to_csv(path, index=False)


def _src(tmp, league_2026=True, bursts_2026="full", birth_2025=True, birth_2026=True):
    """bursts_2026: "full", "none" (file absent), "header" (header only), or a list of ids."""
    src = tmp / "data"
    ids = list(range(10))
    _league_db(src / "2024/generated/browser/league.db", ids)
    _league_db(src / "2025/generated/browser/league.db", ids, birth=birth_2025)
    (src / "2025/generated/browser/edm.db").write_bytes(b"x" * 10)
    _bursts(src / "2025/generated/edge/player_bursts.csv", ids)
    g = src / "generated/browser/goalies.db"
    g.parent.mkdir(parents=True)
    con = sqlite3.connect(g)
    pd.DataFrame({"situation": ["all", "5v5"]}).to_sql("goalie_seasons", con, index=False)
    con.close()
    if league_2026:
        _league_db(src / "2026/generated/browser/league.db", ids, birth=birth_2026)
    csv_2026 = src / "2026/generated/edge/player_bursts.csv"
    if bursts_2026 == "full":
        _bursts(csv_2026, ids)
    elif bursts_2026 == "header":
        csv_2026.parent.mkdir(parents=True, exist_ok=True)
        csv_2026.write_text("playerId,bursts_per_60,speed_max_mph,birth_date\n")
    elif isinstance(bursts_2026, list):
        _bursts(csv_2026, bursts_2026)
    return src


def _run(src, dst):
    # The script calls `python3` from PATH, which must have pandas (same as a real sync).
    env = {**os.environ, "SYNC_SRC": str(src), "SYNC_DST": str(dst)}
    return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)


def _warning_line(stderr):
    lines = [l for l in stderr.splitlines() if l.startswith("WARNING: 2026 not synced")]
    assert len(lines) == 1, stderr
    return lines[0]


def test_optional_season_synced_when_passing(tmp_path):
    dst = tmp_path / "rt"
    r = _run(_src(tmp_path), dst)
    assert r.returncode == 0, r.stderr
    assert (dst / "2026/league.db").exists() and (dst / "2026/player_bursts.csv").exists()
    assert "Seasons in image: 2025 (required), 2026 (optional)" in r.stdout


def test_optional_season_bursts_missing_removes_stale_copy(tmp_path):
    dst = tmp_path / "rt"
    (dst / "2026").mkdir(parents=True)
    (dst / "2026/league.db").write_bytes(b"stale")
    r = _run(_src(tmp_path, bursts_2026="none"), dst)
    assert r.returncode == 0, r.stderr
    assert "missing" in _warning_line(r.stderr)
    assert not (dst / "2026").exists()
    assert "skipped: 2026" in r.stdout


def test_optional_season_low_coverage_names_check(tmp_path):
    dst = tmp_path / "rt"
    (dst / "2026").mkdir(parents=True)
    (dst / "2026/league.db").write_bytes(b"stale")
    r = _run(_src(tmp_path, bursts_2026=[0, 1]), dst)
    assert r.returncode == 0, r.stderr
    assert "burst coverage" in _warning_line(r.stderr)
    assert not (dst / "2026").exists()


def test_optional_season_header_only_csv_names_check(tmp_path):
    dst = tmp_path / "rt"
    r = _run(_src(tmp_path, bursts_2026="header"), dst)
    assert r.returncode == 0, r.stderr
    assert "empty burst CSV" in _warning_line(r.stderr)
    assert not (dst / "2026").exists()


def test_optional_season_without_birthdates_names_check(tmp_path):
    dst = tmp_path / "rt"
    r = _run(_src(tmp_path, birth_2026=False), dst)
    assert r.returncode == 0, r.stderr
    assert "birthDate" in _warning_line(r.stderr)
    assert not (dst / "2026").exists()


def test_required_season_without_birthdates_is_fatal(tmp_path):
    r = _run(_src(tmp_path, birth_2025=False), tmp_path / "rt")
    assert r.returncode != 0
    assert "birthDate" in r.stderr


def test_required_season_failure_is_fatal_and_keeps_last_good_copy(tmp_path):
    src = _src(tmp_path)
    (src / "2025/generated/edge/player_bursts.csv").unlink()
    dst = tmp_path / "rt"
    (dst / "2025").mkdir(parents=True)
    (dst / "2025/league.db").write_bytes(b"last good")
    r = _run(src, dst)
    assert r.returncode != 0
    assert "required season 2025" in r.stderr
    assert (dst / "2025/league.db").read_bytes() == b"last good"
