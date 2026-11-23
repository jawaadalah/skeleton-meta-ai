#!/usr/bin/env python3
"""
AGENT — harness semi (semi-harness) di atas otak (Meta AI) + skill (tangan/kaki).

Alur satu putaran /agent:
  1. ROUTER DETERMINISTIK dulu (0 token LLM): pola yang jelas langsung dipetakan
     ke skill — hitungan, jam/tanggal, URL, perintah catat/baca/hapus catatan.
  2. Kalau router tidak yakin:
     - mode live  -> LLM diminta MEMILIH (JSON): jawab langsung atau panggil 1 skill.
     - mode mock  -> jawab langsung (teks mock).
  3. Skill level "aman" dijalankan; hasilnya (observasi) diberikan kembali —
     mode live: ke LLM untuk dirangkai jadi jawaban akhir; mode mock: dirangkai
     deterministik.
  4. Skill level "konfirmasi" TIDAK pernah dijalankan otomatis. Harness berhenti,
     menerbitkan confirm_token, dan menunggu manusia menekan Setuju di aplikasi.
     Token hanya berlaku 1x untuk 1 aksi yang persis itu.

Rem pengaman harness (tidak bisa ditawar LLM):
  - MAX_STEPS membatasi jumlah pemanggilan skill per pesan.
  - Hanya skill di registry skills.SKILLS yang bisa dipanggil — tidak ada eval,
    tidak ada shell, tidak ada jalur aksi lain.
  - Setiap langkah dicatat di "steps" dan dikembalikan ke klien (jejak audit).
"""
import json
import urllib.error
import re
import secrets

import skills as skills_mod

MAX_STEPS = 3
_pending = {}  # confirm_token -> {"session_id", "skill", "args"}


_JUNK_NAMES = {"nya", "game", "gamenya", "aplikasi", "aplikasinya", "itu", "ini",
               "dong", "aja", "saja", "yang", "saya", "ku", "punyaku", "punya saya"}


def _clean_name(raw, default):
    """Bersihkan nama proyek dari teks pengguna; tolak nama sampah.

    Regresi v12: perintah lanjutan "Buat gamenya" menghasilkan proyek bernama
    "nya" (sisa kata sesudah "game"). Nama < 3 huruf atau kata sisa seperti itu
    diganti nama bawaan yang masuk akal.
    """
    nama = " ".join(str(raw or "").split()).strip(" :,'\"")
    nama = nama.split(":")[0].strip(" ,")
    nama = re.sub(r"\b(proyek saja|kode saja|tanpa apk)\b", "", nama,
                  flags=re.I).strip(" ,")
    if len(nama) < 3 or nama.lower() in _JUNK_NAMES:
        return default
    return nama


