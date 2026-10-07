package com.hexnext.themer.theme

import android.content.SharedPreferences
import android.os.Bundle
import com.hexnext.themer.IThemeService
import com.hexnext.themer.shizuku.ThemeService
import org.json.JSONObject

enum class LogLevel { INFO, OK, WARN, ERROR }

data class LogLine(val level: LogLevel, val text: String)

/**
 * Applies and removes themes through the Shizuku user service. Every step reports the real
 * exit code and output; nothing here claims success it didn't observe.
 */
class ThemeEngine(private val prefs: SharedPreferences) {

    /** Root path: framework Monet colors as fabricated overlays. */
    fun applyFabricated(service: IThemeService, palette: MonetPalette, log: (LogLine) -> Unit): Boolean {
        val shades = palette.shadeEntries()
        log(LogLine(LogLevel.INFO, "Fabricating $SHADES_OVERLAY (${shades.size} Monet shades)…"))
        val shadeResult = service.applyColorOverlay(SHADES_OVERLAY, TARGET, shades.names(), shades.colors())
        if (!report(shadeResult, log)) return false

        val roles = palette.roleEntries()
        log(LogLine(LogLevel.INFO, "Fabricating $ROLES_OVERLAY (${roles.size} Material role colors)…"))
        val roleResult = service.applyColorOverlay(ROLES_OVERLAY, TARGET, roles.names(), roles.colors())
        if (!report(roleResult, log, failLevel = LogLevel.WARN)) {
            log(LogLine(LogLevel.WARN, "Role colors were skipped; the Monet shades are still applied."))
        }

        verify(service, shades.first { it.name == "system_accent1_500" }, log)
        log(LogLine(LogLevel.OK, "Theme applied. Apps pick up the new colors as they redraw or restart."))
        return true
    }

    /**
     * Non-root path. Android won't let the shell user fabricate overlays, so hand the seed color and
     * style to System UI's own Monet engine through the setting it watches. Stock Android honors it;
     * One UI may override it with its own color palette, so this is a best-effort fallback.
     */
    fun applySeedSetting(service: IThemeService, spec: ThemeSpec, log: (LogLine) -> Unit): Boolean {
        if (!prefs.contains(PREF_SETTING_BACKUP)) {
            val current = service.exec("settings get secure $SETTING")
            if (current.code() != 0) return report(current, log)
            prefs.edit().putString(PREF_SETTING_BACKUP, current.output()).apply()
            log(LogLine(LogLevel.INFO, "Saved your current palette setting so Remove can restore it."))
        }
        val hex = spec.seed.toHex().removePrefix("#")
        val json = JSONObject()
            .put("android.theme.customization.color_source", "preset")
            .put("android.theme.customization.system_palette", hex)
            .put("android.theme.customization.accent_color", hex)
            .put("android.theme.customization.theme_style", spec.style.systemUiName)
            .put("_applied_timestamp", System.currentTimeMillis())
        log(LogLine(LogLevel.INFO, "Setting System UI seed color $hex (${spec.style.label})…"))
        val result = service.exec("settings put secure $SETTING '$json'")
        if (!report(result, log)) return false
        if (spec.pureBlack) {
            log(LogLine(LogLevel.WARN, "Pure black needs root, so it was skipped."))
        }
        log(LogLine(LogLevel.OK, "Seed color handed to System UI. If One UI ignores it, root Shizuku is needed."))
        return true
    }

    fun remove(service: IThemeService, isRoot: Boolean, log: (LogLine) -> Unit): Boolean {
        var ok = true
        if (isRoot) {
            for (name in listOf(ROLES_OVERLAY, SHADES_OVERLAY)) {
                log(LogLine(LogLevel.INFO, "Removing $name…"))
                ok = report(service.removeOverlay(name), log) && ok
            }
        }
        val backup = prefs.getString(PREF_SETTING_BACKUP, null)
        if (backup != null) {
            log(LogLine(LogLevel.INFO, "Restoring your previous palette setting…"))
            val command = if (backup.isBlank() || backup == "null") {
                "settings delete secure $SETTING"
            } else {
                "settings put secure $SETTING '${backup.replace("'", "")}'"
            }
            val restored = report(service.exec(command), log)
            if (restored) prefs.edit().remove(PREF_SETTING_BACKUP).apply()
            ok = restored && ok
        } else if (!isRoot) {
            log(LogLine(LogLevel.INFO, "Nothing to remove."))
        }
        if (ok) log(LogLine(LogLevel.OK, "Back to the system palette."))
        return ok
    }

    /** Reads back what the framework now resolves for one color. */
    private fun verify(service: IThemeService, expected: ColorEntry, log: (LogLine) -> Unit) {
        val lookup = service.exec("cmd overlay lookup --user current android ${expected.resourceName}")
        val text = lookup.output()
        val want = expected.argb.toHex().removePrefix("#")
        when {
            lookup.code() != 0 -> log(LogLine(LogLevel.WARN, "Couldn't read back ${expected.name}: $text"))
            text.contains(want, ignoreCase = true) ->
                log(LogLine(LogLevel.OK, "Verified: ${expected.name} now resolves to #$want."))
            else -> log(LogLine(LogLevel.WARN, "${expected.name} resolves to \"$text\", expected #$want."))
        }
    }

    private fun report(result: Bundle, log: (LogLine) -> Unit, failLevel: LogLevel = LogLevel.ERROR): Boolean {
        val ok = result.code() == 0
        val output = result.output()
        if (ok) {
            if (output.isNotBlank()) log(LogLine(LogLevel.OK, output))
        } else {
            log(LogLine(failLevel, "Exit ${result.code()}: ${output.ifBlank { "no output" }}"))
        }
        return ok
    }

    private fun Bundle.code() = getInt(ThemeService.KEY_CODE, -1)
    private fun Bundle.output() = getString(ThemeService.KEY_OUTPUT).orEmpty()
    private fun List<ColorEntry>.names() = map { it.resourceName }.toTypedArray()
    private fun List<ColorEntry>.colors() = map { it.argb }.toIntArray()

    companion object {
        const val TARGET = "android"
        const val SHADES_OVERLAY = "HexNextMonetShades"
        const val ROLES_OVERLAY = "HexNextMonetRoles"
        private const val SETTING = "theme_customization_overlay_packages"
        private const val PREF_SETTING_BACKUP = "setting_backup"
    }
}
