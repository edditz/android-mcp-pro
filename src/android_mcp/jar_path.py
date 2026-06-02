"""Locate the default deep-inspector.jar across install layouts.

The jar can live in two places depending on how the package was installed:

  * **Installed wheel** — bundled INSIDE the package at
    ``android_mcp/prebuilt/deep-inspector.jar`` (hatchling force-includes it).
    This is the only copy available once the repo checkout is gone, so it wins.
  * **Editable / source checkout** — at ``<repo_root>/prebuilt/deep-inspector.jar``,
    outside the import package, where gradle's ``shadowJar`` writes it.

``resolve_default_jar`` prefers the in-package copy and falls back to the
repo-root copy, returning the first that exists. When neither exists it returns
the in-package path so the caller's fail-fast check reports a stable location.
"""
import os

_JAR_NAME = "deep-inspector.jar"


def resolve_default_jar(package_dir: str, repo_root: str) -> str:
    """Return the best-guess path to the bundled deep-inspector.jar.

    package_dir: the android_mcp package directory (dir of this module).
    repo_root:   the source-checkout root (three levels up from this module).
    """
    in_package = os.path.join(package_dir, "prebuilt", _JAR_NAME)
    in_repo = os.path.join(repo_root, "prebuilt", _JAR_NAME)
    if os.path.isfile(in_package):
        return in_package
    if os.path.isfile(in_repo):
        return in_repo
    return in_package
