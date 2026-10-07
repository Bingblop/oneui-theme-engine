package com.hexnext.themer.shizuku

import android.content.ComponentName
import android.content.ServiceConnection
import android.content.pm.PackageManager
import android.os.IBinder
import com.hexnext.themer.BuildConfig
import com.hexnext.themer.IThemeService
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withTimeout
import rikka.shizuku.Shizuku

/** Where Shizuku stands, from this app's point of view. */
sealed interface ShizukuState {
    /** Shizuku isn't installed or isn't running. */
    data object NotRunning : ShizukuState

    /** Shizuku is older than the v11 API this app uses. */
    data object TooOld : ShizukuState

    data object PermissionNeeded : ShizukuState

    /** The user picked "deny and don't ask again"; it must be granted in the Shizuku app. */
    data object PermissionDenied : ShizukuState

    data class Ready(val uid: Int, val version: Int) : ShizukuState {
        val isRoot get() = uid == 0
    }
}

object ShizukuManager {
    private const val PERMISSION_REQUEST = 7301

    private val _state = MutableStateFlow<ShizukuState>(ShizukuState.NotRunning)
    val state: StateFlow<ShizukuState> = _state.asStateFlow()

    private var service: IThemeService? = null
    private var pending: CompletableDeferred<IThemeService>? = null

    private val serviceArgs by lazy {
        Shizuku.UserServiceArgs(ComponentName(BuildConfig.APPLICATION_ID, ThemeService::class.java.name))
            .daemon(false)
            .processNameSuffix("theme")
            .debuggable(BuildConfig.DEBUG)
            .version(BuildConfig.VERSION_CODE)
    }

    private val connection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, binder: IBinder?) {
            if (binder == null || !binder.pingBinder()) return
            val bound = IThemeService.Stub.asInterface(binder)
            service = bound
            pending?.complete(bound)
            pending = null
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            service = null
        }
    }

    private var initialized = false

    fun init() {
        if (initialized) return
        initialized = true
        Shizuku.addBinderReceivedListenerSticky { refresh() }
        Shizuku.addBinderDeadListener {
            service = null
            refresh()
        }
        Shizuku.addRequestPermissionResultListener { requestCode, _ ->
            if (requestCode == PERMISSION_REQUEST) refresh()
        }
        refresh()
    }

    fun refresh() {
        _state.value = when {
            !Shizuku.pingBinder() -> ShizukuState.NotRunning
            Shizuku.isPreV11() -> ShizukuState.TooOld
            Shizuku.checkSelfPermission() == PackageManager.PERMISSION_GRANTED ->
                ShizukuState.Ready(Shizuku.getUid(), Shizuku.getVersion())
            Shizuku.shouldShowRequestPermissionRationale() -> ShizukuState.PermissionDenied
            else -> ShizukuState.PermissionNeeded
        }
    }

    fun requestPermission() {
        if (Shizuku.pingBinder() && !Shizuku.isPreV11()) {
            Shizuku.requestPermission(PERMISSION_REQUEST)
        }
    }

    /** Binds the privileged user service, starting it if needed. Blocking callers should use IO. */
    suspend fun service(): IThemeService {
        service?.let { if (it.asBinder().pingBinder()) return it }
        check(_state.value is ShizukuState.Ready) { "Shizuku isn't ready" }
        val deferred = pending ?: CompletableDeferred<IThemeService>().also {
            pending = it
            Shizuku.bindUserService(serviceArgs, connection)
        }
        return try {
            withTimeout(15_000) { deferred.await() }
        } catch (e: TimeoutCancellationException) {
            pending = null
            throw IllegalStateException("Shizuku didn't start the theme service within 15 seconds")
        }
    }
}
