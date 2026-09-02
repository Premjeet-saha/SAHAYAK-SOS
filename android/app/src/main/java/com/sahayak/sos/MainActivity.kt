package com.sahayak.sos

import android.Manifest
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.net.ConnectivityManager
import android.net.Network
import android.os.Bundle
import android.os.Looper
import android.telephony.SmsManager
import android.webkit.JavascriptInterface
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID

class MainActivity : ComponentActivity() {

    private lateinit var webView: WebView
    private lateinit var locationManager: LocationManager
    private lateinit var connectivityManager: ConnectivityManager
    private lateinit var networkCallback: ConnectivityManager.NetworkCallback

    // Emergency / relay phone number
    private val emergencyNumber = "7666886291"

    // Flask backend
    private val backendUrl =
        "http://172.21.198.142:5000"

    private val prefsName = "sahayak_offline_storage"
    private val sosListKey = "pending_sos"

    companion object {
        private const val LOCATION_PERMISSION = 100
        private const val SMS_PERMISSION = 101
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        locationManager =
            getSystemService(LOCATION_SERVICE) as LocationManager

        connectivityManager =
            getSystemService(CONNECTIVITY_SERVICE) as ConnectivityManager

        webView = WebView(this)

        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.settings.useWideViewPort = true
        webView.settings.loadWithOverviewMode = true

        webView.webViewClient = WebViewClient()

        webView.addJavascriptInterface(
            AndroidBridge(),
            "Android"
        )

        webView.loadUrl(
            "file:///android_asset/index.html"
        )

        setContentView(webView)
        if (ContextCompat.checkSelfPermission(
                this,
                Manifest.permission.ACCESS_FINE_LOCATION
            ) != PackageManager.PERMISSION_GRANTED ||
            ContextCompat.checkSelfPermission(
                this,
                Manifest.permission.SEND_SMS
            ) != PackageManager.PERMISSION_GRANTED
        ) {

            ActivityCompat.requestPermissions(
                this,
                arrayOf(
                    Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.SEND_SMS
                ),
                LOCATION_PERMISSION
            )
        }
        // Check for pending SOS when app starts
        syncPendingSOS()

        // Automatically sync when network becomes available
        registerNetworkCallback()
    }

    // ============================================================
    // JAVASCRIPT → ANDROID
    // ============================================================

    inner class AndroidBridge {

        @JavascriptInterface
        fun sendOfflineSOS(emergencyText: String) {

            if (ContextCompat.checkSelfPermission(
                    this@MainActivity,
                    Manifest.permission.ACCESS_FINE_LOCATION
                ) != PackageManager.PERMISSION_GRANTED
            ) {
                ActivityCompat.requestPermissions(
                    this@MainActivity,
                    arrayOf(Manifest.permission.ACCESS_FINE_LOCATION),
                    LOCATION_PERMISSION
                )

                runOnUiThread {
                    Toast.makeText(
                        this@MainActivity,
                        "Location permission required. Press SOS again.",
                        Toast.LENGTH_LONG
                    ).show()
                }

                return
            }

            getLocationAndSendSms(emergencyText)
        }

    }

    @JavascriptInterface
    fun isNetworkAvailable(): Boolean {

        val connectivityManager =
            getSystemService(CONNECTIVITY_SERVICE)
                    as ConnectivityManager

        val network =
            connectivityManager.activeNetwork
                ?: return false

        val capabilities =
            connectivityManager.getNetworkCapabilities(network)
                ?: return false

        return capabilities.hasCapability(
            android.net.NetworkCapabilities.NET_CAPABILITY_INTERNET
        ) &&
                capabilities.hasCapability(
                    android.net.NetworkCapabilities.NET_CAPABILITY_VALIDATED
                )
    }
    // ============================================================
    // GET GPS LOCATION
    // ============================================================

