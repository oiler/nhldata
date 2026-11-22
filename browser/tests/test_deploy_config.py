"""fly.toml must not point the app at a data folder the image doesn't have.

On 2026-11-22, fly.toml still set DATA_DIR = /app/runtime_data after the
image moved the data to /app/browser/runtime_data. Fly's [env] overrides the
Dockerfile's ENV, so production found no seasons while /healthz passed.
"""
import re
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _dockerfile_data_dir():
    text = (REPO / "Dockerfile").read_text()
    m = re.search(r"^ENV DATA_DIR=(\S+)", text, flags=re.M)
    assert m, "Dockerfile no longer sets DATA_DIR"
    return m.group(1)


def test_fly_env_does_not_override_data_dir_with_another_path():
    fly = tomllib.loads((REPO / "fly.toml").read_text())
    override = fly.get("env", {}).get("DATA_DIR")
    assert override in (None, _dockerfile_data_dir())


def test_dockerfile_data_dir_is_where_the_image_copies_runtime_data():
    text = (REPO / "Dockerfile").read_text()
    m = re.search(r"^COPY --chown=\S+ browser/ (\S+)$", text, flags=re.M)
    assert m, "Dockerfile no longer copies browser/"
    dest = m.group(1).rstrip("/")
    assert _dockerfile_data_dir() == f"{dest}/runtime_data"
