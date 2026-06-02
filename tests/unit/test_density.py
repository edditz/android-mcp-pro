from android_mcp.layout.density import display_scale, px_to_dp


class _FakeDevice:
    def __init__(self, info=None, density_output=None):
        self.info = info or {}
        self._density_output = density_output

    def shell(self, cmd):
        class R:
            output = self._density_output or ""
        return R()


def test_scale_from_display_info():
    dev = _FakeDevice(info={"displayWidth": 1200, "displaySizeDpX": 400})
    assert display_scale(dev) == 3.0


def test_scale_falls_back_to_wm_density():
    dev = _FakeDevice(info={}, density_output="Physical density: 480")
    assert display_scale(dev) == 3.0


def test_scale_defaults_to_one_when_unknown():
    dev = _FakeDevice(info={})
    assert display_scale(dev) == 1.0


def test_px_to_dp_drops_trailing_zero():
    # 73px @ ×3 → 24.3 (kept), 69px @ ×3 → 23 (int, no .0)
    assert px_to_dp(69, 3.0) == 23
    assert px_to_dp(73, 3.0) == 24.3


def test_px_to_dp_scale_one_is_identity():
    assert px_to_dp(48, 1.0) == 48
