package com.elyanivery.app

import android.Manifest
import android.annotation.SuppressLint
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.media.AudioAttributes
import android.media.RingtoneManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.view.View
import android.webkit.*
import android.widget.EditText
import android.widget.ProgressBar
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var progressBar: ProgressBar

    companion object {
        const val CHANNEL_ID = "elyanivery_orders_channel"
        const val CHANNEL_NAME = "Elyanivery Orders & Delivery"
        const val PREFS_NAME = "elyanivery_config"
        const val KEY_CUSTOM_SERVER = "custom_server_url"
    }

    private fun getEffectiveUrl(): String {
        val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val customServer = prefs.getString(KEY_CUSTOM_SERVER, null)
        if (!customServer.isNullOrBlank()) {
            val portal = when {
                BuildConfig.APPLICATION_ID.contains("courier") -> "/courier"
                BuildConfig.APPLICATION_ID.contains("partner") -> "/partner"
                BuildConfig.APPLICATION_ID.contains("admin") -> "/admin"
                BuildConfig.APPLICATION_ID.contains("support") -> "/support"
                else -> "/customer"
            }
            return customServer.trimEnd('/') + portal
        }
        return BuildConfig.APP_URL
    }

    private val requestPermissionsLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val notificationsGranted = permissions[Manifest.permission.POST_NOTIFICATIONS] ?: true
        val locationGranted = permissions[Manifest.permission.ACCESS_FINE_LOCATION] ?: false
        if (locationGranted) {
            webView.reload()
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.webView)
        progressBar = findViewById(R.id.progressBar)

        createNotificationChannel()
        requestHardwarePermissions()
        setupWebView()

        // Support deep link or server URL parameter: ?server=https://...
        intent.data?.getQueryParameter("server")?.let { newServer ->
            if (newServer.isNotBlank()) {
                getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                    .edit()
                    .putString(KEY_CUSTOM_SERVER, newServer)
                    .apply()
            }
        }

        if (savedInstanceState != null) {
            webView.restoreState(savedInstanceState)
        } else {
            webView.loadUrl(getEffectiveUrl())
        }
    }

    private fun showServerConfigDialog() {
        val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val currentServer = prefs.getString(KEY_CUSTOM_SERVER, "") ?: ""

        val input = EditText(this).apply {
            hint = "https://elyanivery.onrender.com"
            setText(currentServer)
            setPadding(40, 30, 40, 30)
        }

        AlertDialog.Builder(this)
            .setTitle("Elyanivery Live Server / OTA")
            .setMessage("Set your Render or custom deployment URL. All future GitHub/Render updates will automatically sync without rebuilding APKs.")
            .setView(input)
            .setPositiveButton("Save & Connect") { _, _ ->
                val entered = input.text.toString().trim()
                prefs.edit().putString(KEY_CUSTOM_SERVER, entered).apply()
                webView.clearCache(true)
                webView.loadUrl(getEffectiveUrl())
                Toast.makeText(this, "Connecting to live server...", Toast.LENGTH_SHORT).show()
            }
            .setNegativeButton("Cancel", null)
            .setNeutralButton("Reset Default") { _, _ ->
                prefs.edit().remove(KEY_CUSTOM_SERVER).apply()
                webView.clearCache(true)
                webView.loadUrl(BuildConfig.APP_URL)
                Toast.makeText(this, "Reset to default server", Toast.LENGTH_SHORT).show()
            }
            .show()
    }

    private fun setupWebView() {
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            useWideViewPort = true
            loadWithOverviewMode = true
            setSupportZoom(false)
            builtInZoomControls = false
            displayZoomControls = false

            // Crucial: Allow notification sound effects and chimes without requiring manual tap
            mediaPlaybackRequiresUserGesture = false

            // Enable geolocation
            setGeolocationEnabled(true)

            // Cache and storage
            cacheMode = WebSettings.LOAD_DEFAULT
            allowFileAccess = true
            allowContentAccess = true

            // Set custom user agent to let web pages know it is running in the native viewer
            userAgentString = "$userAgentString ElyaniveryNativeApp/1.0.0 (Android; Standalone)"
        }

        // WebChromeClient handles progress, GPS geolocation, and hardware permissions
        webView.webChromeClient = object : WebChromeClient() {
            override fun onProgressChanged(view: WebView?, newProgress: Int) {
                if (newProgress < 100) {
                    progressBar.visibility = View.VISIBLE
                    progressBar.progress = newProgress
                } else {
                    progressBar.visibility = View.GONE
                }
            }

            override fun onGeolocationPermissionsShowPrompt(
                origin: String?,
                callback: GeolocationPermissions.Callback?
            ) {
                // Grant location to the Elyanivery web application
                callback?.invoke(origin, true, false)
            }

            override fun onPermissionRequest(request: PermissionRequest?) {
                // Auto grant camera and microphone for live calls/uploads
                runOnUiThread {
                    request?.grant(request.resources)
                }
            }
        }

        // WebViewClient ensures all links run inside this app viewer, NOT in external Chrome
        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(
                view: WebView?,
                request: WebResourceRequest?
            ): Boolean {
                val url = request?.url?.toString() ?: return false

                // Keep app navigation strictly inside this viewer
                if (url.contains("run.app") || url.contains("elyanivery") || url.contains("onrender.com") || url.startsWith("/")) {
                    return false
                }

                // Handle external intents (calls, emails, maps)
                if (url.startsWith("tel:") || url.startsWith("mailto:") || url.startsWith("whatsapp:")) {
                    try {
                        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                        startActivity(intent)
                        return true
                    } catch (e: Exception) {
                        e.printStackTrace()
                    }
                }

                return false
            }

            override fun onReceivedError(
                view: WebView?,
                request: WebResourceRequest?,
                error: WebResourceError?
            ) {
                super.onReceivedError(view, request, error)
                if (request?.isForMainFrame == true) {
                    val htmlError = """
                        <!DOCTYPE html>
                        <html>
                        <head>
                            <meta name="viewport" content="width=device-width, initial-scale=1">
                            <style>
                                body { font-family: sans-serif; background: #0f172a; color: #f8fafc; text-align: center; padding: 40px 20px; }
                                .logo { width: 80px; height: 80px; border-radius: 20px; margin-bottom: 20px; }
                                h2 { font-size: 20px; margin-bottom: 8px; }
                                p { color: #94a3b8; font-size: 14px; margin-bottom: 24px; line-height: 1.5; }
                                .btn { background: #ea580c; color: white; border: none; padding: 12px 24px; border-radius: 12px; font-weight: bold; font-size: 14px; margin: 6px; cursor: pointer; }
                                .btn-sec { background: #334155; }
                            </style>
                        </head>
                        <body>
                            <img src="file:///android_res/drawable/logo.png" class="logo" onerror="this.style.display='none'">
                            <h2>Connecting to Elyanivery...</h2>
                            <p>Unable to connect to the server right now. Please check your connection or tap below to reconnect.</p>
                            <button class="btn" onclick="location.reload()">Retry Connection</button>
                        </body>
                        </html>
                    """.trimIndent()
                    view?.loadDataWithBaseURL(null, htmlError, "text/html", "utf-8", null)
                }
            }
        }

        // Long press on webview allows updating server URL if needed
        webView.setOnLongClickListener {
            // Optional admin shortcut
            false
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val defaultSoundUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
            val audioAttributes = AudioAttributes.Builder()
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .setUsage(AudioAttributes.USAGE_NOTIFICATION)
                .build()

            val channel = NotificationChannel(
                CHANNEL_ID,
                CHANNEL_NAME,
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Real-time delivery updates, order status changes, and courier alerts"
                enableLights(true)
                lightColor = Color.parseColor("#FF6B00")
                enableVibration(true)
                vibrationPattern = longArrayOf(0, 200, 100, 200)
                setSound(defaultSoundUri, audioAttributes)
            }

            val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            notificationManager.createNotificationChannel(channel)
        }
    }

    private fun requestHardwarePermissions() {
        val permissionsToRequest = mutableListOf<String>()

        // Android 13+ Notification permission
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(
                    this,
                    Manifest.permission.POST_NOTIFICATIONS
                ) != PackageManager.PERMISSION_GRANTED
            ) {
                permissionsToRequest.add(Manifest.permission.POST_NOTIFICATIONS)
            }
        }

        // Live Geolocation permission
        if (ContextCompat.checkSelfPermission(
                this,
                Manifest.permission.ACCESS_FINE_LOCATION
            ) != PackageManager.PERMISSION_GRANTED
        ) {
            permissionsToRequest.add(Manifest.permission.ACCESS_FINE_LOCATION)
            permissionsToRequest.add(Manifest.permission.ACCESS_COARSE_LOCATION)
        }

        if (permissionsToRequest.isNotEmpty()) {
            requestPermissionsLauncher.launch(permissionsToRequest.toTypedArray())
        }
    }

    // Android back button navigation inside WebView
    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }
}
