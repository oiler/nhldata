# Front-End Redesign — Integration Spec

**Date:** 2026-06-09
**Status:** Approved design, pending implementation plan
**Visual system:** `DESIGN.md` (repo root) — Vercel-derived, Oilers-anchored, light, table-first
**App:** `v2/browser/` — Plotly Dash 4.0 multi-page, deployed on fly.io

## 1. Goal

Replace the stock `dash-bootstrap-components` BOOTSTRAP look ("default admin panel") with a
distinctive, production-grade visual identity defined in `DESIGN.md`. Full identity system
across all 8 pages. **No data or computation logic changes** — this is presentation only.

## 2. Decisions (locked during brainstorming)

| Decision | Choice |
|---|---|
| Aesthetic base | Vercel — light/white, Geist, shadow-as-border |
| Brand anchor | Solid Oilers-navy (`#00205B`) top bar above white body |
| Accent | Navy primary (links, active, table headers); orange (`#FF4C00`) high-emphasis only |
| Fonts | Geist Sans + Geist Mono, **self-hosted** (see §5) |
| Numerics | Geist Mono with tabular figures, right-aligned, in every table |
| Scope | Shell + tables + all 8 pages |
| Dark mode | Deferred (YAGNI); token structure leaves room |

## 3. Architecture & Components Touched

| File | Change |
|---|---|
| `v2/browser/assets/style.css` | Rewrite to the `DESIGN.md` token system. CSS custom properties for the full palette/scale; restyle header, nav, filter bar, footer/glossary, dbc overrides. Keep + restyle the existing row-number counter. |
| `v2/browser/app.py` | Add `app.index_string` with `@font-face` for self-hosted Geist; restyle the shell layout (navy brand bar, active-link underline, footer to tokens). Move inline `style={...}` dicts in the header/footer into CSS classes where practical. |
| `v2/browser/assets/fonts/` | **New** — self-hosted Geist Sans + Geist Mono `.woff2` files (subset to latin). |
| `v2/browser/table_style.py` | **New** — shared module exporting DataTable `style_header`, `style_cell`, `style_data`, `style_data_conditional`, `css` dicts so all 8 pages render identically. Single source of truth for table look. |
| `v2/browser/pages/*.py` (×8) | Replace ad-hoc per-page DataTable `style_*` args with the shared `table_style` helpers. home, games, game, skaters, teams, team, player, elites. |
| `v2/browser/security.py` | No change needed if fonts are self-hosted (stays `font-src 'self'`). See §5. |

### Why a shared `table_style.py`
Tables are the bulk of the content across 8 pages. Today each page sets `style_*` props
ad hoc, which drifts. A single helper module enforces the `DESIGN.md` table spec everywhere
and is the one piece with enough structure to unit-test (per the project's "test computations,
not callbacks" rule — assert the helper returns the expected token values/keys).

## 4. Component Mapping (DESIGN.md → Dash)

- **Brand bar** → restyle `.app-header` to solid navy; `.app-nav a` to translucent-white; add
  `.app-nav a.active` (orange underline). Dash `dcc.Link` active state via a clientside callback
  or `className` comparison against `pathname`.
- **Tables** → `table_style.py` dicts applied to every `dash_table.DataTable`. Shadow-border
  container + radius via a wrapping `className` styled in CSS (DataTable itself can't take a
  box-shadow cleanly, so wrap it).
- **Cards** → `.card` utility class with the level-2 shadow stack for stat panels.
- **Filter bar / footer / glossary** → restyle existing markup to tokens; convert inline styles
  to classes.
- **dbc overrides** → override Bootstrap's default link/button/focus colors to navy via CSS
  custom-property overrides so stray dbc components inherit the system.

## 5. Fonts & CSP (resolved)

Current CSP (`security.py`): `style-src 'self' 'unsafe-inline'`, `font-src 'self' data:`.

**Chosen path: self-host Geist.** Download Geist Sans + Geist Mono (SIL OFL), subset to latin,
place `.woff2` in `assets/fonts/`, declare via `@font-face` in `app.index_string`. This keeps
`font-src 'self'` intact, drops a third-party request (privacy + reliability + no Google Fonts
CSP loosening), and survives offline/edge cases on fly.io.

Rejected alternative: Google Fonts CDN — would require adding `fonts.googleapis.com` to
`style-src` and `fonts.gstatic.com` to `font-src`, weakening CSP for no benefit.

Dash auto-serves anything under `assets/`, so the `.woff2` files are reachable at
`/assets/fonts/...` with no extra config.

## 6. Testing & Verification

- **Existing suite must stay green:** `python -m pytest v2/ -v` (82 tests). No logic changes,
  so any failure means an import/structure regression.
- **New unit test** (`v2/browser/tests/test_table_style.py`): assert `table_style.py` exports
  the expected dicts with the locked token values (navy header color, Geist Mono numeric font,
  right-alignment, hover tint). Synthetic, no data files — matches the project test pattern.
- **Visual verification:** run the app locally (`python v2/browser/app.py`) and eyeball all 8
  pages against `DESIGN.md` — brand bar, active-link underline, tabular numeric alignment,
  shadow-borders, hover states. Use the `verify`/`run` skill.
- **Font load check:** confirm `@font-face` resolves (no fallback flash) and CSP headers still
  pass when `DASH_ENABLE_SECURITY_HEADERS=1`.

## 7. Rollout

1. Self-host fonts + `index_string`.
2. Rewrite `assets/style.css` to tokens; restyle shell in `app.py`.
3. Build `table_style.py` + test; wire into all 8 pages.
4. Run full pytest suite; visual pass on all pages.
5. Deploy to fly.io; verify fonts + CSP on the live host.

**Git:** oiler commits manually. Implementation will stage files and report; never auto-commit.

## 8. Out of Scope (YAGNI)

- Dark-mode toggle (structure leaves room; not built now).
- Per-page bespoke layouts beyond applying the system (a later pass).
- Any change to data, metrics, queries, or callbacks' behavior.
- New charts/visualizations — this is identity, not new features.

## 9. Open Questions

- None blocking. Geist `.woff2` subsetting can be done with `fonttools`/`glyphhanger` during
  implementation; if undesired, ship the full latin `.woff2` from the Geist release.
