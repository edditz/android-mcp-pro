# Report Format

Produce **both** outputs every time: the Markdown report first (for the human),
then the JSON object in a fenced ```json block (for pipelines / ticketing). The
two must describe the same findings — don't let them drift.

## Markdown template

Use this structure exactly; fill in the bracketed parts and repeat finding rows
as needed.

```markdown
# 设计走查报告 — [screen / frame name]

**设计稿:** [Figma node id or selection name]
**设备:** [device serial / model] · [foreground package/activity]
**模式:** deep | accessibility-only
**走查时间:** [date]

## 摘要

| 严重度 | 数量 |
|--------|------|
| 🔴 Critical | [n] |
| 🟠 Major | [n] |
| 🟡 Minor | [n] |
| **合计** | **[n]** |

**未检查维度（缺 --deep）:** [list, or “无”]
**总体结论:** [一句话，例如“还原度良好，2 处间距需修正” 或 “存在 1 处文案错误，需阻塞发布”]

## 问题清单

### 🔴 Critical

| # | 元素 | 维度 | 设计值 | 实现值 | 说明 / 修复建议 |
|---|------|------|--------|--------|----------------|
| 1 | [element] | [dimension] | [design value + unit] | [measured value + unit] | [fix hint] |

### 🟠 Major

| # | 元素 | 维度 | 设计值 | 实现值 | 说明 / 修复建议 |
|---|------|------|--------|--------|----------------|
| … | | | | | |

### 🟡 Minor

| # | 元素 | 维度 | 设计值 | 实现值 | 说明 / 修复建议 |
|---|------|------|--------|--------|----------------|
| … | | | | | |

## 通过项

[Optional: brief list of dimensions/elements that matched, so the reader trusts
coverage. Keep it short.]
```

If there are zero findings in a severity bucket, write "无" under that heading
rather than dropping the heading — the reader should see it was checked.

## JSON template

```json
{
  "screen": "string — screen / frame name",
  "design_ref": "string — Figma node id or selection name",
  "device": "string — serial / model",
  "foreground": "string — package/activity",
  "mode": "deep | accessibility",
  "summary": {
    "critical": 0,
    "major": 0,
    "minor": 0,
    "total": 0,
    "not_checked": ["padding", "textSize"],
    "verdict": "string — one-line conclusion"
  },
  "findings": [
    {
      "id": 1,
      "element": "string — how the element was identified (text / resource-id)",
      "dimension": "spacing | size | typography | color | shape | layout | content",
      "property": "string — e.g. paddingTop, textColor, cornerRadius",
      "design_value": "string — value with unit, incl. token name if any",
      "actual_value": "string — measured value with unit",
      "delta": "string — difference, e.g. '-4dp' or 'n/a'",
      "severity": "critical | major | minor",
      "fix_hint": "string — actionable suggestion, may be empty"
    }
  ]
}
```

## Conventions

- **Always include units** in `design_value` / `actual_value` (dp, sp, hex).
- For color, use lowercase hex with alpha where present (`#ff2d7d9a`).
- When a value comes from a Figma Variable, put the token name in
  `design_value` alongside the resolved value: `"spacing/md (16dp)"`. This makes
  the fix unambiguous and ties the defect back to the design system.
- `delta` is "n/a" for non-numeric diffs (text, presence, color).
- Keep `element` identifiers stable between the Markdown and JSON so a reader can
  cross-reference.