    private fun getLocationAndSendSms(
        emergencyText: String
    ) {

        if (!locationManager.isProviderEnabled(
                LocationManager.GPS_PROVIDER
            )
        ) {
            runOnUiThread {
                Toast.makeText(
                    this,
                    "Please enable Location/GPS",
                    Toast.LENGTH_LONG
                ).show()
            }
            return
        }

        try {

            // First try last known GPS location
            val lastLocation =
                locationManager.getLastKnownLocation(
                    LocationManager.GPS_PROVIDER
                )

            if (lastLocation != null) {

                processOfflineSOS(
                    emergencyText,
                    lastLocation.latitude,
                    lastLocation.longitude
                )

                return
            }

            // If no previous location exists, request a fresh GPS location
            val listener = object : LocationListener {

                override fun onLocationChanged(
                    location: Location
                ) {

                    processOfflineSOS(
                        emergencyText,
                        location.latitude,
                        location.longitude
                    )

                    locationManager.removeUpdates(this)
                }
            }

            locationManager.requestLocationUpdates(
                LocationManager.GPS_PROVIDER,
                1000L,
                1f,
                listener,
                Looper.getMainLooper()
            )

            runOnUiThread {
                Toast.makeText(
                    this,
                    "Getting GPS location...",
                    Toast.LENGTH_SHORT
                ).show()
            }

        } catch (e: SecurityException) {

            runOnUiThread {
                Toast.makeText(
                    this,
                    "Location permission denied",
                    Toast.LENGTH_LONG
                ).show()
            }
        }
    }


// ============================================================
// PROCESS OFFLINE SOS
// ============================================================

    private fun processOfflineSOS(
        emergencyText: String,
        lat: Double,
        lng: Double
    ) {

        val incidentId = generateIncidentId()
        val timestamp = getCurrentTimestamp()

        // Save SOS locally first
        saveSOSLocally(
            incidentId = incidentId,
            emergencyText = emergencyText,
            latitude = lat,
            longitude = lng,
            timestamp = timestamp
        )

        val message =
            "SAHAYAK SOS\n" +
                    "ID: $incidentId\n" +
                    "Emergency assistance required.\n" +
                    "Location: %.6f, %.6f\n".format(
                        lat,
                        lng
                    ) +
                    "Emergency: $emergencyText"

        // Send SMS
        sendSms(message)

        // Try syncing if internet is available
        syncPendingSOS()
    }

    // ============================================================
    // GENERATE UNIQUE SOS ID
    // ============================================================

    private fun generateIncidentId(): String {

        val shortId =
            UUID.randomUUID()
                .toString()
                .substring(0, 8)
                .uppercase()

        return "OFF-$shortId"
    }

    // ============================================================
    // CURRENT TIMESTAMP
    // ============================================================

    private fun getCurrentTimestamp(): String {

        val formatter =
            SimpleDateFormat(
                "yyyy-MM-dd'T'HH:mm:ss",
                Locale.getDefault()
            )

        return formatter.format(Date())
    }

    // ============================================================
    // SAVE SOS LOCALLY
    // ============================================================

    private fun saveSOSLocally(
        incidentId: String,
        emergencyText: String,
        latitude: Double,
        longitude: Double,
        timestamp: String
    ) {

        try {

            val prefs =
                getSharedPreferences(
                    prefsName,
                    MODE_PRIVATE
                )

            val existingData =
                prefs.getString(
                    sosListKey,
                    "[]"
                )

            val sosArray =
                JSONArray(existingData)

            val sos =
                JSONObject()

            sos.put(
                "client_incident_id",
                incidentId
            )

            sos.put(
                "emergency_text",
                emergencyText
            )

            sos.put(
                "latitude",
                latitude
            )

            sos.put(
                "longitude",
                longitude
            )

            sos.put(
                "timestamp",
                timestamp
            )

            sos.put(
                "sms_status",
                "sent"
            )

            sos.put(
                "sync_status",
                "pending"
            )

            sosArray.put(sos)

            prefs.edit()
                .putString(
                    sosListKey,
                    sosArray.toString()
                )
                .apply()

            Toast.makeText(
                this,
                "SOS saved locally: $incidentId",
                Toast.LENGTH_SHORT
            ).show()

        } catch (e: Exception) {

            Toast.makeText(
                this,
                "Local storage failed: ${e.message}",
                Toast.LENGTH_LONG
            ).show()
        }
    }

    // ============================================================
    // SEND SMS
    // ============================================================

