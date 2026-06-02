---
name: design-review
description: >-
  Automated Android design QA (设计走查). Compares a live Android screen against
  its Figma design spec and produces a difference report. Use this whenever the
  user wants to "走查"/"设计走查"/"design review"/"design QA"/"check the
  implementation against the design"/"对比设计稿和真机"/"验收 UI"/"还原度检查",
  or asks whether an app screen matches its Figma mockup — even if they don't
  name a specific tool. Requires the android-mcp-pro MCP (device control; in
  --deep mode it also exposes real View properties like padding/textSize/color)
  and a Figma MCP (FigRelay, or Figma Dev Mode / Framelink) for the design spec.
---

# Design Review (设计走查)

Compare what's actually rendered on an Android device against what the Figma
design says it should be, then report every discrepancy with a severity and a
fix hint. The goal is to replace tedious manual pixel-peeping by an engineer or
designer with a repeatable, evidence-based pass.

The work splits cleanly in two: pull the **design spec** from Figma, pull the
**live implementation** from the device, align them element-by-element, and diff
each dimension. Most of the skill's value is in being disciplined about that
alignment and about the tolerances — a naive "looks the same" check is exactly
what we're trying to improve on.

## Prerequisites — check these first

This skill leans on two MCP servers. Before doing anything else, confirm both
are reachable, because failing late (after pulling half the data) wastes the
user's time.

1. **android-mcp-pro.** Confirm it's reachable (`ListDevices`). Which backend
   it uses — accessibility or `--deep` (JDWP) — is the user's startup choice and
   is **not** something this skill controls or should ask the user to change.
   Instead, **read the active backend off the tool output and adapt coverage to
   it.** Both `GetLayoutTree` and `GetElementDetails` report it explicitly:
   - `GetLayoutTree`'s first line is a `[window]` header containing
     `mode=deep` or `mode=accessibility`.
   - `GetElementDetails`'s first line is `mode: deep` or `mode: accessibility`.

   Then set your coverage accordingly:
   - **`mode=deep`** — nodes carry real View properties (`padding`, `margin`,
     `textSize`, `cornerRadius`, `elevation`, and `textColor` as `#AARRGGBB` on
     TextViews). Review all dimensions.
   - **`mode=accessibility`** — you get bounds + accessibility attributes only.
     Review what it supports (text, bounds-derived sizes/gaps, presence,
     hierarchy, alignment) and clearly mark padding/margin/textSize/textColor/
     cornerRadius/elevation as "not checked" in the report summary so the pass
     rate isn't misread as full coverage.

   Either way, **background/fill color is never captured** — verify fills
   visually from the `Snapshot`, as a visual-only check.

   **Two deep-backend behaviors to plan around (observed in practice):**
   - **A dump can momentarily fail with `DUMP_FAILED` / `no window`.** JDWP
     window selection occasionally misses on the first try. Retry the dump once
     or twice before concluding it can't be read.
   - **Attaching the debugger can knock a sensitive app back to its home/launch
     screen.** Some apps react to a JDWP attach by losing their foreground
     Activity, so each `GetLayoutTree` / `GetElementDetails` call may disturb the
     screen you're reviewing. Capture everything you need in as few deep calls as
     possible, and after a deep call re-`Snapshot` to confirm the device is still
     on the target screen before trusting the next measurement.

2. **A Figma MCP.** This skill is written against **FigRelay** (`get_selection`,
   `get_figma_data`, `get_document_info`, `find_nodes`, `download_images`). If
   the user has Figma Dev Mode MCP or Framelink instead, the tool names differ
   but the workflow is identical — map "get the selected node's data" and "get a
   node by id" onto whatever that server exposes.

If either side is missing, stop and say so plainly rather than guessing values.

## Decide the alignment: which Figma node ↔ which screen

A review compares one design frame against one device screen. Establish the pair
before pulling data, supporting both entry styles:

- **By selection (lightest):** the user selects the target Frame in the Figma
  desktop client. Call `get_selection` to get its design data. The device should
  already be sitting on the matching screen.
- **By node id / URL:** the user gives a Figma node id (e.g. `1:234`) or a share
  URL containing one. Call `get_figma_data` with that id. Again, the device
  should be on the matching screen.

Either way, the **device side is always "the current screen"** — capture it with
android-mcp-pro's `Snapshot` + `GetLayoutTree`. If you're unsure the device is on
the right screen, take a `Snapshot` and show/describe it to the user to confirm
before spending effort on the diff.

