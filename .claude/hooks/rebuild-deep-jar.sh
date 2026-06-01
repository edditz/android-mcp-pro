#!/usr/bin/env bash
# PostToolUse hook: rebuild the deep-inspector fat-jar whenever a .java file under
# java-deep-inspector/ is edited. Deep mode runs the COMPILED jar at
# prebuilt/deep-inspector.jar, so a .java edit has no runtime effect until the jar is
# rebuilt. shadowJar's destinationDirectory is configured to write straight into
# prebuilt/, so a single `./gradlew shadowJar` republishes the runtime artifact.
#
# Reads the PostToolUse JSON event on stdin; emits a JSON directive on stdout so the
# result (success or build error) is surfaced back to Claude.
set -euo pipefail

input=$(cat)

# Extract the edited file path (Edit/Write use file_path; MultiEdit too).
file_path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')

# Only react to Java sources inside the gradle subproject.
case "$file_path" in
  *java-deep-inspector/*.java) ;;
  *) exit 0 ;;
esac

repo_root=$(printf '%s' "$input" | jq -r '.cwd // empty')
[ -z "$repo_root" ] && repo_root=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
gradle_dir="$repo_root/java-deep-inspector"

emit() {
  # $1 = additionalContext message for Claude
  jq -n --arg ctx "$1" \
    '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $ctx}}'
}

if [ ! -x "$gradle_dir/gradlew" ]; then
  emit "deep-inspector: edited $file_path but $gradle_dir/gradlew was not found — rebuild the jar manually before relying on --deep."
  exit 0
fi

log=$(cd "$gradle_dir" && ./gradlew shadowJar 2>&1) && status=ok || status=fail

if [ "$status" = ok ]; then
  emit "deep-inspector: $(basename "$file_path") changed → rebuilt prebuilt/deep-inspector.jar via ./gradlew shadowJar. Remember to commit the regenerated jar alongside the .java change."
else
  emit "deep-inspector: $(basename "$file_path") changed but ./gradlew shadowJar FAILED — prebuilt/deep-inspector.jar is now STALE. Fix the build before continuing. Gradle output:
$(printf '%s' "$log" | tail -25)"
fi
exit 0
