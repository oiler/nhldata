# v2/browser/pages/notes.py
from pathlib import Path

import dash
from dash import html

dash.register_page(__name__, path="/notes", name="Notes")

# notes/ lives inside the app dir, so this resolves in both local dev and the
# Docker image (pages/ -> app root), unlike repo-root lookups.
NOTES_DIR = Path(__file__).resolve().parent.parent / "notes"


def _note_meta(md_path: Path) -> dict:
    title, date = md_path.stem.replace("-", " ").title(), ""
    for line in md_path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
        elif stripped.startswith("*") and stripped.endswith("*") and not date:
            date = stripped.strip("*").strip()
        if title and date:
            break
    return {"slug": md_path.stem, "title": title, "date": date}


def list_notes() -> list[dict]:
    if not NOTES_DIR.exists():
        return []
    return [_note_meta(p) for p in sorted(NOTES_DIR.glob("*.md"), reverse=True)]


def layout():
    notes = list_notes()
    if not notes:
        return html.Div([html.H2("Notes"), html.P("Nothing here yet.")])
    return html.Div([
        html.H2("Notes"),
        html.P("Write-ups from the research behind this site.",
               style={"fontSize": "0.85rem", "color": "#6c757d"}),
        html.Ul([
            html.Li([
                html.A(n["title"], href=f"/notes/{n['slug']}"),
                html.Span(f" — {n['date']}" if n["date"] else "",
                          style={"color": "#6c757d", "fontSize": "0.85rem"}),
            ])
            for n in notes
        ]),
    ])
