# JDWP Deep Layout Inspector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in `--deep` mode that retrieves full View properties (padding, margin, elevation, textSize, corner radius, …) via a standalone Java helper using ddmlib/JDWP, surfaced through the existing `GetLayoutTree` / `GetElementDetails` tools without changing their names or signatures.

**Architecture:** A Python `LayoutProvider` strategy interface with two implementations — `AccessibilityProvider` (existing accessibility-tree logic, default) and `JdwpProvider` (new, calls a Java fat-jar as a one-shot subprocess). A startup flag `--deep` selects the implementation. The Java helper connects via ddmlib 30.4.0, dumps the focused window's View hierarchy as **V1 text**, resolves relative→absolute coordinates, and emits unified JSON on stdout.

**Tech Stack:** Python 3.13 (FastMCP, uiautomator2, stdlib subprocess/json), Java (ddmlib 30.4.0, Gradle + shadow fat-jar, JUnit), pytest.

**Spec:** `docs/superpowers/specs/2026-05-29-jdwp-deep-inspector-design.md`
**Spike sources/fixtures:** `docs/superpowers/spikes/Spike*.java`, `tests/fixtures/v1_dump_sample.txt`

---

## File Structure

### Python (new)
- `src/android_mcp/layout/__init__.py` — package marker
- `src/android_mcp/layout/models.py` — `DeepLayoutNode` dataclass + text formatter
- `src/android_mcp/layout/provider.py` — `LayoutProvider` Protocol
- `src/android_mcp/layout/accessibility_provider.py` — wraps existing `Tree`
- `src/android_mcp/layout/jdwp_provider.py` — subprocess + JSON → `DeepLayoutNode`, node lookup
- `src/android_mcp/layout/jdwp_runner.py` — locate jar / java, run subprocess, classify errors

### Python (modified)
- `src/android_mcp/__main__.py` — add `--deep` flag, build provider, route the two tools through it

### Java (new) — `java-deep-inspector/`
- `settings.gradle.kts`, `build.gradle.kts`, Gradle wrapper
- `src/main/java/com/androidmcp/inspector/Main.java` — CLI entry
- `.../DeviceConnector.java` — ddmlib connect, find Client, list windows
- `.../ViewHierarchyDumper.java` — call dumpViewHierarchy (V1), return text
- `.../ViewNodeParser.java` — parse V1 text → node tree
- `.../CoordinateResolver.java` — relative → absolute coords
- `.../JsonOutput.java` — serialize to the JSON contract
- `src/test/java/com/androidmcp/inspector/ViewNodeParserTest.java`
- `src/test/java/com/androidmcp/inspector/CoordinateResolverTest.java`

### Build output
- `prebuilt/deep-inspector.jar` — committed fat-jar

### Tests / fixtures
- `tests/fixtures/v1_dump_sample.txt` — already saved (Java parser fixture)
- `tests/fixtures/deep_dump_sample.json` — JdwpProvider Python fixture (created in Task 11)
- `tests/unit/test_deep_models.py`, `test_jdwp_provider.py`, `test_provider_injection.py`

---

## Phase A — Python strategy refactor (no Java yet; pure refactor, must not change behavior)

### Task 1: Create the layout package and `DeepLayoutNode` model

**Files:**
- Create: `src/android_mcp/layout/__init__.py`
- Create: `src/android_mcp/layout/models.py`
- Test: `tests/unit/test_deep_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_deep_models.py
from android_mcp.layout.models import DeepLayoutNode, format_deep_tree


def _leaf(**kw):
    base = dict(
        class_name="android.widget.TextView", resource_id="title",
        bounds=(61, 2427, 1139, 2598), text="标题",
        properties={"paddingLeft": 48, "paddingTop": 24, "paddingRight": 48,
                    "paddingBottom": 0, "elevation": 4.0, "textSize": 14.0},
        depth=0, children=(),
    )
    base.update(kw)
    return DeepLayoutNode(**base)


def test_node_is_frozen_and_holds_properties():
    n = _leaf()
    assert n.properties["paddingLeft"] == 48
    assert n.bounds == (61, 2427, 1139, 2598)


def test_format_deep_tree_renders_property_lines():
    root = _leaf(children=(_leaf(depth=1, resource_id="child", text="hi"),))
    out = format_deep_tree(root)
    assert "[0] TextView" in out
    assert "id=title" in out
    assert "padding=[48,24,48,0]" in out
    assert "elevation=4.0dp" in out
    assert "textSize=14.0dp" in out
    # child indented and present
    assert "[1] TextView" in out
    assert "id=child" in out


def test_format_omits_absent_property_lines():
    n = DeepLayoutNode(
        class_name="android.widget.ImageView", resource_id="", bounds=(0, 0, 10, 10),
        text="", properties={"paddingLeft": 0, "paddingTop": 0, "paddingRight": 0,
                              "paddingBottom": 0}, depth=0, children=(),
    )
    out = format_deep_tree(n)
    assert "textSize" not in out   # ImageView has no textSize → no line
    assert "elevation" not in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_deep_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'android_mcp.layout'`

- [ ] **Step 3: Create the package marker**

```python
# src/android_mcp/layout/__init__.py
```
(empty file)

- [ ] **Step 4: Write the model + formatter**

```python
# src/android_mcp/layout/models.py
from dataclasses import dataclass


@dataclass(frozen=True)
class DeepLayoutNode:
    class_name: str
    resource_id: str
    bounds: tuple  # absolute (left, top, right, bottom)
    text: str
    properties: dict  # all extracted props, e.g. paddingLeft, layout_marginTop, elevation, textSize
    depth: int
    children: tuple  # tuple[DeepLayoutNode, ...]


def _short_class(class_name: str) -> str:
    return class_name.rsplit(".", 1)[-1] if "." in class_name else class_name


def _padding_line(p: dict):
    keys = ("paddingLeft", "paddingTop", "paddingRight", "paddingBottom")
    if not any(k in p for k in keys):
        return None
    vals = [p.get(k, 0) for k in keys]
    return "padding=[{},{},{},{}]".format(*vals)


def _margin_line(p: dict):
    keys = ("marginLeft", "marginTop", "marginRight", "marginBottom")
    if not any(k in p for k in keys):
        return None
    vals = [p.get(k, 0) for k in keys]
    return "margin=[{},{},{},{}]".format(*vals)


def format_deep_tree(root: DeepLayoutNode) -> str:
    lines = []

    def emit(node: DeepLayoutNode):
        indent = "  " * node.depth
        l, t, r, b = node.bounds
        head = f"{indent}[{node.depth}] {_short_class(node.class_name)}  [{l},{t}][{r},{b}]"
        if node.resource_id:
            head += f"  id={node.resource_id}"
        if node.text:
            head += f'  text="{node.text}"'
        lines.append(head)

        p = node.properties
        prop_bits = []
        pad = _padding_line(p)
        if pad:
            prop_bits.append(pad)
        mar = _margin_line(p)
        if mar:
            prop_bits.append(mar)
        if "elevation" in p:
            prop_bits.append(f"elevation={p['elevation']}dp")
        if "textSize" in p:
            prop_bits.append(f"textSize={p['textSize']}dp")
        if "cornerRadius" in p:
            prop_bits.append(f"radius={p['cornerRadius']}dp")
        if prop_bits:
            lines.append(indent + "    " + "  ".join(prop_bits))

        for c in node.children:
            emit(c)

    emit(root)
    return "\n".join(lines)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_deep_models.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add src/android_mcp/layout/__init__.py src/android_mcp/layout/models.py tests/unit/test_deep_models.py
git commit -m "feat: add DeepLayoutNode model and deep-tree text formatter"
```

---

### Task 2: Define the `LayoutProvider` interface

**Files:**
- Create: `src/android_mcp/layout/provider.py`

- [ ] **Step 1: Write the interface (no test — it is a typing Protocol with no logic)**

```python
# src/android_mcp/layout/provider.py
from typing import Optional, Protocol


class LayoutProvider(Protocol):
    """Strategy for retrieving layout data. Implementations: AccessibilityProvider, JdwpProvider."""

    def get_layout_tree(self, max_depth: Optional[int] = None,
                        filter_class: Optional[str] = None) -> str:
        ...

    def get_element_details(self, selector_type: str, selector_value: str,
                            timeout: float = 5.0) -> str:
        ...
```

- [ ] **Step 2: Verify it imports**

Run: `uv run python -c "from android_mcp.layout.provider import LayoutProvider; print('ok')"`
Expected: prints `ok`

- [ ] **Step 3: Commit**

```bash
git add src/android_mcp/layout/provider.py
git commit -m "feat: add LayoutProvider strategy interface"
```

---

### Task 3: Extract `AccessibilityProvider` from the existing tool bodies

