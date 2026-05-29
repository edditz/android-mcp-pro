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


def test_empty_stdout_raises_dump_failed(monkeypatch, tmp_path):
    jar = tmp_path / "deep-inspector.jar"; jar.write_text("x")
    monkeypatch.setattr(jdwp_runner.shutil, "which", lambda n: "/usr/bin/java")

    def fake_run(cmd, capture_output, text, timeout):
        class R: pass
        r = R(); r.returncode = 1; r.stdout = "   "; r.stderr = "boom"
        return r

    monkeypatch.setattr(jdwp_runner.subprocess, "run", fake_run)
    with pytest.raises(jdwp_runner.DeepDumpError) as ei:
        jdwp_runner.run_deep_dump(str(jar), serial="s", package="com.x", adb_path="adb")
    assert ei.value.error_type == "DUMP_FAILED"
