package com.hexnext.themer.shizuku

import android.content.Context
import android.content.om.FabricatedOverlay
import android.content.om.OverlayManagerTransaction
import android.os.Bundle
import android.os.IBinder
import android.os.Process
import android.util.TypedValue
import androidx.annotation.Keep
import com.hexnext.themer.IThemeService
import org.lsposed.hiddenapibypass.HiddenApiBypass
import java.lang.reflect.InvocationTargetException
import java.util.concurrent.TimeUnit
import kotlin.system.exitProcess

/**
 * Shizuku user service. Shizuku starts this class in its own process with Shizuku's identity:
 * uid 2000 (shell) when Shizuku was started over ADB, or uid 0 when it was started with root (or Sui).
 *
 * Fabricated overlays are registered by talking to the overlay manager binder directly.
 * `cmd overlay fabricate` cannot be used: AOSP rejects it unless the caller is root, and
 * OverlayManagerService rejects fabricated-overlay transactions from the shell uid outright
 * ("Non-root shell cannot fabricate overlays"). So this path needs root-backed Shizuku.
 */
@Keep
class ThemeService() : IThemeService.Stub() {

    // Shizuku prefers a (Context) constructor when one exists.
    @Keep
    @Suppress("UNUSED_PARAMETER")
    constructor(context: Context) : this()

    init {
        // Processes started by app_process usually aren't restricted, but be safe.
        runCatching { HiddenApiBypass.addHiddenApiExemptions("") }
    }

    override fun destroy() {
        exitProcess(0)
    }

    override fun getUid(): Int = Process.myUid()

    override fun exec(command: String): Bundle = try {
        val process = ProcessBuilder("sh", "-c", command)
            .redirectErrorStream(true)
            .start()
        val output = process.inputStream.bufferedReader().use { it.readText() }
        if (!process.waitFor(60, TimeUnit.SECONDS)) {
            process.destroyForcibly()
            result(124, output + "\n(timed out after 60s)")
        } else {
            result(process.exitValue(), output)
        }
    } catch (t: Throwable) {
        result(-1, describe(t))
    }

    override fun applyColorOverlay(
        name: String,
        targetPackage: String,
        resourceNames: Array<String>,
        colors: IntArray,
    ): Bundle {
        if (Process.myUid() != 0) return rootRequired()
        if (resourceNames.size != colors.size) {
            return result(-1, "resourceNames and colors differ in length")
        }
        return try {
            val overlay = newOverlay(name, targetPackage)
            resourceNames.forEachIndexed { i, res ->
                overlay.setResourceValue(res, TypedValue.TYPE_INT_COLOR_ARGB8, colors[i], null)
            }
            val register = OverlayManagerTransaction.newInstance()
            register.registerFabricatedOverlay(overlay)
            commit(register)

            // Enabling through the shell also raises the overlay to the highest priority,
            // which puts it above System UI's own Monet overlays.
            val id = overlayId(name)
            val enable = exec("cmd overlay enable --user current $id")
            val code = enable.getInt(KEY_CODE)
            result(
                code,
                "Registered $id with ${resourceNames.size} colors on $targetPackage" +
                    if (code == 0) ", enabled." else ".\nEnable failed: ${enable.getString(KEY_OUTPUT)}"
            )
        } catch (t: Throwable) {
            result(-1, describe(t))
        }
    }

    override fun removeOverlay(name: String): Bundle {
        if (Process.myUid() != 0) return rootRequired()
        return try {
            val id = overlayId(name)
            exec("cmd overlay disable --user current $id")
            val unregister = OverlayManagerTransaction.newInstance()
            // The identifier is (owning package, name); the target doesn't matter for removal.
            unregister.unregisterFabricatedOverlay(newOverlay(name, "android").identifier)
            commit(unregister)
            result(0, "Removed $id")
        } catch (t: Throwable) {
            result(-1, describe(t))
        }
    }

    private fun newOverlay(name: String, target: String): FabricatedOverlay {
        val overlay = FabricatedOverlay(name, target)
        // Hidden setter. Matches what `cmd overlay fabricate` uses, so overlays show up as
        // com.android.shell:<name> in `cmd overlay list`.
        FabricatedOverlay::class.java
            .getMethod("setOwningPackage", String::class.java)
            .invoke(overlay, OWNER)
        return overlay
    }

    private fun commit(transaction: OverlayManagerTransaction) {
        val binder = Class.forName("android.os.ServiceManager")
            .getMethod("getService", String::class.java)
            .invoke(null, "overlay") as IBinder
        val iom = Class.forName("android.content.om.IOverlayManager\$Stub")
            .getMethod("asInterface", IBinder::class.java)
            .invoke(null, binder)
        Class.forName("android.content.om.IOverlayManager")
            .getMethod("commit", OverlayManagerTransaction::class.java)
            .invoke(iom, transaction)
    }

    private fun rootRequired() = result(
        -1,
        "Fabricated overlays need Shizuku running as root (uid 0). " +
            "This Shizuku runs as uid ${Process.myUid()}, and Android blocks the shell user from fabricating overlays."
    )

    private fun describe(t: Throwable): String {
        val cause = if (t is InvocationTargetException) t.targetException ?: t else t
        return "${cause.javaClass.simpleName}: ${cause.message}"
    }

    companion object {
        const val KEY_CODE = "code"
        const val KEY_OUTPUT = "output"
        const val OWNER = "com.android.shell"

        fun overlayId(name: String) = "$OWNER:$name"

        fun result(code: Int, output: String) = Bundle().apply {
            putInt(KEY_CODE, code)
            putString(KEY_OUTPUT, output.trimEnd())
        }
    }
}
