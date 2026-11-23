package studio.kontenlaris.skeleton

import android.app.AlertDialog
import android.graphics.Color
import android.os.Bundle
import android.view.Gravity
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Switch
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID
import java.util.concurrent.Executors

/**
 * Your Agent.
 *
 * Baru di v5 (Mode Agen):
 *  - Sakelar "Mode Agen": pesan dikirim ke /agent, bukan /chat/stream.
 *    Agen bisa memakai skill (kalkulator, web, catatan) lewat harness semi
 *    di backend. Jejak skill yang dipakai ditampilkan di bawah jawaban.
 *  - Aksi merusak dari agen TIDAK langsung jalan: aplikasi menampilkan
 *    dialog konfirmasi; hanya tombol "Setuju, jalankan" yang meneruskan
 *    confirm_token ke backend.
 *
 * Dari v4 (siap backend publik):
 *  - Token aplikasi: bila backend di-deploy dengan APP_TOKEN, aplikasi mengirim
 *    header X-App-Token. Token diatur dari dialog tombol URL, tersimpan lokal.
 *
 * Dari v3:
 *  - Jawaban STREAMING: Android membaca /chat/stream (SSE) dan menumbuhkan
 *    balon AI potongan demi potongan, seperti aplikasi chat AI beneran.
 *
 * Dari v2:
 *  - Balon chat berwarna (biru = kamu, abu = AI) + indikator "Sedang mengetik..."
 *  - Riwayat tampil tersimpan lokal (SharedPreferences) — chat tidak hilang saat aplikasi ditutup.
 *  - Percakapan memakai session_id: backend yang mengingat konteks, Android cukup kirim 1 pesan.
 *  - Tombol URL: ganti alamat backend dari aplikasi (untuk tes di HP fisik tanpa edit kode).
 *  - Tombol Hapus: bersihkan layar + reset ingatan sesi di backend.
 *
 * API key tetap TIDAK ada di aplikasi ini — key disimpan backend (.env).
 */
class MainActivity : AppCompatActivity() {

    private lateinit var chatContainer: LinearLayout
    private lateinit var scrollChat: ScrollView
    private lateinit var editMessage: EditText
    private lateinit var buttonSend: Button

    private val executor = Executors.newSingleThreadExecutor()
    private val prefs by lazy { getSharedPreferences("skeleton", MODE_PRIVATE) }

    private var backendUrl: String
        get() = prefs.getString("backend_url", "https://jawaadalah.pythonanywhere.com")!!
        set(value) = prefs.edit().putString("backend_url", value).apply()

    private var appToken: String
        get() = prefs.getString("app_token", "")!!
        set(value) = prefs.edit().putString("app_token", value).apply()

    private var sessionId: String
        get() = prefs.getString("session_id", null) ?: UUID.randomUUID().toString()
            .also { prefs.edit().putString("session_id", it).apply() }
        set(value) = prefs.edit().putString("session_id", value).apply()

    // Daftar pesan yang tampil: [{"fromUser": true/false, "text": "..."}]
    private val shown = mutableListOf<Pair<Boolean, String>>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        chatContainer = findViewById(R.id.chatContainer)
        scrollChat = findViewById(R.id.scrollChat)
        editMessage = findViewById(R.id.editMessage)
        buttonSend = findViewById(R.id.buttonSend)

        restoreChat()
        if (shown.isEmpty()) {
            addBubble("Halo! Saya Skele, asisten Your Agent v7. Tanya apa saja, atau aktifkan Mode Agen dan suruh saya bekerja: hitung, mencatat, mengingat, sampai membuatkan aplikasi, game, dan web. Tulis pesan, lalu tekan Kirim.", fromUser = false, save = true)
        }

