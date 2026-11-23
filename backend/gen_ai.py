#!/usr/bin/env python3
"""
GENERATOR CERDAS (v10) — kode kustom dari LLM mengikuti instruksi pengguna.

Dulu generator hanya mengganti judul pada template tetap. Sekarang, bila LLM
tersedia (ctx["llm"]), kode MainActivity.kt / index.html ditulis AI sesuai
instruksi lengkap pengguna (tema, mekanisme, fitur), lalu DICEK dengan
validator deterministik: struktur wajib ada, kurung seimbang, impor aman.
Gagal satu cek saja -> jatuh ke template bawaan yang pasti jalan.
Mode mock (llm None) -> selalu template.
"""
import re

_FORBIDDEN = ("java.net", "java.io", "ProcessBuilder", "Runtime.getRuntime",
              "System.exit", "URL(", "HttpURLConnection", "Socket", "File(")


def _strip_fences(raw):
    s = raw.strip()
    s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()


def validate_kotlin(code, pkg):
    """True bila kode Kotlin cukup aman & utuh untuk dibangun jadi APK."""
    if not code or not (900 <= len(code) <= 40000):
        return False
    if not code.startswith(f"package {pkg}"):
        return False
    if "class MainActivity" not in code or "AppCompatActivity" not in code:
        return False
    if "onCreate" not in code:
        return False
    if code.count("{") != code.count("}") or code.count("(") != code.count(")"):
        return False
    if any(bad in code for bad in _FORBIDDEN):
        return False
    # Pola rawan error kompilasi dari LLM: Handler/Runnable/Thread/Timer.
    if re.search(r"\b(Handler|Runnable|Thread|Timer)\b", code):
        return False
    # Variabel Runnable/lambda yang mereferensikan dirinya pada inisialisasi
    # (pola spesifik penyebab error "must be initialized"). Self-ref umum
    # sengaja tidak dicek: variabel normal memang langsung dipakai lagi.
    for m in re.finditer(r"\b(?:val|var)\s+(\w+)\s*(?::[^=\n]+)?=\s*[^\n]*(?:Runnable|object\s*:|\{)", code):
        name = m.group(1)
        seg = code[m.end():m.end() + 300]
        if re.search(r"\b" + re.escape(name) + r"\b", seg):
            return False
    allowed_prefixes = ("android.", "androidx.appcompat", "kotlin.", "java.lang", pkg)
    for imp in re.findall(r"^import\s+([\w.]+)", code, flags=re.M):
        if not imp.startswith(allowed_prefixes):
            return False
    return True


def custom_activity(llm, nama, jenis, deskripsi, pkg):
    """Minta LLM menulis MainActivity.kt utuh. None bila gagal/ tidak sah."""
    tema = (deskripsi or "").strip() or nama
    if jenis == "game":
        tugas = (
            "sebuah GAME Android yang bisa dimainkan penuh dalam satu View Canvas kustom: "
            "ada skor, batas waktu atau nyawa, kondisi game over, dan mulai ulang dengan ketukan. "
            "Mekanisme & tema WAJIB mengikuti instruksi pengguna di bawah — jangan buat game "
            "ketuk-target generik kecuali memang itu yang diminta. Sertakan progres "
            "kesulitan (kecepatan/level naik seiring skor), kontrol sentuh yang "
            "responsif, dan tampilan rapi (skor & nyawa selalu terlihat).")
    else:
        tugas = (
            "sebuah APLIKASI Android interaktif: UI dibangun programatis di MainActivity "
            "(LinearLayout/TextView/EditText/Button), fitur & alur WAJIB mengikuti instruksi "
            "pengguna di bawah — bukan sekadar layar halo. Sertakan validasi input "
            "sederhana, keadaan kosong yang ramah, dan hasil yang langsung terasa berguna.")
    prompt = (
        f"Tulis SATU file MainActivity.kt (Kotlin Android) untuk {tugas}\n"
        f"Judul: {nama}\nInstruksi pengguna: {tema}\n\n"
        "Aturan keras:\n"
        f"- Baris pertama persis: package {pkg}\n"
        "- Hanya satu kelas publik: MainActivity : AppCompatActivity; kelas bantu boleh di file yang sama.\n"
        "- Impor hanya dari: android.*, androidx.appcompat.app.AppCompatActivity, kotlin.*.\n"
        "- TANPA internet, TANPA file, TANPA library eksternal, TANPA XML layout (semua dari kode).\n"
        "- Loop game WAJIB postInvalidateDelayed(16) di akhir onDraw. DILARANG memakai Handler, "
        "Runnable, Thread, Timer, dan coroutine (rawan error inisialisasi).\n"
        "- Semua variabel harus diinisialisasi sebelum dipakai; jangan mereferensikan variabel "
        "di dalam inisialisasinya sendiri.\n"
        "- Kode harus lengkap & bisa dikompilasi apa adanya. Balas HANYA kode Kotlin — tanpa markdown, tanpa penjelasan.")
    try:
        raw = llm([{"role": "user", "content": prompt}])
    except Exception:
        return None
    code = _strip_fences(raw or "")
    # LLM kadang menaruh teks sebelum "package" — potong dari sana.
    idx = code.find("package ")
    if idx > 0:
        code = code[idx:]
    return code if validate_kotlin(code, pkg) else None


