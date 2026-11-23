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
            "ketuk-target generik kecuali memang itu yang diminta.")
    else:
        tugas = (
            "sebuah APLIKASI Android interaktif: UI dibangun programatis di MainActivity "
            "(LinearLayout/TextView/EditText/Button), fitur & alur WAJIB mengikuti instruksi "
            "pengguna di bawah — bukan sekadar layar halo.")
    prompt = (
        f"Tulis SATU file MainActivity.kt (Kotlin Android) untuk {tugas}\n"
        f"Judul: {nama}\nInstruksi pengguna: {tema}\n\n"
        "Aturan keras:\n"
        f"- Baris pertama persis: package {pkg}\n"
        "- Hanya satu kelas publik: MainActivity : AppCompatActivity; kelas bantu boleh di file yang sama.\n"
        "- Impor hanya dari: android.*, androidx.appcompat.app.AppCompatActivity, kotlin.*.\n"
        "- TANPA internet, TANPA file, TANPA library eksternal, TANPA XML layout (semua dari kode).\n"
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
