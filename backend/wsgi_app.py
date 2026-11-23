#!/usr/bin/env python3
"""
Adapter WSGI untuk PythonAnywhere (free) — memakai ulang semua logika
backend/main.py (sesi, mock/live, agen) tanpa mengubah perilaku HTTP aslinya.

Dipakai oleh file WSGI PythonAnywhere:
    import sys
    sys.path.insert(0, "/home/<username>/skeleton-meta-ai/backend")
    from wsgi_app import application

Catatan platform: di PythonAnywhere free, /chat/stream dikirim sebagai satu
aliran SSE oleh uWSGI tetapi bisa ter-buffer (jawaban tiba sekaligus di akhir,
bukan kata-per-kata). Endpoint lain identik dengan server HTTP biasa.
"""
import json
import os
import socket
import urllib.error


def _ensure_pa_proxy():
    """PythonAnywhere free: worker WSGI tidak mewarisi env proxy konsol,
    padahal semua trafik keluar wajib lewat proxy.server:3128 (whitelist).
    Tanpa ini urllib gagal "Tunnel connection failed: 403". Hanya aktif
    bila host proxy.server bisa di-resolve (khusus PA) dan env belum ada."""
    if os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY"):
        return
    try:
        socket.gethostbyname("proxy.server")
    except OSError:
        return
    os.environ["http_proxy"] = "http://proxy.server:3128"
    os.environ["https_proxy"] = "http://proxy.server:3128"


_ensure_pa_proxy()

import main as bm  # backend/main.py — fungsi inti dipakai ulang, server tidak dijalankan

_STATUS = {200: "200 OK", 400: "400 Bad Request", 401: "401 Unauthorized",
           404: "404 Not Found", 502: "502 Bad Gateway"}


def _json(start_response, code, obj):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    start_response(_STATUS[code], [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Access-Control-Allow-Origin", "*"),
        ("Access-Control-Allow-Headers", "Content-Type, X-App-Token"),
        ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
    ])
    return [body]


def _read_json(environ):
    length = int(environ.get("CONTENT_LENGTH") or 0)
    raw = environ["wsgi.input"].read(length) if length else b"{}"
    return json.loads(raw or b"{}")


def _remember(session_id, history, user_text, reply):
    if not session_id:
        return
    with bm._lock:
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": reply})
        del history[:-bm.MAX_HISTORY]
        bm.store_mod.save_sessions(bm._sessions)


def _handle_agent(environ, start_response):
    try:
        data = _read_json(environ)
    except (ValueError, json.JSONDecodeError):
        return _json(start_response, 400, {"error": "body harus JSON"})
    session_id = str(data.get("session_id", "")).strip()
    effective_session = session_id or "default"
    history = bm.get_session(session_id) if session_id else []

    confirm_token = str(data.get("confirm_token", "")).strip()
    if confirm_token:
        outcome, err = bm.agent_mod.run_confirmed(confirm_token, effective_session)
        if err:
            return _json(start_response, 400, {"error": err})
        result, steps = outcome
        _remember(session_id, history, "(konfirmasi aksi)", result)
        return _json(start_response, 200, {"reply": result, "steps": steps, "confirmed": True,
                                           "mode": "mock" if bm.MOCK else "live",
                                           "version": bm.VERSION})

    user_text = str(data.get("message", "")).strip()
    if not user_text:
        return _json(start_response, 400, {"error": "field 'message' wajib diisi"})
    if len(user_text) > bm.MAX_CHARS:
        return _json(start_response, 400,
                     {"error": f"pesan terlalu panjang (maks {bm.MAX_CHARS} karakter)"})

    bm._reset_usage()
    llm_call = None if bm.MOCK else (lambda msgs: bm.ask_meta(msgs, data.get("llm")))
    try:
        result = bm.agent_mod.run_agent(user_text, effective_session,
                                        bm._system_messages(data.get("lang")) + list(history),
                                        llm_call, bm.mock_reply)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return _json(start_response, 200, {"reply": bm.agent_mod.BUSY_REPLY, "steps": [],
                                               "mode": "live", "version": bm.VERSION})
        return _json(start_response, 502, {"error": "agen gagal berjalan", "detail": str(e)[:300]})
    except Exception as e:
        return _json(start_response, 502, {"error": "agen gagal berjalan", "detail": str(e)[:300]})
    result.setdefault("steps", [])
    if not result.get("needs_confirmation"):
        _remember(session_id, history, user_text, result.get("reply", ""))
    result.update({"mode": "mock" if bm.MOCK else "live", "version": bm.VERSION})
    usage = bm._get_usage()
    if usage:
        result["usage"] = usage
    quota = bm._get_quota()
    if quota:
        result["quota"] = quota
    return _json(start_response, 200, result)


