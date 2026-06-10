# Design System of NHL Data

A Vercel-derived, table-first visual system anchored in Edmonton Oilers brand cues.
Format: Stitch DESIGN.md, 9-section extended variant (2025). Authored by `front-end-design`.

## 1. Visual Theme & Atmosphere

NHL Data is an analytics instrument, not a marketing site. The design follows Vercel's
engineering-minimalism: an overwhelmingly white canvas where dense statistical tables are
the subject and the chrome recedes to hairlines. Every element earns its pixel. Borders are
expressed as zero-offset shadows rather than box-model lines, so surfaces feel layered and
precise rather than boxed-in.

The identity is anchored by a single solid Oilers-navy brand bar at the top — the one place
the app declares whose data this is — above a near-pure-white body. Color is otherwise spent
sparingly: navy carries interactivity (links, active states, table headers), and Oilers
orange is reserved for rare, earned high-emphasis moments. The result reads calm, premium,
and authoritative — a tool a hockey analyst trusts, not a dashboard that shouts.

Typography does the heavy lifting. Geist Sans with tight negative tracking gives headings an
engineered, compressed character; Geist Mono with tabular figures makes every numeric column
align to the pixel, which is the single most important detail in a stats browser.

**Key Characteristics:**
- White canvas (`#ffffff`) with near-black text (`#171717`) — micro-contrast softness, not harsh pure black
- Geist Sans (UI/headings) + Geist Mono (all numerics) — self-hosted, OpenType `liga` + `tnum`
- Shadow-as-border: `box-shadow: 0 0 0 1px rgba(0,0,0,0.08)` replaces traditional borders throughout
- Multi-layer shadow stacks for nuanced card elevation (border + lift + ambient in one declaration)
- Solid Oilers-navy (`#00205B`) brand bar and primary accent; Oilers orange (`#FF4C00`) as a rare high-emphasis pop
- Tabular-figure numerics, right-aligned, in every data table
- Pill badges (9999px) with tinted backgrounds for status/labels

## 2. Color Palette & Roles

### Background Surfaces
- **Canvas White** (`#ffffff`): Page background, card surfaces, table backgrounds.
- **Surface Tint** (`#fafafa`): Subtle zebra/hover tint, header-row fill, inset highlight.
- **Brand Navy** (`#00205B`): The top brand bar — the single dark surface in the system.

### Text & Content
- **Primary Text** (`#171717`): Body, headings, table cell values. Warm near-black.
- **Secondary Text** (`#4d4d4d`): Descriptions, secondary copy.
- **Tertiary Text** (`#666666`): Muted labels, captions, glossary terms.
- **Quaternary Text** (`#808080`): Placeholders, disabled states, row numbers.
- **On-Navy Text** (`#ffffff`): Wordmark and nav text on the brand bar.
- **On-Navy Muted** (`rgba(255,255,255,0.72)`): Inactive nav links on the brand bar.

### Brand & Accent
- **Brand Navy** (`#00205B`): Primary accent — links, active states, table-header text, focus rings.
- **Navy Hover** (`#0a2f7a`): Hover/active variant for navy interactive elements.
- **Oilers Orange** (`#FF4C00`): High-emphasis only — active-nav underline, key highlights, rare CTAs. Never a body color.
- **Orange Hover** (`#e64500`): Hover variant for the few orange elements.

### Status Colors
- **Positive** (`#10b981`): Up-deltas, positive stat changes, "good" indicators.
- **Negative** (`#ff5b4f`): Down-deltas, negative stat changes, warm coral-red.
- **Neutral** (`#666666`): No-change deltas, neutral status.

### Border & Divider
- **Shadow Border** (`rgba(0,0,0,0.08)`): The signature `0 0 0 1px` border — cards, tables, inputs.
- **Divider** (`#ebebeb`): Solid hairline for `<hr>`, row separators, table grid lines.
- **Divider Subtle** (`#f0f0f0`): The faintest internal division.

### Overlay
- **Backdrop** (`rgba(23,23,23,0.4)`): Modal/dialog backdrop, if introduced.
- **Selection** (`rgba(0,32,91,0.12)`): Text-selection highlight — tinted navy.

## 3. Typography Rules

### Font Family
- **Primary**: `Geist`, fallbacks: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
- **Monospace**: `"Geist Mono"`, fallbacks: `ui-monospace, "SF Mono", Menlo, monospace`
- **OpenType Features**: `"liga" 1` globally; numerics add `"tnum" 1` (tabular figures); table mono cells `"tnum" 1, "zero" 1`

