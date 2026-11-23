# Your Agent — Asisten AI Pribadi dengan Mode Agen & Pabrik APK

**Your Agent** adalah aplikasi Android + backend ringan (Python murni, tanpa
dependensi) yang mengubah model AI biasa menjadi **agen yang bisa bertindak**:
menghitung, mencatat, mengingat jangka panjang, mengambil isi web, membuat
proyek aplikasi/game/web — bahkan **membangun aplikasi Android menjadi file
APK asli** langsung dari perintah chat.

- 📱 **Aplikasi Android:** unduh APK dari halaman
  [Releases](https://github.com/jawaadalah/your-agent/releases) repo ini.
- 🖥️ **Backend live (demo publik):** https://jawaadalah.pythonanywhere.com
  — cek sendiri: [GET /health](https://jawaadalah.pythonanywhere.com/health)
- 🧠 **Otak AI:** provider apa pun yang kompatibel OpenAI API (bawaan: Groq
  gratis). Bisa diganti dari aplikasi tanpa menyentuh server (**BYOK** —
  Bring Your Own Key).

> API key tidak pernah disimpan di aplikasi untuk server bawaan — aplikasi
> hanya bicara ke backend, backend yang bicara ke provider AI. Kunci BYOK
> milikmu hanya diteruskan per permintaan dan tidak disimpan server.

---

## Fitur utama

| Fitur | Penjelasan |
|---|---|
| **Chat streaming** | Jawaban mengalir kata per kata (SSE), dengan render markdown ringan (tebal/miring/kode/tautan). |
| **Mode Agen (16 skill)** | Agen menjalankan skill nyata, bukan cuma menjawab. Setiap langkah tercatat di "Log proses". |
| **Pabrik APK** | "buatkan game android X jadi apk" → proyek didorong ke repo → GitHub Actions membangunnya → APK terbit sebagai Release, siap unduh & pasang. |
| **Generator Cerdas** | Kode game/aplikasi/web **ditulis AI mengikuti instruksimu**, lalu dicek validator deterministik (struktur, impor aman, tanpa pola terlarang). Gagal cek → fallback template bawaan. |
| **Ingatan jangka panjang** | "ingat bahwa …" tersimpan di server dan dipakai di percakapan berikutnya; sesi chat juga persisten. |
| **Gerbang konfirmasi** | Aksi merusak (hapus catatan/memori) tidak pernah jalan sendiri — selalu menunggu persetujuanmu di aplikasi. |
| **Info token & kuota live** | Setiap balasan menampilkan pemakaian token; strip di layar utama + kartu di Pengaturan menampilkan **sisa kuota provider secara live**. |
| **BYOK** | Pakai API key milikmu (Groq, OpenRouter, OpenAI, Gemini, atau server kompatibel lain) langsung dari Pengaturan. |
| **3 tema** | Premium Navy, Terang, AMOLED — plus tampilan edge-to-edge modern. |
| **Integrasi n8n** | Skill `kirim_ke_n8n` meneruskan perintah ke webhook n8n milikmu (URL hanya dari konfigurasi server, anti-SSRF). |

## 16 skill agen

| Skill | Fungsi | Risiko |
|---|---|---|
| `kalkulator` | Hitung ekspresi matematika dengan aman (tanpa eval) | aman |
| `waktu_sekarang` | Jam & tanggal saat ini | aman |
| `ambil_halaman_web` | Ambil & ringkas isi sebuah URL (anti-SSRF) | aman |
| `simpan_catatan` / `baca_catatan` | Catatan per sesi | aman |
| `hapus_catatan` | Hapus semua catatan | **konfirmasi** |
| `ingat` / `baca_memori` | Ingatan jangka panjang lintas sesi | aman |
| `hapus_memori` | Hapus seluruh ingatan | **konfirmasi** |
| `buat_aplikasi_android` | Buat proyek aplikasi Android (kode ditulis AI) | aman |
| `buat_game_android` | Buat proyek game Android (kode ditulis AI) | aman |
| `buat_halaman_web` | Buat halaman web (landing/game/kalkulator) | aman |
| `daftar_hasil_generate` | Daftar proyek yang sudah dibuat | aman |
| `buat_apk_android` | Buat proyek **dan** bangun jadi APK (Pabrik APK) | aman |
| `cek_apk` | Cek status unduhan APK sebuah proyek | aman |
| `kirim_ke_n8n` | Kirim perintah ke webhook n8n (bila dikonfigurasi) | aman |

Cara kerja agen: **router deterministik (0 token)** memetakan perintah yang
polanya jelas langsung ke skill; sisanya direncanakan LLM (maks 3 langkah per
pesan). Hanya skill di registry yang bisa dipanggil — tidak ada eval, tidak
ada shell.

## Cara pakai (di aplikasi)

1. Pasang APK dari [Releases](https://github.com/jawaadalah/your-agent/releases),
   buka aplikasi — langsung tersambung ke backend bawaan.
2. Ngobrol biasa, atau aktifkan **Mode Agen** (sakelar "AGEN" di header, hijau
   = aktif) lalu coba perintah:
   - `hitung 125 * 48`
   - `jam berapa sekarang?`
   - `catat: beli stok kopi untuk warung`
   - `ingat bahwa nama warung saya Kopi Senja`
   - `buatkan game android Perang Bintang: pesawat menembak asteroid yang jatuh, nyawa 3, jadi apk`
     → tunggu ±3–6 menit, tautan unduh APK muncul di balasan (atau tanya
     `cek apk perang-bintang`)
   - `buatkan halaman web Toko Kopi Senja`
   - `ambil isi https://example.com`
3. Di **⚙ Atur** kamu bisa: mengganti alamat backend & token aplikasi, memakai
   API key milikmu (preset Groq/OpenRouter/OpenAI/Gemini/Kustom), memilih tema,
   dan memantau **kuota & limit backend** secara live.

## Self-host backend

Backend hanya butuh **Python 3.10+** — semua pustaka standar, tanpa `pip install`.

```bash
git clone https://github.com/jawaadalah/your-agent.git
cd your-agent
cp .env.example .env   # lalu isi nilainya (lihat tabel di bawah)
python3 backend/main.py   # server jalan di http://localhost:8000
```

Variabel `.env`:

| Variabel | Wajib | Penjelasan |
|---|---|---|
| `META_API_KEY` | ya (mode live) | API key provider AI (mis. Groq). Kosong = mode mock (tanpa AI, skill tetap jalan). |
| `META_API_BASE_URL` | ya (mode live) | Base URL kompatibel OpenAI, mis. `https://api.groq.com/openai/v1`. |
| `META_MODEL` | ya (mode live) | Nama model, mis. `openai/gpt-oss-120b`. |
| `APP_TOKEN` | dianjurkan | Token rahasia; klien wajib mengirim header `X-App-Token`. Tanpa ini backend terbuka untuk siapa pun yang tahu alamatnya. |
| `SYSTEM_PROMPT` | tidak | Kepribadian tambahan agen (selain `backend/SOUL.md`). |
| `GITHUB_TOKEN` | untuk Pabrik APK | Fine-grained PAT khusus repo ini (Contents: Read & write) agar backend bisa mendorong proyek ke folder `factory/`. |
| `N8N_WEBHOOK_URL` | untuk n8n | URL webhook produksi n8n milikmu. |
| `N8N_WEBHOOK_SECRET` | tidak | Dikirim sebagai header `X-Webhook-Secret`. |

Untuk hosting WSGI (PythonAnywhere dan sejenisnya) pakai `backend/wsgi_app.py`
sebagai application. Langkah deploy PythonAnywhere yang terbukti jalan ada di
[DEPLOY.md](DEPLOY.md).

## API ringkas

| Endpoint | Fungsi |
|---|---|
| `GET /health` | Status, versi, model, jumlah skill, snapshot kuota terakhir |
| `POST /chat` | Chat biasa → `{reply, usage, quota}` |
| `POST /chat/stream` | Chat streaming (SSE); event `done` membawa `usage` + `quota` |
| `POST /agent` | Mode agen → `{reply, steps, usage, quota}` / gerbang konfirmasi |
| `GET /skills` | Daftar skill terdaftar |
| `GET /soul` | Isi SOUL.md (persona agen) |
| `GET /memory` | Isi ingatan jangka panjang |
| `POST /reset` | Reset sesi percakapan |

Contoh:

```bash
curl -X POST https://jawaadalah.pythonanywhere.com/agent \
  -H 'Content-Type: application/json' \
  -d '{"message": "hitung 125 * 48", "session_id": "coba"}'
```

**Override LLM per permintaan (BYOK):** tambahkan objek `llm` pada body
`/chat`, `/chat/stream`, atau `/agent`:

```json
{"message": "halo", "llm": {"base_url": "https://api.groq.com/openai/v1",
 "model": "openai/gpt-oss-120b", "api_key": "kunci-milikmu"}}
```

Kunci hanya dipakai untuk permintaan itu — tidak disimpan, tidak dicatat.

**Bidang `usage` & `quota`:** `usage` = token terpakai pada permintaan ini
(`prompt_tokens`, `completion_tokens`, `total_tokens`, `calls`). `quota` =
snapshot sisa kuota provider dari header rate-limit terakhir
(`remaining_requests`/`limit_requests`, `remaining_tokens`/`limit_tokens`,
`reset_*`) — pada Groq gratis, limit token yang dilaporkan adalah jatah
**per menit** (8.000) dan limit permintaan adalah jatah **harian** (1.000).

## Arsitektur

```
[ Aplikasi Android (Kotlin) ]
        │  HTTPS  /chat /chat/stream /agent
        ▼
[ Backend Python stdlib ]  ──► [ Provider AI kompatibel OpenAI ]
   main.py / wsgi_app.py        (Groq / OpenRouter / OpenAI / Gemini)
   agent.py  — harness: router deterministik → perencana LLM → skill
   skills.py — registry 16 skill (tangan/kaki, aman/konfirmasi)
   gen_ai.py — penulis kode AI + validator deterministik
   generate.py — template proyek Android & web (fallback)
   apk_factory.py — dorong proyek ke factory/ via GitHub Git Data API
   store.py / memory_store.py — sesi & ingatan persisten (tulis atomik)
        │  push factory/<slug>
        ▼
[ GitHub Actions: factory-apk.yml ] ──► [ Release apk-<slug>: file .apk ]
```

## Keamanan

- Atur `APP_TOKEN` di server dan samakan di aplikasi (⚙ Atur → Koneksi Server)
  — tanpa token, siapa pun yang tahu URL backend bisa memakai kuotamu.
- Aksi merusak selalu berhenti di gerbang konfirmasi (token sekali pakai).
- `ambil_halaman_web` dan `kirim_ke_n8n` anti-SSRF: tujuan dibatasi skema
  http/https; webhook n8n hanya dari konfigurasi server, bukan dari chat.
- Jangan commit `.env` — sudah tercakup `.gitignore` beserta `backend/data/`.

## Pengembangan

```bash
python3 backend/selftest.py   # seluruh rangkaian tes backend (wajib lulus)
```

Build APK aplikasi: GitHub Actions (`.github/workflows/android-apk.yml`) —
tidak butuh Android SDK lokal. APK debug ditandatangani keystore debug tetap
di repo (`android/debug.p12`, khusus debug) supaya setiap rilis bisa dipasang
sebagai pembaruan langsung di atas versi sebelumnya.

## Batasan jujur

- Kuota otak bawaan mengikuti batas gratis provider (Groq: 30 permintaan/menit,
  1.000/hari, 8.000 token/menit) — untuk pemakaian berat pakai BYOK.
- Pabrik APK membangun aplikasi sederhana satu-layar dari generator; bukan
  pengganti Android Studio untuk aplikasi kompleks.
- Hosting gratis punya masa aktif & batas sumber daya masing-masing.

---

**Your Agent v1.0.0** — dibuat oleh **Jawaadalah (J-DEV)**, Sidoarjo, Indonesia.
Konsep agen (otak + skill + harness) dijelaskan lebih lanjut di [AGENT.md](AGENT.md).