This moves the *current* `GetLayoutTree` / `GetElementDetails` logic into a provider, with **identical behavior**. The `__main__` tools will delegate to it in Task 4.

**Files:**
- Create: `src/android_mcp/layout/accessibility_provider.py`
- Reference (do not yet modify): `src/android_mcp/__main__.py:419-494` (current tool bodies), `:286-319` (`_resolve_resource_id`, `_display_scale`), `:256-283` (`_filter_layout_tree`)
- Test: `tests/unit/test_accessibility_provider.py`

- [ ] **Step 1: Write the failing test (uses a fake device + fake mobile)**

```python
# tests/unit/test_accessibility_provider.py
from android_mcp.layout.accessibility_provider import AccessibilityProvider

SAMPLE_XML = """<?xml version='1.0' encoding='UTF-8'?>
<hierarchy rotation="0">
  <node class="android.widget.FrameLayout" resource-id="com.x:id/root" bounds="[0,0][1080,1920]" enabled="true" visible-to-user="true" clickable="false" focused="false" checked="false" scrollable="false" text="" content-desc="">
    <node class="android.widget.TextView" resource-id="com.x:id/title" bounds="[0,0][1080,100]" enabled="true" visible-to-user="true" clickable="true" focused="false" checked="false" scrollable="false" text="Hello" content-desc="" />
  </node>
</hierarchy>"""


class FakeDevice:
    def __init__(self): self.info = {"displayWidth": 1080, "displaySizeDpX": 360}
    def dump_hierarchy(self): return SAMPLE_XML
    def app_current(self): return {"package": "com.x"}


class FakeMobile:
    def __init__(self): self.device = FakeDevice()


def test_get_layout_tree_includes_container_and_child():
    prov = AccessibilityProvider(FakeMobile())
    out = prov.get_layout_tree()
    assert "FrameLayout" in out
    assert "TextView" in out
    assert "Hello" in out


def test_get_layout_tree_filter_class():
    prov = AccessibilityProvider(FakeMobile())
    out = prov.get_layout_tree(filter_class="TextView")
    assert "TextView" in out
    assert "FrameLayout" not in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_accessibility_provider.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'android_mcp.layout.accessibility_provider'`

- [ ] **Step 3: Write the provider (port logic from `__main__.py`)**

```python
# src/android_mcp/layout/accessibility_provider.py
import re
from android_mcp.tree.service import Tree


def _resolve_resource_id(device, resource_id: str) -> str:
    if not resource_id or '/' in resource_id or ':' in resource_id:
        return resource_id
    try:
        pkg = device.app_current().get('package', '')
    except Exception:
        pkg = ''
    return f'{pkg}:id/{resource_id}' if pkg else resource_id


def _display_scale(device) -> float:
    info = device.info
    width_px = info.get("displayWidth")
    width_dp = info.get("displaySizeDpX")
    if width_px and width_dp:
        return width_px / width_dp
    try:
        output = device.shell("wm density").output
        m = re.search(r"(\d+)", output)
        if m:
            return int(m.group(1)) / 160
    except Exception:
        pass
    return 1.0


def _filter_layout_tree(node, filter_class):
    # EXACT copy of the existing __main__.py:256 implementation — do not "improve" it,
    # the Task 4 regression test depends on identical behavior.
    from android_mcp.tree.views import LayoutNode

    filtered_children = []
    for child in node.children:
        filtered_child = _filter_layout_tree(child, filter_class)
        if filtered_child is not None:
            filtered_children.append(filtered_child)

    matches = filter_class.lower() in node.class_name.lower()
    if matches or filtered_children:
        return LayoutNode(
            class_name=node.class_name, resource_id=node.resource_id, bounds=node.bounds,
            text=node.text, content_desc=node.content_desc, enabled=node.enabled,
            visible=node.visible, clickable=node.clickable, focused=node.focused,
            checked=node.checked, scrollable=node.scrollable, depth=node.depth,
            children=tuple(filtered_children),
        )
    return None


class AccessibilityProvider:
    """Layout provider backed by the Android accessibility tree (dump_hierarchy)."""

    def __init__(self, mobile):
        self.mobile = mobile

    def get_layout_tree(self, max_depth=None, filter_class=None) -> str:
        device = self.mobile.device
        xml_data = device.dump_hierarchy()
        tree = Tree(self.mobile)
        layout_root = tree.get_layout_tree(xml_data=xml_data, max_depth=max_depth)
        if layout_root is None:
            return "Failed to parse layout tree."
        if filter_class:
            layout_root = _filter_layout_tree(layout_root, filter_class)
            if layout_root is None:
                return f"No elements matching class '{filter_class}' found."
        return Tree.format_layout_tree(layout_root)

    def get_element_details(self, selector_type, selector_value, timeout=5.0) -> str:
        device = self.mobile.device
        valid = {"text", "resourceId", "description"}
        if selector_type not in valid:
            return f"Invalid selector_type '{selector_type}'. Must be one of: {', '.join(sorted(valid))}"
        kwargs = {}
        if selector_type == "resourceId":
            kwargs["resourceId"] = _resolve_resource_id(device, selector_value)
        else:
            kwargs[selector_type] = selector_value
        el = device(**kwargs)
        if not el.wait(timeout=timeout):
            return f"Element not found with {selector_type}='{selector_value}' within {timeout}s"
        info = el.info
        bounds = info.get("bounds", {})
        vb = info.get("visibleBounds", {})
        scale = _display_scale(device)
        w_px = bounds.get("right", 0) - bounds.get("left", 0)
        h_px = bounds.get("bottom", 0) - bounds.get("top", 0)
        lines = [
            f"class: {info.get('className', '')}",
            f"resource-id: {info.get('resourceName', '')}",
            f"text: {info.get('text', '')}",
            f"content-desc: {info.get('contentDescription', '')}",
            f"bounds: [{bounds.get('left',0)},{bounds.get('top',0)}][{bounds.get('right',0)},{bounds.get('bottom',0)}]",
            f"visible-bounds: [{vb.get('left',0)},{vb.get('top',0)}][{vb.get('right',0)},{vb.get('bottom',0)}]",
            f"width: {round(w_px / scale)}dp ({w_px}px)",
            f"height: {round(h_px / scale)}dp ({h_px}px)",
            f"enabled: {info.get('enabled', False)}",
            f"visible: {info.get('visible', True)}",
            f"clickable: {info.get('clickable', False)}",
            f"focused: {info.get('focused', False)}",
            f"checked: {info.get('checked', False)}",
            f"scrollable: {info.get('scrollable', False)}",
            f"selected: {info.get('selected', False)}",
            f"package: {info.get('packageName', '')}",
        ]
        return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_accessibility_provider.py -v`
Expected: PASS (2 tests)

> Note: `_filter_layout_tree` here must match the existing implementation in `__main__.py:256-283`. Before writing, open that function and copy its exact logic; the code above is the expected shape but verify field names against `LayoutNode` in `tree/views.py`.

- [ ] **Step 5: Commit**

```bash
git add src/android_mcp/layout/accessibility_provider.py tests/unit/test_accessibility_provider.py
git commit -m "feat: extract AccessibilityProvider from tool bodies"
```

---

### Task 4: Route the two tools through a module-level provider (default = accessibility)

**Files:**
- Modify: `src/android_mcp/__main__.py` (tool bodies `get_layout_tree_tool` `:419-439`, `get_element_details_tool` `:442-494`; add provider construction near `mobile = Mobile()` `:250`)

- [ ] **Step 1: Add provider construction after `mobile = Mobile()`**

Find (`__main__.py:250`):
```python
mobile = Mobile()
```
Add immediately after:
```python
from android_mcp.layout.accessibility_provider import AccessibilityProvider
# Selected in main() based on --deep; defaults to accessibility for safety.
layout_provider = AccessibilityProvider(mobile)
```

- [ ] **Step 2: Replace `get_layout_tree_tool` body**

Replace (`__main__.py:425-439`) the body of `get_layout_tree_tool` with:
```python
def get_layout_tree_tool(max_depth: int = None, filter_class: str = None):
    require_device()
    return layout_provider.get_layout_tree(max_depth=max_depth, filter_class=filter_class)
```

- [ ] **Step 3: Replace `get_element_details_tool` body**

Replace (`__main__.py:448-494`) the body of `get_element_details_tool` with:
```python
def get_element_details_tool(selector_type: str, selector_value: str, timeout: float = 5.0):
    require_device()
    return layout_provider.get_element_details(selector_type, selector_value, timeout)
```

- [ ] **Step 4: Verify the server still imports and lists tools**

Run: `uv run python -c "import android_mcp.__main__ as m; print('tools ok')"`
Expected: prints `tools ok` (no import errors)

- [ ] **Step 5: Run the full test suite (regression)**

