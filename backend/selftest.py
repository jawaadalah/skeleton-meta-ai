#!/usr/bin/env python3
"""Selftest end-to-end v6: health, /chat, streaming, sesi, validasi, token, AGEN + skill, persistensi."""
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:8000"


def call(method, path, obj=None):
    data = json.dumps(obj).encode("utf-8") if obj is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def stream(path, obj):
    """POST lalu baca event SSE satu per satu. Kembalikan (list_chunk, event_terakhir)."""
    req = urllib.request.Request(BASE + path, data=json.dumps(obj).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    chunks, last = [], {}
    with urllib.request.urlopen(req, timeout=15) as r:
        for raw in r:
            line = raw.decode("utf-8").strip()
            if line.startswith("data:"):
                event = json.loads(line[5:].strip())
                if "chunk" in event:
                    chunks.append(event["chunk"])
                last = event
    return chunks, last


def test_agent():
    agent = lambda obj: call("POST", "/agent", obj)

    skills = call("GET", "/skills")["skills"]
    by_name = {s["name"]: s for s in skills}
    assert by_name["kalkulator"]["risk"] == "aman"
    assert by_name["hapus_catatan"]["risk"] == "konfirmasi"
    print(f"OK  /skills -> {len(skills)} skill terdaftar (tangan & kaki)")

    r = agent({"message": "hitung 12*8+4", "session_id": "agen-tes"})
    assert "100" in r["reply"] and r["steps"][0]["skill"] == "kalkulator", r
    print("OK  agen router: 'hitung 12*8+4' -> skill kalkulator, hasil 100 (0 token LLM)")

    r = agent({"message": "jam berapa sekarang?", "session_id": "agen-tes"})
    assert r["steps"][0]["skill"] == "waktu_sekarang", r
    print("OK  agen router: pertanyaan jam -> skill waktu_sekarang")

    agent({"message": "catat: beli kopi untuk warung", "session_id": "agen-tes"})
    r = agent({"message": "baca catatan saya", "session_id": "agen-tes"})
    assert "beli kopi" in r["reply"], r
    print("OK  agen tangan: simpan_catatan + baca_catatan nyambung per sesi")

    r = agent({"message": "ambil isi https://127.0.0.1:8000/health", "session_id": "agen-tes"})
    assert r["steps"][0]["skill"] == "ambil_halaman_web" and "ditolak" in r["steps"][0]["result"], r
    print("OK  agen kaki: URL lokal/privat ditolak gerbang anti-SSRF")

    r = agent({"message": "hapus catatan saya", "session_id": "agen-tes"})
    assert r.get("needs_confirmation") and r.get("confirm_token"), r
    token = r["confirm_token"]
    masih = agent({"message": "baca catatan saya", "session_id": "agen-tes"})
    assert "beli kopi" in masih["reply"], "catatan tidak boleh terhapus sebelum konfirmasi!"
    print("OK  harness semi: hapus_catatan BERHENTI di gerbang konfirmasi, belum terhapus")

    r = agent({"session_id": "agen-tes", "confirm_token": token})
    assert "dihapus" in r["reply"], r
    kosong = agent({"message": "baca catatan saya", "session_id": "agen-tes"})
    assert "Belum ada catatan" in kosong["reply"], kosong
    try:
        agent({"session_id": "agen-tes", "confirm_token": token})
        raise AssertionError("token konfirmasi bekas seharusnya ditolak")
    except urllib.error.HTTPError as e:
        assert e.code == 400
    print("OK  konfirmasi manusia menjalankan aksi 1x; token bekas ditolak")


def test_persistence():
    """v6: sesi harus selamat dari restart server (server kedua di port 8002)."""
    import os
    env = dict(os.environ, PORT="8002", MOCK_MODE="1")
    base = "http://127.0.0.1:8002"

    def start():
        proc = subprocess.Popen([sys.executable, str(HERE / "main.py")],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, env=env)
        for _ in range(50):
            try:
                req = urllib.request.Request(base + "/health")
                with urllib.request.urlopen(req, timeout=5) as r:
                    json.loads(r.read().decode("utf-8"))
                return proc
            except Exception:
                time.sleep(0.2)
        proc.terminate()
        raise AssertionError("server persistensi tidak menyala")

    def stop(proc):
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    def post(obj):
        req = urllib.request.Request(base + "/chat", method="POST",
                                     headers={"Content-Type": "application/json"},
                                     data=json.dumps(obj).encode("utf-8"))
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode("utf-8"))

    def reset():
        req = urllib.request.Request(base + "/reset", method="POST",
                                     headers={"Content-Type": "application/json"},
                                     data=json.dumps({"session_id": "persist-test"}).encode("utf-8"))
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode("utf-8"))

    proc = start()
    try:
        reset()  # bersih dari run selftest sebelumnya, bila ada
        r = post({"message": "Pesan abadi pertama.", "session_id": "persist-test"})
        assert "mengingat 0 pesan" in r["reply"], r
    finally:
        stop(proc)

    proc = start()  # restart: sesi harus masih ada di disk
    try:
        r = post({"message": "Pesan abadi kedua.", "session_id": "persist-test"})
        assert "mengingat 2 pesan" in r["reply"], r
        reset()
    finally:
        stop(proc)

    proc = start()  # restart lagi: reset juga harus permanen
    try:
        r = post({"message": "Setelah reset dan restart.", "session_id": "persist-test"})
        assert "mengingat 0 pesan" in r["reply"], r
        reset()
    finally:
        stop(proc)
    print("OK  persistensi v6: sesi selamat dari restart server; /reset juga permanen")


