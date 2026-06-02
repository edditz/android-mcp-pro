import re


def display_scale(device) -> float:
    """Return the px-to-dp scale factor (density / 160).

    uiautomator2's device.info has no displayDensityDpi key, so derive the
    scale from displayWidth / displaySizeDpX (e.g. 1200 / 400 = 3.0). Falls
    back to `wm density`, then to 1.0 if neither is available.

    Shared by both layout providers so deep-mode and accessibility-mode report
    distances in the same dp units.
    """
    info = device.info
    width_px = info.get("displayWidth")
    width_dp = info.get("displaySizeDpX")
    if width_px and width_dp:
        return width_px / width_dp

    try:
        output = device.shell("wm density").output
        match = re.search(r"(\d+)", output)
        if match:
            return int(match.group(1)) / 160
    except Exception:
        pass

    return 1.0


def px_to_dp(px: float, scale: float) -> float:
    """Convert a pixel value to dp, rounded to 1 decimal with trailing .0 dropped.

    Matches the precision a design review needs (sub-dp differences rarely
    matter) while staying honest — 49px @ ×3 → 16.3dp, not a fabricated 16.
    """
    dp = px / scale if scale else px
    r = round(dp, 1)
    return int(r) if r == int(r) else r
