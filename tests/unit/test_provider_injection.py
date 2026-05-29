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