def test_v7():
    """v7: SOUL.md, MEMORY.md jangka panjang, dan skill generator proyek."""
    agent = lambda obj: call("POST", "/agent", obj)

    health = call("GET", "/health")
    assert health["version"] == "11.3" and health["soul"] is True, health
    assert health["skills"] == 16, health
    soul = call("GET", "/soul")["soul"]
    assert "Skele" in soul, soul[:100]
    print("OK  v7 /health: versi 11.3, SOUL.md termuat, 16 skill terdaftar; /soul terbaca")

    r = agent({"message": "ingat bahwa warna favorit saya biru langit", "session_id": "v7-tes"})
    assert r["steps"][0]["skill"] == "ingat", r
    r = agent({"message": "apa yang kamu ingat tentang saya?", "session_id": "v7-tes"})
    assert r["steps"][0]["skill"] == "baca_memori" and "biru langit" in r["reply"], r
    mem = call("GET", "/memory")["memory"]
    assert "biru langit" in mem, mem
    print("OK  v7 memori: 'ingat bahwa ...' tersimpan di MEMORY.md dan terbaca lintas endpoint")

    r = agent({"message": "buatkan aplikasi android Kasir Warung", "session_id": "v7-tes"})
    assert r["steps"][0]["skill"] == "buat_aplikasi_android", r
    proj = HERE / "data" / "generated" / "android" / "kasir-warung"
    assert (proj / "app" / "src" / "main" / "AndroidManifest.xml").is_file(), proj
    assert (proj / "settings.gradle.kts").is_file()
    print("OK  v7 generator: proyek aplikasi Android 'Kasir Warung' terbuat lengkap (gradle+manifest)")

    r = agent({"message": "buatkan game android Balap Kelereng", "session_id": "v7-tes"})
    assert r["steps"][0]["skill"] == "buat_game_android", r
    kt = list((HERE / "data" / "generated" / "android" / "balap-kelereng").rglob("MainActivity.kt"))
    assert kt and "GameView" in kt[0].read_text(encoding="utf-8")
    print("OK  v7 generator: proyek game Android terbuat dengan GameView Canvas")

    r = agent({"message": "buatkan halaman web Toko Bunga Melati", "session_id": "v7-tes"})
    assert r["steps"][0]["skill"] == "buat_halaman_web", r
    html_file = HERE / "data" / "generated" / "web" / "toko-bunga-melati" / "index.html"
    assert html_file.is_file() and "Toko Bunga Melati" in html_file.read_text(encoding="utf-8")
    print("OK  v7 generator: halaman web landing terbuat sebagai index.html utuh")

    r = agent({"message": "daftar proyek yang sudah dibuat", "session_id": "v7-tes"})
    assert r["steps"][0]["skill"] == "daftar_hasil_generate" and "kasir-warung" in r["reply"], r
    print("OK  v7 generator: daftar hasil generate menampilkan proyek-proyek tadi")

    r = agent({"message": "buat aplikasi game simpel", "session_id": "v7-tes"})
    assert r["steps"] and r["steps"][0]["skill"] == "buat_game_android", r
    print("OK  v7.1 router natural: 'buat aplikasi game simpel' -> buat_game_android (kasus nyata dari HP pengguna)")

    r = agent({"message": "tolong dong kerjakan sesuatu yang bebas", "session_id": "v7-tes"})
    assert "META_API_KEY" in r["reply"] and "buatkan game android" in r["reply"], r
    print("OK  v7.1 fallback mock: perintah bebas dijawab panduan contoh perintah, bukan echo mentah")

    r = agent({"message": "hapus memori saya", "session_id": "v7-tes"})
    assert r.get("needs_confirmation") and r.get("confirm_token"), r
    masih = call("GET", "/memory")["memory"]
    assert "biru langit" in masih, "memori tidak boleh terhapus sebelum konfirmasi!"
    r2 = agent({"session_id": "v7-tes", "confirm_token": r["confirm_token"]})
    assert "dihapus" in r2["reply"], r2
    bersih = call("GET", "/memory")["memory"]
    assert "biru langit" not in bersih, bersih
    print("OK  v7 harness semi: hapus_memori berhenti di gerbang konfirmasi, lalu terhapus setelah disetujui")


