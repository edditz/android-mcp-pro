from argparse import ArgumentParser
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from textwrap import dedent
from typing import Literal, Optional
import asyncio
import functools
import json
import os

from fastmcp import FastMCP
from fastmcp.utilities.types import Image
from mcp.types import ToolAnnotations

from android_mcp.mobile.service import Mobile
from android_mcp.tree.service import Tree

parser = ArgumentParser()
parser.add_argument("--device", type=str, help="ADB device serial or host:port")
parser.add_argument(
    "--connection",
    "--transport",
    dest="connection",
    choices=("auto", "usb", "wifi"),
    help="Preferred device connection type",
)
parser.add_argument(
    "--wifi",
    nargs="?",
    const="",
    metavar="HOST",
    help="Use WiFi ADB. Accepts HOST or HOST:PORT and defaults to port 5555.",
)
parser.add_argument(
    "--usb",
    nargs="?",
    const="",
    metavar="SERIAL",
    help="Use USB ADB. Optionally provide a specific device serial.",
)
parser.add_argument(
    "--debug",
    action="store_true",
    help="Enable debug mode to log all tool calls to JSON files.",
)
args, _ = parser.parse_known_args()

DEBUG_MODE = args.debug or os.getenv("ANDROID_MCP_DEBUG", "").lower() in ("1", "true", "yes")
DEBUG_LOG_DIR = os.getenv("ANDROID_MCP_DEBUG_LOG_DIR", "debug_logs")


