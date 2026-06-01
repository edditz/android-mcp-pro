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

# Run the MCP server with JDWP deep layout mode
uv run android-mcp --deep

# Run tests (pytest; unit tests live in tests/unit/)
uv run pytest tests/

# Rebuild the deep-inspector fat-jar after ANY change under java-deep-inspector/
# (shadowJar writes straight into prebuilt/ — see "Rebuilding the Java helper" below)
cd java-deep-inspector && ./gradlew shadowJar
```

## Rebuilding the Java helper (REQUIRED after any Java change)

**Rule: whenever you edit any file under `java-deep-inspector/`, you MUST rebuild the
jar before the change can take effect — do this automatically, without waiting to be
asked.** (A `PostToolUse` hook in `.claude/settings.json` reminds you on every edit to a
`.java` file under that directory, but don't rely on it — rebuild as part of the change.)

Deep mode runs the *compiled* fat-jar at `prebuilt/deep-inspector.jar`, not the Java
source. The Python side only shells out to `java -jar prebuilt/deep-inspector.jar`, so
editing `.java` files has **zero runtime effect** until the jar is rebuilt.

```bash
cd java-deep-inspector
./gradlew test          # run the JUnit tests for the change
./gradlew shadowJar     # recompile AND publish → prebuilt/deep-inspector.jar (no copy needed)
```

`shadowJar`'s `destinationDirectory` is configured to `../prebuilt/`, so the build writes
the runtime jar in place — there is no separate copy step and no `build/libs/` artifact to
forget. Commit the regenerated `prebuilt/deep-inspector.jar` alongside the `.java` changes.

By contrast, **Python (`.py`) changes need no build** — `uv run` executes source directly;
just restart the MCP server. Doc-only (`.md`) changes need nothing.

## Architecture

Three-layer architecture with data flowing: AI Agent → MCP Protocol → Tools → Mobile Service → uiautomator2/ADB → Android Device.

### Layer 1: MCP Server Entry Point (`src/android_mcp/__main__.py`)
- Parses CLI args (`--device`, `--connection`, `--wifi`, `--usb`, `--debug`, `--deep`, `--deep-jar`) and env vars (`ANDROID_MCP_DEVICE`, `ANDROID_MCP_CONNECTION`, `ANDROID_MCP_HOST`, `SCREENSHOT_QUANTIZED`, `ANDROID_MCP_DEBUG`, `ADB_PATH`)
- Creates `FastMCP` server instance and `Mobile` instance
- Defines 17 MCP tools: `ListDevices`, `ConnectDevice`, `Device`, `Click`, `ClickBySelector`, `Snapshot`, `GetLayoutTree`, `GetElementDetails`, `GetSpacing`, `LongClick`, `Swipe`, `Type`, `Drag`, `Press`, `Notification`, `Wait`, `WaitForElement`
- **Lazy device connection**: Server starts without a device; connection happens on first tool call via `require_device()`
- **Provider injection**: `build_provider()` selects the layout strategy at startup — `JdwpProvider` when `--deep` is set, otherwise `AccessibilityProvider`. `GetLayoutTree`/`GetElementDetails` delegate to whichever provider is bound. Deep mode **fails fast at startup** (no silent fallback) if `java` is missing from PATH or the jar is absent.

### Layer 2: Mobile Service (`src/android_mcp/mobile/service.py`)
- `Mobile` class handles ADB device listing, WiFi connection, uiautomator2 connection
- Parallel data capture: XML hierarchy dump + screenshot run in separate threads
- Screenshot processing: raw capture → quantization (256-color palette) → base64 encoding
- Resource ID auto-expansion: short IDs like `btn_login` expand to `com.example.app:id/btn_login` using foreground app's package name

### Layer 3a: Tree Parser (`src/android_mcp/tree/`)
- `Tree` class parses Android UI XML hierarchy from `device.dump_hierarchy()`
- Identifies interactive elements using accessibility attributes (focusable, clickable, etc.) + hardcoded class names in `config.py`
- Generates annotated screenshots with bounding boxes and numbered labels
- Coordinate extraction from Android bounds format `[x1,y1][x2,y2]`

### Layer 3b: Layout Providers (`src/android_mcp/layout/`)
- `LayoutProvider` (`provider.py`): `Protocol` defining `get_layout_tree()` / `get_element_details()`. Two implementations behind one interface.
- `AccessibilityProvider` (`accessibility_provider.py`): default path, extracted from the old inline tool bodies. Uses uiautomator2's accessibility tree (same data as the rest of the toolset).
- `JdwpProvider` (`jdwp_provider.py`): `--deep` path. Calls the Java helper via `jdwp_runner`, parses its JSON into `DeepLayoutNode` trees, and renders them. Provides real View properties (padding, margin, elevation, textSize, corner-radius) the accessibility tree cannot. Note: the deep tree has **no content-description**, so `description` lookups fall back to text; `max_depth` is accepted but ignored (full tree always returned).
- `jdwp_runner.py`: subprocess wrapper that invokes `java -jar deep-inspector.jar`, enforces a timeout, and classifies failures into a typed `DeepDumpError` (`NO_JAVA`, `NO_JAR`, `TIMEOUT`, `DUMP_FAILED`).

### Java Deep Inspector (`java-deep-inspector/`)
- Gradle subproject (ddmlib 30.4.0 + shadow plugin) that connects to a debuggable process over JDWP and dumps the full View hierarchy as JSON. Built into `prebuilt/deep-inspector.jar` (checked in).
- `Main` → `DeviceConnector` (ddmlib) → `ViewHierarchyDumper` (V1 protocol) → `ViewNodeParser` (`key=LEN,VALUE` text) → `CoordinateResolver` (relative→absolute) → `JsonOutput`. stdout carries only JSON; ddmlib logs are routed to stderr.
- **Window selection**: a process can have several JDWP view roots (e.g. a backgrounded Activity still alive beneath the foreground one), and ddmlib's `listViewRoots` order does **not** guarantee the focused window is first. `JdwpProvider` passes the foreground activity (from `device.app_current()`) as `--activity`, and `ViewHierarchyDumper.pickWindow()` selects the window whose name matches it — falling back to the first window when there's no hint/match. Without this the dump can target the wrong page (mismatch with `Snapshot`).
- Requires a debuggable target: a debug-built app, or any app on a `userdebug` / `ro.debuggable=1` device.

## Key Data Models

- `src/android_mcp/mobile/views.py`: `MobileState`, `App` dataclasses
- `src/android_mcp/tree/views.py`: `ElementNode`, `BoundingBox`, `TreeState`, `CenterCord` dataclasses
- `src/android_mcp/layout/models.py`: `DeepLayoutNode` (frozen, immutable tree node for deep mode) + `format_deep_tree()` renderer + `format_window_header()` (the `[window]` debug line both providers prepend to `GetLayoutTree` output)

## Dependencies

| Package | Purpose |
|---------|---------|
| `fastmcp` | MCP server framework |
| `pillow` | Image processing (screenshots, annotation) |
| `tabulate` | Formatting element state as text tables |
| `uiautomator2` | Android device automation via ADB |

Deep mode additionally requires a **JDK/JRE on PATH** at runtime (to launch the prebuilt jar) and **Gradle** only when rebuilding the jar (the wrapper `./gradlew` is vendored under `java-deep-inspector/`). The Java side depends on `ddmlib` 30.4.0.

## Bundle Configuration

- `manifest.json`: MCP bundle manifest (v0.4 schema) with tool list and user_config schema
- `.mcpbignore`: Exclusion rules for MCP bundle builds (venv, .git, build artifacts)
- `prebuilt/deep-inspector.jar`: checked-in fat-jar for `--deep` mode. `_DEFAULT_JAR` in `__main__.py` resolves it relative to the source checkout (works for `uv run`/`uvx` from source; a pip-installed wheel would need the jar bundled inside the package).

## Tests

Unit tests live in `tests/unit/` (run with `uv run pytest tests/`). Fixtures in `tests/fixtures/` include a real deep-dump JSON (`deep_dump_sample.json`) and a V1 hierarchy text sample. The Java subproject has its own JUnit tests under `java-deep-inspector/src/test/`. Deep-mode startup checks are skipped during pytest because `--deep` is never in `sys.argv` at collection time.

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
