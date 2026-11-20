import os
import sqlite3
import subprocess
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "browser" / "sync-runtime-data.sh"
# The tiers in browser/sync-runtime-data.sh. REQ is the default season.
REQ, OPT = "2026", "2025"
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


def _src(tmp, league_opt=True, bursts_opt="full", birth_req=True, birth_opt=True):
    """bursts_opt: "full", "none" (file absent), "header" (header only), or a list of ids."""
    src = tmp / "data"
    ids = list(range(10))
    _league_db(src / "2024/generated/browser/league.db", ids)
    _league_db(src / f"{REQ}/generated/browser/league.db", ids, birth=birth_req)
    _bursts(src / f"{REQ}/generated/edge/player_bursts.csv", ids)
    (src / "2025/generated/browser").mkdir(parents=True, exist_ok=True)
    (src / "2025/generated/browser/edm.db").write_bytes(b"x" * 10)
    g = src / "generated/browser/goalies.db"
    g.parent.mkdir(parents=True)
    con = sqlite3.connect(g)
    pd.DataFrame({"situation": ["all", "5v5"]}).to_sql("goalie_seasons", con, index=False)
    con.close()
    if league_opt:
        _league_db(src / f"{OPT}/generated/browser/league.db", ids, birth=birth_opt)
    csv_opt = src / f"{OPT}/generated/edge/player_bursts.csv"
    if bursts_opt == "full":
        _bursts(csv_opt, ids)
    elif bursts_opt == "header":
        csv_opt.parent.mkdir(parents=True, exist_ok=True)
        csv_opt.write_text("playerId,bursts_per_60,speed_max_mph,birth_date\n")
    elif isinstance(bursts_opt, list):
        _bursts(csv_opt, bursts_opt)
    return src


def _run(src, dst):
    # The script calls `python3` from PATH, which must have pandas (same as a real sync).
    env = {**os.environ, "SYNC_SRC": str(src), "SYNC_DST": str(dst)}
    return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)


def _warning_line(stderr):
    lines = [l for l in stderr.splitlines() if l.startswith(f"WARNING: {OPT} not synced")]
    assert len(lines) == 1, stderr
    return lines[0]


def _opt_absent(dst):
    """The optional season's files are gone. Its folder may stay: it also holds edm.db."""
    return not (dst / OPT / "league.db").exists() and not (dst / OPT / "player_bursts.csv").exists()


def _stale_opt(dst):
    (dst / OPT).mkdir(parents=True)
    (dst / OPT / "league.db").write_bytes(b"stale")
    (dst / OPT / "player_bursts.csv").write_bytes(b"stale")


def test_optional_season_synced_when_passing(tmp_path):
    dst = tmp_path / "rt"
    r = _run(_src(tmp_path), dst)
    assert r.returncode == 0, r.stderr
    assert (dst / OPT / "league.db").exists() and (dst / OPT / "player_bursts.csv").exists()
    assert f"Seasons in image: {REQ} (required), {OPT} (optional)" in r.stdout


def test_optional_season_bursts_missing_removes_stale_copy(tmp_path):
    dst = tmp_path / "rt"
    _stale_opt(dst)
    r = _run(_src(tmp_path, bursts_opt="none"), dst)
    assert r.returncode == 0, r.stderr
    assert "missing" in _warning_line(r.stderr)
    assert _opt_absent(dst)
    assert f"skipped: {OPT}" in r.stdout


def test_optional_season_failure_keeps_edm_db(tmp_path):
    dst = tmp_path / "rt"
    r = _run(_src(tmp_path, bursts_opt="none"), dst)
    assert r.returncode == 0, r.stderr
    assert (dst / "2025/edm.db").stat().st_size > 0


def test_optional_season_low_coverage_names_check(tmp_path):
    dst = tmp_path / "rt"
    _stale_opt(dst)
    r = _run(_src(tmp_path, bursts_opt=[0, 1]), dst)
    assert r.returncode == 0, r.stderr
    assert "burst coverage" in _warning_line(r.stderr)
    assert _opt_absent(dst)


