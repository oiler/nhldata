# v2/browser/pages/note.py
import dash
from dash import dcc, html

from pages.notes import NOTES_DIR

dash.register_page(__name__, path_template="/notes/<slug>", name="Note")


def layout(slug=None):
    # Whitelist the slug against the directory listing — never build a path
    # from user input directly.
    valid = {p.stem: p for p in NOTES_DIR.glob("*.md")} if NOTES_DIR.exists() else {}
    md_path = valid.get(str(slug))
    if md_path is None:
        return html.Div([html.H2("Notes"), html.P("Unknown note."),
                         html.A("← All notes", href="/notes")])
    return html.Div([
        html.A("← All notes", href="/notes",
               style={"fontSize": "0.85rem", "display": "inline-block",
                      "marginBottom": "0.75rem"}),
        dcc.Markdown(md_path.read_text(), className="note-body"),
    ], style={"maxWidth": "48rem"})