### Hierarchy
| Role | Font | Size | Weight | Line Height | Letter Spacing | Notes |
|------|------|------|--------|-------------|----------------|-------|
| Wordmark | Geist | 1.2rem | 600 | 1 | -0.01em | On navy bar, white |
| Page H1 | Geist | 1.875rem | 600 | 1.15 | -0.03em | Tight tracking, the page title |
| Section H2 | Geist | 1.25rem | 600 | 1.25 | -0.02em | Table/section headings |
| H3 / label head | Geist | 1rem | 600 | 1.3 | -0.01em | Sub-sections |
| Body | Geist | 0.95rem | 400 | 1.5 | 0 | Default copy |
| Body small | Geist | 0.82rem | 400 | 1.5 | 0 | Glossary, footnotes |
| Nav link | Geist | 0.9rem | 500 | 1 | 0 | Brand-bar nav |
| Table header | Geist | 0.78rem | 600 | 1.2 | 0.04em | Navy, slight uppercase tracking |
| Table numeric | Geist Mono | 0.85rem | 400 | 1.4 | 0 | Tabular figures, right-aligned |
| Table text cell | Geist | 0.88rem | 400 | 1.4 | 0 | Names, labels |
| Eyebrow/label | Geist | 0.75rem | 600 | 1.2 | 0.05em | Uppercase, tertiary |
| Code/inline | Geist Mono | 0.85em | 400 | 1.4 | 0 | `/a60`-style tokens |

### Principles
- Negative tracking scales with size — display headings compress (-0.03em), body stays neutral (0).
- **Every numeric column uses Geist Mono with tabular figures.** Non-negotiable in a stats browser.
- Navy is the only chromatic text color; orange never appears as running text.
- Weight 600 is the heaviest used in UI; reserve 700 only if a single hero number needs it.

## 4. Component Stylings

### Buttons
**Primary (navy)** — bg `#00205B` / text `#ffffff` / padding `0.5rem 1rem` / radius `6px` / border none / shadow `0 1px 2px rgba(0,0,0,0.06)`. Hover: bg `#0a2f7a`. Focus: `0 0 0 3px rgba(0,32,91,0.3)`. Use for the primary action on a view.
**Secondary (ghost)** — bg `#ffffff` / text `#171717` / shadow-border `0 0 0 1px rgba(0,0,0,0.08)` / radius `6px`. Hover: bg `#fafafa`. Use for secondary actions, toggles.
**Emphasis (orange)** — bg `#FF4C00` / text `#ffffff` / radius `6px`. Hover: `#e64500`. Reserved for the single most important action on a page; usually absent.

### Cards & Containers
White bg, radius `8px`, shadow stack `0 0 0 1px rgba(0,0,0,0.08), 0 2px 2px rgba(0,0,0,0.04), 0 8px 8px -8px rgba(0,0,0,0.04)`. Internal padding `1rem`–`1.25rem`. No visible CSS border — depth comes from the shadow stack.

### Inputs & Forms
bg `#ffffff` / text `#171717` / shadow-border `0 0 0 1px rgba(0,0,0,0.08)` / radius `6px` / padding `0.4rem 0.6rem`. Focus: shadow-border deepens to navy `0 0 0 1px #00205B, 0 0 0 3px rgba(0,32,91,0.15)`. Placeholder: `#808080`. Radio/checkbox accent: navy.

### Badges & Pills
Radius `9999px`, padding `0.1rem 0.55rem`, size `0.72rem`, weight 600. Tinted-surface pattern: navy badge bg `rgba(0,32,91,0.08)` / text `#00205B`; positive bg `rgba(16,185,129,0.12)` / text `#0a7d5a`; negative bg `rgba(255,91,79,0.12)` / text `#c43c33`.

### Navigation
Solid navy brand bar, height ~`3rem`, padding `0.75rem 1.5rem`. Wordmark left (white, 600). Nav links right: `rgba(255,255,255,0.72)`, hover `#ffffff`. **Active link**: white text with a 2px Oilers-orange bottom-border underline (`#FF4C00`). No background changes on links — the underline is the only active signal.

### Tables (DataTable — the core component)
- Container: white, wrapped in shadow-border `0 0 0 1px rgba(0,0,0,0.08)`, radius `8px`, `overflow: hidden` so corners stay clean.
- Header row: bg `#ffffff` (or `#fafafa`), text navy `#00205B`, 0.78rem/600, letter-spacing `0.04em`, bottom border `1px solid #ebebeb`. Sort arrows in navy.
- Body rows: text `#171717`, row separators `1px solid #f0f0f0`. Hover: bg `#fafafa`.
- Numeric cells: Geist Mono, tabular figures, **right-aligned**. Text cells (names): Geist Sans, left-aligned.
- Row-number gutter: first-column `::before` counter, `#808080`, 0.85em, right-aligned (preserve existing technique).
- Active/selected cell: navy 2px outline, never a fill.
- Conditional stat coloring (optional): positive `#0a7d5a`, negative `#c43c33` for delta columns only.

### Image Treatment
Minimal imagery. Team logos/headshots, where used, on transparent or white; no drop shadows beyond the system card stack. Rounded `6px` if framed.

## 5. Layout Principles