When a single screen has many components, it's fine to scope the review to the
selected Frame's subtree rather than the whole page — say so in the report.

## Workflow

Follow these steps in order. Steps 1 and 2 are independent — if you have the
ability to run tool calls in parallel, pull the design spec and the live
implementation at the same time to cut latency.

### 1. Pull the design spec (Figma)

- If working by selection: `get_selection`. If by id: `get_figma_data`.
- FigRelay writes the full design data to a temp file and returns a light
  summary — **read the temp file** to get the actual YAML spec (layout as
  Flexbox, deduped styles, Variables token names like `color/brand/primary`,
  `spacing/md`, and per-node sizes).
- Preserve Variables **token names** alongside resolved values. A mismatch
  against a token (`spacing/md` = 16dp but implemented as 12dp) is more
  actionable in the report than a bare number.
- For icons/images where pixel comparison matters, `download_images` can export
  the node — optional, only if the user cares about asset-level fidelity.

### 2. Capture the live implementation (device)

- `Snapshot` for the annotated screenshot + foreground app/activity context.
- `GetLayoutTree` for the full hierarchy. When the device is served in deep
  mode, this carries real View properties (padding, margin, textSize, textColor
  as `#AARRGGBB`, cornerRadius, elevation, alpha). Background/fill color is not
  among them.
- For specific elements, `GetElementDetails` gives the full property set, and
  `GetSpacing` gives the measured distance/alignment between two elements — use
  it for gap/margin checks instead of subtracting bounds by hand (it already
  does the px→dp conversion using the device's real density).
- **Units:** Figma is in dp/px at 1×; the device reports px. Always convert
  device px → dp using the device density before comparing, and state both in
  the report. `GetSpacing` returns dp already; raw bounds are px.

### 3. Align elements

Match each design node to its device element. Use, in order of reliability:
text content → resource-id / node name → class/type → position within the
parent. Note any design node with **no** device counterpart (missing element)
and any device element with no design counterpart (extra element) — both are
findings, usually Critical/Major.

Don't force a match. If you genuinely can't pair a node, record it as
"unmatched" rather than comparing it against the wrong element and producing a
phantom diff.

### 4. Diff each dimension

Compare the four dimensions below. The detailed checklists, what each maps to on
each side, and the default tolerances live in
`references/dimensions.md` — **read that file** before diffing so you apply the
tolerances consistently. The dimensions:

- **Spacing & size** — padding, margin, element width/height, inter-element gaps.
- **Typography** — textSize (sp), textColor, font weight, the text string itself.
- **Color & shape** — background color, cornerRadius, elevation/shadow, borders.
- **Layout & content** — element presence (missing/extra), hierarchy, alignment,
  copy/text content.

Each discrepancy becomes one finding with a **severity** (see below) and, where
you can infer it, a short fix hint (e.g. "increase top padding 12dp → 16dp to
match `spacing/md`").

### 5. Produce the report

Output **both** a human-readable Markdown report and a machine-readable JSON
object, following the exact templates in `references/report-format.md` — read
that file for the structure. Lead with the Markdown (that's what the user reads),
then the JSON in a fenced ```json block (for pipelines / ticketing). Always
include the overall pass summary (counts by severity) at the top.

## Severity

Keep severities consistent across reviews — they drive whether something blocks
release:

- **Critical** — wrong/missing text, a missing or extra element, or a clearly
  wrong color. The user sees something the design didn't intend.
- **Major** — a spacing or size or font-size deviation beyond tolerance that's
  visible to a careful eye.
- **Minor** — subtle deviations within a hair of tolerance, slight shadow/corner
  differences, things only a designer with a ruler would catch.

When unsure between two levels, explain the user-facing impact and pick the
lower one — over-flagging trains people to ignore the report.

## Principles

- **Evidence over assertion.** Every finding cites the design value and the
  measured value with units. Never report a diff you didn't actually measure.
- **No phantom precision.** Adapt to whatever backend the device is served with;
  don't ask the user to change it. If you only have accessibility data, say which
  dimensions you couldn't check rather than implying everything passed.
- **Tolerances are defaults, not law.** If the user gives you a design system
  with its own grid (e.g. 4dp baseline) or their own tolerances, use theirs.
- **One screen at a time.** A review pairs one frame with one screen. For a
  multi-screen flow, repeat the process per screen and the user can aggregate.
