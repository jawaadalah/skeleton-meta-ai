# Agen: Otak + Kaki + Tangan, dengan Harness Semi

Di v1–v4, proyek ini baru "kepala yang bisa bicara": Meta AI menjawab lewat chat.
Di v5 ia jadi **agen**:

| Organ | Wujudnya di proyek ini | File |
|---|---|---|
| **Otak** | Meta AI (Llama API) — memahami, merencanakan, merangkai jawaban. Ingatannya = sesi di server + `SYSTEM_PROMPT` di `.env` (v6: sesi tersimpan permanen di `backend/data/sessions.json`, selamat dari restart) | `backend/main.py`, `backend/store.py` |
| **Kaki** | Skill penjangkau: `waktu_sekarang`, `ambil_halaman_web` — agen "pergi" mengambil fakta dari luar dirinya | `backend/skills.py` |
| **Tangan** | Skill pelaku: `kalkulator`, `simpan_catatan`, `baca_catatan`, `hapus_catatan` — agen mengubah keadaan, bukan cuma bicara | `backend/skills.py` |
| **Logika / harness** | `backend/agent.py` — yang memutuskan kapan otak berpikir, kapan skill jalan, dan kapan harus berhenti minta izin manusia | `backend/agent.py` |

## Cara harness bekerja (semi, bukan liar)

1. **Router deterministik dulu (0 token).** Pola yang jelas — "hitung …",
   "jam berapa", URL + kata ambil/buka, "catat: …", "baca catatan",
   "hapus catatan" — langsung dipetakan ke skill tanpa memanggil LLM sama sekali.
   Ini murah, cepat, dan bisa ditebak. LLM hanya dipanggil bila router tidak yakin.
2. **Perencana LLM (mode live).** LLM hanya boleh membalas JSON ketat:
   jawab langsung, atau panggil **1 skill dari registry**. Tidak ada eval,
   tidak ada shell, tidak ada aksi di luar registry — otak tidak bisa
   menciptakan tangan baru sendiri.
3. **Batas langkah.** Maksimal `MAX_STEPS = 3` pemanggilan skill per pesan
   (di `backend/agent.py`). Agen tidak bisa berputar tanpa ujung.
4. **Gerbang konfirmasi (inti "semi"-nya).** Skill berisiko `konfirmasi`
   (saat ini: `hapus_catatan`) **tidak pernah dijalankan otomatis**.
   Harness berhenti, menerbitkan `confirm_token` sekali pakai, dan aplikasi
   Android menampilkan dialog. Hanya ketukan "Setuju, jalankan" dari manusia
   yang menjalankan aksi itu — token hangus setelah 1x pakai dan terikat sesi.
5. **Jejak audit.** Setiap pemanggilan skill dicatat di field `steps`
   (skill, args, potongan hasil, via router/llm, dan `confirmed_by_user`)
   dan ditampilkan di aplikasi. Agen tidak bertindak diam-diam.
6. **Anti-SSRF di kaki.** `ambil_halaman_web` menolak host ber-IP privat/lokal/
   loopback — agen tidak bisa disuruh mengintip jaringan internal server.

## Menambah skill baru

1. Tulis fungsi `skill_xxx(args, ctx)` di `backend/skills.py` — kembalikan teks hasil.
2. Daftarkan di `SKILLS` dengan `organ`, `risk`, `params`, `description`.
   Pilih `risk: "konfirmasi"` untuk apa pun yang menghapus, mengirim,
   membeli, atau mengubah data penting.
3. (Opsional) Tambahkan pola di `deterministic_route()` di `backend/agent.py`
   bila perintahnya berpola jelas, supaya tidak membakar token LLM.
4. Jalankan `python3 backend/selftest.py`.

## API agen

```
GET  /skills
-> {"skills": [{"name", "organ", "risk", "params", "description"}], "version": "5.0"}

POST /agent   {"message": "...", "session_id": "..."}
-> {"reply": "...", "steps": [{"skill", "args", "result", "via"}], "mode", "version"}
-> atau, bila berhenti di gerbang:
   {"needs_confirmation": true, "confirm_token": "...", "proposed": {"skill", "args"}, "reply": "...", "steps": []}

POST /agent   {"session_id": "...", "confirm_token": "..."}   (setelah manusia menekan Setuju)
-> {"reply": "<hasil aksi>", "steps": [...], "confirmed": true}
```

Di aplikasi Android, aktifkan sakelar **Mode Agen** untuk memakai jalur ini;
matikan untuk kembali ke chat streaming biasa (`/chat/stream`).

## Batas yang disengaja (agar tetap "semi")

- Catatan disimpan per sesi di `backend/data/notes.json` (file lokal server,
  hilang bila container deploy dibuang — wajar untuk skeleton).
- Mode mock tidak memanggil LLM: yang diuji adalah logika harness + skill-nya.
  Perencana LLM aktif penuh hanya di mode live (ada `META_API_KEY`).