def validate_html(html):
    if not html or not (400 <= len(html) <= 60000):
        return False
    low = html.lower()
    return "<html" in low and "</html>" in low and "<script src" not in low


def custom_web(llm, nama, jenis, deskripsi):
    """Minta LLM menulis index.html utuh sesuai instruksi. None bila gagal."""
    tema = (deskripsi or "").strip() or nama
    prompt = (
        f"Tulis SATU file index.html lengkap untuk halaman web jenis '{jenis}' bernama \"{nama}\".\n"
        f"Instruksi pengguna: {tema}\n\n"
        "Aturan keras: HTML+CSS+JS semuanya inline dalam satu file; tampilan modern premium "
        "(gradasi, kartu, responsif mobile); Bahasa Indonesia; bila jenis game/kalkulator harus "
        "benar-benar berfungsi saat dibuka. TANPA script eksternal. "
        "Balas HANYA kode HTML — tanpa markdown, tanpa penjelasan.")
    try:
        raw = llm([{"role": "user", "content": prompt}])
    except Exception:
        return None
    html = _strip_fences(raw or "")
    idx = html.lower().find("<!doctype")
    if idx < 0:
        idx = html.lower().find("<html")
    if idx > 0:
        html = html[idx:]
    return html if validate_html(html) else None


# ------------------------------------------------------------ fullstack ------
_PY_STDLIB_OK = {"http", "json", "os", "sys", "re", "threading", "datetime",
                 "pathlib", "urllib", "html", "time", "math", "random", "sqlite3",
                 "collections", "typing", "functools", "itertools"}
_PY_FORBIDDEN = ("subprocess", "eval(", "exec(", "__import__", "socket",
                 "os.system", "os.popen", "shutil.rmtree", "requests")


def validate_python_server(code):
    """True bila server.py AI aman & utuh: stdlib saja, sintaks sah, pola API."""
    if not code or not (600 <= len(code) <= 30000):
        return False
    if "HTTPServer" not in code or "/api/" not in code:
        return False
    if any(bad in code for bad in _PY_FORBIDDEN):
        return False
    for m in re.finditer(r"^\s*(?:import|from)\s+([a-zA-Z_][\w.]*)", code, re.M):
        if m.group(1).split(".")[0] not in _PY_STDLIB_OK:
            return False
    try:
        compile(code, "server.py", "exec")
    except SyntaxError:
        return False
    return True


def fullstack_bundle(llm, nama, deskripsi):
    """Minta LLM menulis (server.py, index.html) satu paket fullstack.

    Kembalikan (server_code, html) bila LOLOS validator, else (None, None)
    supaya pemanggil jatuh ke template bawaan yang pasti jalan.
    """
    if llm is None:
        return None, None
    instr = (deskripsi or nama).strip()
    try:
        raw_server = llm([
            {"role": "system", "content":
             "Kamu programmer Python senior. Tulis SATU file server.py fullstack "
             "untuk aplikasi '" + nama + "' mengikuti instruksi pengguna: " + instr + "\n"
             "ATURAN KERAS:\n"
             "- Hanya pustaka standar Python (http.server, json, pathlib, threading, "
             "datetime, re, urllib, html, time, math, random, os, sys). Tanpa pip.\n"
             "- Pakai ThreadingHTTPServer di port 8000, host 0.0.0.0.\n"
             "- Sediakan API JSON di awalan /api/ (minimal GET /api/items dan "
             "POST /api/items) dengan data dalam memori (list/dict Python).\n"
             "- GET / menyajikan file index.html di folder yang sama.\n"
             "- DILARANG: subprocess, eval, exec, socket, os.system, akses file di "
             "luar folder sendiri.\n"
             "- Balas HANYA isi file server.py, tanpa penjelasan, tanpa pagar kode."},
            {"role": "user", "content": "Tulis server.py untuk: " + instr}])
        server = _strip_fences(raw_server or "")
        # LLM kadang memberi prosa sebelum kode — potong dari baris kode pertama
        # (pola yang sama seperti jalur Kotlin memotong dari "package ").
        lines = server.split("\n")
        for i, ln in enumerate(lines):
            ls = ln.lstrip()
            if ls.startswith(("#!", "import ", "from ", "# ")):
                server = "\n".join(lines[i:])
                break
        if not validate_python_server(server):
            return None, None
        raw_html = llm([
            {"role": "system", "content":
             "Kamu programmer web senior. Tulis SATU file index.html utuh untuk "
             "aplikasi '" + nama + "' mengikuti instruksi pengguna: " + instr + "\n"
             "ATURAN KERAS:\n"
             "- Satu file: CSS & JS inline, TANPA <script src> atau CDN eksternal.\n"
             "- Halaman HARUS memanggil API backend-nya dengan fetch() ke path "
             "/api/... (relatif, tanpa host) untuk membaca & menambah data.\n"
             "- Tampilan modern, rapi, Bahasa Indonesia, responsif untuk HP.\n"
             "- Balas HANYA isi file index.html lengkap, tanpa penjelasan."},
            {"role": "user", "content": "Tulis index.html untuk: " + instr}])
        html = _strip_fences(raw_html or "")
        if not html.lstrip().startswith("<"):
            idx = html.find("<")
            if idx > 0:
                html = html[idx:]
        if not validate_html(html) or "fetch(" not in html or "/api/" not in html:
            return None, None
        return server, html
    except Exception:
        return None, None