# ---------------------------------------------------------- router (0 token) --
def deterministic_route(message):
    """Petakan pesan yang polanya jelas ke (skill, args). None bila tidak yakin."""
    text = message.strip()
    low = text.lower()

    if "hapus" in low and "catatan" in low:
        return "hapus_catatan", {}

    # v7 — memori jangka panjang (MEMORY.md)
    if any(w in low for w in ("hapus memori", "hapus ingatan", "lupakan semua")):
        return "hapus_memori", {}

    if low.startswith(("ingat:", "ingat bahwa ", "tolong ingat ", "ingat ya")):
        fakta = re.sub(r"^(ingat[: ]+|tolong ingat[: ]+)", "", text, flags=re.I)
        fakta = re.sub(r"^bahwa\s+", "", fakta.strip(), flags=re.I)
        fakta = re.sub(r"\s*ya$", "", fakta.strip())
        return "ingat", {"fakta": fakta.strip() or text}

    if ("memori" in low or "ingatan" in low or "kamu ingat" in low) and \
            any(w in low for w in ("baca", "lihat", "tampilkan", "apa", "ingat apa")):
        return "baca_memori", {}

    # v1.0.0 — skill inti fullstack: "buatkan fullstack X" / "fullstack: X"
    m = re.search(r"(?:buat(?:kan)?|bikin(?:kan)?|buatin|bikinin)\s+(?:saya\s+)?(?:aplikasi\s+|web\s*app\s+|sistem\s+)?fullstack\s*(.*)", text, flags=re.I)
    if m:
        return "inti_fullstack", {"nama": _clean_name(m.group(1), "Aplikasi Fullstack"), "deskripsi": text}
    m = re.match(r"fullstack\s*[: ]\s*(.+)", text, flags=re.I)
    if m:
        return "inti_fullstack", {"nama": _clean_name(m.group(1), "Aplikasi Fullstack"), "deskripsi": text}

    # "proyek saja/kode saja/tanpa apk" = pengguna eksplisit TIDAK mau APK.
    proyek_saja = any(w in low for w in ("proyek saja", "kode saja", "tanpa apk",
                                         "jangan jadi apk", "tidak jadi apk"))

    # v8 — pabrik APK: bila ada kata "apk", arahkan ke skill pembuat APK
    # (bukan sekadar proyek). Pola ini harus dicek sebelum generator biasa.
    m = re.search(r"cek\s+apk\s+([\w-]+)", low)
    if m:
        return "cek_apk", {"slug": m.group(1)}
    if "apk" in low and "buat" in low:
        gm = re.search(r"game\s*(?:android\s*)?(.*)", text, flags=re.I)
        am = re.search(r"(?:aplikasi|app)\s+(?:android\s*)?(.*)", text, flags=re.I)
        if gm and ("game" in low):
            nama = re.sub(r"\b(jadi|menjadi|bentuk|file|apk|android|simpel|sederhana)\b", "",
                          gm.group(1), flags=re.I).strip(" :") or "Game Ketuk Target"
            # Nama proyek berhenti di ':' pertama — sisanya deskripsi.
            nama = _clean_name(nama, "Game Ketuk Target")
            return "buat_apk_android", {"nama": nama, "jenis": "game", "deskripsi": text}
        if am:
            nama = re.sub(r"\b(jadi|menjadi|bentuk|file|apk|android|simpel|sederhana)\b", "",
                          am.group(1), flags=re.I).strip(" :") or "AplikasiKu"
            nama = _clean_name(nama, "AplikasiKu")
            return "buat_apk_android", {"nama": nama, "jenis": "aplikasi", "deskripsi": text}

    # v7 — generator proyek (Android / game / web) — nama diambil dari teks asli
    # (bukan lowercase) supaya kapitalisasi judul proyek tetap benar.
    m = re.search(r"(?:buat(?:kan)?|bikin(?:kan)?|buatin|bikinin)\s+(?:saya\s+)?game\s+android\s*(.*)", text, flags=re.I)
    if m:
        nama = _clean_name(m.group(1), "Game Ketuk Target")
        if proyek_saja:
            return "buat_game_android", {"nama": nama, "deskripsi": text}
        return "buat_apk_android", {"nama": nama, "jenis": "game", "deskripsi": text}

    m = re.search(r"(?:buat(?:kan)?|bikin(?:kan)?|buatin|bikinin)\s+(?:saya\s+)?(?:aplikasi|app)\s+android\s*(.*)", text, flags=re.I)
    if m:
        nama = _clean_name(m.group(1), "AplikasiKu")
        if proyek_saja:
            return "buat_aplikasi_android", {"nama": nama, "deskripsi": text}
        return "buat_apk_android", {"nama": nama, "jenis": "aplikasi", "deskripsi": text}

    m = re.search(r"buat(?:kan)?\s+(?:saya\s+)?(?:halaman\s+web|website|situs\s+web|web)\s*(.*)", text, flags=re.I)
    if m:
        rest = m.group(1).strip(" :")
        rest_low = rest.lower()
        jenis = "game" if "game" in rest_low else ("kalkulator" if "kalkulator" in rest_low else "landing")
        nama = re.sub(r"^(game|kalkulator)\s+", "", rest, flags=re.I).strip() or "Halamanku"
        nama = _clean_name(nama, "Halamanku")
        return "buat_halaman_web", {"nama": nama, "jenis": jenis, "deskripsi": text}

    if any(w in low for w in ("daftar proyek", "proyek yang sudah dibuat",
                               "hasil generate", "daftar hasil")):
        return "daftar_hasil_generate", {}

    # v7.1 — frasa natural tanpa kata "android"/"web" (dari pemakaian nyata:
    # "buat aplikasi game simpel" dulu jatuh ke echo mock dan membingungkan).
    m = re.search(r"(?:buat(?:kan)?|bikin(?:kan)?|buatin|bikinin)\s+(?:saya\s+)?(?:aplikasi\s+)?game\s*(.*)", text, flags=re.I)
    if m:
        nama = re.sub(r"\b(simpel|sederhana|simple)\b", "", m.group(1), flags=re.I).strip(" :")
        nama = _clean_name(nama, "Game Ketuk Target")
        if proyek_saja:
            return "buat_game_android", {"nama": nama, "deskripsi": text}
        return "buat_apk_android", {"nama": nama, "jenis": "game", "deskripsi": text}

    m = re.search(r"(?:buat(?:kan)?|bikin(?:kan)?|buatin|bikinin)\s+(?:saya\s+)?aplikasi\s+(.+)", text, flags=re.I)
    if m:
        nama = _clean_name(m.group(1), "AplikasiKu")
        if proyek_saja:
            return "buat_aplikasi_android", {"nama": nama, "deskripsi": text}
        return "buat_apk_android", {"nama": nama, "jenis": "aplikasi", "deskripsi": text}

    if low.startswith(("catat:", "catat ", "simpan catatan")):
        teks = re.sub(r"^(catat[: ]+|simpan catatan[: ]+)", "", text, flags=re.I).strip()
        return "simpan_catatan", {"teks": teks or text}

    if "catatan" in low and any(w in low for w in ("baca", "lihat", "apa saja", "tampilkan", "saya apa")):
        return "baca_catatan", {}

    url_match = re.search(r"https?://\S+", text)
    if url_match and any(w in low for w in ("ambil", "buka", "baca", "fetch", "kunjungi", "isi", "ringkas")):
        return "ambil_halaman_web", {"url": url_match.group(0).rstrip(").,")}

    if any(w in low for w in ("jam berapa", "pukul berapa", "tanggal berapa", "hari apa", "waktu sekarang")):
        return "waktu_sekarang", {}

    math_match = re.search(r"(?:hitung|berapa|hitunglah)\s+([\d\s+\-*/().%]+)", low)
    if math_match and re.search(r"\d\s*[-+*/%]\s*\d", math_match.group(1)):
        return "kalkulator", {"ekspresi": math_match.group(1).strip()}
    if re.fullmatch(r"[\d\s+\-*/().%]+", text) and re.search(r"\d\s*[-+*/%]\s*\d", text):
        return "kalkulator", {"ekspresi": text}

    return None