        buttonSend.setOnClickListener {
            val text = editMessage.text.toString().trim()
            if (text.isEmpty()) return@setOnClickListener
            editMessage.text.clear()
            if (findViewById<Switch>(R.id.switchAgent).isChecked) sendAgent(text) else sendMessage(text)
        }
        findViewById<Button>(R.id.buttonClear).setOnClickListener { clearChat() }
        findViewById<Button>(R.id.buttonUrl).setOnClickListener { askBackendUrl() }
    }

    private fun sendMessage(text: String) {
        addBubble(text, fromUser = true, save = true)
        buttonSend.isEnabled = false
        val bubble = addBubble("Sedang mengetik...", fromUser = false, save = false)

        executor.execute {
            val full = StringBuilder()
            try {
                streamChat(text) { chunk ->
                    full.append(chunk)
                    runOnUiThread {
                        bubble.text = full.toString()
                        scrollChat.post { scrollChat.fullScroll(ScrollView.FOCUS_DOWN) }
                    }
                }
                if (full.isEmpty()) full.append("(jawaban kosong dari backend)")
            } catch (e: Exception) {
                if (full.isEmpty()) {
                    full.append(
                        "Gagal menghubungi backend: ${e.message}\n" +
                            "Pastikan backend jalan (python3 backend/main.py) dan alamatnya benar (tombol URL)."
                    )
                } else {
                    full.append("\n[Koneksi terputus di tengah jawaban]")
                }
            }
            runOnUiThread {
                bubble.text = full.toString()
                shown.add(false to full.toString())
                saveChat()
                buttonSend.isEnabled = true
            }
        }
    }

    /**
     * POST ke /chat/stream lalu baca event SSE baris demi baris:
     *   data: {"chunk": "..."}   -> onChunk dipanggil untuk tiap potongan
     *   data: {"done": true}     -> stream selesai
     *   data: {"error": "..."}   -> dilempar sebagai exception
     */
    private fun streamChat(text: String, onChunk: (String) -> Unit) {
        val body = JSONObject()
            .put("message", text)
            .put("session_id", sessionId)
            .toString()
        val conn = URL("$backendUrl/chat/stream").openConnection() as HttpURLConnection
        conn.requestMethod = "POST"
        conn.setRequestProperty("Content-Type", "application/json")
        if (appToken.isNotEmpty()) conn.setRequestProperty("X-App-Token", appToken)
        conn.connectTimeout = 10_000
        conn.readTimeout = 120_000
        conn.doOutput = true
        conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }

        if (conn.responseCode !in 200..299) {
            val response = conn.errorStream.bufferedReader().use { it.readText() }
            val msg = try { JSONObject(response).optString("error", response) } catch (_: Exception) { response }
            throw IllegalStateException("Backend menjawab ${conn.responseCode}: $msg")
        }

        conn.inputStream.bufferedReader().useLines { lines ->
            for (line in lines) {
                val trimmed = line.trim()
                if (!trimmed.startsWith("data:")) continue
                val event = JSONObject(trimmed.removePrefix("data:").trim())
                when {
                    event.has("chunk") -> onChunk(event.getString("chunk"))
                    event.has("error") -> throw IllegalStateException(event.getString("error"))
                    event.optBoolean("done") -> return
                }
            }
        }
    }

    // ------------------------------------------------------------- Mode Agen --
    private fun sendAgent(text: String) {
        addBubble(text, fromUser = true, save = true)
        buttonSend.isEnabled = false
        val bubble = addBubble("Agen sedang bekerja...", fromUser = false, save = false)

        executor.execute {
            var display = ""
            var confirmToken: String? = null
            var proposed = ""
            try {
                val json = postAgent(JSONObject().put("message", text).put("session_id", sessionId))
                display = json.optString("reply", "(tanpa jawaban)")
                val steps = json.optJSONArray("steps")
                if (steps != null && steps.length() > 0) {
                    val names = (0 until steps.length()).map { steps.getJSONObject(it).optString("skill") }
                    display += "\n\n— Jejak agen: " + names.joinToString(", ")
                }
                if (json.optBoolean("needs_confirmation")) {
                    confirmToken = json.optString("confirm_token")
                    proposed = json.optJSONObject("proposed")?.optString("skill") ?: "aksi agen"
                }
            } catch (e: Exception) {
                display = "Agen gagal: ${e.message}"
            }
            val token = confirmToken
            val skillName = proposed
            runOnUiThread {
                bubble.text = display
                shown.add(false to display)
                saveChat()
                buttonSend.isEnabled = true
                if (token != null) askConfirmation(skillName, token)
            }
        }
    }

    private fun askConfirmation(skillName: String, token: String) {
        AlertDialog.Builder(this)
            .setTitle("Konfirmasi aksi agen")
            .setMessage("Agen ingin menjalankan aksi merusak: $skillName.\nAksi ini belum dijalankan. Setuju?")
            .setPositiveButton("Setuju, jalankan") { _, _ ->
                buttonSend.isEnabled = false
                executor.execute {
                    val result = try {
                        val json = postAgent(JSONObject().put("session_id", sessionId).put("confirm_token", token))
                        json.optString("reply", "(selesai)")
                    } catch (e: Exception) {
                        "Konfirmasi gagal: ${e.message}"
                    }
                    runOnUiThread {
                        addBubble(result, fromUser = false, save = true)
                        buttonSend.isEnabled = true
                    }
                }
            }
            .setNegativeButton("Batal") { _, _ ->
                addBubble("Aksi $skillName dibatalkan — tidak ada yang dijalankan.", fromUser = false, save = true)
            }
            .show()
    }

    /** POST JSON ke /agent dengan header token (bila diatur). */
    private fun postAgent(body: JSONObject): JSONObject {
        val conn = URL("$backendUrl/agent").openConnection() as HttpURLConnection
        conn.requestMethod = "POST"
        conn.setRequestProperty("Content-Type", "application/json")
        if (appToken.isNotEmpty()) conn.setRequestProperty("X-App-Token", appToken)
        conn.connectTimeout = 10_000
        conn.readTimeout = 120_000
        conn.doOutput = true
        conn.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
        val stream = if (conn.responseCode in 200..299) conn.inputStream else conn.errorStream
        val response = stream.bufferedReader().use { it.readText() }
        val json = JSONObject(response)
        if (conn.responseCode !in 200..299) {
            throw IllegalStateException("Backend ${conn.responseCode}: ${json.optString("error", response)}")
        }
        return json
    }

    private fun clearChat() {
        val oldSession = sessionId
        sessionId = UUID.randomUUID().toString()
        shown.clear()
        saveChat()
        chatContainer.removeAllViews()
        executor.execute {
            try {
                val conn = URL("$backendUrl/reset").openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                conn.setRequestProperty("Content-Type", "application/json")
                if (appToken.isNotEmpty()) conn.setRequestProperty("X-App-Token", appToken)
                conn.doOutput = true
                val body = JSONObject().put("session_id", oldSession).toString()
                conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
                conn.inputStream.bufferedReader().use { it.readText() }
            } catch (_: Exception) { /* backend mati pun layar tetap dibersihkan */ }
        }
        addBubble("Chat dibersihkan. Kita mulai dari awal.", fromUser = false, save = true)
    }

    private fun askBackendUrl() {
        val urlInput = EditText(this).apply {
            setText(backendUrl)
            hint = "Publik: https://jawaadalah.pythonanywhere.com | Emulator: http://10.0.2.2:8000"
        }
        val tokenInput = EditText(this).apply {
            setText(appToken)
            hint = "Token aplikasi (kosongkan bila backend lokal tanpa APP_TOKEN)"
        }
        val container = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 16, 48, 8)
            addView(urlInput)
            addView(tokenInput)
        }
        AlertDialog.Builder(this)
            .setTitle("Alamat backend & token")
            .setView(container)
            .setPositiveButton("Simpan") { _, _ ->
                backendUrl = urlInput.text.toString().trim().trimEnd('/')
                appToken = tokenInput.text.toString().trim()
            }
            .setNegativeButton("Batal", null)
            .show()
    }

    private fun addBubble(text: String, fromUser: Boolean, save: Boolean): TextView {
        val bubble = TextView(this).apply {
            this.text = text
            textSize = 16f
            setBackgroundResource(if (fromUser) R.drawable.bubble_user else R.drawable.bubble_ai)
            setTextColor(if (fromUser) Color.WHITE else Color.BLACK)
        }
        val params = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        ).apply {
            gravity = if (fromUser) Gravity.END else Gravity.START
            setMargins(0, 6, 0, 6)
        }
        chatContainer.addView(bubble, params)
        scrollChat.post { scrollChat.fullScroll(ScrollView.FOCUS_DOWN) }
        if (save) {
            shown.add(fromUser to text)
            saveChat()
        }
        return bubble
    }

    private fun saveChat() {
        val arr = JSONArray()
        for ((fromUser, text) in shown) {
            arr.put(JSONObject().put("fromUser", fromUser).put("text", text))
        }
        prefs.edit().putString("chat_history", arr.toString()).apply()
    }

    private fun restoreChat() {
        val raw = prefs.getString("chat_history", null) ?: return
        try {
            val arr = JSONArray(raw)
            for (i in 0 until arr.length()) {
                val item = arr.getJSONObject(i)
                val fromUser = item.getBoolean("fromUser")
                val text = item.getString("text")
                shown.add(fromUser to text)
                // Gambar ulang tanpa menyimpan ulang.
                val bubble = TextView(this).apply {
                    this.text = text
                    textSize = 16f
                    setBackgroundResource(if (fromUser) R.drawable.bubble_user else R.drawable.bubble_ai)
                    setTextColor(if (fromUser) Color.WHITE else Color.BLACK)
                }
                val params = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                ).apply {
                    gravity = if (fromUser) Gravity.END else Gravity.START
                    setMargins(0, 6, 0, 6)
                }
                chatContainer.addView(bubble, params)
            }
        } catch (_: Exception) { /* riwayat rusak -> mulai bersih */ }
    }
}
