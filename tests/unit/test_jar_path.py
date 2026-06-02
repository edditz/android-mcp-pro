"""Tests for default deep-inspector.jar resolution across install layouts.

Two layouts must both work:
  * editable / source checkout — jar lives at <repo_root>/prebuilt/deep-inspector.jar,
    i.e. OUTSIDE the import package.
  * installed wheel — jar is bundled INSIDE the package at android_mcp/prebuilt/deep-inspector.jar
    (force-included by hatchling), because the repo root no longer exists.

resolve_default_jar(package_dir, repo_root) must prefer the in-package copy and
fall back to the repo-root copy, returning the first that exists. It returns a
path string even when neither exists (so the caller's own fail-fast check owns
the error message), defaulting to the in-package location.
"""
from android_mcp.jar_path import resolve_default_jar


def test_prefers_in_package_jar(tmp_path):
    # wheel layout: jar bundled inside the package
    pkg = tmp_path / "android_mcp"
    (pkg / "prebuilt").mkdir(parents=True)
    in_pkg = pkg / "prebuilt" / "deep-inspector.jar"
    in_pkg.write_text("jar")
    repo_root = tmp_path / "repo"  # no jar here
    got = resolve_default_jar(package_dir=str(pkg), repo_root=str(repo_root))
    assert got == str(in_pkg)


def test_falls_back_to_repo_root_jar(tmp_path):
    # source/editable layout: jar only at repo_root/prebuilt
    pkg = tmp_path / "src" / "android_mcp"
    pkg.mkdir(parents=True)  # package dir exists, but no prebuilt/ inside
    repo_root = tmp_path
    (repo_root / "prebuilt").mkdir()
    root_jar = repo_root / "prebuilt" / "deep-inspector.jar"
    root_jar.write_text("jar")
    got = resolve_default_jar(package_dir=str(pkg), repo_root=str(repo_root))
    assert got == str(root_jar)


def test_defaults_to_in_package_path_when_neither_exists(tmp_path):
    # Neither copy present — return the in-package path so the caller's
    # fail-fast check reports a stable, package-relative location.
    pkg = tmp_path / "android_mcp"
    pkg.mkdir(parents=True)
    repo_root = tmp_path / "repo"
    got = resolve_default_jar(package_dir=str(pkg), repo_root=str(repo_root))
    assert got == str(pkg / "prebuilt" / "deep-inspector.jar")
