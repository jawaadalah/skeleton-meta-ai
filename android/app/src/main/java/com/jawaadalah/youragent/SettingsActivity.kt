package com.jawaadalah.youragent

import android.os.Bundle
import android.view.View
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.Spinner
import android.widget.Switch
import android.widget.TextView
import android.widget.Toast
import android.os.Handler
import android.os.Looper
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.app.AppCompatDelegate
import androidx.core.os.LocaleListCompat
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat

/**
 * Layar Pengaturan Your Agent (v11) — layar kedua selain chat:
 *  - Koneksi Server: alamat backend + token aplikasi.
 *  - Otak AI: preset provider (Groq, OpenRouter, OpenAI, Gemini, Kustom)
 *    atau bawaan server; API key milik pengguna sendiri (BYOK) tersimpan
 *    lokal di HP dan dikirim per permintaan — server tidak menyimpannya.
 *  - Fitur: Mode Agen bawaan & streaming jawaban.
 *  - Tentang: versi, deskripsi, dan daftar fitur aplikasi.
 */
class SettingsActivity : AppCompatActivity() {

    private val prefs by lazy { getSharedPreferences("skeleton", MODE_PRIVATE) }
    private val quotaExecutor = Executors.newSingleThreadExecutor()
    private val quotaHandler = Handler(Looper.getMainLooper())
    private lateinit var textQuota: TextView
    // Kuota LIVE: snapshot terakhir dari /health + tenggat reset (elapsedRealtime)
    // supaya hitung mundur berjalan per detik secara lokal di antara polling.
    private var lastQuota: JSONObject? = null
    private var lastModel: String = "-"
    private var tokenResetAtMs: Long = 0L
    private var requestResetAtMs: Long = 0L
    private val quotaPoll = object : Runnable {
        override fun run() {
            loadQuota()
            quotaHandler.postDelayed(this, 3_000)
        }
    }
    private val quotaTicker = object : Runnable {
        override fun run() {
            renderQuota()
            val now = android.os.SystemClock.elapsedRealtime()
            if ((tokenResetAtMs > 0 && now >= tokenResetAtMs) ||
                (requestResetAtMs > 0 && now >= requestResetAtMs)) {
                tokenResetAtMs = 0L
                requestResetAtMs = 0L
                loadQuota()
            }
            quotaHandler.postDelayed(this, 1_000)
        }
    }

    override fun onResume() {
        super.onResume()
        if (::textQuota.isInitialized) {
            quotaHandler.post(quotaPoll)
            quotaHandler.post(quotaTicker)
        }
    }

    override fun onPause() {
        quotaHandler.removeCallbacks(quotaPoll)
        quotaHandler.removeCallbacks(quotaTicker)
        super.onPause()
    }

    private fun loadQuota() {
        val base = (prefs.getString("backend_url", "https://jawaadalah.pythonanywhere.com")
            ?: "https://jawaadalah.pythonanywhere.com").trimEnd('/')
        quotaExecutor.execute {
            try {
                val conn = (URL(base + "/health").openConnection() as HttpURLConnection).apply {
                    connectTimeout = 8000
                    readTimeout = 8000
                }
                val health = JSONObject(conn.inputStream.bufferedReader().use { it.readText() })
                lastModel = health.optString("model", "-")
                val quota = health.optJSONObject("quota")
                if (quota != null) {
                    lastQuota = quota
                    val now = android.os.SystemClock.elapsedRealtime()
                    tokenResetAtMs = parseDurationSec(quota.optString("reset_tokens", ""))
                        ?.let { now + (it * 1000).toLong() } ?: 0L
                    requestResetAtMs = parseDurationSec(quota.optString("reset_requests", ""))
                        ?.let { now + (it * 1000).toLong() } ?: 0L
                }
                runOnUiThread { renderQuota() }
            } catch (e: Exception) {
                runOnUiThread {
                    // Live: gagal sesaat tidak menghapus angka terakhir yang tampil.
                    if (::textQuota.isInitialized && lastQuota == null) {
                        textQuota.text = getString(R.string.quota_failed,
                            e.message ?: getString(R.string.quota_conn_problem))
                    }
                }
            }
        }
    }

