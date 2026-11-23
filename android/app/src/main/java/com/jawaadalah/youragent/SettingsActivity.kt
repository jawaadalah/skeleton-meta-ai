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
import androidx.appcompat.app.AppCompatActivity
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
        val themeNames = listOf("Premium Navy (gelap)", "Terang", "AMOLED (hitam pekat)")
        val themeAdapter = ArrayAdapter(this, R.layout.spinner_item, themeNames)
        themeAdapter.setDropDownViewResource(R.layout.spinner_dropdown)
        spinnerTheme.adapter = themeAdapter
        spinnerTheme.setSelection(prefs.getInt("tema", 0).coerceIn(0, themeNames.size - 1))
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
        findViewById<TextView>(R.id.textAbout).text =
            "Your Agent v$versionName — asisten AI pribadi dengan Mode Agen dan Pabrik APK.\n\n" +
                "Fitur utama:\n" +
                "• Chat streaming dengan otak AI pilihanmu (BYOK: Groq, OpenRouter, OpenAI, Gemini, atau server sendiri)\n" +
                "• Mode Agen: 15 skill — kalkulator, catatan, ingatan jangka panjang, ambil web, generator proyek\n" +
                "• Pabrik APK: buat aplikasi & game Android jadi file APK asli dari chat\n" +
                "• Generator Cerdas: kode ditulis AI mengikuti instruksimu, dicek validator, fallback template\n" +
                "• Gerbang konfirmasi untuk aksi merusak\n" +
                "• Riwayat chat lokal + sesi & ingatan tersimpan di backend\n\n" +
                "Backend: jawaadalah.pythonanywhere.com\n" +
                "Kode sumber: github.com/jawaadalah/your-agent\n" +
                "Dibuat oleh Jawaadalah (J-DEV)."

        findViewById<Button>(R.id.buttonBack).setOnClickListener { finish() }
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
            Toast.makeText(this, "Pengaturan tersimpan", Toast.LENGTH_SHORT).show()
            finish()
        }
    }
}
