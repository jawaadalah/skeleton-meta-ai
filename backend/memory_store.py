#!/usr/bin/env python3
"""
MEMORY_STORE — ingatan jangka panjang agen, ala MEMORY.md milik Muse.

Fakta disimpan sebagai bullet Markdown di backend/data/MEMORY.md (folder data
tidak ikut git, jadi ingatan ini privat dan selamat dari update kode — di
PythonAnywhere file ini persisten). Berbeda dari catatan per-sesi (notes.json):
memori ini berlaku lintas sesi dan dibaca agen setiap percakapan.
"""
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DATA_DIR = Path(__file__).resolve().parent / "data"
MEMORY_FILE = DATA_DIR / "MEMORY.md"
_lock = threading.Lock()

_HEADER = "# MEMORY — ingatan jangka panjang agen\n\n## Fakta\n"


def load_text(max_chars=3000):
    """Isi MEMORY.md (dipotong) untuk disuntikkan ke konteks. '' bila kosong."""
    with _lock:
        try:
            text = MEMORY_FILE.read_text(encoding="utf-8")
        except Exception:
            return ""
    facts = [ln for ln in text.splitlines() if ln.startswith("- ")]
    if not facts:
        return ""
    return "\n".join(facts)[:max_chars]


def read_full():
    with _lock:
        try:
            return MEMORY_FILE.read_text(encoding="utf-8")
        except Exception:
            return ""


def append_fact(fakta):
    """Tambah satu fakta. Mengembalikan jumlah fakta sekarang."""
    fakta = " ".join(str(fakta).split())[:500]
    with _lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            text = MEMORY_FILE.read_text(encoding="utf-8")
        except Exception:
            text = _HEADER
        if "## Fakta" not in text:
            text = _HEADER
        tanggal = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d %b %Y")
        text = text.rstrip() + f"\n- ({tanggal}) {fakta}\n"
        tmp = MEMORY_FILE.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(MEMORY_FILE)
        return sum(1 for ln in text.splitlines() if ln.startswith("- "))


def clear_all():
    """Hapus semua fakta (skill level konfirmasi). Mengembalikan jumlah terhapus."""
    with _lock:
        count = 0
        try:
            count = sum(1 for ln in MEMORY_FILE.read_text(encoding="utf-8").splitlines()
                        if ln.startswith("- "))
        except Exception:
            pass
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        MEMORY_FILE.write_text(_HEADER, encoding="utf-8")
        return count
