#!/usr/bin/env python3
"""
SKILLS — tangan & kaki agen. Python stdlib saja.

Setiap skill adalah fungsi kecil dengan metadata:
  name        : nama unik (dipakai perencana/LLM untuk memilih)
  organ       : "tangan" (mengeksekusi aksi) atau "kaki" (menjangkau/pergi ke sumber)
  risk        : "aman"    -> boleh jalan otomatis di harness
                "konfirmasi" -> harness TIDAK menjalankannya langsung;
                                manusia harus menyetujui dulu (semi-harness)
  params      : daftar parameter yang diterima
  description : kapan skill ini dipakai (dibaca perencana)

Menambah skill baru = tambah 1 fungsi + 1 entri di SKILLS. Tidak ada jalur lain
untuk agen bertindak — di luar registry ini, agen hanya bisa bicara.
"""
import ast
import html
import ipaddress
import json
import operator
import os
import re
import socket
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DATA_DIR = Path(__file__).resolve().parent / "data"
NOTES_FILE = DATA_DIR / "notes.json"

# ---------------------------------------------------------------- catatan ----
def _load_notes():
    try:
        return json.loads(NOTES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_notes(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


# ----------------------------------------------------------------- tangan ----
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod, ast.Pow: operator.pow,
        ast.USub: operator.neg, ast.UAdd: operator.pos}


def _eval_node(node):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("ekspresi tidak didukung (hanya angka dan + - * / // % ** kurung)")


def skill_kalkulator(args, ctx):
    expr = str(args.get("ekspresi", "")).strip()
    if not expr:
        return "Error: parameter 'ekspresi' kosong."
    result = _eval_node(ast.parse(expr, mode="eval"))
    if isinstance(result, float) and result.is_integer():
        result = int(result)
    return f"{expr} = {result}"


def skill_simpan_catatan(args, ctx):
    text = str(args.get("teks", "")).strip()
    if not text:
        return "Error: parameter 'teks' kosong."
    data = _load_notes()
    notes = data.setdefault(ctx["session_id"] or "default", [])
    notes.append({"teks": text, "waktu": datetime.now(ZoneInfo("Asia/Jakarta")).isoformat(timespec="seconds")})
    _save_notes(data)
    return f"Catatan tersimpan (total {len(notes)} catatan di sesi ini): \"{text}\""


def skill_baca_catatan(args, ctx):
    notes = _load_notes().get(ctx["session_id"] or "default", [])
    if not notes:
        return "Belum ada catatan tersimpan di sesi ini."
    lines = [f"{i+1}. {n['teks']} ({n['waktu']})" for i, n in enumerate(notes)]
    return "Catatan sesi ini:\n" + "\n".join(lines)


def skill_hapus_catatan(args, ctx):
    """Level KONFIRMASI — fungsi ini hanya jalan setelah manusia menyetujui."""
    data = _load_notes()
    count = len(data.pop(ctx["session_id"] or "default", []))
    _save_notes(data)
    return f"{count} catatan sesi ini sudah dihapus."


# ------------------------------------------------------------------- kaki ----
_HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
_BULAN = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
          "Agustus", "September", "Oktober", "November", "Desember"]


def skill_waktu(args, ctx):
    tz = str(args.get("zona", "Asia/Jakarta"))
    try:
        now = datetime.now(ZoneInfo(tz))
    except Exception:
        return f"Error: zona waktu '{tz}' tidak dikenal."
    return (f"Sekarang {_HARI[now.weekday()]}, {now.day} {_BULAN[now.month]} {now.year} "
            f"pukul {now:%H:%M:%S} ({tz})")


