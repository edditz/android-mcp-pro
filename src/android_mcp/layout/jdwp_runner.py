import json
import os
import shutil
import subprocess


class DeepDumpError(Exception):
    def __init__(self, message: str, error_type: str):
        super().__init__(message)
        self.error_type = error_type


def run_deep_dump(jar_path: str, *, serial: str, package: str,
                  adb_path: str, window: str | None = None, timeout_s: float = 35.0) -> dict:
    """Run the Java deep-inspector jar and return parsed JSON. Raises DeepDumpError on any failure."""
    if shutil.which("java") is None:
        raise DeepDumpError("java not found on PATH; deep mode requires a JDK/JRE", "NO_JAVA")
    if not os.path.isfile(jar_path):
        raise DeepDumpError(f"deep-inspector jar not found at {jar_path}", "NO_JAR")

    cmd = ["java", "-jar", jar_path, "--package", package,
           "--adb", adb_path, "--timeout-ms", str(max(1000, int(timeout_s * 1000) - 5000))]
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
