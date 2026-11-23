package com.jawaadalah.youragent

import android.app.AlertDialog
import android.content.Intent
import android.content.res.ColorStateList
import android.graphics.drawable.GradientDrawable
import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.Spannable
import android.text.SpannableStringBuilder
import android.text.method.LinkMovementMethod
import android.text.style.StyleSpan
import android.text.style.TypefaceSpan
import android.text.util.Linkify
import android.view.Gravity
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Switch
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.SocketTimeoutException
import java.net.URL
import java.net.UnknownHostException
import java.util.UUID
import java.util.concurrent.Executors

/**
 * Your Agent — aplikasi chat Android (Kotlin, tanpa library HTTP tambahan).
 *
 * v9 (optimalisasi mobile + premium):
 *  - Edge-to-edge modern (targetSdk 35): konten menghormati status bar,
 *    navigation bar, dan keyboard lewat WindowInsets.
 *  - Balasan AI dirender markdown ringan: **tebal**, *miring*, `kode`,
 *    judul #, dan tautan yang bisa diketuk (termasuk link unduh APK).
 *  - Indikator mengetik beranimasi titik, tombol kirim meredup saat sibuk.
 *  - Enter/ tombol kirim IME langsung mengirim pesan.
 *  - Pesan error ramah Bahasa Indonesia (koneksi/ timeout dibedakan).
 *
 * v8: link di balasan agen bisa diketuk (unduh APK pabrik).
 * v5: Mode Agen (/agent + skill + gerbang konfirmasi aksi merusak).
 * v4: APP_TOKEN opsional. v3: streaming SSE /chat/stream.
 * v2: session_id backend, riwayat lokal SharedPreferences, tombol URL/Hapus.
 *
 * API key TIDAK ada di aplikasi — key disimpan backend (.env).
 */
class MainActivity : AppCompatActivity() {

    private lateinit var chatContainer: LinearLayout
    private lateinit var scrollChat: ScrollView
    private lateinit var editMessage: EditText
    private lateinit var buttonSend: Button

    private val executor = Executors.newSingleThreadExecutor()
    private val prefs by lazy { getSharedPreferences("skeleton", MODE_PRIVATE) }
    private val uiHandler = Handler(Looper.getMainLooper())
    private var typingRunnable: Runnable? = null

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

    private val shown = mutableListOf<Pair<Boolean, String>>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Edge-to-edge: gambar di belakang system bars, atur padding via insets.
        WindowCompat.setDecorFitsSystemWindows(window, false)
        // Fullscreen tepi-ke-tepi: bar sistem transparan, gradasi aplikasi
        // mengisi sampai tepi atas & bawah layar (v12).
        window.statusBarColor = Color.TRANSPARENT
        window.navigationBarColor = Color.TRANSPARENT
        setContentView(R.layout.activity_main)
        val root = findViewById<View>(R.id.rootLayout)
        WindowInsetsControllerCompat(window, root).apply {
            isAppearanceLightStatusBars = false
            isAppearanceLightNavigationBars = false
        }
        ViewCompat.setOnApplyWindowInsetsListener(root) { v, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            val ime = insets.getInsets(WindowInsetsCompat.Type.ime())
            v.setPadding(bars.left, bars.top, bars.right, maxOf(bars.bottom, ime.bottom))
            insets
        }

        chatContainer = findViewById(R.id.chatContainer)
        scrollChat = findViewById(R.id.scrollChat)
        editMessage = findViewById(R.id.editMessage)
        buttonSend = findViewById(R.id.buttonSend)

        // SETELAH semua view terikat: applyTheme menyentuh editMessage dll.
        // (v12.0/12.1 crash di sini — applyTheme dipanggil sebelum inisialisasi.)
        applyTheme()
        restoreChat()
        if (shown.isEmpty()) {
            addBubble(
                "Halo! Saya Skele, asisten Your Agent. Tanya apa saja — atau aktifkan **Mode Agen** lalu suruh saya bekerja: menghitung, mencatat, mengingat, membuat halaman web, sampai membuatkan **aplikasi & game Android jadi APK**. Coba tulis: buatkan game android Balap Kelereng jadi apk",
                fromUser = false, save = true
            )
        }