    /** Urai durasi gaya Go dari header provider ("22.59s", "1m30s", "350ms") menjadi detik. */
    private fun parseDurationSec(raw: String): Double? {
        if (raw.isBlank()) return null
        var total = 0.0
        var matched = false
        for (m in Regex("""(\d+(?:\.\d+)?)(ms|s|m|h)""").findAll(raw)) {
            matched = true
            val v = m.groupValues[1].toDouble()
            total += when (m.groupValues[2]) {
                "ms" -> v / 1000.0
                "s" -> v
                "m" -> v * 60.0
                else -> v * 3600.0
            }
        }
        return if (matched) total else null
    }

    private fun fmtCountdown(deadlineMs: Long): String {
        val sisa = (deadlineMs - android.os.SystemClock.elapsedRealtime() + 999) / 1000
        if (sisa <= 0) return getString(R.string.countdown_now)
        return if (sisa < 60) sisa.toString() + "d"
        else (sisa / 60).toString() + "m " + (sisa % 60).toString() + "d"
    }

    /** Gambar ulang kartu kuota dari snapshot terakhir + hitung mundur saat ini. */
    private fun renderQuota() {
        if (!::textQuota.isInitialized) return
        val quota = lastQuota
        textQuota.text = if (quota == null) {
            getString(R.string.quota_model_active, lastModel) + "\n" +
                getString(R.string.quota_not_ready)
        } else {
            val fmt = java.text.NumberFormat.getInstance(
                resources.configuration.locales.get(0))
            fun n(key: String): String {
                val v = quota.optLong(key, -1)
                return if (v >= 0) fmt.format(v) else "?"
            }
            getString(R.string.quota_model_active, lastModel) + "\n" +
                getString(R.string.quota_tokens, n("remaining_tokens"), n("limit_tokens")) + "\n" +
                getString(R.string.quota_requests, n("remaining_requests"), n("limit_requests")) +
                (if (tokenResetAtMs > 0) "\n" + getString(R.string.quota_reset_tokens, fmtCountdown(tokenResetAtMs)) else "") +
                (if (requestResetAtMs > 0) "\n" + getString(R.string.quota_reset_requests, fmtCountdown(requestResetAtMs)) else "")
        }
    }

    private data class Preset(val nama: String, val baseUrl: String, val model: String)

    private val presets = listOf(
        Preset("Bawaan server", "", ""),
        Preset("Groq", "https://api.groq.com/openai/v1", "openai/gpt-oss-120b"),
        Preset("OpenRouter", "https://openrouter.ai/api/v1", "meta-llama/llama-3.3-70b-instruct"),
        Preset("OpenAI", "https://api.openai.com/v1", "gpt-4o-mini"),
        Preset("Google Gemini", "https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-2.0-flash"),
        Preset("Kustom", "", "")
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        window.statusBarColor = android.graphics.Color.TRANSPARENT
        window.navigationBarColor = android.graphics.Color.TRANSPARENT
        setContentView(R.layout.activity_settings)
        val root = findViewById<View>(R.id.settingsRoot)
        WindowInsetsControllerCompat(window, root).apply {
            isAppearanceLightStatusBars = false
            isAppearanceLightNavigationBars = false
        }
        ViewCompat.setOnApplyWindowInsetsListener(root) { v, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            insets
        }

        val editBackend = findViewById<EditText>(R.id.editBackendUrl)
        val editToken = findViewById<EditText>(R.id.editAppToken)
        val spinner = findViewById<Spinner>(R.id.spinnerProvider)
        val editBase = findViewById<EditText>(R.id.editLlmBase)
        val editModel = findViewById<EditText>(R.id.editLlmModel)
        val editKey = findViewById<EditText>(R.id.editLlmKey)
        val spinnerTheme = findViewById<Spinner>(R.id.spinnerTheme)
        val themeNames = listOf(getString(R.string.theme_navy), getString(R.string.theme_bright),
            getString(R.string.theme_amoled))
        val themeAdapter = ArrayAdapter(this, R.layout.spinner_item, themeNames)
        themeAdapter.setDropDownViewResource(R.layout.spinner_dropdown)
        spinnerTheme.adapter = themeAdapter
        spinnerTheme.setSelection(prefs.getInt("tema", 0).coerceIn(0, themeNames.size - 1))
        val languages = listOf(
            "Bahasa Indonesia" to "id", "English" to "en", "Español" to "es",
            "中文" to "zh", "العربية" to "ar", "हिन्दी" to "hi",
            "Português" to "pt", "Français" to "fr", "Deutsch" to "de",
            "日本語" to "ja", "한국어" to "ko", "Русский" to "ru")
        val spinnerLanguage = findViewById<Spinner>(R.id.spinnerLanguage)
        val langAdapter = ArrayAdapter(this, R.layout.spinner_item, languages.map { it.first })
        langAdapter.setDropDownViewResource(R.layout.spinner_dropdown)
        spinnerLanguage.adapter = langAdapter
        val currentLang = prefs.getString("bahasa", "id") ?: "id"
        spinnerLanguage.setSelection(
            languages.indexOfFirst { it.second == currentLang }.coerceAtLeast(0))
        spinnerLanguage.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, pos: Int, id: Long) {
                val code = languages[pos].second
                if (code != (prefs.getString("bahasa", "id") ?: "id")) {
                    prefs.edit().putString("bahasa", code).apply()
                    AppCompatDelegate.setApplicationLocales(
                        LocaleListCompat.forLanguageTags(code))
                }
            }

