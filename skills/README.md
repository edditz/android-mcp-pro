# Skills

Agent skills that pair with **Android MCP Pro**. Each subfolder is a
self-contained [Agent Skill](https://docs.claude.com/en/docs/claude-code/skills)
— a `SKILL.md` plus any bundled references — that you can drop into a
skills-aware client (Claude Code, Claude.ai, etc.).

## Available skills

| Skill | What it does | Needs |
|-------|--------------|-------|
| [`design-review`](./design-review) | Automated Android design QA (设计走查): compares a live device screen against its Figma spec and reports every discrepancy with severity + fix hints. | android-mcp-pro (`--deep`) + a Figma MCP (FigRelay / Dev Mode / Framelink) |

## Installing

### Claude Code

Copy a skill into your skills directory (personal or project):

```bash
# Personal (available everywhere)
cp -r skills/design-review ~/.claude/skills/

# Project-scoped (committed with a repo)
cp -r skills/design-review /path/to/your-project/.claude/skills/
```

Then reload skills (`/reload-skills` in Claude Code) — the skill triggers
automatically based on its `description`, or invoke it explicitly.

### Claude.ai

Zip the skill folder and upload it in the skill settings, or use the
`skill-creator` packaging tool to produce a `.skill` file.

## What each skill expects

A skill's `SKILL.md` frontmatter `description` controls when the agent reaches
for it; the body holds the workflow, and `references/` holds detail loaded on
demand. Open a skill's `SKILL.md` to see its exact prerequisites — `design-review`,
for instance, expects the Android MCP server to be started with `--deep` so it
can read real View properties (padding, textSize, color, cornerRadius) that the
accessibility tree can't expose.
