#!/usr/bin/env python3
"""
Backend Your Agent v7 — Python stdlib saja, tanpa pip install.

Baru di v6 (penyimpanan permanen):
  A. Sesi percakapan tersimpan di backend/data/sessions.json (lihat store.py):
     restart server / tidur di Render gratis tidak lagi menghapus ingatan sesi.
     Catatan (notes.json) sudah permanen sejak v5; token konfirmasi agen sengaja
     tetap in-memory supaya gagal-aman (aksi tertunda hangus saat restart).

Baru di v5 (agen: otak + kaki + tangan, harness semi):
  A. POST /agent — satu putaran agen (lihat agent.py): router deterministik
     0-token dulu, perencana LLM sesudahnya, skill dari registry skills.py,
     skill merusak berhenti di gerbang konfirmasi manusia.
  B. GET /skills — daftar skill (tangan/kaki) beserta level risikonya.

Dari v4 (siap deploy publik):
  0. APP_TOKEN: bila diisi di .env, semua endpoint POST wajib membawa header
     X-App-Token yang cocok — tanpa itu backend publik bisa dipakai orang lain
     untuk menghabiskan kuota API key-mu. /health tetap terbuka (tanpa data sensitif).

Fitur:
  1. API key Meta/Llama disimpan aman di .env (tidak pernah dikirim ke Android).
  2. POST /chat menerima pesan Android dan meneruskannya ke Meta AI (Llama API).
  3. POST /chat/stream (v3): jawaban STREAMING via Server-Sent Events —
     potongan teks dikirim begitu dihasilkan, Android menampilkannya kata per kata.
     Format tiap event:  data: {"chunk": "..."}  dan penutup  data: {"done": true}
  4. SESI percakapan di server: kirim "session_id" yang sama, backend mengingat
     riwayatnya — Android tidak perlu mengirim ulang seluruh riwayat.
  5. SYSTEM_PROMPT bisa diatur dari .env (kepribadian asistenmu sendiri).
  6. POST /reset menghapus ingatan satu sesi.
  7. Tanpa key -> MODE MOCK otomatis (streaming disimulasikan per kata),
     alur tetap bisa dites end-to-end.

Jalankan:  python3 backend/main.py
"""
import json
import os
import sys
import threading
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import agent as agent_mod
import memory_store as memory_mod
import skills as skills_mod
import store as store_mod

VERSION = "11.1"
ROOT = Path(__file__).resolve().parent.parent


def load_env():
    for candidate in (ROOT / ".env", Path(__file__).resolve().parent / ".env"):
        if candidate.is_file():
            for line in candidate.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()

API_KEY = os.environ.get("META_API_KEY", "").strip()
BASE_URL = (os.environ.get("META_API_BASE_URL") or os.environ.get("META_API_BASE") or "https://api.llama.com/v1").rstrip("/")
MODEL = os.environ.get("META_MODEL", "Llama-4-Maverick-17B-128E-Instruct-FP8")
PORT = int(os.environ.get("PORT", "8000"))
SYSTEM_PROMPT = os.environ.get(
    "SYSTEM_PROMPT",
    "Kamu adalah asisten berbahasa Indonesia yang membantu dengan singkat, jelas, dan ramah.",
).strip()
MAX_CHARS = int(os.environ.get("MAX_MESSAGE_CHARS", "4000"))
MAX_HISTORY = 20  # pesan terakhir per sesi yang diingat server
MOCK = os.environ.get("MOCK_MODE", "").lower() in ("1", "true", "yes") or not API_KEY
APP_TOKEN = os.environ.get("APP_TOKEN", "").strip()

_sessions = store_mod.load_sessions()  # v6: dimuat dari disk, bukan dict kosong
_lock = threading.Lock()

# v7: SOUL.md — jati diri agen, dibaca sekali saat start (edit file lalu restart).
try:
    SOUL_TEXT = (Path(__file__).resolve().parent / "SOUL.md").read_text(encoding="utf-8").strip()
except Exception:
    SOUL_TEXT = ""


def _system_messages():
    """Pesan system untuk LLM: prompt dasar + SOUL.md + ingatan MEMORY.md."""
    msgs = []
    prompt = SYSTEM_PROMPT
    if SOUL_TEXT:
        prompt = (prompt + "\n\n" + SOUL_TEXT).strip() if prompt else SOUL_TEXT
    if prompt:
        msgs.append({"role": "system", "content": prompt})
    memory = memory_mod.load_text()
    if memory:
        msgs.append({"role": "system",
                     "content": "Ingatan jangka panjangmu tentang pengguna (dari MEMORY.md):\n" + memory})
    return msgs


def get_session(session_id):
    with _lock:
        return _sessions.setdefault(session_id, [])



