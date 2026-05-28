# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Android-MCP is a Python MCP (Model Context Protocol) server that bridges AI agents with Android devices via ADB. It exposes device-control tools (tap, swipe, type, screenshot, etc.) through the MCP protocol. This is **not** an Android app — it's a Python CLI tool that connects to Android devices over ADB.

**Python version**: 3.13 (strictly `>=3.13,<3.14`)

## Development Commands

```bash
# Install dependencies (dev mode)
uv sync

# Run the MCP server locally
uv run android-mcp

# Run as standalone tool (no local install)
uvx android-mcp

# Run tests (pytest, no tests exist yet)
pytest tests/
```

## Architecture

Three-layer architecture with data flowing: AI Agent → MCP Protocol → Tools → Mobile Service → uiautomator2/ADB → Android Device.

### Layer 1: MCP Server Entry Point (`src/android_mcp/__main__.py`)
- Parses CLI args (`--device`, `--connection`, `--wifi`, `--usb`) and env vars (`ANDROID_MCP_DEVICE`, `ANDROID_MCP_CONNECTION`, `ANDROID_MCP_HOST`, `SCREENSHOT_QUANTIZED`)
- Creates `FastMCP` server instance and `Mobile` instance
- Defines all 13 MCP tools: `ListDevices`, `ConnectDevice`, `Device`, `Click`, `ClickBySelector`, `Snapshot`, `LongClick`, `Swipe`, `Type`, `Drag`, `Press`, `Notification`, `Wait`, `WaitForElement`
- **Lazy device connection**: Server starts without a device; connection happens on first tool call via `require_device()`

### Layer 2: Mobile Service (`src/android_mcp/mobile/service.py`)
- `Mobile` class handles ADB device listing, WiFi connection, uiautomator2 connection
- Parallel data capture: XML hierarchy dump + screenshot run in separate threads
- Screenshot processing: raw capture → quantization (256-color palette) → base64 encoding
- Resource ID auto-expansion: short IDs like `btn_login` expand to `com.example.app:id/btn_login` using foreground app's package name

### Layer 3: Tree Parser (`src/android_mcp/tree/`)
- `Tree` class parses Android UI XML hierarchy from `device.dump_hierarchy()`
- Identifies interactive elements using accessibility attributes (focusable, clickable, etc.) + hardcoded class names in `config.py`
- Generates annotated screenshots with bounding boxes and numbered labels
- Coordinate extraction from Android bounds format `[x1,y1][x2,y2]`

## Key Data Models

- `src/android_mcp/mobile/views.py`: `MobileState`, `App` dataclasses
- `src/android_mcp/tree/views.py`: `ElementNode`, `BoundingBox`, `TreeState`, `CenterCord` dataclasses

## Dependencies

| Package | Purpose |
|---------|---------|
| `fastmcp` | MCP server framework |
| `pillow` | Image processing (screenshots, annotation) |
| `tabulate` | Formatting element state as text tables |
| `uiautomator2` | Android device automation via ADB |

## Bundle Configuration

- `manifest.json`: MCP bundle manifest (v0.4 schema) with tool list and user_config schema
- `.mcpbignore`: Exclusion rules for MCP bundle builds (venv, .git, build artifacts)

## Code Search

Use `semble search` to find code by describing what it does or naming a symbol/identifier, instead of grep:

​```bash
semble search "authentication flow" ./my-project
semble search "save_pretrained" ./my-project
semble search "save model to disk" ./my-project --top-k 10
​```

The index is built on first run (and cached for subsequent runs) and invalidated automatically when files change.

Use `--content docs` to search documentation and prose, `--content config` for config files (yaml, toml, etc.), or `--content all` to search code, docs, and config:

​```bash
semble search "deployment guide" ./my-project --content docs
semble search "database host port" ./my-project --content config
semble search "authentication" ./my-project --content all
​```

Use `semble find-related` to discover code similar to a known location (pass `file_path` and `line` from a prior search result):

​```bash
semble find-related src/auth.py 42 ./my-project
​```

`path` defaults to the current directory when omitted; git URLs are accepted.

If `semble` is not on `$PATH`, use `uvx --from "semble[mcp]" semble` in its place.

### Workflow

1. Start with `semble search` to find relevant chunks. The index is built and cached automatically.
2. Use `--content docs` for documentation, `--content config` for config files, or `--content all` for everything.
3. Inspect full files only when the returned chunk does not give enough context.
4. Optionally use `semble find-related` with a promising result's `file_path` and `line` to discover related implementations.
5. Use grep only when you need exhaustive literal matches or quick confirmation of an exact string.