def _is_public_host(host):
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def skill_ambil_web(args, ctx):
    url = str(args.get("url", "")).strip()
    if not re.match(r"^https?://", url):
        return "Error: URL harus diawali http:// atau https://"
    host = re.sub(r"^https?://", "", url).split("/")[0].split(":")[0]
    if not _is_public_host(host):
        return f"Error: host '{host}' ditolak — alamat privat/lokal tidak boleh dijangkau agen (anti-SSRF)."
    req = urllib.request.Request(url, headers={"User-Agent": "YourAgent/7.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read(200_000).decode("utf-8", "replace")
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw, flags=re.S | re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"\s+", " ", text).strip()
    return f"Isi {url} (±{len(text)} karakter, dipotong 2.000):\n{text[:2000]}"


# ------------------------------------------------- memori & generator (v7) --
import generate as generate_mod
import memory_store as memory_mod


def skill_ingat(args, ctx):
    fakta = str(args.get("fakta", "")).strip()
    if not fakta:
        return "Error: parameter 'fakta' kosong."
    total = memory_mod.append_fact(fakta)
    return f"Diingat di MEMORY.md (total {total} fakta): \"{fakta}\""


def skill_baca_memori(args, ctx):
    text = memory_mod.read_full()
    if not text or "- " not in text:
        return "MEMORY.md masih kosong — belum ada fakta yang diingat."
    return "Isi MEMORY.md:\n" + text


def skill_hapus_memori(args, ctx):
    """Level KONFIRMASI — hanya jalan setelah manusia menyetujui."""
    count = memory_mod.clear_all()
    return f"{count} fakta di MEMORY.md sudah dihapus. Ingatan jangka panjang kosong lagi."


import gen_ai as genai_mod


def _ai_activity(args, ctx, nama, jenis):
    """Kode kustom dari LLM (v10) — None bila mock/gagal validasi."""
    llm = ctx.get("llm")
    if not llm:
        return None
    deskripsi = str(args.get("deskripsi", "")).strip()
    slug, title, pkg, _ = generate_mod.android_project(nama, jenis)
    return genai_mod.custom_activity(llm, title, jenis, deskripsi, pkg)


def skill_buat_aplikasi_android(args, ctx):
    nama = str(args.get("nama", "")).strip()
    custom = _ai_activity(args, ctx, nama, "aplikasi")
    out = generate_mod.android_app(nama, str(args.get("paket", "")).strip(),
                                   activity_override=custom)
    return out + (" Kodenya ditulis AI mengikuti instruksimu." if custom else
                  " (Template bawaan — AI kustom tidak tersedia/ tidak lolos cek.)")


def skill_buat_game_android(args, ctx):
    nama = str(args.get("nama", "")).strip()
    custom = _ai_activity(args, ctx, nama, "game")
    out = generate_mod.android_game(nama, str(args.get("paket", "")).strip(),
                                    activity_override=custom)
    return out + (" Kodenya ditulis AI mengikuti instruksimu." if custom else
                  " (Template bawaan — AI kustom tidak tersedia/ tidak lolos cek.)")


def skill_buat_halaman_web(args, ctx):
    jenis = str(args.get("jenis", "landing")).strip().lower()
    if jenis not in ("landing", "game", "kalkulator"):
        jenis = "landing"
    nama = str(args.get("nama", "")).strip()
    llm = ctx.get("llm")
    custom = genai_mod.custom_web(llm, nama, jenis,
                                  str(args.get("deskripsi", "")).strip()) if llm else None
    out = generate_mod.web_page(nama, jenis, html_override=custom)
    return out + (" Kodenya ditulis AI mengikuti instruksimu." if custom else
                  " (Template bawaan — AI kustom tidak tersedia/ tidak lolos cek.)")


def skill_daftar_hasil(args, ctx):
    return generate_mod.list_generated()


# ------------------------------------------------------- pabrik APK (v8) ----
import apk_factory as factory_mod


def skill_buat_apk_android(args, ctx):
    nama = str(args.get("nama", "")).strip()
    jenis = str(args.get("jenis", "aplikasi")).strip().lower()
    if jenis not in ("game", "aplikasi"):
        jenis = "game" if "game" in str(args.get("nama", "")).lower() else "aplikasi"
    custom = _ai_activity(args, ctx, nama, jenis)
    slug, title, pkg, files = generate_mod.android_project(
        nama, jenis, activity_override=custom)
    generate_mod._write(generate_mod.GEN_DIR / "android" / slug, files)
    try:
        info = factory_mod.push_project(slug, title, pkg, files)
    except RuntimeError as e:
        if "GITHUB_TOKEN" in str(e):
            return (f"Proyek '{title}' sudah dibuat, tapi pabrik APK belum aktif: "
                    "token GitHub belum terpasang di server. Pemilik perlu memasang "
                    "GITHUB_TOKEN (izin Contents ke repo your-agent) di backend/.env.")
        return f"Error pabrik APK: {e}"
    return ((f"Kode '{title}' ditulis AI mengikuti instruksimu. " if custom else
             f"'{title}' memakai template bawaan (AI kustom tidak lolos cek). ") +
            f"APK '{title}' sedang dibangun di GitHub Actions (commit {info['commit']}, "
            f"paket {pkg}). Biasanya selesai 3-6 menit. Link unduh APK (ketuk setelah "
            f"beberapa menit): {info['apk_url']} — status build: {info['actions_url']}. "
            f"Untuk mengecek sudah jadi atau belum, kirim: cek apk {slug}")


def skill_cek_apk(args, ctx):
    slug = generate_mod.slugify(str(args.get("slug", "")).strip(), "")
    if not slug:
        return "Error: sebutkan nama/slug aplikasinya, contoh: cek apk game-ketuk-target"
    try:
        ready = factory_mod.check_apk(slug)
    except Exception as e:
        return f"Belum bisa memastikan status APK '{slug}' dari server: {e}"
    if ready:
        return f"APK '{slug}' SUDAH JADI dan bisa diunduh: {factory_mod.release_url(slug)}"
    return (f"APK '{slug}' belum tersedia — build mungkin masih berjalan atau gagal. "
            f"Cek status build: {factory_mod.actions_url()}")


# ---------------------------------------------------- integrasi n8n (v11) --
def skill_kirim_ke_n8n(args, ctx):
    """Kirim perintah/data ke workflow n8n lewat webhook produksi.

    Tujuan HANYA dari env N8N_WEBHOOK_URL di server (bukan dari pesan user),
    jadi skill ini tidak bisa dipakai sebagai proxy SSRF. Bila env
    N8N_WEBHOOK_SECRET terisi, nilainya dikirim sebagai header
    X-Webhook-Secret agar workflow n8n bisa memverifikasi pengirim.
    Balasan JSON dari node 'Respond to Webhook' di n8n diteruskan ke user.
    """
    url = os.environ.get("N8N_WEBHOOK_URL", "").strip()
    if not url:
        return ("Error: integrasi n8n belum dikonfigurasi di server. "
                "Isi N8N_WEBHOOK_URL di .env backend dengan URL webhook "
                "produksi n8n (contoh: https://n8n.example.com/webhook/your-agent), "
                "lalu restart/reload backend.")
    teks = str(args.get("teks", "")).strip()
    if not teks:
        return "Error: parameter 'teks' kosong — tidak ada yang dikirim ke n8n."
    payload = {
        "source": "your-agent",
        "session_id": ctx.get("session_id") or "default",
        "aksi": str(args.get("aksi", "perintah")).strip() or "perintah",
        "teks": teks,
        "waktu": datetime.now(ZoneInfo("Asia/Jakarta")).isoformat(timespec="seconds"),
    }
    headers = {"Content-Type": "application/json",
               "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                             "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
    secret = os.environ.get("N8N_WEBHOOK_SECRET", "").strip()
    if secret:
        headers["X-Webhook-Secret"] = secret
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read(20_000).decode("utf-8", "replace").strip()
            status = resp.status
    except urllib.error.HTTPError as e:
        return f"Error: n8n menolak permintaan (HTTP {e.code}). Cek workflow n8n aktif & URL webhook benar."
    except Exception as e:
        return f"Error: tidak bisa menjangkau n8n ({e}). Cek server n8n hidup & N8N_WEBHOOK_URL benar."
    if not raw:
        return f"Terkirim ke n8n (HTTP {status}), workflow berjalan tanpa balasan teks."
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            pesan = data.get("pesan") or data.get("message") or data.get("reply")
            if pesan:
                return f"Balasan n8n: {pesan}"
        return f"Balasan n8n (HTTP {status}): {raw[:1000]}"
    except Exception:
        return f"Balasan n8n (HTTP {status}): {raw[:1000]}"


# --------------------------------------------------------------- registry ----
SKILLS = {
    "kalkulator": {
        "organ": "tangan", "risk": "aman", "params": ["ekspresi"],
        "description": "Menghitung ekspresi aritmetika, contoh: (120000*3)/4 + 5000",
        "run": skill_kalkulator,
    },
    "waktu_sekarang": {
        "organ": "kaki", "risk": "aman", "params": ["zona"],
        "description": "Menjawab tanggal/hari/jam sekarang pada zona waktu tertentu (default Asia/Jakarta).",
        "run": skill_waktu,
    },
    "ambil_halaman_web": {
        "organ": "kaki", "risk": "aman", "params": ["url"],
        "description": "Mengambil dan membaca teks sebuah halaman web publik dari URL.",
        "run": skill_ambil_web,
    },
    "simpan_catatan": {
        "organ": "tangan", "risk": "aman", "params": ["teks"],
        "description": "Menyimpan catatan/teks penting milik pengguna untuk sesi ini.",
        "run": skill_simpan_catatan,
    },
    "baca_catatan": {
        "organ": "tangan", "risk": "aman", "params": [],
        "description": "Membaca kembali semua catatan yang tersimpan untuk sesi ini.",
        "run": skill_baca_catatan,
    },
    "hapus_catatan": {
        "organ": "tangan", "risk": "konfirmasi", "params": [],
        "description": "Menghapus SEMUA catatan sesi ini. Merusak — wajib persetujuan manusia dulu.",
        "run": skill_hapus_catatan,
    },
    "ingat": {
        "organ": "tangan", "risk": "aman", "params": ["fakta"],
        "description": "Menyimpan satu fakta ke ingatan jangka panjang MEMORY.md (lintas sesi). Pakai saat pengguna berkata 'ingat ...'.",
        "run": skill_ingat,
    },
    "baca_memori": {
        "organ": "tangan", "risk": "aman", "params": [],
        "description": "Membaca isi ingatan jangka panjang MEMORY.md.",
        "run": skill_baca_memori,
    },
    "hapus_memori": {
        "organ": "tangan", "risk": "konfirmasi", "params": [],
        "description": "Menghapus SEMUA fakta di MEMORY.md. Merusak — wajib persetujuan manusia dulu.",
        "run": skill_hapus_memori,
    },
    "buat_aplikasi_android": {
        "organ": "tangan", "risk": "aman", "params": ["nama", "paket", "deskripsi"],
        "description": "Membuat proyek aplikasi Android Kotlin lengkap (gradle, manifest, MainActivity) dari template, siap dibuka di Android Studio.",
        "run": skill_buat_aplikasi_android,
    },
    "buat_game_android": {
        "organ": "tangan", "risk": "aman", "params": ["nama", "paket", "deskripsi"],
        "description": "Membuat proyek game Android Kotlin (Canvas 'Ketuk Target': skor + timer) lengkap, siap build di Android Studio.",
        "run": skill_buat_game_android,
    },
    "buat_halaman_web": {
        "organ": "tangan", "risk": "aman", "params": ["nama", "jenis", "deskripsi"],
        "description": "Membuat satu file index.html utuh. jenis: landing (default), game, atau kalkulator.",
        "run": skill_buat_halaman_web,
    },
    "daftar_hasil_generate": {
        "organ": "kaki", "risk": "aman", "params": [],
        "description": "Mendaftar semua proyek yang pernah dibuat skill generator (Android/web).",
        "run": skill_daftar_hasil,
    },
    "buat_apk_android": {
        "organ": "tangan", "risk": "aman", "params": ["nama", "jenis", "deskripsi"],
        "description": "Membuat aplikasi/game Android DAN membangunnya jadi file APK asli lewat GitHub Actions (jenis: game/aplikasi). Pakai saat pengguna meminta APK, bukan sekadar proyek/kode.",
        "run": skill_buat_apk_android,
    },
    "cek_apk": {
        "organ": "kaki", "risk": "aman", "params": ["slug"],
        "description": "Mengecek apakah APK hasil pabrik (dari buat_apk_android) sudah jadi dan bisa diunduh.",
        "run": skill_cek_apk,
    },
    "kirim_ke_n8n": {
        "organ": "tangan", "risk": "aman", "params": ["aksi", "teks"],
        "description": "Mengirim perintah/data ke workflow otomasi n8n lewat webhook (URL tujuan diatur server lewat N8N_WEBHOOK_URL). Pakai saat pengguna berkata 'n8n: ...', 'otomasi: ...', atau 'kirim ke n8n ...'. Balasan workflow n8n diteruskan ke pengguna.",
        "run": skill_kirim_ke_n8n,
    },
}


def public_list():
    return [{"name": name, "organ": s["organ"], "risk": s["risk"],
             "params": s["params"], "description": s["description"]}
            for name, s in SKILLS.items()]


def execute(name, args, ctx):
    """Jalankan skill. Mengembalikan (hasil_teks, error_bool). Risiko dicek pemanggil."""
    skill = SKILLS.get(name)
    if not skill:
        return f"Error: skill '{name}' tidak ada di registry.", True
    try:
        return skill["run"](args or {}, ctx), False
    except Exception as e:
        return f"Error saat menjalankan skill {name}: {e}", True
