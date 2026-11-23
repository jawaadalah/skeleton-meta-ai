# Skeleton Meta AI — Kepala Meta AI + Badan Buatanmu

Kerangka proyek **kosong tapi sudah jalan end-to-end**: tinggal kembangkan.
Bukan aplikasi jadi — ini fondasi yang sudah nyambung dan bisa langsung dites kirim-terima pesan.

**v6 (terbaru) — ingatan permanen:**
- Sesi percakapan kini tersimpan di `backend/data/sessions.json` (file baru
  `backend/store.py`, stdlib saja, tulis atomik, maks 50 sesi). Restart server
  atau tidur di Render gratis tidak lagi menghapus riwayat chat dan ingatan agen.
  Catatan sudah permanen sejak v5; token konfirmasi sengaja tetap in-memory
  supaya aksi tertunda hangus dengan aman saat restart.
- Batasan jujur: filesystem Render gratis itu ephemeral — redeploy/deploy ulang
  tetap menghapus file ini. Daya tahan lintas deploy butuh database (langkah berikut).

**v5 — jadi agen: otak + kaki + tangan, harness semi:**
- Endpoint `POST /agent` + `GET /skills`, file baru `backend/agent.py` dan
  `backend/skills.py`. Detail konsep & cara menambah skill: **AGENT.md**.
- Skill bawaan: kalkulator & catatan (tangan), waktu & ambil halaman web
  anti-SSRF (kaki). Router deterministik 0-token dulu, perencana LLM sesudahnya,
  maks 3 langkah per pesan, dan skill merusak (`hapus_catatan`) berhenti di
  gerbang konfirmasi manusia (token sekali pakai).
- Android: sakelar **Mode Agen**, jejak skill ditampilkan di jawaban, dan dialog
  konfirmasi "Setuju, jalankan" untuk aksi merusak.

**v4 — siap deploy publik:**
- Proteksi **APP_TOKEN**: endpoint POST wajib membawa header `X-App-Token` bila
  token diatur di server — backend publik tidak bisa dipakai orang lain.
  Aplikasi Android mengatur tokennya dari dialog tombol **URL**.
- File deploy: `Dockerfile`, `render.yaml` (Render), `Procfile`, `.dockerignore`,
  dan panduan langkah demi langkah di **DEPLOY.md** (jalur gratis tanpa kartu:
  Render atau Hugging Face Spaces).

**v3:**
- **Streaming jawaban** — endpoint baru `POST /chat/stream` (Server-Sent Events):
  backend meneruskan potongan teks dari Meta AI begitu dihasilkan, Android
  menumbuhkan balon jawaban kata per kata. Mode mock men-stream per kata juga,
  jadi efeknya bisa dilihat tanpa API key. `POST /chat` biasa tetap ada.

**v2:**

- Backend mengingat percakapan per **sesi** (`session_id`) + endpoint `POST /reset`
- **System prompt** diatur dari `.env` — beri asistenmu kepribadian sendiri
- Validasi pesan: kosong / lebih dari `MAX_MESSAGE_CHARS` ditolak (400)
- Android: balon chat berwarna, indikator "Sedang mengetik...", riwayat tersimpan
  lokal (tidak hilang saat aplikasi ditutup), tombol **URL** untuk ganti alamat
  backend dari aplikasi, dan tombol **Hapus** untuk mulai percakapan baru

```
[ Aplikasi Android ]  --POST /chat-->  [ Backend kecil ]  --API key dari .env-->  [ Meta AI / Llama API ]
   layar chat + Kirim                   simpan key dengan aman                    jawaban kembali
```

API key **tidak pernah** ada di aplikasi Android. Android hanya bicara dengan backend,
backend yang bicara dengan Meta AI. Itu pola yang aman untuk dikembangkan jadi produk beneran.

## Isi

| Bagian | Isi |
|---|---|
| `android/` | Aplikasi Android (Kotlin, Android Studio): 1 layar chat + tombol kirim, tanpa library chat aneh-aneh |
| `backend/main.py` | Backend Python **stdlib saja** (tanpa `pip install`): `GET /health`, `POST /chat` |
| `backend/selftest.py` | Tes otomatis end-to-end: nyalakan backend → cek health → kirim pesan → terima jawaban |
| `.env.example` | Contoh konfigurasi: tempat pasang API key, model, port |

