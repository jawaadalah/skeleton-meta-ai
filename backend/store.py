#!/usr/bin/env python3
"""
STORE — penyimpanan permanen sesi percakapan (v6). Python stdlib saja.

File: backend/data/sessions.json — sudah masuk .gitignore lewat "backend/data/",
jadi riwayat chat tidak ikut ter-commit ke Git. Format:
  {"sessions": {"<session_id>": {"messages": [...], "updated": "<iso>"}}}

Aturan:
  - Simpan atomik: tulis ke file .tmp lalu os.replace, supaya crash di tengah
    tulis tidak merusak file sesi yang sudah ada.
  - File rusak / tidak bisa dibaca -> mulai dari sesi kosong, server tetap jalan.
  - Maks 50 sesi; bila lebih, sesi yang paling lama tidak dipakai dibuang dulu.
    Tiap sesi tetap dibatasi 20 pesan terakhir (MAX_HISTORY di main.py).

Batasan jujur: file ini bertahan saat server di-restart atau tidur di instance
yang sama (persis kasus Render gratis yang tidur setelah ~15 menit idle).
Tapi filesystem Render gratis itu ephemeral — redeploy / deploy ulang akan
menghapusnya. Untuk daya tahan lintas deploy, langkah berikut adalah database
(SQLite di disk persisten / Postgres gratis), bukan file JSON ini.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
SESSIONS_FILE = DATA_DIR / "sessions.json"
MAX_SESSIONS = 50


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_sessions():
    """Baca sesi dari disk. Kembalikan {session_id: [pesan, ...]}."""
    try:
        raw = json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    sessions = raw.get("sessions", {}) if isinstance(raw, dict) else {}
    out = {}
    for sid, entry in sessions.items():
        if not isinstance(sid, str) or not isinstance(entry, dict):
            continue
        msgs = entry.get("messages", [])
        if not isinstance(msgs, list):
            continue
        clean = [m for m in msgs
                 if isinstance(m, dict) and "role" in m and "content" in m]
        if clean:
            out[sid] = clean
    return out


def _previous_updated():
    try:
        raw = json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
        sessions = raw.get("sessions", {}) if isinstance(raw, dict) else {}
        return {sid: e.get("updated", "")
                for sid, e in sessions.items() if isinstance(e, dict)}
    except Exception:
        return {}


def save_sessions(sessions):
    """Tulis seluruh sesi ke disk secara atomik. Gagal tulis tidak melempar."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        prev = _previous_updated()
        now = _now_iso()
        payload = {"sessions": {}}
        for sid, msgs in sessions.items():
            payload["sessions"][sid] = {
                "messages": list(msgs),
                "updated": prev.get(sid) or now,
            }
        # Buang sesi terlama bila melebihi batas.
        if len(payload["sessions"]) > MAX_SESSIONS:
            ordered = sorted(payload["sessions"].items(),
                             key=lambda kv: kv[1]["updated"])
            for sid, _ in ordered[:len(payload["sessions"]) - MAX_SESSIONS]:
                del payload["sessions"][sid]
        tmp = SESSIONS_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        os.replace(tmp, SESSIONS_FILE)
    except Exception:
        pass