def _llm_cfg(override=None):
    """Konfigurasi LLM efektif (v11): override per-request dari aplikasi
    (base_url/model/api_key gaya OpenAI-compatible) menang atas env server.
    Dipakai sesaat untuk request itu saja — TIDAK disimpan/ dicatat server."""
    cfg = {"base_url": BASE_URL, "model": MODEL, "api_key": API_KEY}
    if isinstance(override, dict):
        base = str(override.get("base_url", "")).strip().rstrip("/")
        if base.startswith(("https://", "http://")):
            cfg["base_url"] = base
        model = str(override.get("model", "")).strip()
        if model:
            cfg["model"] = model
        key = str(override.get("api_key", "")).strip()
        if key:
            cfg["api_key"] = key
    return cfg


# UA browser wajib: Cloudflare di depan Groq menolak UA bawaan Python-urllib (403).
def _retryable(e):
    """429 (kuota/rate limit) & 5xx layak dicoba ulang dengan jeda."""
    return isinstance(e, urllib.error.HTTPError) and e.code in (429, 500, 502, 503)


def ask_meta(messages, override=None):
    cfg = _llm_cfg(override)
    payload = json.dumps({"model": cfg["model"], "messages": messages}).encode("utf-8")
    last_err = None
    for attempt, wait in enumerate((0, 2, 5)):
        if wait:
            time.sleep(wait)
        req = urllib.request.Request(
            f"{cfg['base_url']}/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['api_key']}", "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001 - retry hanya untuk 429/5xx
            last_err = e
            if not _retryable(e):
                raise
    raise last_err


def stream_meta(messages, override=None):
    """Yield potongan teks dari API gaya OpenAI dengan stream=true (SSE hulu)."""
    cfg = _llm_cfg(override)
    payload = json.dumps({"model": cfg["model"], "messages": messages, "stream": True}).encode("utf-8")
    req = urllib.request.Request(
        f"{cfg['base_url']}/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['api_key']}", "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"},
        method="POST",
    )
    resp = None
    last_err = None
    for attempt, wait in enumerate((0, 2, 5)):
        if wait:
            time.sleep(wait)
        try:
            resp = urllib.request.urlopen(req, timeout=120)
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            if not _retryable(e):
                raise
    if resp is None:
        raise last_err
    with resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
                chunk = obj["choices"][0].get("delta", {}).get("content", "")
            except (ValueError, KeyError, IndexError):
                continue
            if chunk:
                yield chunk


def stream_mock(user_text, history_len):
    """Simulasi streaming mode mock: kirim balasan per beberapa kata."""
    words = mock_reply(user_text, history_len).split(" ")
    for i in range(0, len(words), 3):
        yield " ".join(words[i:i + 3]) + (" " if i + 3 < len(words) else "")
        time.sleep(0.05)


def mock_reply(user_text, history_len):
    return (
        "[MODE MOCK — META_API_KEY belum diisi] "
        f"Pesanmu sampai dengan utuh: \"{user_text}\". "
        f"Backend mengingat {history_len} pesan sebelumnya dalam sesi ini. "
        "Isi META_API_KEY di .env lalu restart backend untuk jawaban Meta AI asli."
    )