## Cara menjalankan

### 1. Backend dulu

```bash
cd skeleton-meta-ai
cp .env.example .env     # lalu isi META_API_KEY di .env (boleh dikosongkan dulu)
python3 backend/main.py
```

Backend jalan di `http://localhost:8000`.

- **Tanpa key** → otomatis **mode mock**: jawaban dibuat lokal, tapi alur kirim-terima
  tetap jalan penuh. Cocok untuk memastikan semuanya nyambung dulu.
- **Dengan key** → mode live: pesan diteruskan ke Meta AI (Llama API) dan jawaban aslinya dikembalikan.

Tes cepat dari terminal:

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" \
     -d '{"message": "Halo, apa kabar?"}'
```

Atau tes otomatis:

```bash
python3 backend/selftest.py
```

### 2. Aplikasi Android

1. Buka folder `android/` di Android Studio → tunggu Gradle sync.
2. Jalankan backend (langkah 1) di komputermu.
3. Run di Emulator — alamat backend bawaan `http://10.0.2.2:8000` sudah mengarah ke
   komputer host dari dalam emulator.
4. **HP fisik:** ganti `BACKEND_URL` di `MainActivity.kt` dengan IP LAN komputermu
   (contoh `http://192.168.1.10:8000`), HP dan komputer di Wi-Fi yang sama.
5. Tulis pesan → tekan **Kirim** → balon jawaban dari backend/Meta AI muncul.

## Cara pasang API key

1. Buat key Llama API (layanan API resmi Meta untuk model Llama) di
   https://www.llama.com/products/llama-api/
2. `cp .env.example .env`, isi `META_API_KEY=...`, sesuaikan `META_MODEL` bila perlu.
3. Restart backend. Cek `GET /health` — `mode` harus berubah dari `mock` menjadi `live`.
4. Jangan pernah menaruh key di kode Android, di Git, atau di screenshot publik.
   File `.env` sudah masuk `.gitignore`.

Endpoint dan formatnya OpenAI-compatible (`/chat/completions`), jadi kalau nanti mau
ganti penyedia/model lain yang kompatibel, cukup ubah `META_API_BASE_URL` dan `META_MODEL`
di `.env` — kode tidak berubah.

## Kontrak API backend

`POST /chat`

```json
// request (cara v2 — pakai sesi, backend yang mengingat konteks)
{"message": "Halo!", "session_id": "id-unik-per-percakapan"}

// request (cara lama, tetap didukung — riwayat dikirim klien)
{"message": "Halo!", "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}

// response 200
{"reply": "Halo juga! Ada yang bisa saya bantu?", "mode": "live", "version": "2.0"}

// response 400/502
{"error": "pesan kesalahan yang bisa dibaca manusia"}
```

`POST /chat/stream` — permintaan sama seperti `/chat`, tapi jawabannya berupa
aliran Server-Sent Events (dipakai aplikasi Android v3):

```
data: {"chunk": "Halo"}
data: {"chunk": " juga!"}
data: {"done": true, "mode": "live", "version": "3.0"}
```

Hasil stream yang utuh ikut disimpan ke ingatan sesi, sama seperti `/chat`.

`POST /reset` dengan `{"session_id": "..."}` menghapus ingatan sesi itu di backend.
Server mengingat maks. 20 pesan terakhir per sesi, dan selalu menyisipkan
`SYSTEM_PROMPT` dari `.env` di depan percakapan saat mode live.

## Langkah kembangkan selanjutnya (di luar skeleton)

- Ganti tampilan chat polos dengan RecyclerView/Compose + simpan riwayat lokal (Room).
- Tambah streaming jawaban, login pengguna, dan rate limit di backend.
- Deploy backend ke server/VPS dengan HTTPS, lalu matikan `usesCleartextTraffic` di Android.
- Pindah backend ke FastAPI/Node bila butuh fitur lebih — kontrak `/chat` di atas pertahankan saja.

---
Skeleton oleh Kontenlaris Studio — fondasi, bukan produk jadi.
