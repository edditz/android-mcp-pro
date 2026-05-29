# JDWP Deep Layout Inspector

**Date**: 2026-05-29
**Status**: Draft (pending user review)
**Branch**: `feature/jdwp-deep-inspector`
**Scope**: Add a JDWP-based deep layout retrieval path that exposes full View properties (padding, margin, elevation, textSize, corner radius, …) for AI-driven design walkthrough (设计走查), via a standalone Java helper invoked by the existing Python MCP.

## Goal

The existing layout tools (`GetLayoutTree`, `GetElementDetails`) read the **accessibility tree** (`uiautomator dump_hierarchy`). That tree carries only semantic info (bounds, text, state flags) — it has **no rendering properties**. Design review needs the precise `padding / margin / elevation / textSize` and similar attributes, which exist only on the real `View` objects.

Those properties are reachable through the **JDWP / DDM debug channel** (the same mechanism Android Studio Layout Inspector and the YALI plugin use). This spec adds a second, opt-in data path that retrieves the full property-rich View tree, while keeping the current accessibility path intact for general use.

## Key Decisions (from brainstorming)

| Decision | Choice |
|----------|--------|
| Integration | One-shot **CLI subprocess**: Python invokes `java -jar`, receives JSON on stdout, process exits |
| Layout source for deep mode | **JDWP tree** is used for *both* `GetLayoutTree` and `GetElementDetails` — no cross-tree alignment needed |
| Tool surface | Tool **names/signatures stay identical**; a startup flag `--deep` routes to the JDWP implementation |
| Failure behavior (deep) | **Fail with a clear error** — no silent fallback to the accessibility tree |
| Java build | **Gradle + prebuilt fat-jar** (committed); end users need only a JRE, not Gradle |
| Java language | **Plain Java** (lighter deps; port YALI's V1/V2 decode logic) |
| dump mechanism | ddmlib `Client.dumpViewHierarchy(includeProperties=true)` (route α), with old-ddmlib fallback (route β) gated by a spike |

## Environment Facts (verified)

- Target device: `ro.debuggable=1`, `ro.build.type=userdebug` → **every process exposes JDWP**, not just debug-built apps.
- `ddmlib` jars already present in the local Gradle cache (30.3.0 … 31.13.1, with sources).
- `adb 36.0.0`, Java available via jenv. No Gradle/Maven installed globally (Gradle wrapper will be vendored).

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Python MCP Server (existing, FastMCP)                    │
│  startup: uvx android-mcp [--deep]                        │
│         │                                                 │
│         ▼                                                 │
│  LayoutProvider (strategy interface) ← injected by --deep │
│    ├─ AccessibilityProvider  (existing dump_hierarchy)    │
│    └─ JdwpProvider           (new: calls Java fat-jar)    │
│         │                                                 │
│  tools GetLayoutTree / GetElementDetails                  │
│    call provider interface only; unaware of backend       │
└─────────────────────────────────────────────────────────┘
              │ (deep mode only) subprocess: java -jar
              ▼
┌─────────────────────────────────────────────────────────┐
│  deep-inspector (new, Java fat-jar, one-shot subprocess)  │
│   input: device serial, package/pid, [window]            │
│   ① ddmlib connect → find Client(process) → list Window   │
│   ② Client.dumpViewHierarchy(includeProperties=true)      │
│   ③ parse V1/V2 → ViewNode tree                           │
│   ④ relative coords → absolute (cumulative)               │
│   ⑤ emit unified JSON to stdout, exit                     │
└─────────────────────────────────────────────────────────┘
              │ ddmlib over ADB (JDWP/DDM)
              ▼
        Android userdebug device (ro.debuggable=1)
```

**Principles**:
- A `LayoutProvider` strategy interface; startup injects one implementation based on `--deep`.
- Tool functions depend only on the interface — **external names and signatures unchanged**.
- The Java helper is a **stateless one-shot subprocess**: dump once, emit JSON, exit.
- Contract = args/stdin in, **JSON on stdout** — plain text, easy to debug.
- Deep mode: JDWP failure → **clear error**, no fallback.

## Components & File Layout

### Python side

```
src/android_mcp/
├── layout/                          # NEW: strategy layer
│   ├── __init__.py
│   ├── provider.py                  # LayoutProvider Protocol
│   ├── accessibility_provider.py    # wraps existing Tree logic
│   ├── jdwp_provider.py             # invokes Java jar, parses JSON
│   └── models.py                    # DeepLayoutNode (full properties)
├── tree/service.py                  # unchanged; reused by accessibility_provider
├── mobile/service.py                # unchanged
└── __main__.py                      # CHANGED: --deep flag, provider injection,
                                     #          tools call the interface
```

Interface (`provider.py`):

```python
class LayoutProvider(Protocol):
    def get_layout_tree(self, max_depth=None, filter_class=None) -> str: ...
    def get_element_details(self, selector_type, selector_value, timeout) -> str: ...
```

- `AccessibilityProvider`: existing tool bodies moved here, behavior unchanged.
- `JdwpProvider`: subprocess → JSON → `DeepLayoutNode` tree → reuse the **same text formatter** so both modes render in a consistent style.

### Java side

```
java-deep-inspector/                 # in-repo standalone Gradle subproject
├── gradlew / gradlew.bat            # wrapper (no global Gradle needed)
├── gradle/wrapper/...
├── build.gradle.kts                 # ddmlib dep, shadow plugin → fat-jar
├── settings.gradle.kts
└── src/main/java/com/androidmcp/inspector/
    ├── Main.java                    # CLI entry: parse args, orchestrate, emit JSON
    ├── DeviceConnector.java         # ddmlib connect, find Client, list Window
    ├── ViewHierarchyDumper.java     # call dumpViewHierarchy, get raw bytes
    ├── ViewNodeParser.java          # V1/V2 decode (port from YALI)
    ├── CoordinateResolver.java      # relative → absolute coords
    └── JsonOutput.java              # unified JSON serialization
prebuilt/
└── deep-inspector.jar               # committed prebuilt artifact
```

- Plain Java; YALI's V1/V2 decode logic translated to Java.
- Fat-jar **prebuilt and committed** to `prebuilt/`; ordinary users run `java -jar prebuilt/deep-inspector.jar` with no Gradle. Gradle is needed only to rebuild after Java changes.
- Jar path configurable in Python (env override + default relative path); missing jar or missing `java` → clear error at deep-mode startup.

## Data Flow (one deep-mode call)

```
AI: GetElementDetails(selector_type="resourceId", selector_value="btn_login")
  → __main__ tool fn → provider.get_element_details(...)   (JdwpProvider injected)

JdwpProvider:
  ① uiautomator2: current foreground package + element absolute bounds (anchor)
  ② subprocess: java -jar deep-inspector.jar --serial <s> --package <pkg> [--window <w>]
  ③ await stdout JSON (timeout, default 15s)

deep-inspector (Java):
  ① DeviceConnector: connect serial → find Client by package → list Window
  ② ViewHierarchyDumper: client.dumpViewHierarchy(includeProperties=true)
  ③ ViewNodeParser: V1/V2 → ViewNode tree (full property map)
  ④ CoordinateResolver: accumulate mLeft/mTop → absolute bounds
  ⑤ JsonOutput: serialize tree → stdout → exit 0
     failure → stderr reason, non-zero exit

JdwpProvider:
  ④ non-zero exit or timeout → raise error (deep mode: no fallback)
  ⑤ JSON → DeepLayoutNode tree
  ⑥ locate target node in-tree (resource-id first, else absolute-bounds match from ①)
  ⑦ format as text → return to AI
```

`GetLayoutTree` skips step ⑥ and formats the whole tree. Because deep mode has **only one tree (JDWP)**, there is no cross-tree alignment problem — this is the simplification gained by sourcing both tools from JDWP.

### JSON contract (Java → Python)

```json
{
  "ok": true,
  "protocol": "V2",
  "package": "com.miui.notes",
  "window": "com.miui.notes/...NotesEditActivity",
  "root": {
    "class": "android.widget.TextView",
    "hash": "d248a7",
    "resourceId": "com.miui.notes:id/title",
    "bounds": [61, 2427, 1139, 2598],
    "relativeBounds": [0, 0, 1078, 171],
    "text": "标题",
    "properties": {
      "paddingLeft": 48, "paddingTop": 24, "paddingRight": 48, "paddingBottom": 24,
      "layout_marginStart": 16, "layout_marginTop": 8,
      "elevation": 4.0, "textSize": 16.0, "alpha": 1.0,
      "visibility": "VISIBLE",
      "background": "rrect r:24.0"
    },
    "children": [ /* recursive */ ]
  }
}
```

Failure: `{"ok": false, "error": "process com.x not debuggable", "errorType": "NOT_DEBUGGABLE"}` + non-zero exit.

Contract principles:
1. **Pass-through + promotion**: padding/margin/elevation/textSize get stable named fields; all other `@ExportedProperty` attributes are passed through in `properties` verbatim (future fields need no Java change).
2. **Units**: JDWP size values are **px**; dp conversion reuses the existing `_display_scale` on the **Python side**. Java passes raw values.

### Text output (both modes, unified style)

```
[0] TextView  [61,2427][1139,2598]  id=title  text="标题"
    padding=[48,24,48,24]  margin=[16,8,0,0]  elevation=4.0dp  textSize=16.0dp  bg=圆角24.0dp
  [1] ...
```

General mode omits property lines it has no data for; deep mode adds the padding/margin/elevation lines.

## Error Handling

### Startup (deep mode, fail-fast)

| Check | On failure |
|-------|-----------|
| `--deep` but no `java` on PATH | error + exit ("deep mode requires a JDK") |
| `--deep` but `deep-inspector.jar` missing | error + exit (print jar path; env override supported) |
| General mode | never touches Java; zero impact |

### Per-call (deep mode: error, never silent fallback; never crash the tool)

| errorType | Meaning | Message to AI |
|-----------|---------|---------------|
| `NOT_DEBUGGABLE` | target process not debuggable | "process X not debuggable; deep mode needs debuggable process or userdebug device" |
| `PROCESS_NOT_FOUND` | no Client for package | "no JDWP client for X on device; may have just started, retry" |
| `DUMP_FAILED` | dumpViewHierarchy empty/exception | "view dump failed; window may be SurfaceView / pure Compose" |
| `TIMEOUT` | subprocess exceeds 15s | "deep capture timed out; device may be busy" |
| `PROTOCOL_UNSUPPORTED` | API<23 / unsupported | "device API too low for V2 protocol" |
| `ELEMENT_NOT_FOUND` | selector not located in JDWP tree | return text + list nearest candidate nodes |

All errors are **clear text + non-crashing** (error ≠ exception that kills the MCP). The AI can decide to retry or switch tools.

### Boundary cases

1. **Compose black box**: pure Jetpack Compose stops at `ComposeView` (internal composables not visible to JDWP). **Out of scope this iteration** (no YALI-style merge — YAGNI). Output annotates "ComposeView (internals not visible)".
2. **Multiple windows**: an app may have Activity + Dialog + Toast windows. Default = top/focused window; `--window` overrides. `GetLayoutTree` defaults to the focused window to avoid output explosion.
3. **Coordinate accumulation pitfalls**: `scrollX/scrollY`, `translationX/Y`, GONE nodes affect absolute coords. CoordinateResolver handles scroll offset; GONE nodes (bounds may be 0) are emitted as-is, not forced.
4. **Missing properties**: different View types expose different attributes (ImageView has no textSize). Missing fields → **omit the line**, no default value (a missing line beats a misleading "textSize=0").
5. **JVM cold start**: ~1–2s per call. Design walkthrough is low-frequency, acceptable; tool description notes deep mode is slower so the AI has the right expectation.
6. **selector miss**: if selector can't be located in the JDWP tree → `ELEMENT_NOT_FOUND` text listing nearest candidates.

### Safety / resources

- Subprocess has a **strict timeout + forced kill** to prevent a hung ddmlib from stalling the MCP.
- Java helper is stateless, exits after use — no daemon, no port, no held device connection.

## Spike (Step 0 — go/no-go gate)

Before any production code, manually run the minimal chain to verify the ddmlib DDM view API still works in this environment:

```
connect device → find Client for com.miui.notes
→ dumpViewHierarchy(includeProperties=true) → print raw tree showing padding
```

- **Pass** (padding/textSize visible) → route α holds; lock that ddmlib version; proceed.
- **Fail** (API deprecated / no properties) → drop to route β (ddmlib 30.4.0), re-run spike; only if that also fails consider route γ (hand-rolled DDM `VURT`/`VUOP` decode).
- The spike result is recorded here as the version-lock rationale.

**If the spike does not pass, nothing else proceeds.** This is the project's single major unknown.

## Testing Strategy

### Java
- **Unit (JUnit)**: `ViewNodeParser` against a **recorded real byte sample** (a V2 dump captured during the spike, stored as a fixture); `CoordinateResolver` against constructed relative-coord trees (incl. scroll/translation edges). These are pure-logic, offline — the Java test focus.
- **Integration**: dump a real device, manually verify a few known elements' padding against Android Studio Layout Inspector (semi-automatic, acceptance).

### Python
- **Unit (pytest)**: `JdwpProvider` with **mocked subprocess** (fed stored JSON fixtures) tests the JSON→`DeepLayoutNode`→text chain offline; error branches mock non-zero exit / timeout / each errorType and assert the right error text; `AccessibilityProvider` follows existing `tests/unit/test_layout.py`; provider injection (does `--deep` pick the right impl).
- **Regression**: confirm general-mode `GetLayoutTree`/`GetElementDetails` output is **identical** to pre-refactor (guard against behavior drift from the strategy refactor).

### Coverage target
**80%+** per project standard. Focus on the two pure-logic cores: V1/V2 parse + coordinate accumulation (Java), and JSON→model→text + error classification (Python). Device-dependent parts use fixtures + mocks for offline, repeatable tests.

## Acceptance Criteria

1. Spike passes and ddmlib version is locked.
2. In deep mode, for a `com.miui.notes` element, `GetElementDetails` returns padding/margin/elevation/textSize matching Android Studio Layout Inspector.
3. General-mode behavior is unchanged (regression passes).
4. Deep-mode errorTypes each return clear text without crashing.
5. Coverage 80%+.

## Files to Add / Modify

| File | Change |
|------|--------|
| `src/android_mcp/layout/provider.py` | NEW — `LayoutProvider` Protocol |
| `src/android_mcp/layout/accessibility_provider.py` | NEW — wraps existing Tree logic |
| `src/android_mcp/layout/jdwp_provider.py` | NEW — invokes Java jar, parses JSON, locates node |
| `src/android_mcp/layout/models.py` | NEW — `DeepLayoutNode` |
| `src/android_mcp/__main__.py` | MODIFY — `--deep` flag, provider injection, tools call interface |
| `java-deep-inspector/**` | NEW — Gradle subproject, ddmlib helper |
| `prebuilt/deep-inspector.jar` | NEW — committed fat-jar |
| `tests/unit/test_jdwp_provider.py` | NEW — Python unit tests with fixtures/mocks |
| `tests/fixtures/*.json`, `*.bin` | NEW — recorded JSON / V2 byte samples |

## Out of Scope (YAGNI)

- Jetpack Compose internal hierarchy merge (YALI's TreeMerger).
- Long-lived Java daemon (chose one-shot subprocess).
- Cross-tree (accessibility + JDWP) merging — deep mode uses JDWP only.
- Node screenshots via `captureView` (not needed for property review).

## Dependencies

- **Python**: no new runtime deps (uses stdlib `subprocess`, `json`, existing `uiautomator2`/`fastmcp`).
- **Java**: `com.android.tools.ddms:ddmlib` (version locked by spike), Gradle shadow plugin for fat-jar. Requires a JRE at runtime only in deep mode.