def test_optional_season_header_only_csv_names_check(tmp_path):
    dst = tmp_path / "rt"
    r = _run(_src(tmp_path, bursts_opt="header"), dst)
    assert r.returncode == 0, r.stderr
    assert "empty burst CSV" in _warning_line(r.stderr)
    assert _opt_absent(dst)


def test_optional_season_without_birthdates_names_check(tmp_path):
    dst = tmp_path / "rt"
    r = _run(_src(tmp_path, birth_opt=False), dst)
    assert r.returncode == 0, r.stderr
    assert "birthDate" in _warning_line(r.stderr)
    assert _opt_absent(dst)


def test_required_season_without_birthdates_is_fatal(tmp_path):
    dst = tmp_path / "rt"
    (dst / REQ).mkdir(parents=True)
    (dst / REQ / "league.db").write_bytes(b"last good")
    r = _run(_src(tmp_path, birth_req=False), dst)
    assert r.returncode != 0
    assert "birthDate" in r.stderr
    assert (dst / REQ / "league.db").read_bytes() == b"last good"


def test_required_season_failure_is_fatal_and_keeps_last_good_copy(tmp_path):
    src = _src(tmp_path)
    (src / f"{REQ}/generated/edge/player_bursts.csv").unlink()
    dst = tmp_path / "rt"
    (dst / REQ).mkdir(parents=True)
    (dst / REQ / "league.db").write_bytes(b"last good")
    r = _run(src, dst)
    assert r.returncode != 0
    assert f"required season {REQ}" in r.stderr
    assert (dst / REQ / "league.db").read_bytes() == b"last good"


def test_required_and_other_files_arrive(tmp_path):
    dst = tmp_path / "rt"
    r = _run(_src(tmp_path), dst)
    assert r.returncode == 0, r.stderr
    for f in [f"{REQ}/league.db", f"{REQ}/player_bursts.csv", "2025/edm.db",
              "2024/league.db", "goalies.db"]:
        assert (dst / f).stat().st_size > 0, f


def _last_good(dst):
    (dst / REQ).mkdir(parents=True)
    (dst / REQ / "league.db").write_bytes(b"last good")
    (dst / "goalies.db").write_bytes(b"last good goalies")


def test_missing_edm_db_is_fatal_and_leaves_runtime_data_unchanged(tmp_path):
    src = _src(tmp_path)
    (src / "2025/generated/browser/edm.db").unlink()
    dst = tmp_path / "rt"
    _last_good(dst)
    r = _run(src, dst)
    assert r.returncode != 0
    assert "edm.db" in r.stderr
    assert (dst / REQ / "league.db").read_bytes() == b"last good"
    assert not (dst / "2025/edm.db").exists()


def test_single_cut_goalies_db_is_fatal_and_leaves_runtime_data_unchanged(tmp_path):
    src = _src(tmp_path)
    g = src / "generated/browser/goalies.db"
    g.unlink()
    con = sqlite3.connect(g)
    pd.DataFrame({"situation": ["all"]}).to_sql("goalie_seasons", con, index=False)
    con.close()
    dst = tmp_path / "rt"
    _last_good(dst)
    r = _run(src, dst)
    assert r.returncode != 0
    assert "goalies.db" in r.stderr
    assert (dst / REQ / "league.db").read_bytes() == b"last good"
    assert (dst / "goalies.db").read_bytes() == b"last good goalies"


def test_required_failure_leaves_optional_season_alone(tmp_path):
    src = _src(tmp_path, birth_req=False)
    dst = tmp_path / "rt"
    (dst / OPT).mkdir(parents=True)
    (dst / OPT / "league.db").write_bytes(b"earlier")
    r = _run(src, dst)
    assert r.returncode != 0
    assert (dst / OPT / "league.db").read_bytes() == b"earlier"


def test_optional_season_zero_byte_csv_names_check(tmp_path):
    src = _src(tmp_path)
    (src / f"{OPT}/generated/edge/player_bursts.csv").write_bytes(b"")
    dst = tmp_path / "rt"
    r = _run(src, dst)
    assert r.returncode == 0, r.stderr
    assert "empty" in _warning_line(r.stderr)
    assert _opt_absent(dst)