        findViewById<Switch>(R.id.switchAgent).isChecked = prefs.getBoolean("agent_default", false)
        paintAgentSwitch()
        findViewById<Switch>(R.id.switchAgent).setOnCheckedChangeListener { _, _ -> paintAgentSwitch() }
        buttonSend.setOnClickListener { trySend() }
        editMessage.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_SEND) { trySend(); true } else false
        }
        findViewById<Button>(R.id.buttonClear).setOnClickListener { clearChat() }
        findViewById<Button>(R.id.buttonSettings).setOnClickListener {
            startActivity(Intent(this, SettingsActivity::class.java))
        }
    }

    private fun trySend() {
        val text = editMessage.text.toString().trim()
        if (text.isEmpty() || !buttonSend.isEnabled) return
        editMessage.text.clear()
        when {
            findViewById<Switch>(R.id.switchAgent).isChecked -> sendAgent(text)
            prefs.getBoolean("streaming", true) -> sendMessage(text)
            else -> sendMessageOnce(text)
        }
    }

    private fun setBusy(busy: Boolean) {
        buttonSend.isEnabled = !busy
        buttonSend.alpha = if (busy) 0.45f else 1f
    }

    // ------------------------------------------------------------ indikator --
    private fun startTyping(bubble: TextView, base: String) {
        stopTyping()
        var dots = 0
        val runnable = object : Runnable {
            override fun run() {
                dots = (dots + 1) % 4
                bubble.text = base + ".".repeat(dots)
                uiHandler.postDelayed(this, 450)
            }
        }
        typingRunnable = runnable
        bubble.text = base
        uiHandler.postDelayed(runnable, 450)
    }

    private fun stopTyping() {
        typingRunnable?.let { uiHandler.removeCallbacks(it) }
        typingRunnable = null
    }


    /** Objek "llm" untuk body request (v11): override otak AI dari Pengaturan.
     *  null bila semua kosong (pakai bawaan server). */
    private fun llmOverrideJson(): JSONObject? {
        val base = prefs.getString("llm_base_url", "")!!.trim()
        val model = prefs.getString("llm_model", "")!!.trim()
        val key = prefs.getString("llm_api_key", "")!!.trim()
        if (base.isEmpty() && model.isEmpty() && key.isEmpty()) return null
        val obj = JSONObject()
        if (base.isNotEmpty()) obj.put("base_url", base)
        if (model.isNotEmpty()) obj.put("model", model)
        if (key.isNotEmpty()) obj.put("api_key", key)
        return obj
    }

    /** Chat sekali kirim (streaming mati di Pengaturan): POST /chat biasa. */
    private fun sendMessageOnce(text: String) {
        addBubble(text, fromUser = true, save = true)
        setBusy(true)
        val bubble = addBubble("", fromUser = false, save = false)
        startProcessLog(bubble, listOf("Menghubungi backend", "Skele sedang berpikir", "Menyusun jawaban"))
        executor.execute {
            val display = try {
                val body = JSONObject().put("message", text).put("session_id", sessionId)
                llmOverrideJson()?.let { body.put("llm", it) }
                val conn = URL("$backendUrl/chat").openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                conn.setRequestProperty("Content-Type", "application/json")
                if (appToken.isNotEmpty()) conn.setRequestProperty("X-App-Token", appToken)
                conn.connectTimeout = 15_000
                conn.readTimeout = 120_000
                conn.doOutput = true
                conn.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
                val stream = if (conn.responseCode in 200..299) conn.inputStream else conn.errorStream
                val response = stream?.bufferedReader()?.use { it.readText() } ?: ""
                val json = try { JSONObject(response) } catch (_: Exception) { JSONObject() }
                if (conn.responseCode !in 200..299) {
                    throw IllegalStateException("Backend ${conn.responseCode}: ${json.optString("error", response)}")
                }
                json.optString("reply", "(jawaban kosong dari backend)")
            } catch (e: Exception) {
                friendlyError(e)
            }
            runOnUiThread {
                stopProcessLog()
                setBubbleFormatted(bubble, display)
                shown.add(false to display)
                saveChat()
                setBusy(false)
                scrollChat.post { scrollChat.fullScroll(ScrollView.FOCUS_DOWN) }
            }
        }
    }


    // ------------------------------------------------------------ tema (v12) --
    /** Palet tema aplikasi: 0 Premium Navy, 1 Terang, 2 AMOLED. */
    private data class ThemeColors(val bgTop: Int, val bgBottom: Int, val surface: Int,
                                   val input: Int, val textPri: Int, val textSec: Int,
                                   val bubbleAi: Int)

    private lateinit var theme: ThemeColors
    private var appliedTheme = -1

    private fun themeColors(): ThemeColors = when (prefs.getInt("tema", 0)) {
        1 -> ThemeColors(Color.parseColor("#F2F5FA"), Color.parseColor("#E4EBF8"),
            Color.WHITE, Color.WHITE, Color.parseColor("#14213D"),
            Color.parseColor("#5A6B8C"), Color.WHITE)
        2 -> ThemeColors(Color.BLACK, Color.BLACK, Color.parseColor("#0D0D10"),
            Color.parseColor("#111114"), Color.parseColor("#E8EDF7"),
            Color.parseColor("#9AA7C2"), Color.parseColor("#111114"))
        else -> ThemeColors(Color.parseColor("#0B1020"), Color.parseColor("#0A1230"),
            Color.parseColor("#121830"), Color.parseColor("#1C2442"),
            Color.parseColor("#EDF1FF"), Color.parseColor("#9AA6C7"),
            Color.parseColor("#1A2138"))
    }

    private fun roundedBg(color: Int, radiusDp: Float): GradientDrawable =
        GradientDrawable().apply {
            setColor(color)
            cornerRadius = radiusDp * resources.displayMetrics.density
        }

    /** Terapkan tema ke rangka layar utama (bubble diatur per-bubble). */
    private fun applyTheme() {
        theme = themeColors()
        appliedTheme = prefs.getInt("tema", 0)
        findViewById<LinearLayout>(R.id.rootLayout).background =
            GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,
                intArrayOf(theme.bgTop, theme.bgBottom))
        findViewById<LinearLayout>(R.id.agentBar).background = roundedBg(theme.surface, 18f)
        findViewById<Switch>(R.id.switchAgent).setTextColor(theme.textPri)
        editMessage.background = roundedBg(theme.input, 24f)
        editMessage.setTextColor(theme.textPri)
        editMessage.setHintTextColor(theme.textSec)
    }

    /** Warna sakelar Mode Agen: hijau LIVE / merah MATI + label status. */
    private fun paintAgentSwitch() {
        val sw = findViewById<Switch>(R.id.switchAgent)
        val green = Color.parseColor("#22C55E")
        val red = Color.parseColor("#EF4444")
        val c = if (sw.isChecked) green else red
        sw.thumbTintList = ColorStateList.valueOf(c)
        sw.trackTintList = ColorStateList.valueOf(
            Color.argb(110, Color.red(c), Color.green(c), Color.blue(c)))
        val st = findViewById<TextView>(R.id.textAgentStatus)
        st.text = if (sw.isChecked) "● LIVE" else "● MATI"
        st.setTextColor(c)
    }

    override fun onResume() {
        super.onResume()
        if (appliedTheme != -1 && prefs.getInt("tema", 0) != appliedTheme) recreate()
    }

    // ------------------------------------------------------- log proses live --
    private var logHandler: Handler? = null

    /** Log proses live di bubble: fase berjalan + timer detik, sampai selesai. */
    private fun startProcessLog(bubble: TextView, phases: List<String>) {
        stopProcessLog()
        val h = Handler(Looper.getMainLooper())
        logHandler = h
        val start = System.currentTimeMillis()
        var tick = 0
        val runner = object : Runnable {
            override fun run() {
                val elapsed = (System.currentTimeMillis() - start) / 1000
                val phase = phases[minOf(tick / 2, phases.size - 1)]
                bubble.text = "⏳ " + phase + " • " + elapsed + "d"
                tick++
                h.postDelayed(this, 1000)
            }
        }
        h.post(runner)
    }

    private fun stopProcessLog() {
        logHandler?.removeCallbacksAndMessages(null)
        logHandler = null
    }

    // ------------------------------------------------------------- chat SSE --
    private fun sendMessage(text: String) {
        addBubble(text, fromUser = true, save = true)
        setBusy(true)
        val bubble = addBubble("", fromUser = false, save = false)
        startTyping(bubble, "Skele sedang mengetik")

        executor.execute {
            val full = StringBuilder()
            try {
                streamChat(text) { chunk ->
                    if (full.isEmpty()) runOnUiThread { stopTyping() }
                    full.append(chunk)
                    runOnUiThread {
                        bubble.text = full.toString()
                        scrollChat.post { scrollChat.fullScroll(ScrollView.FOCUS_DOWN) }
                    }
                }
                if (full.isEmpty()) full.append("(jawaban kosong dari backend)")
            } catch (e: Exception) {
                if (full.isEmpty()) full.append(friendlyError(e)) else full.append("\n[Koneksi terputus di tengah jawaban]")
            }
            runOnUiThread {
                stopTyping()
                setBubbleFormatted(bubble, full.toString())
                shown.add(false to full.toString())
                saveChat()
                setBusy(false)
                scrollChat.post { scrollChat.fullScroll(ScrollView.FOCUS_DOWN) }
            }
        }
    }

    private fun friendlyError(e: Exception): String = when (e) {
        is UnknownHostException -> "Tidak ada koneksi internet atau server tidak terjangkau. Periksa jaringan HP kamu, lalu coba lagi."
        is SocketTimeoutException -> "Server terlalu lama menjawab (timeout). Coba kirim lagi sebentar."
        else -> "Maaf, gagal menghubungi server: ${e.message ?: "koneksi bermasalah"}. Periksa jaringan, lalu coba lagi."
    }

    /** POST /chat/stream — baca SSE: data {"chunk"} / {"done"} / {"error"}. */
    private fun streamChat(text: String, onChunk: (String) -> Unit) {
        val bodyObj = JSONObject().put("message", text).put("session_id", sessionId)
        llmOverrideJson()?.let { bodyObj.put("llm", it) }
        val body = bodyObj.toString()
        val conn = URL("$backendUrl/chat/stream").openConnection() as HttpURLConnection
        conn.requestMethod = "POST"
        conn.setRequestProperty("Content-Type", "application/json")
        if (appToken.isNotEmpty()) conn.setRequestProperty("X-App-Token", appToken)
        conn.connectTimeout = 15_000
        conn.readTimeout = 120_000
        conn.doOutput = true
        conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }

        if (conn.responseCode !in 200..299) {
            val response = conn.errorStream?.bufferedReader()?.use { it.readText() } ?: ""
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
        setBusy(true)
        val bubble = addBubble("", fromUser = false, save = false)
        startProcessLog(bubble, listOf("Menghubungi backend", "Agen merencanakan langkah",
            "Menjalankan skill", "Menyusun jawaban"))

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
                    display += "\n\n— Log proses:\n" + names.joinToString("\n") { "✓ " + it + " — selesai" }
                }
                if (json.optBoolean("needs_confirmation")) {
                    confirmToken = json.optString("confirm_token")
                    proposed = json.optJSONObject("proposed")?.optString("skill") ?: "aksi agen"
                }
            } catch (e: Exception) {
                display = friendlyError(e)
            }
            val token = confirmToken
            val skillName = proposed
            runOnUiThread {
                stopProcessLog()
                setBubbleFormatted(bubble, display)
                shown.add(false to display)
                saveChat()
                setBusy(false)
                scrollChat.post { scrollChat.fullScroll(ScrollView.FOCUS_DOWN) }
                if (token != null) askConfirmation(skillName, token)
            }
        }
    }

    private fun askConfirmation(skillName: String, token: String) {
        AlertDialog.Builder(this)
            .setTitle("Konfirmasi aksi agen")
            .setMessage("Agen ingin menjalankan aksi merusak: $skillName.\nAksi ini belum dijalankan. Setuju?")
            .setPositiveButton("Setuju, jalankan") { _, _ ->
                setBusy(true)
                executor.execute {
                    val result = try {
                        val json = postAgent(JSONObject().put("session_id", sessionId).put("confirm_token", token))
                        json.optString("reply", "(selesai)")
                    } catch (e: Exception) {
                        friendlyError(e)
                    }
                    runOnUiThread {
                        addBubble(result, fromUser = false, save = true)
                        setBusy(false)
                    }
                }
            }
            .setNegativeButton("Batal") { _, _ ->
                addBubble("Aksi $skillName dibatalkan — tidak ada yang dijalankan.", fromUser = false, save = true)
            }
            .show()
    }

    private fun postAgent(body: JSONObject): JSONObject {
        if (!body.has("llm")) llmOverrideJson()?.let { body.put("llm", it) }
        val conn = URL("$backendUrl/agent").openConnection() as HttpURLConnection
        conn.requestMethod = "POST"
        conn.setRequestProperty("Content-Type", "application/json")
        if (appToken.isNotEmpty()) conn.setRequestProperty("X-App-Token", appToken)
        conn.connectTimeout = 15_000
        conn.readTimeout = 180_000
        conn.doOutput = true
        conn.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
        val stream = if (conn.responseCode in 200..299) conn.inputStream else conn.errorStream
        val response = stream?.bufferedReader()?.use { it.readText() } ?: ""
        val json = try { JSONObject(response) } catch (_: Exception) { JSONObject() }
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

    // ------------------------------------------------------------ bubble UI --
    /** Tampilkan teks final balasan AI: render markdown ringan + link aktif. */
    private fun setBubbleFormatted(bubble: TextView, raw: String) {
        bubble.text = formatReply(raw)
        bubble.movementMethod = LinkMovementMethod.getInstance()
    }

    private fun addBubble(text: String, fromUser: Boolean, save: Boolean): TextView {
        val rawText = text
        val bubble = TextView(this).apply {
            textSize = 15.5f
            if (fromUser) {
                setBackgroundResource(R.drawable.bubble_user)
                setTextColor(Color.WHITE)
            } else if (prefs.getInt("tema", 0) == 0) {
                setBackgroundResource(R.drawable.bubble_ai)
                setTextColor(getColor(R.color.text_primary))
            } else {
                background = roundedBg(theme.bubbleAi, 18f)
                setTextColor(theme.textPri)
            }
            setLineSpacing(0f, 1.12f)
            if (fromUser) {
                this.text = rawText
            } else {
                this.text = formatReply(rawText)
                movementMethod = LinkMovementMethod.getInstance()
                setLinkTextColor(Color.parseColor("#4DD8FF"))
            }
            maxWidth = (resources.displayMetrics.widthPixels * 0.86).toInt()
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

    /**
     * Markdown ringan untuk balasan AI: **tebal**, *miring*, `kode`,
     * judul (#), dan URL yang bisa diketuk. Bentuk <https://...> dari LLM
     * diluruskan dulu menjadi URL polos agar terbaca Linkify.
     */
    private fun formatReply(raw: String): CharSequence {
        val cleaned = raw.replace(Regex("<(https?://[^>\\s]+)>"), "$1")
        val sb = SpannableStringBuilder()
        val lines = cleaned.split("\n")
        for ((idx, rawLine) in lines.withIndex()) {
            var line = rawLine
            val isHeading = line.startsWith("#")
            if (isHeading) line = line.trimStart('#').trim()
            val start = sb.length
            appendInline(sb, line)
            if (isHeading && sb.length > start) {
                sb.setSpan(StyleSpan(Typeface.BOLD), start, sb.length, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE)
            }
            if (idx < lines.size - 1) sb.append("\n")
        }
        Linkify.addLinks(sb, Linkify.WEB_URLS)
        return sb
    }

    private fun appendInline(sb: SpannableStringBuilder, line: String) {
        var i = 0
        while (i < line.length) {
            when {
                line.startsWith("**", i) -> {
                    val end = line.indexOf("**", i + 2)
                    if (end > i + 2) {
                        val s = sb.length
                        sb.append(line.substring(i + 2, end))
                        sb.setSpan(StyleSpan(Typeface.BOLD), s, sb.length, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE)
                        i = end + 2
                    } else { sb.append("**"); i += 2 }
                }
                line.startsWith("`", i) -> {
                    val end = line.indexOf('`', i + 1)
                    if (end > i + 1) {
                        val s = sb.length
                        sb.append(line.substring(i + 1, end))
                        sb.setSpan(TypefaceSpan("monospace"), s, sb.length, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE)
                        i = end + 1
                    } else { sb.append("`"); i += 1 }
                }
                line[i] == '*' -> {
                    val end = line.indexOf('*', i + 1)
                    if (end > i + 1) {
                        val s = sb.length
                        sb.append(line.substring(i + 1, end))
                        sb.setSpan(StyleSpan(Typeface.ITALIC), s, sb.length, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE)
                        i = end + 1
                    } else { sb.append("*"); i += 1 }
                }
                else -> { sb.append(line[i]); i += 1 }
            }
        }
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
                // Gambar ulang tanpa menyimpan ulang (shown diisi manual di sini).
                shown.add(item.getBoolean("fromUser") to item.getString("text"))
            }
            for ((fromUser, text) in shown) {
                val rawText = text
                val bubble = TextView(this).apply {
                    textSize = 15.5f
                    setBackgroundResource(if (fromUser) R.drawable.bubble_user else R.drawable.bubble_ai)
                    setTextColor(if (fromUser) Color.WHITE else getColor(R.color.text_primary))
                    setLineSpacing(0f, 1.12f)
                    if (fromUser) {
                        this.text = rawText
                    } else {
                        this.text = formatReply(rawText)
                        movementMethod = LinkMovementMethod.getInstance()
                        setLinkTextColor(Color.parseColor("#4DD8FF"))
                    }
                    maxWidth = (resources.displayMetrics.widthPixels * 0.86).toInt()
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
