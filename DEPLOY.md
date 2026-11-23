# Deploy Backend Your Agent

Tujuan: backend punya alamat publik `https://...` yang bisa dijangkau aplikasi
Android dari mana saja. Backend ini murni Python stdlib — tidak ada build step,
tidak ada `pip install`.

## Sebelum deploy — wajib

1. **Isi `APP_TOKEN`** sebagai environment variable / di `.env` server (jangan
   di file repo). Backend publik tanpa token = siapa pun bisa memakai kuota
   API key-mu. Samakan tokennya di aplikasi: **⚙ Atur → Koneksi Server**.
2. **Isi `META_API_KEY`, `META_API_BASE_URL`, `META_MODEL`** di server —
   bukan di Git (`.env` sudah ditahan `.gitignore`).
3. Setelah live, tes dari luar: buka `https://alamatmu/health` — harus
   menjawab `{"status": "ok", ...}`.

## Jalur A — PythonAnywhere (terbukti jalan, gratis, tanpa kartu)

Ini jalur yang dipakai backend resmi Your Agent
(https://jawaadalah.pythonanywhere.com).

1. Daftar di https://www.pythonanywhere.com (cukup email, tanpa kartu).
2. Buka **Bash console** → clone repo:
   `git clone https://github.com/jawaadalah/your-agent.git`
3. Buat file `backend/.env` di hasil clone dan isi variabelnya (lihat README).
4. Tab **Web** → **Add a new web app** → pilih **Manual configuration** →
   Python versi terbaru.
5. Atur **WSGI configuration file** agar mengarah ke `backend/wsgi_app.py`
   repo ini (sesuaikan `project_home` dengan folder clone-mu), contoh pola:

   ```python
   import os, sys
   project_home = os.path.expanduser('~/your-agent/backend')
   if project_home not in sys.path:
       sys.path.insert(0, project_home)
   os.chdir(project_home)
   from wsgi_app import application
   ```

6. Klik **Reload** di tab Web → tes `https://<username>.pythonanywhere.com/health`.

Catatan jujur jalur gratis PythonAnywhere:
- Situs gratis **dinonaktifkan setelah ±1 bulan** bila tidak diperpanjang —
  perpanjang gratis dari tab Web ("Run until 1 month from today").
- Hanya host dalam whitelist proxy gratisnya yang bisa dijangkau backend;
  `api.groq.com` termasuk, jadi Groq cocok untuk jalur ini.
- Update versi: di Bash console `git pull` di folder clone → **Reload**.

## Jalur B — Server/VPS sendiri atau komputer rumah

```bash
git clone https://github.com/jawaadalah/your-agent.git
cd your-agent && cp .env.example .env   # isi nilainya
python3 backend/main.py                  # dengarkan PORT dari env (bawaan 8000)
```

Taruh di belakang reverse proxy HTTPS (Caddy/Nginx) bila diekspos ke internet,
atau jalankan `wsgi_app.py` dengan server WSGI apa pun (gunicorn/waitress —
di luar stdlib, pilihanmu).

## Jalur yang TIDAK lagi disarankan (pengalaman nyata proyek ini)

- **Render (akun baru):** kini meminta verifikasi kartu kredit sebelum deploy
  pertama — tidak lagi "gratis tanpa kartu".
- **Hugging Face Spaces (Docker):** kini mensyaratkan langganan PRO berbayar
  untuk Space Docker.

File `Dockerfile`, `render.yaml`, dan `Procfile` tetap ada di repo bila kamu
punya akun lama/berbayar di platform tersebut.

## Setelah deploy

Di aplikasi Android: **⚙ Atur → Koneksi Server** → isi alamat `https://...`
hasil deploy + token yang sama dengan `APP_TOKEN` server → Simpan.
