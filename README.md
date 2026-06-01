<div align="center">

  <h1>🤖 Android MCP Pro</h1>

  <a href="https://github.com/edditz/android-mcp-pro/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </a>
  <img src="https://img.shields.io/badge/python-3.13-blue" alt="Python">
  <img src="https://img.shields.io/badge/platform-Android%2010+-blue" alt="Platform">

</div>

<br>

**Android MCP Pro** is a fork of [Android-MCP](https://github.com/CursorTouch/Android-MCP), extended with enhanced layout inspection and debugging capabilities.

## Acknowledgments

This project is based on the work of [CursorTouch/Android-MCP](https://github.com/CursorTouch/Android-MCP) by [Jeomon George](https://github.com/jeomon) and [Muhammad Yaseen](https://github.com/mhmdyaseen), licensed under the [MIT License](LICENSE).

## What's New in Pro

In addition to the original Android-MCP capabilities, this version adds:

- **GetLayoutTree** - Full view hierarchy tree including containers (FrameLayout, LinearLayout, etc.) with `max_depth` and `filter_class` support
- **GetElementDetails** - Detailed properties of a single element (bounds, text, state flags, size in dp)
- **GetSpacing** - Calculate spacing and alignment between two elements, with automatic containment detection
- **Deep Mode** - Opt-in JDWP-based layout path (`--deep`) that returns precise padding, margin, elevation, textSize, and corner-radius from the real View tree (see [Deep Mode](#deep-mode-full-view-properties))
- **Debug Mode** - Log all tool calls to JSON files for inspection (`--debug` flag or `ANDROID_MCP_DEBUG=1`)

## Features (from original Android-MCP)

- **Native Android Integration** - Interact with UI elements via ADB and the Android Accessibility API
- **Bring Your Own LLM/VLM** - Works with any language model
- **Rich Toolset for Mobile Automation** - Pre-built tools for gestures, keystrokes, capture, device state
- **Real-Time Interaction** - Typical latency between actions ranges 2-4s

## Installation

### Prerequisites

- Python 3.13
- ADB (Android Debug Bridge)
- Android 10+ device or emulator

### Getting Started

1. **Clone and Install**
   ```shell
   git clone <your-repo-url>
   cd android-mcp-pro
   uv sync
   ```

2. **Configure Claude Desktop or Claude Code**

   Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`):
   ```json
   {
     "mcpServers": {
       "android-mcp-pro": {
         "command": "uv",
         "args": [
           "--directory",
           "</PATH/TO/android-mcp-pro>",
           "run",
           "android-mcp"
         ]
       }
     }
   }
   ```

   Claude Code:
   ```shell
   claude mcp add android-mcp-pro uv --directory </PATH/TO/android-mcp-pro> run android-mcp
   ```

3. **Restart Claude**

### Device Selection

- `--device RFCN2013V8D`: connect to a specific USB serial
- `--device 192.168.1.3:5555`: connect to a specific WiFi ADB target
- `--wifi 192.168.1.3`: use WiFi and auto-append port `5555`
- `--usb`: auto-detect the first USB-connected device

Environment variables:
- `ANDROID_MCP_DEVICE`: explicit serial or `host:port`
- `ANDROID_MCP_CONNECTION`: `auto`, `usb`, or `wifi`
- `ANDROID_MCP_HOST`: WiFi host
- `SCREENSHOT_QUANTIZED`: set to `true` to reduce screenshot tokens

### Deep Mode (full View properties)

`--deep` enables a JDWP-based layout path that returns precise padding, margin,
elevation, textSize, and corner-radius — properties the accessibility tree cannot
provide. It requires a debuggable process (a debug-built app, or any app on a
`userdebug` / `ro.debuggable=1` device) and a JDK/JRE on PATH.

```json
{
  "mcpServers": {
    "android-mcp-pro": {
      "command": "uv",
      "args": ["--directory", "</PATH/TO/android-mcp-pro>", "run", "android-mcp", "--deep"],
      "env": { "ADB_PATH": "/path/to/adb" }
    }
  }
}
```

The tool names are unchanged (`GetLayoutTree`, `GetElementDetails`); deep mode only
changes the data source. Deep calls take ~2s and, if the target process is not
debuggable, return a clear error rather than silently falling back. Deep mode is
backed by a prebuilt Java helper at `prebuilt/deep-inspector.jar` (rebuild with
`cd java-deep-inspector && ./gradlew shadowJar`).

## Available Tools

### Original Tools

| Tool | Description |
|------|-------------|
| `ListDevices` | List ADB devices |
| `ConnectDevice` | Connect by serial |
| `Device` | Manage devices (list/connect/disconnect) |
| `Click` | Tap at coordinates |
| `ClickBySelector` | Tap by text/resourceId/className/description |
| `Snapshot` | Get device state (element list + optional screenshot) |
| `LongClick` | Long press at coordinates |
| `Swipe` | Swipe between coordinates |
| `Type` | Type text at coordinates |
| `Drag` | Drag and drop |
| `Press` | Press hardware buttons |
| `Notification` | Open notification bar |
| `Wait` | Sleep for duration |
| `WaitForElement` | Wait for element to appear |

### Pro Tools

| Tool | Description |
|------|-------------|
| `GetLayoutTree` | Full view hierarchy tree with `max_depth` and `filter_class`; output starts with a `[window]` header naming the captured package/activity (plus JDWP window in deep mode) |
| `GetElementDetails` | Detailed element properties (bounds, text, state, size in dp) |
| `GetSpacing` | Spacing and alignment between two elements |

## Debug Mode

Enable debug logging to inspect all tool calls:

```json
{
  "mcpServers": {
    "android-mcp-pro": {
      "command": "uv",
      "args": ["--directory", "</PATH>", "run", "android-mcp", "--debug"],
      "env": {
        "ANDROID_MCP_DEBUG_LOG_DIR": "/path/to/debug_logs"
      }
    }
  }
}
```

Each tool call generates a JSON file in the debug log directory.

## Caution

This tool can execute arbitrary UI actions on your mobile device. Use it in controlled environments when running untrusted prompts or agents.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

The original code is Copyright (c) 2025 JEOMON GEORGE.