    private fun sendSms(message: String) {

        if (ContextCompat.checkSelfPermission(
                this,
                Manifest.permission.SEND_SMS
            ) != PackageManager.PERMISSION_GRANTED
        ) {

            ActivityCompat.requestPermissions(
                this,
                arrayOf(
                    Manifest.permission.SEND_SMS
                ),
                SMS_PERMISSION
            )

            Toast.makeText(
                this,
                "SMS permission required. Press SOS again.",
                Toast.LENGTH_LONG
            ).show()

            return
        }

        try {

            val smsManager =
                SmsManager.getDefault()

            smsManager.sendTextMessage(
                emergencyNumber,
                null,
                message,
                null,
                null
            )

            Toast.makeText(
                this,
                "SOS SMS sent successfully",
                Toast.LENGTH_LONG
            ).show()

        } catch (e: Exception) {

            Toast.makeText(
                this,
                "SMS failed: ${e.message}",
                Toast.LENGTH_LONG
            ).show()
        }
    }

    // ============================================================
    // CHECK INTERNET / NETWORK
    // ============================================================

    private fun registerNetworkCallback() {

        val request =
            android.net.NetworkRequest.Builder()
                .build()

        networkCallback =
            object : ConnectivityManager.NetworkCallback() {

                override fun onAvailable(
                    network: Network
                ) {

                    runOnUiThread {

                        Toast.makeText(
                            this@MainActivity,
                            "Internet available - syncing SOS...",
                            Toast.LENGTH_SHORT
                        ).show()
                    }

                    syncPendingSOS()
                }
            }

        connectivityManager.registerNetworkCallback(
            request,
            networkCallback
        )
    }

    // ============================================================
    // SYNC PENDING SOS
    // ============================================================

    private fun syncPendingSOS() {

        Thread {

            try {

                val prefs =
                    getSharedPreferences(
                        prefsName,
                        MODE_PRIVATE
                    )

                val existingData =
                    prefs.getString(
                        sosListKey,
                        "[]"
                    )

                val sosArray =
                    JSONArray(existingData)

                if (sosArray.length() == 0) {
                    return@Thread
                }

                for (i in 0 until sosArray.length()) {

                    val sos =
                        sosArray.getJSONObject(i)

                    val status =
                        sos.optString(
                            "sync_status",
                            "pending"
                        )

                    if (status != "pending") {
                        continue
                    }

                    val success =
                        sendSOSToBackend(sos)

                    if (success) {

                        sos.put(
                            "sync_status",
                            "synced"
                        )

                        runOnUiThread {

                            Toast.makeText(
                                this@MainActivity,
                                "SOS synced to backend",
                                Toast.LENGTH_SHORT
                            ).show()
                        }
                    }
                }

                // Save updated statuses
                prefs.edit()
                    .putString(
                        sosListKey,
                        sosArray.toString()
                    )
                    .apply()

            } catch (e: Exception) {

                // Internet may not actually be available.
                // Keep SOS as pending.
            }

        }.start()
    }

    // ============================================================
    // SEND ONE SOS TO FLASK
    // ============================================================

    private fun sendSOSToBackend(
        sos: JSONObject
    ): Boolean {

        var connection:
                HttpURLConnection? = null

        return try {

            val url =
                URL(
                    "$backendUrl/report-emergency"
                )

            connection =
                url.openConnection()
                        as HttpURLConnection

            connection.requestMethod = "POST"

            connection.setRequestProperty(
                "Content-Type",
                "application/json"
            )

            connection.connectTimeout = 5000
            connection.readTimeout = 5000
            connection.doOutput = true

            // Build request for Flask

            val request = JSONObject()

            request.put(
                "client_incident_id",
                sos.getString("client_incident_id")
            )

            request.put(
                "client_timestamp",
                sos.getString("timestamp")
            )

            request.put(
                "raw_input",
                sos.getString("emergency_text")
            )

            request.put("type", "text")

            request.put(
                "lat",
                sos.getDouble("latitude")
            )

            request.put(
                "lng",
                sos.getDouble("longitude")
            )

            request.put("location_source", "gps")

            val responseCode =
                connection.responseCode

            responseCode in 200..299

        } catch (e: Exception) {

            runOnUiThread {
                Toast.makeText(
                    this@MainActivity,
                    "SYNC ERROR: ${e.message}",
                    Toast.LENGTH_LONG
                ).show()
            }

            false
        } finally {

            connection?.disconnect()
        }
    }

    override fun onDestroy() {

        try {
            connectivityManager.unregisterNetworkCallback(
                networkCallback
            )
        } catch (e: Exception) {
            // Ignore
        }

        super.onDestroy()
    }
}