# --------------------------------------------------------------- gerbang ------
def _gate(skill_name, args, session_id):
    """Kembalikan dict needs_confirmation bila skill butuh persetujuan, else None."""
    skill = skills_mod.SKILLS.get(skill_name)
    if skill and skill["risk"] == "konfirmasi":
        token = secrets.token_hex(8)
        _pending[token] = {"session_id": session_id, "skill": skill_name, "args": args}
        return {"needs_confirmation": True, "confirm_token": token,
                "proposed": {"skill": skill_name, "args": args},
                "reply": (f"Aksi '{skill_name}' bersifat merusak dan butuh persetujuanmu dulu. "
                          "Tekan Setuju di aplikasi untuk menjalankannya — aku tidak akan "
                          "menjalankannya sendiri.")}
    return None


def run_confirmed(token, session_id):
    """Jalankan aksi yang sudah disetujui manusia. Token hangus setelah dipakai."""
    pending = _pending.pop(token, None)
    if not pending:
        return None, "Token konfirmasi tidak dikenal atau sudah dipakai/kedaluwarsa."
    if pending["session_id"] != session_id:
        return None, "Token konfirmasi ini bukan untuk sesi ini."
    result, is_err = skills_mod.execute(pending["skill"], pending["args"], {"session_id": session_id})
    step = {"skill": pending["skill"], "args": pending["args"],
            "result": result[:500], "confirmed_by_user": True}
    return (result, [step]), None


# ------------------------------------------------------------------- inti -----
def run_agent(message, session_id, history, llm_call, mock_reply_fn):
    """
    Jalankan satu putaran agen.
    llm_call(messages) -> teks, atau None bila mode mock.
    Mengembalikan dict: {reply, steps, needs_confirmation?, confirm_token?, proposed?}
    """
    ctx = {"session_id": session_id, "llm": llm_call}
    steps = []

    routed = deterministic_route(message)
    if routed:
        skill_name, args = routed
        gate = _gate(skill_name, args, session_id)
        if gate:
            gate["steps"] = steps
            return gate
        result, is_err = skills_mod.execute(skill_name, args, ctx)
        steps.append({"skill": skill_name, "args": args, "result": result[:500], "via": "router"})
        reply = _compose(message, steps, history, llm_call, mock_reply_fn)
        return {"reply": reply, "steps": steps}

    if llm_call is None:
        # Mode mock: tanpa otak LLM, agen hanya bisa menjalankan perintah yang
        # cocok dengan skill. Jelaskan itu + beri contoh, jangan echo mentah.
        return {"reply": (
            "Aku masih mode mock (META_API_KEY belum dipasang), jadi perintah bebas "
            "belum bisa kupahami — tapi skill-ku jalan penuh. Coba salah satu:\n"
            "• hitung 45 * 3\n"
            "• jam berapa sekarang?\n"
            "• catat: beli kopi untuk warung\n"
            "• ingat bahwa warna favorit saya biru\n"
            "• buatkan aplikasi android Kasir Warung\n"
            "• buatkan game android Balap Kelereng\n"
            "• buatkan halaman web Toko Bunga Melati\n"
            "• ambil isi https://contoh.com\n"
            "Pasang META_API_KEY di backend supaya aku bisa memahami perintah apa pun."
        ), "steps": steps}

    # Mode live: LLM memilih skill atau jawab langsung, maks MAX_STEPS putaran.
    try:
        return _run_live(message, session_id, history, llm_call, ctx, steps)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return {"reply": BUSY_REPLY, "steps": steps}
        raise


