# Overlay APKs

Prebuilt Runtime Resource Overlays for phones without root. Each folder here
(`test-accent/`, ...) is one overlay; `build.sh` turns every folder into a
signed APK in `overlays/dist/`, and the **Overlay APKs** workflow publishes them
to the [`overlay-test`](https://github.com/Bingblop/oneui-theme-engine/releases/tag/overlay-test)
prerelease.

## test-accent

Targets the framework (`android`) and paints the primary Monet ramp
(`system_accent1_0` ... `system_accent1_1000`) plus the Android 14 primary role
colors bright magenta. It answers one question: can a user-installed overlay
change framework colors on One UI 9, or does the overlayable policy skip them?

### Run it

Every command below works from a PC as `adb shell <command>`, or on the phone
inside a Shizuku shell (`rish`). Download `oneuitheme-test-accent.apk` from the
prerelease to `Download/` first.

1. Record the current value:

       cmd overlay lookup --user current android android:color/system_accent1_600

2. Install:

       pm install -r /sdcard/Download/oneuitheme-test-accent.apk

   (From a PC, `adb install -r oneuitheme-test-accent.apk` does the same.)

3. See whether Android accepted it for the framework:

       cmd overlay list android | grep oneuitheme

   `[ ]` means installed and allowed but not enabled yet. `---` means Android
   refused it (the overlayable policy check failed); stop and report that.

4. Enable it and put it above Samsung's own palette overlays:

       cmd overlay enable --user current com.oneuitheme.test.accent
       cmd overlay set-priority com.oneuitheme.test.accent highest

5. Check the value again; a working overlay returns `#ffb800ad`:

       cmd overlay lookup --user current android android:color/system_accent1_600
       cmd overlay dump com.oneuitheme.test.accent | head -20

6. Look at the screen: force-stop Settings (`am force-stop com.android.settings`)
   and reopen it. Switches and highlights turning magenta means it works.

### Undo

    cmd overlay disable --user current com.oneuitheme.test.accent
    pm uninstall com.oneuitheme.test.accent

### What to report

The line from step 3, both lookups (steps 1 and 5), the `dump` output, and
whether anything on screen turned magenta.