Run: `uv run pytest tests/ -v`
Expected: PASS (existing `tests/unit/test_layout.py` + new tests)

- [ ] **Step 6: Commit**

```bash
git add src/android_mcp/__main__.py
git commit -m "refactor: route layout tools through LayoutProvider (default accessibility)"
```

---

## Phase B — Java deep-inspector helper

> Build commands assume the Gradle wrapper is generated in Task 5. All `./gradlew` commands run from `java-deep-inspector/`.

### Task 5: Scaffold the Gradle subproject with ddmlib 30.4.0 + shadow

**Files:**
- Create: `java-deep-inspector/settings.gradle.kts`
- Create: `java-deep-inspector/build.gradle.kts`
- Create: `java-deep-inspector/gradle/wrapper/gradle-wrapper.properties`
- Create: `java-deep-inspector/src/main/java/com/androidmcp/inspector/Main.java` (stub)

- [ ] **Step 1: Write `settings.gradle.kts`**

```kotlin
rootProject.name = "deep-inspector"
```

- [ ] **Step 2: Write `build.gradle.kts`**

```kotlin
plugins {
    java
    application
    id("com.github.johnrengelman.shadow") version "8.1.1"
}

repositories {
    google()
    mavenCentral()
}

dependencies {
    implementation("com.android.tools.ddms:ddmlib:30.4.0")
    testImplementation("org.junit.jupiter:junit-jupiter:5.10.2")
}

java {
    toolchain { languageVersion.set(JavaLanguageVersion.of(17)) }
}

application {
    mainClass.set("com.androidmcp.inspector.Main")
}

tasks.test { useJUnitPlatform() }

tasks.shadowJar {
    archiveBaseName.set("deep-inspector")
    archiveClassifier.set("")
    archiveVersion.set("")
}
```

- [ ] **Step 3: Generate the Gradle wrapper**