            override fun onNothingSelected(parent: AdapterView<*>?) {}
        }
        val switchAgentDefault = findViewById<Switch>(R.id.switchAgentDefault)
        val switchStreaming = findViewById<Switch>(R.id.switchStreaming)

        editBackend.setText(prefs.getString("backend_url", "https://jawaadalah.pythonanywhere.com"))
        editToken.setText(prefs.getString("app_token", ""))
        editBase.setText(prefs.getString("llm_base_url", ""))
        editModel.setText(prefs.getString("llm_model", ""))
        editKey.setText(prefs.getString("llm_api_key", ""))
        switchAgentDefault.isChecked = prefs.getBoolean("agent_default", false)
        switchStreaming.isChecked = prefs.getBoolean("streaming", true)

        val adapter = ArrayAdapter(this, R.layout.spinner_item, presets.map { it.nama })
        adapter.setDropDownViewResource(R.layout.spinner_dropdown)
        spinner.adapter = adapter
        spinner.setSelection(prefs.getInt("llm_preset", 0).coerceIn(0, presets.size - 1))
        spinner.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, pos: Int, id: Long) {
                val p = presets[pos]
                if (p.nama != "Kustom" && p.nama != "Bawaan server") {
                    editBase.setText(p.baseUrl)
                    editModel.setText(p.model)
                } else if (p.nama == "Bawaan server") {
                    editBase.setText("")
                    editModel.setText("")
                }
            }

            override fun onNothingSelected(parent: AdapterView<*>?) {}
        }

        val versionName = try {
            packageManager.getPackageInfo(packageName, 0).versionName ?: "?"
        } catch (_: Exception) {
            "?"
        }
        textQuota = findViewById(R.id.textQuota)
        loadQuota()
        findViewById<TextView>(R.id.textAbout).text = getString(R.string.about_text, versionName)

        findViewById<Button>(R.id.buttonBack).setOnClickListener { finish() }
        findViewById<Button>(R.id.buttonExitApp).setOnClickListener { finishAffinity() }
        findViewById<Button>(R.id.buttonSaveSettings).setOnClickListener {
            prefs.edit()
                .putString("backend_url", editBackend.text.toString().trim().trimEnd('/'))
                .putString("app_token", editToken.text.toString().trim())
                .putInt("llm_preset", spinner.selectedItemPosition)
                .putString("llm_base_url", editBase.text.toString().trim())
                .putString("llm_model", editModel.text.toString().trim())
                .putString("llm_api_key", editKey.text.toString().trim())
                .putInt("tema", spinnerTheme.selectedItemPosition)
                .putBoolean("agent_default", switchAgentDefault.isChecked)
                .putBoolean("streaming", switchStreaming.isChecked)
                .apply()
            Toast.makeText(this, getString(R.string.saved_toast), Toast.LENGTH_SHORT).show()
            finish()
        }
    }
}
