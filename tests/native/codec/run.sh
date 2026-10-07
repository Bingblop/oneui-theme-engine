#!/usr/bin/env bash
set -euo pipefail

codec_test_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
codec_repo=$(cd -- "$codec_test_dir/../../.." && pwd -P)
codec_output=${THEME_CODEC_OUTPUT:-}
codec_json_jar=${JSON_JAVA_JAR:-}
codec_font=${THEME_CODEC_FONT:-}
codec_font_license=${THEME_CODEC_FONT_LICENSE:-Host test fixture}
codec_java=${JAVA:-java}
codec_javac=${JAVAC:-}
codec_python=${PYTHON:-python3}
codec_source=${THEME_SOURCE_JAVA:-}
codec_workspace_source=${THEME_WORKSPACE_JAVA:-}
codec_json_sha=3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed

usage() {
  cat <<'EOF'
Usage: run.sh --json-jar /path/json-20240303.jar --font /path/licensed.ttf [options]

  --repo PATH          Repository root (default: inferred from this script)
  --output PATH        External directory for generated fixtures, classes, and results
  --json-jar PATH      JSON-java 20240303 jar (or JSON_JAVA_JAR)
  --font PATH          Licensed host TTF fixture (or THEME_CODEC_FONT)
  --font-license TEXT  Fixture license label (or THEME_CODEC_FONT_LICENSE)
  --source PATH        ThemeSource.java override (or THEME_SOURCE_JAVA)
  --workspace-source PATH  WorkspaceIO.java override (or THEME_WORKSPACE_JAVA)
  --java PATH          Java executable (or JAVA)
  --javac PATH         Compiler executable (or JAVAC)
  --python PATH        Python 3 executable (or PYTHON)

Without --output/THEME_CODEC_OUTPUT, a temporary directory is retained for review.
Without javac, the runner uses Java's com.sun.tools.javac.Main compiler module.
EOF
}
while (($#)); do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --repo|--output|--json-jar|--font|--font-license|--source|--workspace-source|--java|--javac|--python)
      if (($# < 2)); then printf 'Missing value for %s\n' "$1" >&2; exit 2; fi
      case "$1" in
        --repo) codec_repo=$2 ;; --output) codec_output=$2 ;;
        --json-jar) codec_json_jar=$2 ;; --font) codec_font=$2 ;;
        --font-license) codec_font_license=$2 ;; --source) codec_source=$2 ;;
        --workspace-source) codec_workspace_source=$2 ;;
        --java) codec_java=$2 ;; --javac) codec_javac=$2 ;; --python) codec_python=$2 ;;
      esac
      shift 2 ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done
if [[ -z "$codec_json_jar" || ! -f "$codec_json_jar" ]]; then
  printf '%s\n' 'Select the pinned JSON-java jar with --json-jar or JSON_JAVA_JAR; see README.md.' >&2
  exit 2
fi
if [[ -z "$codec_font" || ! -f "$codec_font" ]]; then
  printf '%s\n' 'Select a licensed host TTF with --font or THEME_CODEC_FONT.' >&2
  exit 2
fi
codec_repo=$(cd -- "$codec_repo" && pwd -P)
if [[ -z "$codec_output" ]]; then codec_output=$(mktemp -d "${TMPDIR:-/tmp}/oneui-codec.XXXXXX"); fi
codec_output=$("$codec_python" -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve())' "$codec_output")
case "$codec_output/" in
  "$codec_repo/"*) printf '%s\n' 'Generated test output must be outside the repository.' >&2; exit 2 ;;
esac
if [[ -z "$codec_source" ]]; then
  codec_source=$codec_repo/apps/oneui-studio/src/org/bingblop/oneui/studio/ThemeSource.java
fi
if [[ -z "$codec_workspace_source" ]]; then
  codec_workspace_source=$codec_repo/apps/oneui-studio/src/org/bingblop/oneui/studio/WorkspaceIO.java
fi
hash_file() {
  "$codec_python" -c 'import hashlib,pathlib,sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())' "$1"
}
if [[ "$(hash_file "$codec_json_jar")" != "$codec_json_sha" ]]; then
  printf '%s\n' 'JSON-java jar hash does not match pinned version 20240303.' >&2
  exit 2
fi
codec_source_hash_before=$(hash_file "$codec_source")
codec_workspace_hash_before=$(hash_file "$codec_workspace_source")
mkdir -p "$codec_output/classes"
"$codec_python" "$codec_test_dir/create_schema_fixtures.py" \
  --baseline "$codec_repo/docs/design/theme-source/bundles/amoled-black.ouitheme" \
  --output "$codec_output/fixtures/schema" --font "$codec_font" --font-license "$codec_font_license"
"$codec_python" "$codec_test_dir/create_zip_fixtures.py" \
  --baseline "$codec_repo/docs/design/theme-source/bundles/amoled-black.ouitheme" \
  --output "$codec_output/fixtures/zip"
if [[ -n "$codec_javac" ]]; then
  codec_compiler=("$codec_javac")
elif command -v javac >/dev/null 2>&1; then
  codec_compiler=(javac)
else
  codec_compiler=("$codec_java" com.sun.tools.javac.Main)
fi
"${codec_compiler[@]}" -source 17 -target 17 -Xlint:-options -encoding UTF-8 \
  -cp "$codec_json_jar" -d "$codec_output/classes" \
  "$codec_test_dir/src/android/content/res/AssetManager.java" \
  "$codec_test_dir/src/android/graphics/Bitmap.java" \
  "$codec_test_dir/src/android/graphics/BitmapFactory.java" \
  "$codec_source" "$codec_workspace_source" \
  "$codec_test_dir/src/CodecTests.java" "$codec_test_dir/src/WorkspaceIOTests.java"
"$codec_java" -Xmx512m -cp "$codec_output/classes:$codec_json_jar" CodecTests "$codec_output" "$codec_repo"
"$codec_java" -Xmx512m -cp "$codec_output/classes:$codec_json_jar" WorkspaceIOTests "$codec_output" "$codec_repo"
codec_source_hash_after=$(hash_file "$codec_source")
codec_workspace_hash_after=$(hash_file "$codec_workspace_source")
if [[ "$codec_source_hash_before" != "$codec_source_hash_after" || "$codec_workspace_hash_before" != "$codec_workspace_hash_after" ]]; then
  printf '%s\n' 'Source changed during the test run; rerun before claiming verification.' >&2
  exit 1
fi
printf '%s  %s\n' "$codec_source_hash_after" "$codec_source" > "$codec_output/source.sha256"
printf '%s  %s\n' "$codec_workspace_hash_after" "$codec_workspace_source" >> "$codec_output/source.sha256"
printf 'Codec test artifacts: %s\n' "$codec_output"