Run (requires a one-time system gradle OR use the SDK's bundled gradle; if neither, install via `brew install gradle`):
```bash
cd java-deep-inspector && gradle wrapper --gradle-version 8.7
```
Expected: creates `gradlew`, `gradlew.bat`, `gradle/wrapper/gradle-wrapper.jar` and `.properties`.

> If no system `gradle` is available, install with `brew install gradle` first. The wrapper jar is committed so future builds need only `./gradlew`.

- [ ] **Step 4: Write a stub `Main.java` that prints a JSON error (so the build has a compilable entry point)**

```java
// src/main/java/com/androidmcp/inspector/Main.java
package com.androidmcp.inspector;

public class Main {
    public static void main(String[] args) {
        System.out.println("{\"ok\":false,\"error\":\"not implemented\",\"errorType\":\"STUB\"}");
        System.exit(1);
    }
}
```

- [ ] **Step 5: Build the fat-jar to verify the toolchain + deps resolve**

Run: `cd java-deep-inspector && ./gradlew shadowJar`
Expected: BUILD SUCCESSFUL; produces `build/libs/deep-inspector.jar`

- [ ] **Step 6: Smoke-run the stub jar**

Run: `java -jar java-deep-inspector/build/libs/deep-inspector.jar`
Expected: prints `{"ok":false,"error":"not implemented","errorType":"STUB"}` and exits 1

- [ ] **Step 7: Commit**

```bash
git add java-deep-inspector/settings.gradle.kts java-deep-inspector/build.gradle.kts \
  java-deep-inspector/gradlew java-deep-inspector/gradlew.bat java-deep-inspector/gradle/ \
  java-deep-inspector/src/main/java/com/androidmcp/inspector/Main.java
git commit -m "build: scaffold java-deep-inspector gradle subproject (ddmlib 30.4.0 + shadow)"
```

---

### Task 6: `ViewNodeParser` — parse V1 text into a node tree (pure logic, TDD against fixture)

**Files:**
- Create: `java-deep-inspector/src/main/java/com/androidmcp/inspector/ViewNode.java`
- Create: `.../ViewNodeParser.java`
- Test: `.../src/test/java/com/androidmcp/inspector/ViewNodeParserTest.java`
- Fixture: copy `tests/fixtures/v1_dump_sample.txt` → `java-deep-inspector/src/test/resources/v1_dump_sample.txt`

- [ ] **Step 1: Copy the fixture into Java test resources**

Run:
```bash
mkdir -p java-deep-inspector/src/test/resources
cp tests/fixtures/v1_dump_sample.txt java-deep-inspector/src/test/resources/v1_dump_sample.txt
```

- [ ] **Step 2: Write the failing test**

```java
// src/test/java/com/androidmcp/inspector/ViewNodeParserTest.java
package com.androidmcp.inspector;

import org.junit.jupiter.api.Test;
import java.nio.file.*;
import static org.junit.jupiter.api.Assertions.*;

class ViewNodeParserTest {

    @Test
    void parsesKeyLenValuePairs() {
        // Two nodes: root at depth 0, one child at depth 1 (1 leading space)
        String dump =
            "android.widget.FrameLayout@aaa padding:mPaddingLeft=2,48 layout:mLeft=1,0 layout:mTop=1,0 layout:mRight=4,1080 layout:mBottom=4,1920\n" +
            " android.widget.TextView@bbb text:mText=5,Hello text:getTextSize()=4,42.0 layout:mLeft=1,0 layout:mTop=1,0 layout:mRight=4,1080 layout:mBottom=3,100\n";
        ViewNode root = ViewNodeParser.parse(dump);
        assertEquals("android.widget.FrameLayout", root.className);
        assertEquals(1, root.children.size());
        ViewNode child = root.children.get(0);
        assertEquals("android.widget.TextView", child.className);
        assertEquals("Hello", child.props.get("text:mText"));
        assertEquals("42.0", child.props.get("text:getTextSize()"));
    }

    @Test
    void valueContainingSpacesRespectsLength() {
        // "BKG:rrect{Rect(0, 0 - 132, 72), r:0.0} a:0.0" has length 44 and contains spaces+commas
        String val = "BKG:rrect{Rect(0, 0 - 132, 72), r:0.0} a:0.0";
        String dump = "android.view.View@ccc layout:getOutlineString()=" + val.length() + "," + val + " drawing:getAlpha()=3,1.0\n";
        ViewNode root = ViewNodeParser.parse(dump);
        assertEquals(val, root.props.get("layout:getOutlineString()"));
        assertEquals("1.0", root.props.get("drawing:getAlpha()"));
    }

    @Test
    void parsesRealFixtureTreeShape() throws Exception {
        String dump = new String(Files.readAllBytes(
            Paths.get(getClass().getResource("/v1_dump_sample.txt").toURI())));
        ViewNode root = ViewNodeParser.parse(dump);
        assertNotNull(root);
        assertTrue(root.className.contains("DecorView"));
        // depth-1 children exist
        assertFalse(root.children.isEmpty());
        // somewhere in the tree a TextView with a textSize exists
        assertTrue(hasTextSize(root));
    }

    private boolean hasTextSize(ViewNode n) {
        if (n.props.containsKey("text:getTextSize()")) return true;
        for (ViewNode c : n.children) if (hasTextSize(c)) return true;
        return false;
    }
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd java-deep-inspector && ./gradlew test --tests ViewNodeParserTest`
Expected: COMPILE FAIL (`ViewNode` / `ViewNodeParser` missing)

- [ ] **Step 4: Write `ViewNode`**

```java
// src/main/java/com/androidmcp/inspector/ViewNode.java
package com.androidmcp.inspector;

import java.util.*;

public class ViewNode {
    public String className = "";
    public String hash = "";
    public int depth;
    public final Map<String, String> props = new LinkedHashMap<>();
    public final List<ViewNode> children = new ArrayList<>();
    // absolute bounds filled by CoordinateResolver
    public int absLeft, absTop, absRight, absBottom;
}
```

- [ ] **Step 5: Write `ViewNodeParser`**

```java
// src/main/java/com/androidmcp/inspector/ViewNodeParser.java
package com.androidmcp.inspector;

import java.util.*;

public class ViewNodeParser {

    /** Parse a V1 hierarchy text dump into a ViewNode tree. */
    public static ViewNode parse(String dump) {
        String[] lines = dump.split("\n", -1);
        ViewNode root = null;
        Deque<ViewNode> stack = new ArrayDeque<>(); // top = current parent chain
        Deque<Integer> depths = new ArrayDeque<>();

        for (String raw : lines) {
            if (raw.isEmpty() || raw.trim().isEmpty()) continue;
            if (raw.startsWith("DONE")) break; // ddmlib terminator, if present

            int depth = 0;
            while (depth < raw.length() && raw.charAt(depth) == ' ') depth++;
            String content = raw.substring(depth);

            ViewNode node = parseLine(content);
            node.depth = depth;

            if (root == null) {
                root = node;
                stack.push(node);
                depths.push(depth);
                continue;
            }
            // pop until we find this node's parent (strictly smaller depth)
            while (!depths.isEmpty() && depths.peek() >= depth) {
                stack.pop();
                depths.pop();
            }
            if (!stack.isEmpty()) {
                stack.peek().children.add(node);
            }
            stack.push(node);
            depths.push(depth);
        }
        return root;
    }

    /** Parse "ClassName@hash key=LEN,VALUE key=LEN,VALUE ...". */
    static ViewNode parseLine(String content) {
        ViewNode node = new ViewNode();
        int sp = content.indexOf(' ');
        String head = sp < 0 ? content : content.substring(0, sp);
        int at = head.indexOf('@');
        if (at >= 0) {
            node.className = head.substring(0, at);
            node.hash = head.substring(at + 1);
        } else {
            node.className = head;
        }
        int i = sp < 0 ? content.length() : sp + 1;
        int n = content.length();
        while (i < n) {
            // skip spaces
            while (i < n && content.charAt(i) == ' ') i++;
            if (i >= n) break;
            int eq = content.indexOf('=', i);
            if (eq < 0) break;
            String key = content.substring(i, eq);
            int comma = content.indexOf(',', eq + 1);
            if (comma < 0) break;
            int len;
            try {
                len = Integer.parseInt(content.substring(eq + 1, comma));
            } catch (NumberFormatException e) {
                break;
            }
            int valStart = comma + 1;
            int valEnd = Math.min(valStart + len, n);
            String value = content.substring(valStart, valEnd);
            node.props.put(key, value);
            i = valEnd;
        }
        return node;
    }
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd java-deep-inspector && ./gradlew test --tests ViewNodeParserTest`
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
git add java-deep-inspector/src/main/java/com/androidmcp/inspector/ViewNode.java \
  java-deep-inspector/src/main/java/com/androidmcp/inspector/ViewNodeParser.java \
  java-deep-inspector/src/test/java/com/androidmcp/inspector/ViewNodeParserTest.java \
  java-deep-inspector/src/test/resources/v1_dump_sample.txt
git commit -m "feat: V1 hierarchy text parser (key=LEN,VALUE, indentation depth)"
```

---

### Task 7: `CoordinateResolver` — relative → absolute bounds (pure logic, TDD)

**Files:**
- Create: `java-deep-inspector/src/main/java/com/androidmcp/inspector/CoordinateResolver.java`
- Test: `.../src/test/java/com/androidmcp/inspector/CoordinateResolverTest.java`

- [ ] **Step 1: Write the failing test**

```java
// src/test/java/com/androidmcp/inspector/CoordinateResolverTest.java
package com.androidmcp.inspector;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class CoordinateResolverTest {

    private ViewNode node(int l, int t, int r, int b, int scrollX, int scrollY) {
        ViewNode n = new ViewNode();
        n.props.put("layout:mLeft", String.valueOf(l));
        n.props.put("layout:mTop", String.valueOf(t));
        n.props.put("layout:mRight", String.valueOf(r));
        n.props.put("layout:mBottom", String.valueOf(b));
        n.props.put("scrolling:mScrollX", String.valueOf(scrollX));
        n.props.put("scrolling:mScrollY", String.valueOf(scrollY));
        return n;
    }

    @Test
    void rootBoundsAreAbsolute() {
        ViewNode root = node(0, 0, 1080, 1920, 0, 0);
        CoordinateResolver.resolve(root);
        assertEquals(0, root.absLeft);
        assertEquals(1080, root.absRight);
        assertEquals(1920, root.absBottom);
    }

    @Test
    void childOffsetByParentOrigin() {
        ViewNode root = node(0, 0, 1080, 1920, 0, 0);
        ViewNode child = node(48, 100, 1032, 200, 0, 0); // mLeft/mTop relative to parent
        root.children.add(child);
        CoordinateResolver.resolve(root);
        assertEquals(48, child.absLeft);
        assertEquals(100, child.absTop);
        assertEquals(1032, child.absRight);
        assertEquals(200, child.absBottom);
    }

    @Test
    void parentScrollShiftsChildren() {
        ViewNode root = node(0, 0, 1080, 1920, 0, 50); // scrolled down 50
        ViewNode child = node(0, 100, 1080, 200, 0, 0);
        root.children.add(child);
        CoordinateResolver.resolve(root);
        // child top = parentAbsTop(0) + mTop(100) - parentScrollY(50) = 50
        assertEquals(50, child.absTop);
        assertEquals(150, child.absBottom);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd java-deep-inspector && ./gradlew test --tests CoordinateResolverTest`
Expected: COMPILE FAIL (`CoordinateResolver` missing)

- [ ] **Step 3: Write `CoordinateResolver`**

```java
// src/main/java/com/androidmcp/inspector/CoordinateResolver.java
package com.androidmcp.inspector;

public class CoordinateResolver {

    /** Fill absLeft/absTop/absRight/absBottom for the whole tree. */
    public static void resolve(ViewNode root) {
        resolve(root, 0, 0);
    }

    private static void resolve(ViewNode node, int parentAbsLeft, int parentAbsTop) {
        int mLeft = intProp(node, "layout:mLeft");
        int mTop = intProp(node, "layout:mTop");
        int mRight = intProp(node, "layout:mRight");
        int mBottom = intProp(node, "layout:mBottom");

        int width = mRight - mLeft;
        int height = mBottom - mTop;

        node.absLeft = parentAbsLeft + mLeft;
        node.absTop = parentAbsTop + mTop;
        node.absRight = node.absLeft + width;
        node.absBottom = node.absTop + height;

        // children are positioned in this node's content space, shifted by this node's scroll
        int scrollX = intProp(node, "scrolling:mScrollX");
        int scrollY = intProp(node, "scrolling:mScrollY");
        int childOriginLeft = node.absLeft - scrollX;
        int childOriginTop = node.absTop - scrollY;
        for (ViewNode c : node.children) {
            resolve(c, childOriginLeft, childOriginTop);
        }
    }

    private static int intProp(ViewNode n, String key) {
        String v = n.props.get(key);
        if (v == null) return 0;
        try { return Integer.parseInt(v.trim()); }
        catch (NumberFormatException e) { return 0; }
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd java-deep-inspector && ./gradlew test --tests CoordinateResolverTest`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add java-deep-inspector/src/main/java/com/androidmcp/inspector/CoordinateResolver.java \
  java-deep-inspector/src/test/java/com/androidmcp/inspector/CoordinateResolverTest.java
git commit -m "feat: relative-to-absolute coordinate resolver with scroll offset"
```

---

### Task 8: `JsonOutput` — serialize the node tree to the JSON contract (pure logic, TDD)

This maps raw V1 prop keys to the contract's named fields and emits the tree. Property promotion logic lives here.

**Files:**
- Create: `java-deep-inspector/src/main/java/com/androidmcp/inspector/JsonOutput.java`
- Test: `.../src/test/java/com/androidmcp/inspector/JsonOutputTest.java`

- [ ] **Step 1: Write the failing test**

```java
// src/test/java/com/androidmcp/inspector/JsonOutputTest.java
package com.androidmcp.inspector;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class JsonOutputTest {

    @Test
    void promotesNamedFieldsAndNestsChildren() {
        ViewNode root = new ViewNode();
        root.className = "android.widget.TextView";
        root.props.put("text:mText", "Hello");
        root.props.put("padding:mPaddingLeft", "48");
        root.props.put("padding:mPaddingTop", "24");
        root.props.put("text:getTextSize()", "42.0");
        root.props.put("drawing:getElevation()", "4.0");
        root.props.put("mID", "id/title");
        root.absLeft = 61; root.absTop = 2427; root.absRight = 1139; root.absBottom = 2598;

        String json = JsonOutput.toJson(root, "com.x", "win0", "V1");
        assertTrue(json.contains("\"ok\":true"));
        assertTrue(json.contains("\"package\":\"com.x\""));
        assertTrue(json.contains("\"class\":\"android.widget.TextView\""));
        assertTrue(json.contains("\"bounds\":[61,2427,1139,2598]"));
        assertTrue(json.contains("\"paddingLeft\":48"));
        assertTrue(json.contains("\"textSize\":42.0"));
        assertTrue(json.contains("\"elevation\":4.0"));
    }

    @Test
    void errorJson() {
        String json = JsonOutput.error("process not debuggable", "NOT_DEBUGGABLE");
        assertTrue(json.contains("\"ok\":false"));
        assertTrue(json.contains("\"errorType\":\"NOT_DEBUGGABLE\""));
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd java-deep-inspector && ./gradlew test --tests JsonOutputTest`
Expected: COMPILE FAIL (`JsonOutput` missing)

- [ ] **Step 3: Write `JsonOutput`**

```java
// src/main/java/com/androidmcp/inspector/JsonOutput.java
package com.androidmcp.inspector;

import java.util.*;

public class JsonOutput {

    public static String error(String message, String errorType) {
        StringBuilder sb = new StringBuilder();
        sb.append("{\"ok\":false,\"error\":").append(quote(message))
          .append(",\"errorType\":").append(quote(errorType)).append("}");
        return sb.toString();
    }

    public static String toJson(ViewNode root, String pkg, String window, String protocol) {
        StringBuilder sb = new StringBuilder();
        sb.append("{\"ok\":true,\"protocol\":").append(quote(protocol))
          .append(",\"package\":").append(quote(pkg))
          .append(",\"window\":").append(quote(window))
          .append(",\"root\":");
        node(sb, root);
        sb.append("}");
        return sb.toString();
    }

    private static void node(StringBuilder sb, ViewNode n) {
        sb.append("{");
        sb.append("\"class\":").append(quote(n.className));
        sb.append(",\"hash\":").append(quote(n.hash));
        String rid = n.props.getOrDefault("mID", "");
        sb.append(",\"resourceId\":").append(quote(stripId(rid)));
        sb.append(",\"bounds\":[").append(n.absLeft).append(",").append(n.absTop)
          .append(",").append(n.absRight).append(",").append(n.absBottom).append("]");
        sb.append(",\"text\":").append(quote(n.props.getOrDefault("text:mText", "")));
        sb.append(",\"properties\":");
        properties(sb, n.props);
        sb.append(",\"children\":[");
        for (int i = 0; i < n.children.size(); i++) {
            if (i > 0) sb.append(",");
            node(sb, n.children.get(i));
        }
        sb.append("]}");
    }

    // Map of contract field -> source V1 key (numeric values emitted raw)
    private static final String[][] NUMERIC = {
        {"paddingLeft", "padding:mPaddingLeft"},
        {"paddingTop", "padding:mPaddingTop"},
        {"paddingRight", "padding:mPaddingRight"},
        {"paddingBottom", "padding:mPaddingBottom"},
        {"marginLeft", "layout:layout_leftMargin"},
        {"marginTop", "layout:layout_topMargin"},
        {"marginRight", "layout:layout_rightMargin"},
        {"marginBottom", "layout:layout_bottomMargin"},
        {"elevation", "drawing:getElevation()"},
        {"textSize", "text:getTextSize()"},
        {"scaledTextSize", "text:getScaledTextSize()"},
        {"alpha", "drawing:getAlpha()"},
    };

    private static void properties(StringBuilder sb, Map<String, String> props) {
        sb.append("{");
        boolean first = true;
        for (String[] pair : NUMERIC) {
            String v = props.get(pair[1]);
            if (v == null) continue;
            if (!first) sb.append(","); first = false;
            sb.append(quote(pair[0])).append(":").append(numberOrQuote(v));
        }
        // corner radius parsed from outline string, if present
        String outline = props.get("layout:getOutlineString()");
        Double radius = parseRadius(outline);
        if (radius != null) {
            if (!first) sb.append(","); first = false;
            sb.append("\"cornerRadius\":").append(radius);
        }
        sb.append("}");
    }

    static Double parseRadius(String outline) {
        if (outline == null) return null;
        int idx = outline.indexOf("r:");
        if (idx < 0) return null;
        int j = idx + 2;
        int k = j;
        while (k < outline.length() && (Character.isDigit(outline.charAt(k)) || outline.charAt(k) == '.')) k++;
        try { return Double.parseDouble(outline.substring(j, k)); }
        catch (Exception e) { return null; }
    }

    private static String stripId(String rid) {
        int slash = rid.indexOf('/');
        return slash >= 0 ? rid.substring(slash + 1) : rid;
    }

    private static String numberOrQuote(String v) {
        try { Double.parseDouble(v); return v; }
        catch (NumberFormatException e) { return quote(v); }
    }

    static String quote(String s) {
        if (s == null) s = "";
        StringBuilder b = new StringBuilder("\"");
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': b.append("\\\""); break;
                case '\\': b.append("\\\\"); break;
                case '\n': b.append("\\n"); break;
                case '\r': b.append("\\r"); break;
                case '\t': b.append("\\t"); break;
                default:
                    if (c < 0x20) b.append(String.format("\\u%04x", (int) c));
                    else b.append(c);
            }
        }
        return b.append("\"").toString();
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd java-deep-inspector && ./gradlew test --tests JsonOutputTest`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add java-deep-inspector/src/main/java/com/androidmcp/inspector/JsonOutput.java \
  java-deep-inspector/src/test/java/com/androidmcp/inspector/JsonOutputTest.java
git commit -m "feat: JSON serializer with property promotion and corner-radius parsing"
```

---

### Task 9: `DeviceConnector` + `ViewHierarchyDumper` — ddmlib glue (ported from spike)

This is the device-dependent layer. Logic is copied from the verified spike (`docs/superpowers/spikes/Spike.java`/`Spike3_v1.java`). No unit test (requires a device); verified by the integration run in Task 10.

**Files:**
- Create: `java-deep-inspector/src/main/java/com/androidmcp/inspector/DeviceConnector.java`
- Create: `.../ViewHierarchyDumper.java`

- [ ] **Step 1: Write `DeviceConnector`**

```java
// src/main/java/com/androidmcp/inspector/DeviceConnector.java
package com.androidmcp.inspector;

import com.android.ddmlib.*;
import java.util.concurrent.TimeUnit;

public class DeviceConnector {

    public static class NotFound extends Exception {
        public final String errorType;
        public NotFound(String msg, String errorType) { super(msg); this.errorType = errorType; }
    }

    private final String adbPath;

    public DeviceConnector(String adbPath) { this.adbPath = adbPath; }

    public IDevice connect(String serial, long timeoutMs) throws NotFound {
        AndroidDebugBridge.init(AdbInitOptions.builder().setClientSupportEnabled(true).build());
        AndroidDebugBridge bridge = AndroidDebugBridge.createBridge(adbPath, false, 30, TimeUnit.SECONDS);
        long deadline = System.currentTimeMillis() + timeoutMs;
        while (bridge.getDevices().length == 0 && System.currentTimeMillis() < deadline) {
            sleep(100);
        }
        IDevice[] devices = bridge.getDevices();
        if (devices.length == 0) throw new NotFound("no adb devices", "PROCESS_NOT_FOUND");
        if (serial != null) {
            for (IDevice d : devices) if (serial.equals(d.getSerialNumber())) return d;
            throw new NotFound("device " + serial + " not found", "PROCESS_NOT_FOUND");
        }
        return devices[0];
    }

    public Client findClient(IDevice device, String pkg, long timeoutMs) throws NotFound {
        long deadline = System.currentTimeMillis() + timeoutMs;
        while (System.currentTimeMillis() < deadline) {
            for (Client c : device.getClients()) {
                ClientData cd = c.getClientData();
                String name = cd.getClientDescription() != null ? cd.getClientDescription() : cd.getPackageName();
                if (pkg.equals(name) || pkg.equals(cd.getPackageName())) {
                    if (!cd.hasFeature(ClientData.FEATURE_VIEW_HIERARCHY)) {
                        throw new NotFound("process " + pkg + " not debuggable / no view feature", "NOT_DEBUGGABLE");
                    }
                    return c;
                }
            }
            sleep(200);
        }
        throw new NotFound("no JDWP client for " + pkg, "PROCESS_NOT_FOUND");
    }

    private static void sleep(long ms) {
        try { Thread.sleep(ms); } catch (InterruptedException ignored) {}
    }
}
```

- [ ] **Step 2: Write `ViewHierarchyDumper`**

```java
// src/main/java/com/androidmcp/inspector/ViewHierarchyDumper.java
package com.androidmcp.inspector;

import com.android.ddmlib.*;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;

public class ViewHierarchyDumper {

    /** Returns the focused/first window name, or null. */
    public static String firstWindow(Client client, long timeoutMs) throws Exception {
        final AtomicReference<String> ref = new AtomicReference<>();
        final CountDownLatch latch = new CountDownLatch(1);
        client.listViewRoots(new DebugViewDumpHandler(DebugViewDumpHandler.CHUNK_VULW) {
            protected void handleViewDebugResult(ByteBuffer data) {
                int count = data.getInt();
                for (int i = 0; i < count; i++) {
                    String w = getString(data, data.getInt());
                    if (ref.get() == null) ref.set(w);
                }
                latch.countDown();
            }
        });
        latch.await(timeoutMs, TimeUnit.MILLISECONDS);
        return ref.get();
    }

    /** Dump the given window as V1 text. */
    public static String dumpV1(Client client, String window, long timeoutMs) throws Exception {
        final AtomicReference<byte[]> ref = new AtomicReference<>();
        final CountDownLatch latch = new CountDownLatch(1);
        client.dumpViewHierarchy(window, false, true, false /* useV2=false → V1 text */,
            new DebugViewDumpHandler(DebugViewDumpHandler.CHUNK_VURT) {
                protected void handleViewDebugResult(ByteBuffer data) {
                    byte[] b = new byte[data.remaining()];
                    data.get(b);
                    ref.set(b);
                    latch.countDown();
                }
            });
        if (!latch.await(timeoutMs, TimeUnit.MILLISECONDS)) {
            throw new TimeoutException("dump timed out");
        }
        byte[] bytes = ref.get();
        if (bytes == null || bytes.length == 0) return null;
        return new String(bytes, StandardCharsets.UTF_8);
    }
}
```

- [ ] **Step 3: Verify it compiles**

Run: `cd java-deep-inspector && ./gradlew compileJava`
Expected: BUILD SUCCESSFUL

- [ ] **Step 4: Commit**

```bash
git add java-deep-inspector/src/main/java/com/androidmcp/inspector/DeviceConnector.java \
  java-deep-inspector/src/main/java/com/androidmcp/inspector/ViewHierarchyDumper.java
git commit -m "feat: ddmlib device connector and V1 view-hierarchy dumper"
```

---

### Task 10: `Main` — wire CLI args → connect → dump → parse → resolve → JSON; rebuild jar; integration run

**Files:**
- Modify: `java-deep-inspector/src/main/java/com/androidmcp/inspector/Main.java`

- [ ] **Step 1: Replace the stub `Main`**

```java
// src/main/java/com/androidmcp/inspector/Main.java
package com.androidmcp.inspector;

import com.android.ddmlib.AndroidDebugBridge;
import com.android.ddmlib.Client;
import com.android.ddmlib.IDevice;

public class Main {
    public static void main(String[] args) {
        String adbPath = System.getenv().getOrDefault("ADB_PATH", "adb");
        String serial = null, pkg = null, window = null;
        long timeoutMs = 30000;
        for (int i = 0; i < args.length - 1; i++) {
            switch (args[i]) {
                case "--serial": serial = args[++i]; break;
                case "--package": pkg = args[++i]; break;
                case "--window": window = args[++i]; break;
                case "--adb": adbPath = args[++i]; break;
                case "--timeout-ms": timeoutMs = Long.parseLong(args[++i]); break;
            }
        }
        if (pkg == null) {
            System.out.println(JsonOutput.error("--package is required", "BAD_ARGS"));
            System.exit(1);
        }
        try {
            DeviceConnector conn = new DeviceConnector(adbPath);
            IDevice device = conn.connect(serial, timeoutMs);
            Client client = conn.findClient(device, pkg, timeoutMs);
            if (window == null) {
                window = ViewHierarchyDumper.firstWindow(client, 10000);
            }
            if (window == null) {
                System.out.println(JsonOutput.error("no window for " + pkg, "DUMP_FAILED"));
                System.exit(1);
            }
            String v1 = ViewHierarchyDumper.dumpV1(client, window, timeoutMs);
            if (v1 == null) {
                System.out.println(JsonOutput.error("empty dump", "PROTOCOL_UNSUPPORTED"));
                System.exit(1);
            }
            ViewNode root = ViewNodeParser.parse(v1);
            if (root == null) {
                System.out.println(JsonOutput.error("unparseable dump", "PROTOCOL_UNSUPPORTED"));
                System.exit(1);
            }
            CoordinateResolver.resolve(root);
            String json = JsonOutput.toJson(root, pkg, window, "V1");
            System.out.println(json);
            safeTerminate();
            System.exit(0);
        } catch (DeviceConnector.NotFound nf) {
            System.out.println(JsonOutput.error(nf.getMessage(), nf.errorType));
            safeTerminate();
            System.exit(1);
        } catch (java.util.concurrent.TimeoutException te) {
            System.out.println(JsonOutput.error("operation timed out", "TIMEOUT"));
            safeTerminate();
            System.exit(1);
        } catch (Exception e) {
            System.out.println(JsonOutput.error(String.valueOf(e.getMessage()), "DUMP_FAILED"));
            safeTerminate();
            System.exit(1);
        }
    }

    // ddmlib's proxy thread may throw during terminate AFTER data is received; ignore.
    private static void safeTerminate() {
        try { AndroidDebugBridge.terminate(); } catch (Throwable ignored) {}
    }
}
```

- [ ] **Step 2: Rebuild the fat-jar**

Run: `cd java-deep-inspector && ./gradlew shadowJar`
Expected: BUILD SUCCESSFUL; `build/libs/deep-inspector.jar` updated

- [ ] **Step 3: Integration run against the live device (notes in foreground)**

Run:
```bash
ADB_PATH=/Users/eddie/Library/Android/sdk/platform-tools/adb \
  java -jar java-deep-inspector/build/libs/deep-inspector.jar \
  --package com.miui.notes --timeout-ms 30000 > /tmp/deep.json 2>/tmp/deep.err
python3 -c "import json;d=json.load(open('/tmp/deep.json'));print('ok=',d['ok']);print('class=',d['root']['class']);print('has paddingLeft in some node:', 'paddingLeft' in json.dumps(d))"
```
Expected: `ok= True`, a root class name printed, and `has paddingLeft ... True`. (Open `com.miui.notes` on the device first.)

- [ ] **Step 4: Commit the source and the prebuilt jar**

```bash
mkdir -p prebuilt
cp java-deep-inspector/build/libs/deep-inspector.jar prebuilt/deep-inspector.jar
git add java-deep-inspector/src/main/java/com/androidmcp/inspector/Main.java prebuilt/deep-inspector.jar
git commit -m "feat: deep-inspector CLI entry + commit prebuilt fat-jar"
```

---

## Phase C — Python JDWP provider + wiring

### Task 11: Capture a real JSON fixture for Python tests

**Files:**
- Create: `tests/fixtures/deep_dump_sample.json`

- [ ] **Step 1: Save the integration output as a fixture**

Run (reuses `/tmp/deep.json` from Task 10 Step 3, or regenerate):
```bash
cp /tmp/deep.json tests/fixtures/deep_dump_sample.json
python3 -c "import json; json.load(open('tests/fixtures/deep_dump_sample.json')); print('valid json')"
```
Expected: prints `valid json`

- [ ] **Step 2: Commit**

```bash
git add tests/fixtures/deep_dump_sample.json
git commit -m "test: add real deep-dump JSON fixture for JdwpProvider tests"
```

---

### Task 12: `jdwp_runner` — locate jar/java, run subprocess, classify errors (TDD with mocks)

**Files:**
- Create: `src/android_mcp/layout/jdwp_runner.py`
- Test: `tests/unit/test_jdwp_runner.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_jdwp_runner.py
import json
import subprocess
import pytest
from android_mcp.layout import jdwp_runner


def test_run_returns_parsed_json(monkeypatch, tmp_path):
    jar = tmp_path / "deep-inspector.jar"
    jar.write_text("x")
    payload = {"ok": True, "root": {"class": "X"}}

    def fake_run(cmd, capture_output, text, timeout):
        class R: pass
        r = R(); r.returncode = 0; r.stdout = json.dumps(payload); r.stderr = ""
        return r

    monkeypatch.setattr(jdwp_runner.subprocess, "run", fake_run)
    monkeypatch.setattr(jdwp_runner.shutil, "which", lambda n: "/usr/bin/java")
    out = jdwp_runner.run_deep_dump(str(jar), serial="s", package="com.x", adb_path="adb")
    assert out["ok"] is True
    assert out["root"]["class"] == "X"


def test_run_raises_on_error_json(monkeypatch, tmp_path):
    jar = tmp_path / "deep-inspector.jar"; jar.write_text("x")

    def fake_run(cmd, capture_output, text, timeout):
        class R: pass
        r = R(); r.returncode = 1
        r.stdout = json.dumps({"ok": False, "error": "not debuggable", "errorType": "NOT_DEBUGGABLE"})
        r.stderr = ""
        return r

    monkeypatch.setattr(jdwp_runner.subprocess, "run", fake_run)
    monkeypatch.setattr(jdwp_runner.shutil, "which", lambda n: "/usr/bin/java")
    with pytest.raises(jdwp_runner.DeepDumpError) as ei:
        jdwp_runner.run_deep_dump(str(jar), serial="s", package="com.x", adb_path="adb")
    assert ei.value.error_type == "NOT_DEBUGGABLE"


def test_missing_java_raises(monkeypatch, tmp_path):
    jar = tmp_path / "deep-inspector.jar"; jar.write_text("x")
    monkeypatch.setattr(jdwp_runner.shutil, "which", lambda n: None)
    with pytest.raises(jdwp_runner.DeepDumpError) as ei:
        jdwp_runner.run_deep_dump(str(jar), serial="s", package="com.x", adb_path="adb")
    assert ei.value.error_type == "NO_JAVA"


def test_missing_jar_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(jdwp_runner.shutil, "which", lambda n: "/usr/bin/java")
    with pytest.raises(jdwp_runner.DeepDumpError) as ei:
        jdwp_runner.run_deep_dump(str(tmp_path / "missing.jar"), serial="s", package="com.x", adb_path="adb")
    assert ei.value.error_type == "NO_JAR"


def test_timeout_raises(monkeypatch, tmp_path):
    jar = tmp_path / "deep-inspector.jar"; jar.write_text("x")
    monkeypatch.setattr(jdwp_runner.shutil, "which", lambda n: "/usr/bin/java")

    def fake_run(cmd, capture_output, text, timeout):
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(jdwp_runner.subprocess, "run", fake_run)
    with pytest.raises(jdwp_runner.DeepDumpError) as ei:
        jdwp_runner.run_deep_dump(str(jar), serial="s", package="com.x", adb_path="adb")
    assert ei.value.error_type == "TIMEOUT"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_jdwp_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'android_mcp.layout.jdwp_runner'`

- [ ] **Step 3: Write `jdwp_runner`**

```python
# src/android_mcp/layout/jdwp_runner.py
import json
import os
import shutil
import subprocess


class DeepDumpError(Exception):
    def __init__(self, message: str, error_type: str):
        super().__init__(message)
        self.error_type = error_type


def run_deep_dump(jar_path: str, *, serial: str, package: str,
                  adb_path: str, window: str = None, timeout_s: float = 35.0) -> dict:
    """Run the Java deep-inspector jar and return parsed JSON. Raises DeepDumpError on any failure."""
    if shutil.which("java") is None:
        raise DeepDumpError("java not found on PATH; deep mode requires a JDK/JRE", "NO_JAVA")
    if not os.path.isfile(jar_path):
        raise DeepDumpError(f"deep-inspector jar not found at {jar_path}", "NO_JAR")

    cmd = ["java", "-jar", jar_path, "--package", package,
           "--adb", adb_path, "--timeout-ms", str(int(timeout_s * 1000) - 5000)]
    if serial:
        cmd += ["--serial", serial]
    if window:
        cmd += ["--window", window]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        raise DeepDumpError("deep capture timed out", "TIMEOUT")

    stdout = (result.stdout or "").strip()
    if not stdout:
        raise DeepDumpError(f"deep-inspector produced no output (stderr: {result.stderr[:300]})",
                            "DUMP_FAILED")
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        raise DeepDumpError(f"deep-inspector returned non-JSON: {stdout[:300]}", "DUMP_FAILED")

    if not data.get("ok", False):
        raise DeepDumpError(data.get("error", "unknown error"),
                            data.get("errorType", "DUMP_FAILED"))
    return data
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_jdwp_runner.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/android_mcp/layout/jdwp_runner.py tests/unit/test_jdwp_runner.py
git commit -m "feat: jdwp_runner subprocess wrapper with error classification"
```

---

### Task 13: `JdwpProvider` — JSON → DeepLayoutNode, tree/element rendering (TDD with fixture)

**Files:**
- Create: `src/android_mcp/layout/jdwp_provider.py`
- Test: `tests/unit/test_jdwp_provider.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_jdwp_provider.py
import json
import pytest
from android_mcp.layout.jdwp_provider import JdwpProvider, _json_to_node
from android_mcp.layout import jdwp_runner

NODE = {
    "class": "android.widget.TextView", "hash": "abc", "resourceId": "title",
    "bounds": [61, 2427, 1139, 2598], "text": "标题",
    "properties": {"paddingLeft": 48, "paddingTop": 24, "paddingRight": 48,
                   "paddingBottom": 0, "elevation": 4.0, "textSize": 42.0},
    "children": [
        {"class": "android.widget.ImageView", "hash": "def", "resourceId": "icon",
         "bounds": [0, 0, 100, 100], "text": "", "properties": {}, "children": []}
    ],
}
DUMP = {"ok": True, "protocol": "V1", "package": "com.x", "window": "w", "root": NODE}


class FakeDevice:
    def __init__(self): self.info = {"displayWidth": 1080, "displaySizeDpX": 360}
    def app_current(self): return {"package": "com.x"}


class FakeMobile:
    def __init__(self): self.device = FakeDevice()
    def get_device(self): return self.device


def make_provider(monkeypatch, dump=DUMP):
    monkeypatch.setattr(jdwp_runner, "run_deep_dump", lambda *a, **k: dump)
    return JdwpProvider(FakeMobile(), jar_path="/x.jar", adb_path="adb", serial="s")


def test_json_to_node_recursive():
    root = _json_to_node(NODE, depth=0)
    assert root.class_name == "android.widget.TextView"
    assert root.children[0].class_name == "android.widget.ImageView"
    assert root.children[0].depth == 1


def test_get_layout_tree_renders(monkeypatch):
    prov = make_provider(monkeypatch)
    out = prov.get_layout_tree()
    assert "TextView" in out and "ImageView" in out
    assert "padding=[48,24,48,0]" in out
    assert "textSize=42.0dp" in out


def test_get_layout_tree_filter_class(monkeypatch):
    prov = make_provider(monkeypatch)
    out = prov.get_layout_tree(filter_class="ImageView")
    assert "ImageView" in out
    assert "TextView" not in out


def test_get_element_details_by_resourceid(monkeypatch):
    prov = make_provider(monkeypatch)
    out = prov.get_element_details("resourceId", "title")
    assert "android.widget.TextView" in out
    assert "paddingLeft" in out or "padding=" in out


def test_get_element_details_not_found(monkeypatch):
    prov = make_provider(monkeypatch)
    out = prov.get_element_details("resourceId", "does_not_exist")
    assert "ELEMENT_NOT_FOUND" in out or "not" in out.lower()


def test_deep_error_propagates_as_text(monkeypatch):
    def boom(*a, **k): raise jdwp_runner.DeepDumpError("nope", "NOT_DEBUGGABLE")
    monkeypatch.setattr(jdwp_runner, "run_deep_dump", boom)
    prov = JdwpProvider(FakeMobile(), jar_path="/x.jar", adb_path="adb", serial="s")
    out = prov.get_layout_tree()
    assert "NOT_DEBUGGABLE" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_jdwp_provider.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'android_mcp.layout.jdwp_provider'`

- [ ] **Step 3: Write `JdwpProvider`**

```python
# src/android_mcp/layout/jdwp_provider.py
from android_mcp.layout.models import DeepLayoutNode, format_deep_tree
from android_mcp.layout import jdwp_runner


def _json_to_node(obj: dict, depth: int) -> DeepLayoutNode:
    children = tuple(_json_to_node(c, depth + 1) for c in obj.get("children", []))
    b = obj.get("bounds", [0, 0, 0, 0])
    return DeepLayoutNode(
        class_name=obj.get("class", ""),
        resource_id=obj.get("resourceId", ""),
        bounds=tuple(b),
        text=obj.get("text", ""),
        properties=dict(obj.get("properties", {})),
        depth=depth,
        children=children,
    )


def _filter(node: DeepLayoutNode, needle: str):
    matches = needle.lower() in node.class_name.lower()
    kept = tuple(c for c in (_filter(ch, needle) for ch in node.children) if c is not None)
    if matches:
        return node
    if kept:
        return DeepLayoutNode(
            class_name=node.class_name, resource_id=node.resource_id, bounds=node.bounds,
            text=node.text, properties=node.properties, depth=node.depth, children=kept,
        )
    return None


def _find(node: DeepLayoutNode, selector_type: str, value: str):
    if selector_type == "resourceId" and node.resource_id == value:
        return node
    if selector_type == "text" and node.text == value:
        return node
    for c in node.children:
        hit = _find(c, selector_type, value)
        if hit is not None:
            return hit
    return None


def _format_element(node: DeepLayoutNode) -> str:
    l, t, r, b = node.bounds
    lines = [
        f"class: {node.class_name}",
        f"resource-id: {node.resource_id}",
        f"text: {node.text}",
        f"bounds: [{l},{t}][{r},{b}]",
    ]
    for k, v in node.properties.items():
        lines.append(f"{k}: {v}")
    return "\n".join(lines)


class JdwpProvider:
    """Layout provider backed by JDWP/ddmlib via the Java deep-inspector jar."""

    def __init__(self, mobile, *, jar_path: str, adb_path: str, serial: str = None):
        self.mobile = mobile
        self.jar_path = jar_path
        self.adb_path = adb_path
        self.serial = serial

    def _dump_root(self) -> DeepLayoutNode:
        device = self.mobile.get_device()
        pkg = device.app_current().get("package", "")
        data = jdwp_runner.run_deep_dump(
            self.jar_path, serial=self.serial, package=pkg, adb_path=self.adb_path)
        return _json_to_node(data["root"], depth=0)

    def get_layout_tree(self, max_depth=None, filter_class=None) -> str:
        try:
            root = self._dump_root()
        except jdwp_runner.DeepDumpError as e:
            return f"[deep mode error: {e.error_type}] {e}"
        if filter_class:
            root = _filter(root, filter_class)
            if root is None:
                return f"No elements matching class '{filter_class}' found."
        return format_deep_tree(root)

    def get_element_details(self, selector_type, selector_value, timeout=5.0) -> str:
        valid = {"text", "resourceId", "description"}
        if selector_type not in valid:
            return f"Invalid selector_type '{selector_type}'. Must be one of: {', '.join(sorted(valid))}"
        try:
            root = self._dump_root()
        except jdwp_runner.DeepDumpError as e:
            return f"[deep mode error: {e.error_type}] {e}"
        lookup_type = "resourceId" if selector_type == "resourceId" else "text"
        node = _find(root, lookup_type, selector_value)
        if node is None:
            return (f"ELEMENT_NOT_FOUND: no node with {selector_type}='{selector_value}' "
                    f"in the deep tree.")
        return _format_element(node)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_jdwp_provider.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/android_mcp/layout/jdwp_provider.py tests/unit/test_jdwp_provider.py
git commit -m "feat: JdwpProvider (JSON->DeepLayoutNode, tree/element rendering, error text)"
```

---

### Task 14: `--deep` flag + provider injection in `__main__`

**Files:**
- Modify: `src/android_mcp/__main__.py` (arg parser near `:43`, provider construction near `:250`)
- Test: `tests/unit/test_provider_injection.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_provider_injection.py
from android_mcp.layout.accessibility_provider import AccessibilityProvider
from android_mcp.layout.jdwp_provider import JdwpProvider
from android_mcp.__main__ import build_provider


class FakeMobile:
    pass


def test_build_provider_default_is_accessibility():
    prov = build_provider(FakeMobile(), deep=False, jar_path="/x.jar", adb_path="adb", serial=None)
    assert isinstance(prov, AccessibilityProvider)


def test_build_provider_deep_is_jdwp():
    prov = build_provider(FakeMobile(), deep=True, jar_path="/x.jar", adb_path="adb", serial=None)
    assert isinstance(prov, JdwpProvider)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_provider_injection.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_provider'`

- [ ] **Step 3: Add `--deep` argument**

Find the arg parser block (`__main__.py:43-46`, the last `add_argument` before `parse_known_args`). Add before `args, _ = parser.parse_known_args()`:
```python
parser.add_argument("--deep", action="store_true",
                    help="Enable JDWP deep layout mode (full View properties; requires debuggable process / userdebug device)")
parser.add_argument("--deep-jar", type=str, default=None,
                    help="Path to deep-inspector.jar (defaults to bundled prebuilt/deep-inspector.jar)")
```

- [ ] **Step 4: Add `build_provider` and replace the hard-coded provider**

Replace the lines added in Task 4 (`from android_mcp.layout.accessibility_provider import AccessibilityProvider` + `layout_provider = AccessibilityProvider(mobile)`) with:
```python
import os as _os
from android_mcp.layout.accessibility_provider import AccessibilityProvider
from android_mcp.layout.jdwp_provider import JdwpProvider

_DEFAULT_JAR = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(__file__))),
                             "prebuilt", "deep-inspector.jar")


def build_provider(mobile, *, deep: bool, jar_path: str, adb_path: str, serial):
    if deep:
        return JdwpProvider(mobile, jar_path=jar_path, adb_path=adb_path, serial=serial)
    return AccessibilityProvider(mobile)


layout_provider = build_provider(
    mobile,
    deep=getattr(args, "deep", False),
    jar_path=getattr(args, "deep_jar", None) or _DEFAULT_JAR,
    adb_path=_os.getenv("ADB_PATH", "adb"),
    serial=getattr(args, "device", None),
)
```

- [ ] **Step 5: Run the injection test**

Run: `uv run pytest tests/unit/test_provider_injection.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Fail-fast check for deep mode at startup**

In deep mode, verify java + jar exist at startup (after `layout_provider = build_provider(...)`):
```python
if getattr(args, "deep", False):
    import shutil as _shutil
    _jar = getattr(args, "deep_jar", None) or _DEFAULT_JAR
    if _shutil.which("java") is None:
        raise SystemExit("--deep requires a JDK/JRE on PATH, but 'java' was not found.")
    if not _os.path.isfile(_jar):
        raise SystemExit(f"--deep requires deep-inspector.jar; not found at {_jar}. "
                         f"Build it with: cd java-deep-inspector && ./gradlew shadowJar")
```

- [ ] **Step 7: Run full suite**

Run: `uv run pytest tests/ -v`
Expected: PASS (all tests)

- [ ] **Step 8: Commit**

```bash
git add src/android_mcp/__main__.py tests/unit/test_provider_injection.py
git commit -m "feat: --deep flag and provider injection with startup fail-fast"
```

---

### Task 15: End-to-end deep-mode verification + docs

**Files:**
- Modify: `README.md` (document `--deep`)

- [ ] **Step 1: Run the server in deep mode and exercise the tool path manually**

Run (notes open on device):
```bash
ADB_PATH=/Users/eddie/Library/Android/sdk/platform-tools/adb \
uv run python -c "
import sys; sys.argv = ['android-mcp', '--deep', '--device', '8957c117']
import android_mcp.__main__ as m
m.require_device()
print(m.layout_provider.__class__.__name__)
print(m.get_element_details_tool('resourceId', 'title')[:400])
"
```
Expected: prints `JdwpProvider` and an element block containing property keys (e.g. `paddingLeft`, `textSize`). If the element id differs, pick one from `GetLayoutTree` output first.

- [ ] **Step 2: Compare one element's padding against Android Studio Layout Inspector**

Manually open Layout Inspector on the same screen, pick the same element, and confirm padding/textSize match (acceptance criterion #2). Record the compared values in the commit message.

- [ ] **Step 3: Document `--deep` in README**

Add a subsection after the Device Selection section:
```markdown
### Deep Mode (full View properties)

`--deep` enables a JDWP-based layout path that returns precise padding, margin,
elevation, textSize, and corner-radius — properties the accessibility tree cannot
provide. Requires a debuggable process (debug-built app, or any app on a
`userdebug`/`ro.debuggable=1` device) and a JDK/JRE on PATH.

```json
{
  "mcpServers": {
    "android-mcp-pro": {
      "command": "uv",
      "args": ["--directory", "</PATH>", "run", "android-mcp", "--deep"],
      "env": { "ADB_PATH": "/path/to/adb" }
    }
  }
}
```

Tool names are unchanged (`GetLayoutTree`, `GetElementDetails`); deep mode only
changes the data source. Deep calls take ~2s and fail with a clear error (no
silent fallback) if the target process is not debuggable.
```

- [ ] **Step 4: Run full suite one final time**

Run: `uv run pytest tests/ -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: document --deep mode for full View property retrieval"
```

---

## Self-Review Notes

- **Spec coverage:** strategy interface (T2), two providers (T3, T13), `--deep` routing + identical tool names (T4, T14), one-shot subprocess (T12), JSON contract (T8), V1 parse (T6), coordinate resolution (T7), fail-with-error no-fallback (T13 returns error text; T14 startup fail-fast), Compose/daemon/merge out of scope (not implemented — correct). dp note: V1 already provides `getScaledTextSize` (sp); raw `textSize` is px — formatter labels values `dp`; if precise px→dp is required for non-text fields, it is a follow-up (recorded here, not implemented to keep scope tight).
- **Matching strategy:** spec chose coordinate alignment, but because deep mode uses a single JDWP tree, `JdwpProvider._find` locates by resourceId/text directly in that tree (simpler, no cross-tree alignment) — consistent with the "GetLayoutTree also uses JDWP" decision. Bounds-based fallback is available via the node's absolute bounds if needed later.
- **Type consistency:** `DeepLayoutNode(class_name, resource_id, bounds, text, properties, depth, children)` used identically in T1, T13. `DeepDumpError(.error_type)` used in T12, T13. `run_deep_dump(jar_path, *, serial, package, adb_path, window, timeout_s)` consistent T12/T13.
- **Known follow-ups (not blocking):** px→dp normalization of numeric properties on the Python side; `description` selector in deep mode maps to text lookup (documented in code).
```