def _log_tool_call(tool_name: str, params: dict, result) -> None:
    if not DEBUG_MODE:
        return
    os.makedirs(DEBUG_LOG_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{tool_name}_{timestamp}.json"
    filepath = os.path.join(DEBUG_LOG_DIR, filename)

    def _serializable(value):
        if isinstance(value, str):
            return value.split("\n")
        try:
            json.dumps(value)
            return value
        except TypeError:
            return f"<{type(value).__name__} (not JSON serializable)>"

    if isinstance(result, str):
        formatted_result = result.split("\n")
    elif isinstance(result, list):
        formatted_result = [_serializable(r) for r in result]
    else:
        formatted_result = _serializable(result)

    log_data = {
        "tool": tool_name,
        "timestamp": datetime.now().isoformat(),
        "params": params,
        "result": formatted_result,
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)


def debug_tool(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        _log_tool_call(func.__name__, kwargs, result)
        return result
    return wrapper


instructions = dedent(
    """
    Android MCP server provides tools to interact directly with the Android device,
    thus enabling to operate the mobile device like an actual USER.
    """
)


@dataclass(frozen=True)
class DevicePreference:
    connection: str = "auto"
    serial: Optional[str] = None
    source: str = "auto-detect"


def _clean_env(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _normalize_connection(value: Optional[str]) -> str:
    if not value:
        return "auto"
    normalized = value.strip().lower()
    if normalized in {"usb", "wifi", "auto"}:
        return normalized
    raise RuntimeError(
        "Invalid connection type. Use --connection auto|usb|wifi or ANDROID_MCP_CONNECTION."
    )


def _configured_preference() -> DevicePreference:
    env_device = _clean_env("ANDROID_MCP_DEVICE")
    env_connection = _normalize_connection(_clean_env("ANDROID_MCP_CONNECTION"))
    env_host = _clean_env("ANDROID_MCP_HOST")

    if args.wifi is not None:
        serial = Mobile.normalize_wifi_serial(args.wifi or env_host)
        return DevicePreference(connection="wifi", serial=serial, source="--wifi")

    if args.usb is not None:
        serial = args.usb.strip() if args.usb else None
        return DevicePreference(connection="usb", serial=serial or None, source="--usb")

    if args.device:
        return DevicePreference(
            connection=_normalize_connection(args.connection) if args.connection else "auto",
            serial=args.device.strip(),
            source="--device",
        )

    if env_device:
        return DevicePreference(connection=env_connection, serial=env_device, source="ANDROID_MCP_DEVICE")

    if env_connection == "wifi" or env_host:
        serial = Mobile.normalize_wifi_serial(env_host)
        return DevicePreference(connection="wifi", serial=serial, source="ANDROID_MCP_CONNECTION/ANDROID_MCP_HOST")

    return DevicePreference(
        connection=_normalize_connection(args.connection) if args.connection else env_connection,
        serial=None,
        source="auto-detect",
    )


def _format_available_devices() -> str:
    devices = Mobile.list_devices()
    online = [(serial, state) for serial, state in devices if state == "device"]
    if not online:
        return ""
    formatted = ", ".join(serial for serial, _ in online)
    return f" Available devices: {formatted}."


def _pick_auto_device(connection: str) -> Optional[str]:
    devices = Mobile.list_devices()
    online = [serial for serial, state in devices if state == "device"]
    if not online:
        return None

    if connection == "wifi":
        for serial in online:
            if ":" in serial:
                return serial
        return None

    if connection == "usb":
        for serial in online:
            if ":" not in serial:
                return serial
        return None

    return online[0]


def _resolve_target() -> DevicePreference:
    preference = _configured_preference()

    if preference.serial:
        serial = preference.serial
        if preference.connection == "wifi":
            serial = Mobile.normalize_wifi_serial(serial)
        return DevicePreference(
            connection=preference.connection,
            serial=serial,
            source=preference.source,
        )

    serial = _pick_auto_device(preference.connection)
    if serial:
        return DevicePreference(
            connection=preference.connection,
            serial=serial,
            source="auto-detect",
        )

    return preference


def _not_configured_message() -> str:
    return (
        "No device configured. Use --device flag, --wifi, --usb, or ANDROID_MCP_DEVICE."
        + _format_available_devices()
    )


def _connect_preferred_device() -> None:
    if mobile.is_connected:
        return

    target = _resolve_target()
    if not target.serial:
        raise RuntimeError(_not_configured_message())

    serial = target.serial
    if target.connection == "wifi" or ":" in serial:
        serial = Mobile.normalize_wifi_serial(serial)
        Mobile.adb_connect(serial)

    mobile.connect(serial)


@asynccontextmanager
async def lifespan(app: FastMCP):
    """Runs initialization code before the server starts and cleanup code after it shuts down."""
    await asyncio.sleep(1)
    yield


mcp = FastMCP(name="Android-MCP", instructions=instructions)
mobile = Mobile()


def require_device():
    _connect_preferred_device()
    return mobile.get_device()

def _filter_layout_tree(node, filter_class):
    """Filter layout tree to only include nodes matching the given class name."""
    from android_mcp.tree.views import LayoutNode

    filtered_children = []
    for child in node.children:
        filtered_child = _filter_layout_tree(child, filter_class)
        if filtered_child is not None:
            filtered_children.append(filtered_child)

    matches = filter_class.lower() in node.class_name.lower()
    if matches or filtered_children:
        return LayoutNode(
            class_name=node.class_name,
            resource_id=node.resource_id,
            bounds=node.bounds,
            text=node.text,
            content_desc=node.content_desc,
            enabled=node.enabled,
            visible=node.visible,
            clickable=node.clickable,
            focused=node.focused,
            checked=node.checked,
            scrollable=node.scrollable,
            depth=node.depth,
            children=tuple(filtered_children),
        )
    return None

def _resolve_resource_id(device, resource_id: str) -> str:
    """Auto-expand short resourceId (e.g. 'btn_login') to full form (e.g. 'com.example.app:id/btn_login') using the current foreground app package."""
    if not resource_id or '/' in resource_id or ':' in resource_id:
        return resource_id
    try:
        pkg = device.app_current().get('package', '')
    except Exception:
        pkg = ''
    if pkg:
        return f'{pkg}:id/{resource_id}'
    return resource_id

@mcp.tool(name='ListDevices',description='List available ADB devices',annotations=ToolAnnotations(title="List Devices",readOnlyHint=True))
@debug_tool
def list_devices_tool():
    devices=Mobile.list_devices()
    if not devices:
        return "No devices found. Ensure a device is connected and ADB is running."
    lines=[f"{serial}\t{state}" for serial,state in devices]
    return "\n".join(lines)

@mcp.tool(name='ConnectDevice',description='Connect to an ADB device by serial number',annotations=ToolAnnotations(title="Connect Device"))
@debug_tool
def connect_device_tool(serial:str):
    target = Mobile.normalize_wifi_serial(serial) if ":" in serial else serial
    if ":" in target:
        Mobile.adb_connect(target)
    mobile.connect(target)
    return f'Connected to {target}'

@mcp.tool(
    name="Device",
    description="Manage ADB devices (list, connect, or disconnect)",
    annotations=ToolAnnotations(title="Device"),
)
@debug_tool
def device_tool(action: Literal["list", "connect", "disconnect"], serial: Optional[str] = None):
    if action == "list":
        devices = Mobile.list_devices()
        if not devices:
            return "No devices found. Ensure a device is connected and ADB is running."
        lines = [f"{device_serial}\t{state}" for device_serial, state in devices]
        return "\n".join(lines)
    if action == "connect":
        target = serial
        if not target:
            resolved = _resolve_target()
            target = resolved.serial
            if not target:
                return _not_configured_message()
            if resolved.connection == "wifi":
                target = Mobile.normalize_wifi_serial(target)
                Mobile.adb_connect(target)
        elif ":" in target:
            target = Mobile.normalize_wifi_serial(target)
            Mobile.adb_connect(target)
        mobile.connect(target)
        return f"Connected to {target}"
    if action == "disconnect":
        mobile.disconnect()
        return "Disconnected from device."
    return f"Unknown action: {action}"


@mcp.tool(
    name="Click",
    description="Click on a specific cordinate",
    annotations=ToolAnnotations(title="Click", destructiveHint=True),
)
@debug_tool
def click_tool(x: int, y: int):
    device = require_device()
    device.click(x, y)
    return f"Clicked on ({x},{y})"


@mcp.tool(name='ClickBySelector',description='Click on an element by selector (text, resourceId, className, description). More reliable than coordinate clicks — handles dynamic layouts and element reflow. At least one selector must be provided.',annotations=ToolAnnotations(title="Click By Selector",destructiveHint=True))
@debug_tool
def click_by_selector_tool(text:str=None,resourceId:str=None,className:str=None,description:str=None,index:int=0,timeout:float=5.0):
    device=require_device()
    kwargs={}
    if text: kwargs['text']=text
    if resourceId: kwargs['resourceId']=_resolve_resource_id(device, resourceId)
    if className: kwargs['className']=className
    if description: kwargs['description']=description
    if not kwargs:
        return 'Error: at least one selector (text, resourceId, className, description) must be provided'
    if index: kwargs['index']=index
    el=device(**kwargs)
    if not el.wait(timeout=timeout):
        return f'Element not found with selectors {kwargs} within {timeout}s'
    el.click()
    return f'Clicked element matching {kwargs}'

@mcp.tool(
    name="Snapshot",
    description="Get the state of the device. Optionally includes visual screenshot when use_vision=True. The use_annotation parameter (default True) can be set to False to get a clean screenshot without bounding boxes.",
    annotations=ToolAnnotations(title="Snapshot", readOnlyHint=True),
)
@debug_tool
def state_tool(use_vision: bool = False, use_annotation: bool = True):
    require_device()
    mobile_state = mobile.get_state(
        use_vision=use_vision, use_annotation=use_annotation, as_bytes=True,
    )
    return [mobile_state.tree_state.to_string()] + (
        [Image(data=mobile_state.screenshot, format="PNG")] if use_vision else []
    )


@mcp.tool(
    name="GetLayoutTree",
    description="Get the full view hierarchy of the device screen as a tree of all UI elements (including containers like FrameLayout, LinearLayout, etc.). Useful for layout debugging and design review. By default (max_depth omitted) the entire hierarchy is returned with no depth limit; pass max_depth to cap traversal depth.",
    annotations=ToolAnnotations(title="Get Layout Tree", readOnlyHint=True),
)
@debug_tool
def get_layout_tree_tool(max_depth: int = None, filter_class: str = None):
    require_device()
    xml_data = mobile.device.dump_hierarchy()
    tree = Tree(mobile)
    layout_root = tree.get_layout_tree(xml_data=xml_data, max_depth=max_depth)

    if layout_root is None:
        return "Failed to parse layout tree."

    if filter_class:
        layout_root = _filter_layout_tree(layout_root, filter_class)
        if layout_root is None:
            return f"No elements matching class '{filter_class}' found."

    return Tree.format_layout_tree(layout_root)


@mcp.tool(
    name="GetElementDetails",
    description="Get detailed properties of a single UI element. Locate by text, resourceId, or description. Returns bounds, text, content-desc, and all state flags.",
    annotations=ToolAnnotations(title="Get Element Details", readOnlyHint=True),
)
@debug_tool
def get_element_details_tool(selector_type: str, selector_value: str, timeout: float = 5.0):
    device = require_device()

    valid_selectors = {"text", "resourceId", "description"}
    if selector_type not in valid_selectors:
        return f"Invalid selector_type '{selector_type}'. Must be one of: {', '.join(sorted(valid_selectors))}"

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
    visible_bounds = info.get("visibleBounds", {})

    density_dpi = device.info.get("displayDensityDpi", 160)
    scale = density_dpi / 160

    width_px = bounds.get("right", 0) - bounds.get("left", 0)
    height_px = bounds.get("bottom", 0) - bounds.get("top", 0)
    width_dp = round(width_px / scale)
    height_dp = round(height_px / scale)

    lines = [
        f"class: {info.get('className', '')}",
        f"resource-id: {info.get('resourceName', '')}",
        f"text: {info.get('text', '')}",
        f"content-desc: {info.get('contentDescription', '')}",
        f"bounds: [{bounds.get('left',0)},{bounds.get('top',0)}][{bounds.get('right',0)},{bounds.get('bottom',0)}]",
        f"visible-bounds: [{visible_bounds.get('left',0)},{visible_bounds.get('top',0)}][{visible_bounds.get('right',0)},{visible_bounds.get('bottom',0)}]",
        f"width: {width_dp}dp ({width_px}px)",
        f"height: {height_dp}dp ({height_px}px)",
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


def _find_element_by_selector(device, selector_type: str, selector_value: str, timeout: float = 5.0):
    valid_selectors = {"text", "resourceId", "description"}
    if selector_type not in valid_selectors:
        return None, f"Invalid selector_type '{selector_type}'. Must be one of: {', '.join(sorted(valid_selectors))}"

    kwargs = {}
    if selector_type == "resourceId":
        kwargs["resourceId"] = _resolve_resource_id(device, selector_value)
    else:
        kwargs[selector_type] = selector_value

    el = device(**kwargs)
    if not el.wait(timeout=timeout):
        return None, f"Element not found with {selector_type}='{selector_value}' within {timeout}s"

    return el, None


@mcp.tool(
    name="GetSpacing",
    description="Calculate spacing and alignment between two UI elements. Returns horizontal/vertical gaps, alignment, and padding if one element contains the other.",
    annotations=ToolAnnotations(title="Get Spacing", readOnlyHint=True),
)
@debug_tool
def get_spacing_tool(
    selector_type_a: str, selector_value_a: str,
    selector_type_b: str, selector_value_b: str,
    timeout: float = 5.0,
):
    device = require_device()

    el_a, err = _find_element_by_selector(device, selector_type_a, selector_value_a, timeout)
    if err:
        return f"Element A: {err}"

    el_b, err = _find_element_by_selector(device, selector_type_b, selector_value_b, timeout)
    if err:
        return f"Element B: {err}"

    bounds_a = el_a.info.get("bounds", {})
    bounds_b = el_b.info.get("bounds", {})

    a_left = bounds_a.get("left", 0)
    a_top = bounds_a.get("top", 0)
    a_right = bounds_a.get("right", 0)
    a_bottom = bounds_a.get("bottom", 0)

    b_left = bounds_b.get("left", 0)
    b_top = bounds_b.get("top", 0)
    b_right = bounds_b.get("right", 0)
    b_bottom = bounds_b.get("bottom", 0)

    density_dpi = device.info.get("displayDensityDpi", 160)
    scale = density_dpi / 160

    def to_dp(px):
        return round(px / scale)

    # Check containment
    b_inside_a = b_left >= a_left and b_right <= a_right and b_top >= a_top and b_bottom <= a_bottom
    a_inside_b = a_left >= b_left and a_right <= b_right and a_top >= b_top and a_bottom <= b_bottom

    lines = [
        f"element_a: [{a_left},{a_top}][{a_right},{a_bottom}]",
        f"element_b: [{b_left},{b_top}][{b_right},{b_bottom}]",
    ]

    if b_inside_a:
        lines.append("relationship: B is inside A")
        lines.append(f"padding_left: {to_dp(b_left - a_left)}dp")
        lines.append(f"padding_top: {to_dp(b_top - a_top)}dp")
        lines.append(f"padding_right: {to_dp(a_right - b_right)}dp")
        lines.append(f"padding_bottom: {to_dp(a_bottom - b_bottom)}dp")
    elif a_inside_b:
        lines.append("relationship: A is inside B")
        lines.append(f"padding_left: {to_dp(a_left - b_left)}dp")
        lines.append(f"padding_top: {to_dp(a_top - b_top)}dp")
        lines.append(f"padding_right: {to_dp(b_right - a_right)}dp")
        lines.append(f"padding_bottom: {to_dp(b_bottom - a_bottom)}dp")
    else:
        # Calculate gaps
        if b_left >= a_right:
            h_gap = b_left - a_right
            h_dir = "B is right of A"
        elif a_left >= b_right:
            h_gap = a_left - b_right
            h_dir = "A is right of B"
        else:
            h_gap = 0
            h_dir = "overlapping horizontally"

        if b_top >= a_bottom:
            v_gap = b_top - a_bottom
            v_dir = "B is below A"
        elif a_top >= b_bottom:
            v_gap = a_top - b_bottom
            v_dir = "A is below B"
        else:
            v_gap = 0
            v_dir = "overlapping vertically"

        lines.append(f"relationship: separate")
        lines.append(f"horizontal_gap: {to_dp(h_gap)}dp ({h_dir})")
        lines.append(f"vertical_gap: {to_dp(v_gap)}dp ({v_dir})")

    # Alignment
    alignments = []
    if a_left == b_left:
        alignments.append("left-aligned")
    if a_right == b_right:
        alignments.append("right-aligned")
    if abs((a_left + a_right) - (b_left + b_right)) <= 1:
        alignments.append("center-aligned")
    if a_top == b_top:
        alignments.append("top-aligned")
    if a_bottom == b_bottom:
        alignments.append("bottom-aligned")
    if abs((a_top + a_bottom) - (b_top + b_bottom)) <= 1:
        alignments.append("middle-aligned")

    lines.append(f"alignment: {', '.join(alignments) if alignments else 'none'}")

    return "\n".join(lines)


@mcp.tool(
    name="LongClick",
    description="Long click on a specific cordinate",
    annotations=ToolAnnotations(title="Long Click", destructiveHint=True),
)
@debug_tool
def long_click_tool(x: int, y: int):
    device = require_device()
    device.long_click(x, y)
    return f"Long Clicked on ({x},{y})"


@mcp.tool(
    name="Swipe",
    description="Swipe on a specific cordinate",
    annotations=ToolAnnotations(title="Swipe", destructiveHint=True),
)
@debug_tool
def swipe_tool(x1: int, y1: int, x2: int, y2: int):
    device = require_device()
    device.swipe(x1, y1, x2, y2)
    return f"Swiped from ({x1},{y1}) to ({x2},{y2})"


@mcp.tool(
    name="Type",
    description="Type on a specific cordinate",
    annotations=ToolAnnotations(title="Type", destructiveHint=True),
)
@debug_tool
def type_tool(text: str, x: int, y: int, clear: bool = False):
    device = require_device()
    device.set_fastinput_ime(enable=True)
    device.send_keys(text=text, clear=clear)
    return f'Typed "{text}" on ({x},{y})'


@mcp.tool(
    name="Drag",
    description="Drag from location and drop on another location",
    annotations=ToolAnnotations(title="Drag", destructiveHint=True),
)
@debug_tool
def drag_tool(x1: int, y1: int, x2: int, y2: int):
    device = require_device()
    device.drag(x1, y1, x2, y2)
    return f"Dragged from ({x1},{y1}) and dropped on ({x2},{y2})"


@mcp.tool(
    name="Press",
    description="Press on specific button on the device",
    annotations=ToolAnnotations(title="Press", destructiveHint=True),
)
@debug_tool
def press_tool(button: str):
    device = require_device()
    device.press(button)
    return f'Pressed the "{button}" button'


@mcp.tool(
    name="Notification",
    description="Access the notifications seen on the device",
    annotations=ToolAnnotations(
        title="Notification", destructiveHint=True, idempotentHint=True
    ),
)
@debug_tool
def notification_tool():
    device = require_device()
    device.open_notification()
    return "Accessed notification bar"


@mcp.tool(
    name="Wait",
    description="Wait for a specific amount of time",
    annotations=ToolAnnotations(title="Wait", destructiveHint=True, idempotentHint=True),
)
@debug_tool
def wait_tool(duration: int):
    device = require_device()
    device.sleep(duration)
    return f"Waited for {duration} seconds"


@mcp.tool(name='WaitForElement',description='Wait for an element to appear on screen. Use this instead of Wait when content is loading dynamically. Returns element info when found or error on timeout.',annotations=ToolAnnotations(title="Wait For Element",readOnlyHint=True))
@debug_tool
def wait_for_element_tool(text:str=None,resourceId:str=None,className:str=None,description:str=None,timeout:float=10.0):
    device=require_device()
    kwargs={}
    if text: kwargs['text']=text
    if resourceId: kwargs['resourceId']=_resolve_resource_id(device, resourceId)
    if className: kwargs['className']=className
    if description: kwargs['description']=description
    if not kwargs:
        return 'Error: at least one selector (text, resourceId, className, description) must be provided'
    el=device(**kwargs)
    if el.wait(timeout=timeout):
        info=el.info
        bounds=info.get('bounds',{})
        cx=(bounds.get('left',0)+bounds.get('right',0))//2
        cy=(bounds.get('top',0)+bounds.get('bottom',0))//2
        return f'Element found: text="{info.get("text","")}" class={info.get("className","")} coords=({cx},{cy}) bounds=[{bounds.get("left",0)},{bounds.get("top",0)}][{bounds.get("right",0)},{bounds.get("bottom",0)}]'
    return f'Element not found with selectors {kwargs} within {timeout}s'

def main():
    mcp.run()


if __name__ == "__main__":
    main()