class Handler(BaseHTTPRequestHandler):
    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-App-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_OPTIONS(self):
        self._json(200, {})

    def do_GET(self):
        path = self.path.rstrip("/")
        if path in ("/soul", "/memory"):
            if not self._authorized():
                self._json(401, {"error": "token aplikasi salah atau tidak ada (header X-App-Token)"})
                return
            if path == "/soul":
                self._json(200, {"soul": SOUL_TEXT, "version": VERSION})
            else:
                self._json(200, {"memory": memory_mod.read_full(), "version": VERSION})
            return
        if path == "/skills":
            self._json(200, {"skills": skills_mod.public_list(), "version": VERSION})
        elif path in ("", "/health"):
            self._json(200, {"status": "ok", "version": VERSION,
                              "mode": "mock" if MOCK else "live", "model": MODEL,
                              "auth": bool(APP_TOKEN), "soul": bool(SOUL_TEXT),
                              "skills": len(skills_mod.SKILLS)})
        else:
            self._json(404, {"error": "not found"})

    def _authorized(self):
        return not APP_TOKEN or self.headers.get("X-App-Token", "") == APP_TOKEN

    def do_POST(self):
        path = self.path.rstrip("/")
        if path in ("/chat", "/chat/stream", "/reset", "/agent") and not self._authorized():
            self._json(401, {"error": "token aplikasi salah atau tidak ada (header X-App-Token)"})
            return
        if path == "/reset":
            try:
                data = self._read_json()
            except (ValueError, json.JSONDecodeError):
                data = {}
            session_id = str(data.get("session_id", "")).strip()
            with _lock:
                _sessions.pop(session_id, None)
                store_mod.save_sessions(_sessions)
            self._json(200, {"status": "ok", "reset": session_id or None})
            return
        if path == "/agent":
            self._handle_agent()
            return
        if path not in ("/chat", "/chat/stream"):
            self._json(404, {"error": "not found"})
            return
        streaming = path == "/chat/stream"

        try:
            data = self._read_json()
        except (ValueError, json.JSONDecodeError):
            self._json(400, {"error": "body harus JSON, contoh: {\"message\": \"halo\"}"})
            return

        user_text = str(data.get("message", "")).strip()
        if not user_text:
            self._json(400, {"error": "field 'message' wajib diisi"})
            return
        if len(user_text) > MAX_CHARS:
            self._json(400, {"error": f"pesan terlalu panjang (maks {MAX_CHARS} karakter)"})
            return

        session_id = str(data.get("session_id", "")).strip()
        if session_id:
            history = get_session(session_id)
        else:
            raw = data.get("history") or []
            history = [m for m in raw if isinstance(m, dict) and "role" in m and "content" in m]

        history_len = len(history)
        messages = _system_messages()
        messages.extend(history[-MAX_HISTORY:])
        messages.append({"role": "user", "content": user_text})

        if streaming:
            self._stream(user_text, messages, history, session_id, history_len, data.get("llm"))
            return

        if MOCK:
            reply = mock_reply(user_text, history_len)
        else:
            try:
                reply = ask_meta(messages, data.get("llm"))
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    self._json(200, {"reply": agent_mod.BUSY_REPLY, "mode": "live",
                                     "version": VERSION})
                    return
                detail = e.read().decode("utf-8", "replace")[:300]
                self._json(502, {"error": f"Meta API menjawab {e.code}", "detail": detail})
                return
            except Exception as e:
                self._json(502, {"error": "gagal menghubungi Meta API", "detail": str(e)[:300]})
                return

        self._remember(session_id, history, user_text, reply)
        self._json(200, {"reply": reply, "mode": "mock" if MOCK else "live", "version": VERSION})

    def _handle_agent(self):
        try:
            data = self._read_json()
        except (ValueError, json.JSONDecodeError):
            self._json(400, {"error": "body harus JSON"})
            return
        session_id = str(data.get("session_id", "")).strip()
        effective_session = session_id or "default"
        history = get_session(session_id) if session_id else []
        agent_history = _system_messages() + list(history)

        confirm_token = str(data.get("confirm_token", "")).strip()
        if confirm_token:
            outcome, err = agent_mod.run_confirmed(confirm_token, effective_session)
            if err:
                self._json(400, {"error": err})
                return
            result, steps = outcome
            self._remember(session_id, history, "(konfirmasi aksi)", result)
            self._json(200, {"reply": result, "steps": steps, "confirmed": True,
                             "mode": "mock" if MOCK else "live", "version": VERSION})
            return

        user_text = str(data.get("message", "")).strip()
        if not user_text:
            self._json(400, {"error": "field 'message' wajib diisi"})
            return
        if len(user_text) > MAX_CHARS:
            self._json(400, {"error": f"pesan terlalu panjang (maks {MAX_CHARS} karakter)"})
            return

        llm_call = None if MOCK else (lambda msgs: ask_meta(msgs, data.get("llm")))
        try:
            result = agent_mod.run_agent(user_text, effective_session, agent_history,
                                         llm_call, mock_reply)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                self._json(200, {"reply": agent_mod.BUSY_REPLY, "steps": [],
                                 "mode": "live", "version": VERSION})
                return
            self._json(502, {"error": "agen gagal berjalan", "detail": str(e)[:300]})
            return
        except Exception as e:
            self._json(502, {"error": "agen gagal berjalan", "detail": str(e)[:300]})
            return
        result.setdefault("steps", [])
        if not result.get("needs_confirmation"):
            self._remember(session_id, history, user_text, result.get("reply", ""))
        result.update({"mode": "mock" if MOCK else "live", "version": VERSION})
        self._json(200, result)

    def _remember(self, session_id, history, user_text, reply):
        if not session_id:
            return
        with _lock:
            history.append({"role": "user", "content": user_text})
            history.append({"role": "assistant", "content": reply})
            del history[:-MAX_HISTORY]
            store_mod.save_sessions(_sessions)  # v6: ingatan langsung tersimpan ke disk

    def _sse(self, obj):
        line = ("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n").encode("utf-8")
        self.wfile.write(line)
        self.wfile.flush()

    def _stream(self, user_text, messages, history, session_id, history_len, llm_override=None):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        parts = []
        try:
            chunks = stream_mock(user_text, history_len) if MOCK else stream_meta(messages, llm_override)
            for chunk in chunks:
                parts.append(chunk)
                self._sse({"chunk": chunk})
        except Exception as e:
            self._sse({"error": "gagal menghubungi Meta API", "detail": str(e)[:300]})
            return
        reply = "".join(parts)
        self._remember(session_id, history, user_text, reply)
        self._sse({"done": True, "mode": "mock" if MOCK else "live", "version": VERSION})

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    mode = "MOCK (tanpa key)" if MOCK else f"LIVE (model {MODEL})"
    print(f"Your Agent backend v{VERSION} jalan di http://0.0.0.0:{PORT} — mode: {mode}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