def _run_live(message, session_id, history, llm_call, ctx, steps):
    convo = list(history[-10:])
    convo.append({"role": "user", "content": message})
    for _ in range(MAX_STEPS):
        plan = _ask_plan(llm_call, convo, steps)
        if not plan or plan.get("action") != "skill":
            reply = (plan or {}).get("reply") or llm_call(convo)
            return {"reply": reply, "steps": steps}
        skill_name, args = plan.get("skill", ""), plan.get("args") or {}
        gate = _gate(skill_name, args, session_id)
        if gate:
            gate["steps"] = steps
            return gate
        result, is_err = skills_mod.execute(skill_name, args, ctx)
        steps.append({"skill": skill_name, "args": args, "result": result[:500], "via": "llm"})
        convo.append({"role": "assistant", "content": f"(memanggil skill {skill_name})"})
        convo.append({"role": "user", "content": f"Hasil skill {skill_name}: {result}\nLanjutkan: jawab final, atau panggil 1 skill lagi bila perlu."})

    reply = llm_call(convo + [{"role": "user", "content": "Batas langkah tercapai. Beri jawaban final dari hasil yang ada."}])
    return {"reply": reply, "steps": steps}


BUSY_REPLY = (
    "⏳ Otak AI sedang kena batas kuota gratis (terlalu banyak permintaan "
    "dalam waktu singkat). Tunggu sekitar 30 detik, lalu kirim lagi pesanmu. "
    "Mau bebas batas? Pakai API key milikmu di ⚙ Atur → Otak AI — daftar "
    "Groq/OpenRouter itu gratis."
)


_VERBATIM_SKILLS = {"buat_apk_android", "buat_aplikasi_android", "buat_game_android",
                    "buat_halaman_web", "cek_apk", "inti_fullstack"}


def _compose(message, steps, history, llm_call, mock_reply_fn):
    """Rangkai jawaban akhir dari hasil skill."""
    last = steps[-1]
    # Hasil skill generator/pabrik adalah pesan final faktual (status + link):
    # tampilkan apa adanya — parafrase LLM rawan distorsi/penolakan karangan.
    if last.get("skill") in _VERBATIM_SKILLS and last.get("result"):
        return last["result"]
    if llm_call is None:
        return f"Hasil skill {last['skill']}: {last['result']}"
    convo = list(history[-10:])
    convo.append({"role": "user", "content": message})
    convo.append({"role": "user", "content": f"Hasil skill {last['skill']}: {last['result']}\nJawab pengguna berdasarkan hasil ini, singkat dan jelas."})
    try:
        return llm_call(convo)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return f"{last['result']}\n\n(Balasan ringkas otomatis: otak AI sedang kena batas kuota, hasil skill ditampilkan apa adanya.)"
        raise


def _ask_plan(llm_call, convo, steps):
    """Minta LLM memilih aksi dalam JSON ketat. None bila jawabannya bukan JSON sah."""
    skill_list = "\n".join(
        f"- {s['name']}({', '.join(s['params'])}) [{s['organ']}/{s['risk']}]: {s['description']}"
        for s in skills_mod.public_list())
    prompt = (
        "Kamu perencana agen. Skill yang tersedia:\n" + skill_list + "\n\n"
        "Balas HANYA dengan JSON salah satu bentuk:\n"
        '{"action": "answer", "reply": "jawaban final untuk pengguna"}\n'
        '{"action": "skill", "skill": "nama_skill", "args": {"param": "nilai"}}\n'
        "Aturan memilih skill: (1) Permintaan membuat game/aplikasi Android SELALU pakai buat_apk_android (langsung jadi APK); buat_game_android/buat_aplikasi_android hanya bila pengguna eksplisit minta proyek/kode saja tanpa APK. "
        "(2) Permintaan aplikasi fullstack / web app dengan backend / sistem lengkap pakai inti_fullstack. "
        "(3) Untuk semua skill pembangun (buat_apk_android, buat_halaman_web, inti_fullstack, buat_game_android, buat_aplikasi_android), selalu isi param deskripsi dengan instruksi lengkap pengguna agar kode ditulis AI mengikuti instruksinya. "
        "(4) Manfaatkan konteks percakapan & ingatan untuk melengkapi nama/deskripsi yang kurang jelas, jangan bertanya balik hal yang bisa disimpulkan."
        "Jangan tulis teks lain di luar JSON."
    )
    try:
        raw = llm_call([{"role": "system", "content": prompt}] + convo)
        raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.M).strip()
        plan = json.loads(raw)
        return plan if isinstance(plan, dict) else None
    except Exception:
        return None
