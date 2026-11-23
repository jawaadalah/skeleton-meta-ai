# Deploy Backend Supaya Bisa Diakses dari Mana Saja

Tujuan: backend tidak lagi hanya di komputer rumah (`10.0.2.2` / IP LAN),
tapi punya alamat publik `https://...` yang bisa dijangkau aplikasi Android dari mana pun.

Backend ini sudah siap deploy: membaca `PORT` dari platform, ada `Dockerfile`,
`render.yaml`, dan `Procfile`. Tinggal pilih **satu** jalur di bawah.

## Sebelum deploy — wajib

1. **Isi `APP_TOKEN`** di pengaturan environment platform (jangan di file repo).
   Backend publik tanpa token = siapa pun bisa memakai API key-mu.
   Di Render, `render.yaml` proyek ini membuatkannya otomatis (`generateValue`).
2. **Isi `META_API_KEY`** sebagai environment variable di platform — bukan di Git.
3. Setelah live, di aplikasi Android: tombol **URL** → isi alamat `https://...`
   hasil deploy + token yang sama dengan `APP_TOKEN` di server.

## Jalur A — Render (disarankan, gratis, daftar pakai GitHub)

1. Push folder proyek ini ke repo GitHub (mis. `jawaadalah/your-agent`).
   Pastikan `.env` **tidak** ikut — sudah ditahan `.gitignore`.
2. Buka https://render.com → **Get Started** → daftar/login pakai GitHub.
3. **New → Blueprint** → pilih repo tadi → Render membaca `render.yaml` proyek ini.
4. Isi `META_API_KEY` saat diminta. `APP_TOKEN` dibuatkan otomatis — buka
   service-nya → **Environment** untuk melihat/menyalin nilainya.
5. Tunggu build selesai → alamatmu jadi `https://skeleton-meta-ai.onrender.com`
   (nama bisa beda). Tes: buka `https://alamatmu/health` di browser —
   harus menjawab `{"status": "ok", ...}`.
6. Di Android: tombol **URL** → tempel alamat itu + token dari langkah 4 → Simpan.

Catatan jalur gratis Render: service **tidur setelah ±15 menit tidak dipakai**;
permintaan pertama setelah tidur butuh ±30–60 detik untuk bangun. Normal untuk
kelas gratis — aplikasi tetap jalan, hanya balasan pertama lebih lambat.

## Jalur B — Hugging Face Spaces (alternatif gratis, daftar pakai email)

1. Daftar di https://huggingface.co (cukup email).
2. **New Space** → SDK: **Docker** → unggah isi proyek ini (atau hubungkan repo).
3. Di Space → **Settings → Variables and secrets**: tambah `META_API_KEY` dan
   `APP_TOKEN` (sebagai *secret*).
4. Space jalan dengan alamat `https://<username>-<nama-space>.hf.space` —
   tes `/health`, lalu atur URL + token di aplikasi Android seperti di atas.

## Yang sengaja TIDAK dipakai

- **Fly.io / Railway**: saat ini umumnya meminta kartu untuk mulai — bertentangan
  dengan aturan proyek ini (tanpa uang/kartu di awal). `Dockerfile` + `Procfile`
  di proyek ini tetap kompatibel bila suatu hari kamu memilihnya sendiri.

## Setelah deploy

- Alamat publik memakai **HTTPS**, jadi batasan `usesCleartextTraffic` di Android
  tidak lagi jadi masalah untuk alamat ini.
- Ingatan sesi masih di memori server: restart/redeploy platform akan
  mengosongkannya. Itu wajar untuk skeleton; penyimpanan permanen adalah langkah v5+.
- Cek berkala: `GET /health` menunjukkan `mode` (`live`/`mock`) dan `auth: true`.
  Kalau `mode` masih `mock`, berarti `META_API_KEY` belum terbaca di platform.