def test_token_auth():
    """Nyalakan server kedua di port 8001 dengan APP_TOKEN, cek gerbang 401-nya."""
    import os
    env = dict(os.environ, PORT="8001", APP_TOKEN="rahasia-tes", MOCK_MODE="1")
    proc = subprocess.Popen([sys.executable, str(HERE / "main.py")],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, env=env)
    base = "http://127.0.0.1:8001"
    try:
        for _ in range(50):
            try:
                req = urllib.request.Request(base + "/health")
                with urllib.request.urlopen(req, timeout=5) as r:
                    health = json.loads(r.read().decode("utf-8"))
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise AssertionError("server bertoken tidak menyala")
        assert health["auth"] is True, health

        def post(token=None):
            headers = {"Content-Type": "application/json"}
            if token is not None:
                headers["X-App-Token"] = token
            req = urllib.request.Request(base + "/chat", method="POST", headers=headers,
                                         data=json.dumps({"message": "halo"}).encode("utf-8"))
            with urllib.request.urlopen(req, timeout=5) as r:
                return json.loads(r.read().decode("utf-8"))

        for bad in (None, "salah"):
            try:
                post(bad)
                raise AssertionError(f"token {bad!r} seharusnya ditolak")
            except urllib.error.HTTPError as e:
                assert e.code == 401, e.code
        ok = post("rahasia-tes")
        assert ok.get("reply"), ok
        print("OK  APP_TOKEN: tanpa/salah token ditolak (401), token benar lolos, /health tetap terbuka")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


def test_v8():
    """v8: pabrik APK — router 'jadi apk' + skill cek_apk; tanpa token harus ramah."""
    agent = lambda obj: call("POST", "/agent", obj)
    r = agent({"message": "buatkan game android Balap Kelereng jadi apk", "session_id": "v8-tes"})
    assert r["steps"][0]["skill"] == "buat_apk_android", r
    assert "token GitHub belum terpasang" in r["reply"], r
    print("OK  v8 router: 'buatkan game android ... jadi apk' -> buat_apk_android (tanpa token: pesan ramah)")
    r = agent({"message": "cek apk balap-kelereng", "session_id": "v8-tes"})
    assert r["steps"][0]["skill"] == "cek_apk", r
    print("OK  v8 router: 'cek apk <slug>' -> cek_apk")


