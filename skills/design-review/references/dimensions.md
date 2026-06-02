# Review Dimensions — checklists, source mapping, tolerances

This file is the detailed reference for the diff step. For each dimension it
lists: what to check, where the value comes from on the **design** side
(FigRelay) and the **device** side (android-mcp-pro `--deep`), and the default
tolerance. Apply tolerances consistently — if the user supplied their own design
system tolerances or grid, prefer those.

## Units & conversion (read first)

- Figma values are in dp at 1× (CSS px in exported data).
- **The android-mcp-pro tools already report dp for you** — no manual
  conversion needed. In deep mode `GetLayoutTree` / `GetElementDetails` print
  every distance as `<dp>dp (<px>px)` (e.g. `padding=[16,8,16,0]dp
  ([48,24,48,0]px)`), and `textSize` as `<sp>sp (<px>px)`. Compare the **dp/sp**
  value against Figma; the px is just there for sanity-checking.
- `GetSpacing` likewise returns **dp**. Prefer it for gaps/margins over
  hand-subtracting raw bounds.
- Always quote the dp (or sp) value in findings, not the px.

## 1. Spacing & size

**Check:** padding (top/left/right/bottom), margin, element width & height,
inter-element gaps, overall frame size.

| Property | Design (FigRelay) | Device (`--deep`) |
|----------|-------------------|-------------------|
| padding | node padding / auto-layout padding | `GetElementDetails` padding fields |
| margin | gap to siblings / item spacing | `GetElementDetails` margin, or `GetSpacing` |
| width/height | node `width`/`height` | element bounds → dp |
| gap between two elements | auto-layout `itemSpacing` | `GetSpacing` (returns dp) |

**Tolerance:** ±1dp. Deviations of 2dp+ are Major; ≤1dp pass. If the design uses
a spacing token (`spacing/md`), compare against the token's value and name the
token in the finding.

## 2. Typography

**Check:** text size, text color, font weight/style, line height, and the actual
text string.

| Property | Design (FigRelay) | Device (`--deep`) |
|----------|-------------------|-------------------|
| text string | node `characters` / text content | element `text` |
| textSize | node fontSize | `textSize` (px → sp) |
| textColor | node fill / `color/*` token | `textColor` — emitted as `#AARRGGBB` (TextViews only) |
| font weight | node fontWeight / style name | (limited; report if available) |

> `textColor` comes back as `#AARRGGBB` (alpha first). Figma fills are usually
> `#RRGGBB` + a separate opacity; combine them before comparing — e.g. design
> `#000000` at opacity 0.6 ≈ device `#99000000`. Compare the RGB exactly and the
> alpha within ~2%.

**Tolerance:** text string must match **exactly** (whitespace-trimmed) — a
mismatch is Critical. textSize exact at sp granularity (±0 sp; sub-sp rounding
ok) — off by ≥1sp is Major. textColor exact hex match, case-insensitive, alpha
included — any mismatch is Critical.

> The deep tree has **no content-description**; text comparisons fall back to the
> `text` field. Don't treat a missing content-description as a finding.

## 3. Color & shape

**Check:** background/fill color, corner radius, elevation/shadow, borders
(width + color).

| Property | Design (FigRelay) | Device (`--deep`) |
|----------|-------------------|-------------------|
| background color | node fill / `color/*` token | background color (hex) |
| cornerRadius | node `cornerRadius` | `cornerRadius` |
| elevation/shadow | effect (drop shadow) | `elevation` |
| border | stroke width + color | (report if exposed) |

**Tolerance:** color exact hex (case-insensitive, incl. alpha) — mismatch is
Critical. cornerRadius ±1dp — beyond is Major. elevation/shadow is often
approximate across the Figma↔Android model; treat small differences as Minor and
flag only clearly-wrong shadows.

## 4. Layout & content

**Check:** element presence (every design node has a device counterpart and vice
versa), hierarchy/nesting, alignment (left/center/right, baseline), and visible
copy.

| Aspect | How to check |
|--------|--------------|
| missing element | design node with no matched device element → Critical |
| extra element | device element with no design counterpart → Major (could be intentional state) |
| alignment | compare edge/center coordinates (dp) of siblings; ±1dp |
| hierarchy | parent/child nesting roughly matches design grouping |
| content | same as Typography text-string check |

**Tolerance:** alignment ±1dp. Presence is binary. For "extra element," consider
whether it's a legitimate runtime state (loading spinner, badge, keyboard) before
flagging — note the suspicion in the finding rather than asserting a defect.

## When a value can't be measured

If `--deep` is unavailable, you can still check: text string, bounds-derived
width/height/gaps, element presence, hierarchy, and alignment. You **cannot**
check padding, margin, textSize, textColor, cornerRadius, or elevation. List
those as "not checked (requires --deep)" in the report's summary so the pass rate
isn't misread as full coverage.

Even **with** `--deep`, **background/fill color is never captured** (only
TextView `textColor` is) — verify backgrounds visually from the `Snapshot` and
mark them as a visual-only check rather than a measured one.
