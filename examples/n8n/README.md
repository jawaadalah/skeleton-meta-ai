# Integrasi Your Agent ↔ n8n via Webhook — Contoh Kerja

n8n **tidak** dimasukkan ke dalam APK. Your Agent tetap ringan di HP;
n8n berjalan sebagai server terpisah, dan keduanya saling memanggil
lewat HTTP/webhook:

```
[HP: aplikasi Your Agent]
        │  user mengetik:  n8n: buat laporan penjualan hari ini
        ▼
[Backend Your Agent]  ── skill kirim_ke_n8n ──►  POST JSON
        │                                          ke N8N_WEBHOOK_URL
        ▼
[n8n: Webhook node] → [node proses/aksi: Sheets, WA, Telegram, AI, …]
        │                                          │
        └◄── [Respond to Webhook: JSON balasan] ◄──┘
        ▼
Balasan workflow tampil apa adanya di chat aplikasi.
```

Arah sebaliknya juga bisa: workflow n8n memanggil backend Your Agent
(lihat bagian 4).

## 1. Pasang n8n (pilih satu, di server — bukan di HP)

- **Docker (VPS/komputer rumah):**
  `docker run -d --name n8n -p 5678:5678 -v n8n_data:/home/node/.n8n docker.n8n.io/n8nio/n8n`
- **n8n Cloud:** daftar di n8n.io, tanpa install.
- Buka dashboard n8n, buat akun pemilik.

## 2. Import workflow contoh

1. Di dashboard n8n: menu **Workflows → Import from File**,
   pilih `workflow-your-agent.json` dari folder ini.
2. Workflow berisi 3 node: **Webhook dari Your Agent** (POST, path
   `your-agent`) → **Olah Perintah** (Code: menyusun teks balasan) →
   **Balas ke Your Agent** (Respond to Webhook).
3. Klik **Active** (pojok kanan atas) agar URL *produksi* aktif:
   `https://<alamat-n8n-kamu>/webhook/your-agent`
   (URL `/webhook-test/` hanya untuk mode Listen, jangan dipakai di server.)

## 3. Sambungkan backend Your Agent

Di `.env` backend (lokal / PythonAnywhere), isi lalu reload backend:

```
N8N_WEBHOOK_URL=https://<alamat-n8n-kamu>/webhook/your-agent
N8N_WEBHOOK_SECRET=teks-rahasia-bebas   # opsional
```

Setelah itu, di aplikasi Your Agent cukup ketik salah satu:

- `n8n: buat laporan penjualan hari ini`
- `otomasi: kirim rekap ke grup`
- `kirim ke n8n rekap stok warung`

Router deterministik backend mengenali pola itu (0 token LLM) dan
menjalankan skill `kirim_ke_n8n`. Payload yang dikirim ke n8n:

```json
{
  "source": "your-agent",
  "session_id": "sesi-chat-pengguna",
  "aksi": "perintah",
  "teks": "buat laporan penjualan hari ini",
  "waktu": "2026-11-23T13:20:00+07:00"
}
```

Di n8n, payload itu ada di node Webhook pada `body` — tinggal sambungkan
node apa pun sesudah "Olah Perintah": Google Sheets, Telegram, WhatsApp,
HTTP Request, AI Agent, dll. Field `pesan` pada JSON balasan node
Respond to Webhook akan diteruskan utuh ke chat pengguna.

**Keamanan:** URL tujuan hanya dibaca dari `.env` server, tidak pernah
dari pesan pengguna — jadi skill ini tidak bisa disalahgunakan untuk
memanggil alamat sembarangan (anti-SSRF). Bila `N8N_WEBHOOK_SECRET`
diisi, nilainya dikirim sebagai header `X-Webhook-Secret`; tambahkan
node IF di n8n untuk menolak permintaan tanpa header itu.

## 4. Arah balik: n8n memanggil Your Agent

Workflow n8n juga bisa menyuruh Skele bekerja, pakai node
**HTTP Request**:

- Method: `POST`
- URL: `https://jawaadalah.pythonanywhere.com/agent`
- Header: `Content-Type: application/json`
  (+ `X-App-Token: <APP_TOKEN>` bila token aplikasi dipasang di server)
- Body JSON: `{"message": "hitung 12000*3", "session_id": "n8n"}`

Contoh gunanya: trigger jadwal di n8n tiap pagi → minta Your Agent
merangkum sesuatu → hasilnya diteruskan n8n ke Telegram/WhatsApp.

## 5. Uji cepat tanpa n8n asli

File `uji_webhook.py` di folder ini adalah server peniru n8n
(1 file, Python stdlib): ia menerima POST, mencetak payload, dan
membalas JSON `pesan` — persis kontrak node Respond to Webhook.

```
python3 uji_webhook.py            # jalan di http://127.0.0.1:5679/webhook/your-agent
N8N_WEBHOOK_URL=http://127.0.0.1:5679/webhook/your-agent python3 -c "
import skills; print(skills.execute('kirim_ke_n8n', {'teks':'halo n8n'}, {'session_id':'uji'}))"
```
