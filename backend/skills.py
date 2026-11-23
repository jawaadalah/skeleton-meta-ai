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
import re
import socket
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
    req = urllib.request.Request(url, headers={"User-Agent": "SkeletonAgent/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read(200_000).decode("utf-8", "replace")
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw, flags=re.S | re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"\s+", " ", text).strip()
    return f"Isi {url} (±{len(text)} karakter, dipotong 2.000):\n{text[:2000]}"


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