def test_v11():
    """v11: override LLM per-request — backend memakai base_url/model/api_key
    kiriman aplikasi (stub OpenAI-compatible lokal), bukan env server."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    seen = {}

    class Stub(BaseHTTPRequestHandler):
        hits = 0

        def do_POST(self):
            Stub.hits += 1
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            if Stub.hits == 1:
                # Pukulan pertama: 429 — backend wajib mencoba ulang (retry).
                raw = json.dumps({"error": {"message": "rate limited"}}).encode()
                self.send_response(429)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            seen["auth"] = self.headers.get("Authorization", "")
            seen["model"] = body.get("model", "")
            out = {"choices": [{"message": {"content": "JAWABAN-STUB-11"}}],
                   "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}}
            raw = json.dumps(out).encode()
            self.send_response(200)
            self.send_header("x-ratelimit-limit-requests", "1000")
            self.send_header("x-ratelimit-remaining-requests", "999")
            self.send_header("x-ratelimit-limit-tokens", "200000")
            self.send_header("x-ratelimit-remaining-tokens", "199000")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *a):
            pass

    stub = ThreadingHTTPServer(("127.0.0.1", 8899), Stub)
    threading.Thread(target=stub.serve_forever, daemon=True).start()

    import os
    env = dict(os.environ, PORT="8002", META_API_KEY="kunci-env-server",
               META_API_BASE_URL="http://127.0.0.1:9/mati", META_MODEL="model-env")
    env.pop("MOCK_MODE", None)
    proc = subprocess.Popen([sys.executable, str(HERE / "main.py")],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, env=env)
    base = "http://127.0.0.1:8002"
    try:
        for _ in range(50):
            try:
                req = urllib.request.Request(base + "/health")
                with urllib.request.urlopen(req, timeout=5) as r:
                    health = json.loads(r.read().decode("utf-8"))
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise AssertionError("server v11 tidak menyala")
        assert health["mode"] == "live", health
        req = urllib.request.Request(
            base + "/chat", method="POST",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"message": "halo",
                             "llm": {"base_url": "http://127.0.0.1:8899/v1",
                                     "model": "stub-model",
                                     "api_key": "kunci-aplikasi"}}).encode("utf-8"))
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = json.loads(r.read().decode("utf-8"))
        assert "JAWABAN-STUB-11" in resp.get("reply", ""), resp
        assert Stub.hits >= 2, "retry 429 tidak terjadi"
        assert seen.get("auth") == "Bearer kunci-aplikasi", seen
        assert seen.get("model") == "stub-model", seen
        assert resp.get("usage", {}).get("total_tokens") == 18, resp
        assert resp.get("quota", {}).get("remaining_tokens") == 199000, resp
        req = urllib.request.Request(base + "/health")
        with urllib.request.urlopen(req, timeout=5) as r:
            h2 = json.loads(r.read().decode("utf-8"))
        assert h2.get("quota", {}).get("remaining_requests") == 999, h2
        assert h2.get("quota", {}).get("remaining_tokens") == 199000, h2
        print("OK  v11.3 kuota: header rate-limit tertangkap, /health menampilkan sisa kuota")
        print("OK  v11.2 info token: usage dari API diteruskan ke respons (total 18)")
        print("OK  v11 override LLM: base_url+model+api_key dari aplikasi dipakai (stub membuktikan), env server tidak dipakai")
        # Jalur WSGI (yang dipakai PythonAnywhere) juga wajib meneruskan override —
        # regresi v11: wsgi_app punya handler sendiri dan sempat tertinggal.
        import io as _io
        sys.path.insert(0, str(HERE))
        import main as _bm
        import wsgi_app as _wsgi
        old_mock = _bm.MOCK
        _bm.MOCK = False
        try:
            payload = json.dumps({"message": "halo wsgi",
                                  "llm": {"base_url": "http://127.0.0.1:8899/v1",
                                          "model": "stub-model",
                                          "api_key": "kunci-aplikasi"}}).encode()
            captured = {}
            def _sr(status, headers):
                captured["status"] = status
            body = b"".join(_wsgi.application(
                {"REQUEST_METHOD": "POST", "PATH_INFO": "/chat",
                 "CONTENT_LENGTH": str(len(payload)), "wsgi.input": _io.BytesIO(payload)}, _sr))
            wsgi_resp = json.loads(body.decode())
            assert "JAWABAN-STUB-11" in wsgi_resp.get("reply", ""), wsgi_resp
            assert wsgi_resp.get("usage", {}).get("total_tokens") == 18, wsgi_resp
            print("OK  v11 WSGI: override LLM diteruskan wsgi_app (jalur produksi PA)")
        finally:
            _bm.MOCK = old_mock

    finally:
        proc.terminate()
        stub.shutdown()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


def main():
    proc = subprocess.Popen([sys.executable, str(HERE / "main.py")],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        health = None
        for _ in range(50):
            try:
                health = call("GET", "/health")
                break
            except Exception:
                time.sleep(0.2)
        assert health and health["status"] == "ok", health
        print(f"OK  /health -> {health}")

        # v7: sesi kini persisten di disk (v6) — bersihkan sesi uji dari run
        # sebelumnya supaya hitungan pesannya deterministik.
        call("POST", "/reset", {"session_id": "selftest"})
        call("POST", "/reset", {"session_id": "stream-test"})

        res = call("POST", "/chat", {"message": "Halo, ini tes end-to-end."})
        assert res.get("reply"), res
        print(f"OK  /chat tanpa sesi -> mode={res.get('mode')}")

        s = {"session_id": "selftest"}
        r1 = call("POST", "/chat", {**s, "message": "Pesan pertama saya."})
        r2 = call("POST", "/chat", {**s, "message": "Pesan kedua saya."})
        assert r1.get("reply") and r2.get("reply"), (r1, r2)
        if r2.get("mode") == "mock":
            # Balasan mock menyebut jumlah pesan yang diingat: sesi harus bertambah.
            assert "mengingat 2 pesan" in r2["reply"], r2["reply"]
        print("OK  sesi diingat server (pesan ke-2 melihat riwayat pesan ke-1)")

        chunks, last = stream("/chat/stream", {"session_id": "stream-test",
                                               "message": "Tes streaming ya."})
        assert len(chunks) >= 3, chunks
        assert last.get("done") is True, last
        assembled = "".join(chunks)
        assert "Tes streaming ya." in assembled, assembled
        print(f"OK  /chat/stream -> {len(chunks)} potongan diterima, rakitan utuh, event done ada")

        after = call("POST", "/chat", {"session_id": "stream-test", "message": "Masih ingat?"})
        if after.get("mode") == "mock":
            assert "mengingat 2 pesan" in after["reply"], after["reply"]
        print("OK  hasil streaming ikut disimpan ke ingatan sesi")

        call("POST", "/reset", s)
        r3 = call("POST", "/chat", {**s, "message": "Setelah reset."})
        if r3.get("mode") == "mock":
            assert "mengingat 0 pesan" in r3["reply"], r3["reply"]
        print("OK  /reset mengosongkan ingatan sesi")

        for bad, label in (({"message": "  "}, "pesan kosong"),
                           ({"message": "x" * 5000}, "pesan terlalu panjang")):
            try:
                call("POST", "/chat", bad)
                print(f"FAIL: {label} seharusnya ditolak")
                return 1
            except urllib.error.HTTPError as e:
                assert e.code == 400
        print("OK  validasi: pesan kosong & terlalu panjang ditolak (400)")

        test_agent()
        test_v7()
        test_v8()
        test_v11()
        test_token_auth()
        test_persistence()
        print("SELFTEST v7 LULUS: chat + streaming + sesi + token + agen/skill + gerbang konfirmasi + persistensi + SOUL/MEMORY + generator proyek jalan.")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
