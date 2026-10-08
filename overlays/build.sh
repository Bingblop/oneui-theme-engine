#!/usr/bin/env bash
# Builds every overlay under overlays/<name>/ into a signed APK in overlays/dist/.
# Needs an Android SDK (ANDROID_HOME) with build-tools and a platform installed.
set -euo pipefail

root="$(cd "$(dirname "$0")" && pwd)"
sdk="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
[ -n "$sdk" ] || { echo "ANDROID_HOME is not set" >&2; exit 1; }

bt="$sdk/build-tools/$(ls "$sdk/build-tools" | sort -V | tail -1)"
platform="$(ls -d "$sdk"/platforms/android-* | sort -V | tail -1)"
android_jar="$platform/android.jar"
keystore="$root/../android/app/debug.keystore"
echo "build-tools: $bt"
echo "platform:    $platform"

dist="$root/dist"
rm -rf "$dist" && mkdir -p "$dist"

for dir in "$root"/*/; do
    name="$(basename "$dir")"
    [ -f "$dir/AndroidManifest.xml" ] || continue
    work="$(mktemp -d)"
    echo "== $name"

    "$bt/aapt2" compile --dir "$dir/res" -o "$work/res.zip"
    "$bt/aapt2" link -I "$android_jar" \
        --manifest "$dir/AndroidManifest.xml" \
        -o "$work/unsigned.apk" "$work/res.zip"
    "$bt/zipalign" -p -f 4 "$work/unsigned.apk" "$work/aligned.apk"
    "$bt/apksigner" sign --ks "$keystore" --ks-pass pass:android \
        --ks-key-alias androiddebugkey --key-pass pass:android \
        --out "$dist/oneuitheme-$name.apk" "$work/aligned.apk"
    "$bt/apksigner" verify "$dist/oneuitheme-$name.apk"

    "$bt/aapt2" dump badging "$dist/oneuitheme-$name.apk" | head -3
    "$bt/aapt2" dump resources "$dist/oneuitheme-$name.apk" | grep -c "color/" \
        | xargs echo "colors:"
    rm -rf "$work"
done