def _handle_chat(environ, start_response, streaming):
    try:
        data = _read_json(environ)
    except (ValueError, json.JSONDecodeError):
        return _json(start_response, 400,
                     {"error": "body harus JSON, contoh: {\"message\": \"halo\"}"})

    user_text = str(data.get("message", "")).strip()
    if not user_text:
        return _json(start_response, 400, {"error": "field 'message' wajib diisi"})
    if len(user_text) > bm.MAX_CHARS:
        return _json(start_response, 400,
                     {"error": f"pesan terlalu panjang (maks {bm.MAX_CHARS} karakter)"})

    session_id = str(data.get("session_id", "")).strip()
    if session_id:
        history = bm.get_session(session_id)
    else:
        raw = data.get("history") or []
        history = [m for m in raw if isinstance(m, dict) and "role" in m and "content" in m]

    bm._reset_usage()
    history_len = len(history)
    messages = bm._system_messages(data.get("lang"))
    messages.extend(history[-bm.MAX_HISTORY:])
    messages.append({"role": "user", "content": user_text})

    if streaming:
        def gen():
            parts = []
            try:
                chunks = bm.stream_mock(user_text, history_len) if bm.MOCK else bm.stream_meta(messages, data.get("llm"))
                for chunk in chunks:
                    parts.append(chunk)
                    yield ("data: " + json.dumps({"chunk": chunk}, ensure_ascii=False) + "\n\n").encode("utf-8")
            except Exception as e:
                yield ("data: " + json.dumps({"error": "gagal menghubungi Meta API",
                                               "detail": str(e)[:300]}, ensure_ascii=False) + "\n\n").encode("utf-8")
                return
            _remember(session_id, history, user_text, "".join(parts))
            done_obj = {"done": True, "mode": "mock" if bm.MOCK else "live",
                        "version": bm.VERSION}
            usage = bm._get_usage()
            if usage:
                done_obj["usage"] = usage
            quota = bm._get_quota()
            if quota:
                done_obj["quota"] = quota
            yield ("data: " + json.dumps(done_obj, ensure_ascii=False) + "\n\n").encode("utf-8")
        start_response("200 OK", [
            ("Content-Type", "text/event-stream; charset=utf-8"),
            ("Cache-Control", "no-cache"),
            ("Access-Control-Allow-Origin", "*"),
        ])
        return gen()

    if bm.MOCK:
        reply = bm.mock_reply(user_text, history_len)
    else:
        try:
            reply = bm.ask_meta(messages, data.get("llm"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                return _json(start_response, 200, {"reply": bm.agent_mod.BUSY_REPLY,
                                                   "mode": "live", "version": bm.VERSION})
            detail = e.read().decode("utf-8", "replace")[:300]
            return _json(start_response, 502, {"error": f"Meta API menjawab {e.code}", "detail": detail})
        except Exception as e:
            return _json(start_response, 502, {"error": "gagal menghubungi Meta API", "detail": str(e)[:300]})

    _remember(session_id, history, user_text, reply)
    out = {"reply": reply, "mode": "mock" if bm.MOCK else "live", "version": bm.VERSION}
    usage = bm._get_usage()
    if usage:
        out["usage"] = usage
    quota = bm._get_quota()
    if quota:
        out["quota"] = quota
    return _json(start_response, 200, out)


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    path = (environ.get("PATH_INFO") or "").rstrip("/")

    if method == "OPTIONS":
        return _json(start_response, 200, {})

    if method == "GET":
        if path in ("/soul", "/memory"):
            if bm.APP_TOKEN and environ.get("HTTP_X_APP_TOKEN", "") != bm.APP_TOKEN:
                return _json(start_response, 401,
                             {"error": "token aplikasi salah atau tidak ada (header X-App-Token)"})
            if path == "/soul":
                return _json(start_response, 200, {"soul": bm.SOUL_TEXT, "version": bm.VERSION})
            return _json(start_response, 200,
                         {"memory": bm.memory_mod.read_full(), "version": bm.VERSION})
        if path == "/skills":
            return _json(start_response, 200,
                         {"skills": bm.skills_mod.public_list(), "version": bm.VERSION})
        if path in ("", "/health"):
            return _json(start_response, 200,
                         {"status": "ok", "version": bm.VERSION,
                          "mode": "mock" if bm.MOCK else "live", "model": bm.MODEL,
                          "auth": bool(bm.APP_TOKEN), "soul": bool(bm.SOUL_TEXT),
                          "skills": len(bm.skills_mod.SKILLS),
                          "quota": bm._get_quota()})
        return _json(start_response, 404, {"error": "not found"})

    if method == "POST":
        if path in ("/chat", "/chat/stream", "/reset", "/agent"):
            if bm.APP_TOKEN and environ.get("HTTP_X_APP_TOKEN", "") != bm.APP_TOKEN:
                return _json(start_response, 401,
                             {"error": "token aplikasi salah atau tidak ada (header X-App-Token)"})
        if path == "/reset":
            try:
                data = _read_json(environ)
            except (ValueError, json.JSONDecodeError):
                data = {}
            session_id = str(data.get("session_id", "")).strip()
            with bm._lock:
                bm._sessions.pop(session_id, None)
                bm.store_mod.save_sessions(bm._sessions)
            return _json(start_response, 200, {"status": "ok", "reset": session_id or None})
        if path == "/agent":
            return _handle_agent(environ, start_response)
        if path in ("/chat", "/chat/stream"):
            return _handle_chat(environ, start_response, streaming=(path == "/chat/stream"))
        return _json(start_response, 404, {"error": "not found"})

    return _json(start_response, 404, {"error": "not found"})