### Spacing System
Base unit `4px`. Scale: `4 / 8 / 12 / 16 / 24 / 32 / 48 / 64`px (`0.25–4rem`). Page content padding `1.5rem`. Vertical rhythm between sections `2rem`.

### Grid & Container
Content container (`.page-content`) width is `min(1680px, 94vw)` — near-full-width on normal screens so dense tables get maximum horizontal room, capped at `1680px` on ultrawide displays. Wide tables still scroll horizontally inside their `.table-wrap` container. Center standalone prose blocks (glossary footer) at `860px`. Single-column flow; multi-stat layouts use CSS grid with `gap: 1rem`.

### Whitespace Philosophy
Generous but not wasteful — whitespace frames the data, density lives inside the tables. Let tables breathe with `1.5rem` margin above/below; never crowd a table against the header.

### Border Radius Scale
`6px` (inputs, buttons, badges-as-tags), `8px` (cards, table containers), `9999px` (pills). No radius on full-bleed bars (navy header is square).

## 6. Depth & Elevation

| Level | Treatment | Use |
|-------|-----------|-----|
| 0 — flat | none | Page background, inline text |
| 1 — border | `0 0 0 1px rgba(0,0,0,0.08)` | Default surfaces, inputs, table container |
| 2 — card | `0 0 0 1px rgba(0,0,0,0.08), 0 2px 2px rgba(0,0,0,0.04), 0 8px 8px -8px rgba(0,0,0,0.04)` | Cards, raised panels |
| 3 — overlay | `0 0 0 1px rgba(0,0,0,0.08), 0 12px 24px -8px rgba(0,0,0,0.12)` | Dropdowns, tooltips, modals |
| brand bar | `0 1px 0 rgba(0,0,0,0.06)` | Subtle lift under the navy header |

**Shadow Philosophy**: Depth is layered shadow, not lines. The 1px-spread zero-blur shadow is always the base layer (the "border"); elevation adds soft, offset blur on top. Never mix a CSS `border` with the shadow-border on the same element.

## 7. Do's and Don'ts

### Do
- Use Geist Mono + tabular figures for every number in a table.
- Express borders as `0 0 0 1px` shadows; keep corners clean with `overflow: hidden`.
- Keep navy for interactivity, orange for rare emphasis, monochrome everywhere else.
- Right-align numerics, left-align names.
- Let the navy brand bar be the only saturated surface.

### Don't
- Don't use pure black (`#000`) for text — use `#171717`.
- Don't introduce a second accent hue or use orange as running text/links.
- Don't add CSS `border` lines alongside shadow-borders.
- Don't crowd tables; don't drop tabular figures for proportional ones.
- Don't ship purple/blue Bootstrap defaults — override dbc component colors to the tokens.

## 8. Responsive Behavior

### Breakpoints
| Name | Width | Key Changes |
|------|-------|-------------|
| Mobile | `< 640px` | Nav collapses to wrap/stack; tables scroll horizontally inside their shadow-border container; page padding `1rem` |
| Tablet | `640–1024px` | Full nav inline; tables full-width with horizontal scroll as needed |
| Desktop | `> 1024px` | Content capped at `1100px`; comfortable table density |

### Touch Targets
Nav links and controls ≥ `40px` tap height on mobile. Radio/checkbox controls padded to `40px` rows.

### Collapsing Strategy
Tables never reflow their columns — they scroll horizontally within the rounded container (preserves tabular alignment). The brand bar wordmark stays; nav links wrap below on narrow screens.

### Image Behavior
Logos/headshots scale down proportionally; never crop. Max display width constrained by container.

## 9. Agent Prompt Guide

### Quick Color Reference
```
Canvas    #ffffff   Tint      #fafafa
Text      #171717   Secondary #4d4d4d   Tertiary #666666   Muted #808080
Navy      #00205B   NavyHover #0a2f7a   (brand bar + primary accent)
Orange    #FF4C00   (high-emphasis only)
Positive  #10b981   Negative  #ff5b4f
Border    rgba(0,0,0,0.08)   Divider #ebebeb
```

### Example Component Prompts
- "Style this DataTable to the system: white shadow-border container, navy 0.78rem/600 header with 0.04em tracking, Geist Mono tabular right-aligned numerics, `#fafafa` row hover, kept row-number gutter."
- "Build the navy brand bar: solid `#00205B`, white wordmark 600, right-aligned nav links at `rgba(255,255,255,0.72)`, active link white with 2px `#FF4C00` underline."
- "Make a stat card: white, 8px radius, level-2 shadow stack, navy section heading, a large Geist-Mono tabular number, a `±` delta colored positive/negative."

### Iteration Guide
- Too plain? Add depth via the shadow stack, not color. Tighten heading tracking.
- Too busy? Remove a color — push it back to monochrome; reserve orange harder.
- Numbers misaligning? Confirm Geist Mono + `font-feature-settings: "tnum" 1` on the column.
- Feels generic? The navy bar + orange active-underline + tabular mono numerics are the identity; make sure all three are present.
