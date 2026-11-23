#!/usr/bin/env python3
"""
GENERATE — tangan pembangun agen: membuat proyek nyata dari template.

Hasil ditulis HANYA di bawah backend/data/generated/ (nama dibersihkan,
tanpa path traversal). Tiga pembangkit:
  - android_app(nama, paket, jenis)  -> proyek Kotlin siap buka di Android Studio
  - android_game(nama, paket)        -> game Canvas "Ketuk Target" siap build
  - web_page(nama, jenis)            -> satu index.html (landing/game/kalkulator)

Template sengaja kecil tapi utuh: settings/build gradle, manifest, activity,
dan README cara build (Android Studio atau GitHub Actions seperti repo utama).
"""
import re
from pathlib import Path

GEN_DIR = Path(__file__).resolve().parent / "data" / "generated"

_SETTINGS = """pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}
rootProject.name = "%(title)s"
include(":app")
"""

_ROOT_BUILD = """plugins {
    id("com.android.application") version "8.5.2" apply false
    id("org.jetbrains.kotlin.android") version "2.0.20" apply false
}
"""

_APP_BUILD = """plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "%(pkg)s"
    compileSdk = 34

    defaultConfig {
        applicationId = "%(pkg)s"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
}
"""

_MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <application
        android:allowBackup="true"
        android:label="%(title)s"
        android:theme="@style/Theme.AppCompat.Light.DarkActionBar">
        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
"""

_ACTIVITY_BASIC = """package %(pkg)s

import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import android.widget.LinearLayout
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {
    private var hitungan = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val layout = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val label = TextView(this).apply {
            text = "Halo dari %(title)s! Tombol ditekan 0 kali."
            textSize = 18f
        }
        val tombol = Button(this).apply {
            text = "Tekan saya"
            setOnClickListener {
                hitungan++
                label.text = "Halo dari %(title)s! Tombol ditekan $hitungan kali."
            }
        }
        layout.addView(label)
        layout.addView(tombol)
        setContentView(layout)
    }
}
"""

_ACTIVITY_GAME = """package %(pkg)s

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.os.Bundle
import android.view.MotionEvent
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import kotlin.random.Random

/** Game Ketuk Target: lingkaran muncul acak, ketuk untuk dapat poin. 30 detik. */
class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(GameView(this))
    }

    class GameView(context: Context) : View(context) {
        private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
        private var tx = 300f
        private var ty = 400f
        private val radius = 90f
        private var skor = 0
        private var mulai = System.currentTimeMillis()
        private var selesai = false

        private fun pindah() {
            tx = Random.nextInt(120, maxOf(121, width - 120)).toFloat()
            ty = Random.nextInt(240, maxOf(241, height - 120)).toFloat()
        }

        override fun onDraw(canvas: Canvas) {
            super.onDraw(canvas)
            canvas.drawColor(Color.rgb(18, 18, 28))
            val sisa = 30 - (System.currentTimeMillis() - mulai) / 1000
            paint.color = Color.WHITE
            paint.textSize = 56f
            if (sisa <= 0) {
                selesai = true
                canvas.drawText("Selesai! Skor akhir: $skor", 60f, height / 2f, paint)
                paint.textSize = 40f
                canvas.drawText("Ketuk layar untuk main lagi", 60f, height / 2f + 70f, paint)
                return
            }
            canvas.drawText("Skor: $skor   Waktu: $sisa", 60f, 110f, paint)
            paint.color = Color.rgb(255, 170, 40)
            canvas.drawCircle(tx, ty, radius, paint)
            postInvalidateDelayed(100)
        }

        override fun onTouchEvent(event: MotionEvent): Boolean {
            if (event.action == MotionEvent.ACTION_DOWN) {
                if (selesai) {
                    skor = 0
                    mulai = System.currentTimeMillis()
                    selesai = false
                    pindah()
                } else {
                    val dx = event.x - tx
                    val dy = event.y - ty
                    if (dx * dx + dy * dy <= radius * radius) {
                        skor++
                        pindah()
                    }
                }
                invalidate()
            }
            return true
        }
    }
}
"""

_README_ANDROID = """# %(title)s

Proyek Android Kotlin yang dibuat oleh agen Your Agent (skill generator).

## Cara build
1. Buka folder ini di Android Studio, tunggu Gradle sync, lalu Run.
2. Atau push ke GitHub dan pakai GitHub Actions (setup-java 17 +
   gradle assembleDebug) seperti repo skeleton-meta-ai.

Paket: %(pkg)s - minSdk 24, target/compileSdk 34, Kotlin 2.0.20, AGP 8.5.2.
"""

_WEB_LANDING = """<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<style>
body{font-family:system-ui,sans-serif;margin:0;background:#0f1220;color:#eef}
.hero{padding:64px 24px;text-align:center;background:linear-gradient(135deg,#3b4bdb,#7b2fbe)}
.hero h1{margin:0 0 12px;font-size:40px}
.btn{display:inline-block;margin-top:20px;padding:12px 28px;background:#ffb020;color:#111;border-radius:999px;text-decoration:none;font-weight:700}
section{max-width:820px;margin:0 auto;padding:40px 24px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}
.card{background:#1a1e33;border-radius:16px;padding:20px}
footer{text-align:center;padding:24px;color:#99a}
</style>
</head>
<body>
<header class="hero">
<h1>%(title)s</h1>
<p>Selamat datang — halaman ini dibuat otomatis oleh agen Your Agent.</p>
<a class="btn" href="#fitur">Lihat Fitur</a>
</header>
<section id="fitur">
<h2>Fitur Utama</h2>
<div class="grid">
<div class="card"><h3>Cepat</h3><p>Satu file HTML, tanpa dependensi, langsung jalan di browser mana pun.</p></div>
<div class="card"><h3>Responsif</h3><p>Tampilan menyesuaikan layar HP dan desktop.</p></div>
<div class="card"><h3>Siap Kembang</h3><p>Tinggal edit teks, warna, dan bagian ini sesuai kebutuhanmu.</p></div>
</div>
</section>
<section>
<h2>Kontak</h2>
<p>Hubungi kami lewat email: halo@contoh.id</p>
</section>
<footer>Dibuat dengan skill buat_halaman_web - Your Agent</footer>
</body>
</html>
"""

_WEB_GAME = """<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s - Game Ketuk Target</title>
<style>
body{font-family:system-ui,sans-serif;margin:0;background:#12121c;color:#eef;text-align:center}
canvas{background:#1a1e33;display:block;margin:12px auto;border-radius:16px;touch-action:none}
</style>
</head>
<body>
<h1>%(title)s</h1>
<p>Ketuk lingkaran oranye sebanyak-banyaknya dalam 30 detik!</p>
<canvas id="c" width="360" height="480"></canvas>
<p id="info">Skor: 0 - Waktu: 30</p>
<button onclick="mulai()">Mulai Lagi</button>
<script>
const cv=document.getElementById('c'),ctx=cv.getContext('2d'),info=document.getElementById('info');
let x=180,y=240,skor=0,sisa=30,timer=null;
function pindah(){x=50+Math.random()*260;y=80+Math.random()*340}
function gambar(){ctx.clearRect(0,0,360,480);ctx.fillStyle='#ffb020';ctx.beginPath();ctx.arc(x,y,36,0,7);ctx.fill();
info.textContent='Skor: '+skor+' - Waktu: '+sisa}
function mulai(){skor=0;sisa=30;pindah();gambar();clearInterval(timer);
timer=setInterval(()=>{sisa--;gambar();if(sisa<=0){clearInterval(timer);info.textContent='Selesai! Skor akhir: '+skor}},1000)}
cv.addEventListener('pointerdown',e=>{const r=cv.getBoundingClientRect();
const dx=e.clientX-r.left-x,dy=e.clientY-r.top-y;
if(dx*dx+dy*dy<=36*36&&sisa>0){skor++;pindah();gambar()}});
mulai();
</script>
</body>
</html>
"""

_WEB_CALC = """<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s - Kalkulator</title>
<style>
body{font-family:system-ui,sans-serif;background:#12121c;color:#eef;display:flex;justify-content:center;padding:32px}
.box{background:#1a1e33;padding:20px;border-radius:16px;width:280px}
#layar{width:100%;font-size:28px;padding:10px;box-sizing:border-box;margin-bottom:12px;text-align:right}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
button{padding:16px;font-size:18px;border:0;border-radius:10px;background:#2a2f4a;color:#eef;cursor:pointer}
button.op{background:#ffb020;color:#111;font-weight:700}
</style>
</head>
<body>
<div class="box">
<h3 style="margin-top:0">%(title)s</h3>
<input id="layar" readonly value="0">
<div class="grid">
<button onclick="tekan('7')">7</button><button onclick="tekan('8')">8</button><button onclick="tekan('9')">9</button><button class="op" onclick="tekan('/')">/</button>
<button onclick="tekan('4')">4</button><button onclick="tekan('5')">5</button><button onclick="tekan('6')">6</button><button class="op" onclick="tekan('*')">x</button>
<button onclick="tekan('1')">1</button><button onclick="tekan('2')">2</button><button onclick="tekan('3')">3</button><button class="op" onclick="tekan('-')">-</button>
<button onclick="tekan('0')">0</button><button onclick="tekan('.')">.</button><button class="op" onclick="hitung()">=</button><button class="op" onclick="tekan('+')">+</button>
<button class="op" style="grid-column:span 4" onclick="layar.value='0'">C</button>
</div>
</div>
<script>
const layar=document.getElementById('layar');
function tekan(t){if(layar.value==='0'&&t!=='.')layar.value=t;else layar.value+=t}
function hitung(){try{layar.value=Function('return ('+layar.value+')')()}catch(e){layar.value='Error'}}
</script>
</body>
</html>
"""


def slugify(text, fallback="proyek"):
    slug = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")[:40].strip("-")
    return slug or fallback


def _write(base, files):
    written = []
    for rel, content in files.items():
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(rel)
    return written


def _android_files(title, pkg, activity):
    ctx = {"title": title, "pkg": pkg}
    return {
        "settings.gradle.kts": _SETTINGS % ctx,
        "gradle.properties": "android.useAndroidX=true\nandroid.nonTransitiveRClass=true\norg.gradle.jvmargs=-Xmx2048m\n",
        "build.gradle.kts": _ROOT_BUILD,
        "app/build.gradle.kts": _APP_BUILD % ctx,
        "app/src/main/AndroidManifest.xml": _MANIFEST % ctx,
        f"app/src/main/java/{pkg.replace('.', '/')}/MainActivity.kt": activity % ctx,
        "README.md": _README_ANDROID % ctx,
    }


def android_app(nama, paket="", jenis="dasar"):
    title = " ".join(str(nama).split())[:60] or "AplikasiKu"
    slug = slugify(title, "aplikasi")
    pkg = paket.strip() or f"com.jawaadalah.{slug.replace('-', '')}"
    pkg = re.sub(r"[^a-z0-9.]", "", pkg.lower()).strip(".") or "com.jawaadalah.app"
    base = GEN_DIR / "android" / slug
    files = _android_files(title, pkg, _ACTIVITY_BASIC)
    written = _write(base, files)
    return (f"Proyek aplikasi Android '{title}' dibuat di data/generated/android/{slug}/ "
            f"({len(written)} file, paket {pkg}). Isi: " + ", ".join(written) +
            ". Buka folder itu di Android Studio untuk build, atau push ke GitHub dan build dengan Actions.")


def android_game(nama, paket=""):
    title = " ".join(str(nama).split())[:60] or "GameKu"
    slug = slugify(title, "game")
    pkg = paket.strip() or f"com.jawaadalah.{slug.replace('-', '')}"
    pkg = re.sub(r"[^a-z0-9.]", "", pkg.lower()).strip(".") or "com.jawaadalah.game"
    base = GEN_DIR / "android" / slug
    files = _android_files(title, pkg, _ACTIVITY_GAME)
    written = _write(base, files)
    return (f"Proyek game Android '{title}' (Ketuk Target: skor + timer 30 detik, Canvas) "
            f"dibuat di data/generated/android/{slug}/ ({len(written)} file, paket {pkg}). "
            "Buka di Android Studio untuk build jadi APK.")


def web_page(nama, jenis="landing"):
    title = " ".join(str(nama).split())[:60] or "Halamanku"
    slug = slugify(title, "web")
    template = {"landing": _WEB_LANDING, "game": _WEB_GAME,
                "kalkulator": _WEB_CALC}.get(jenis, _WEB_LANDING)
    base = GEN_DIR / "web" / slug
    _write(base, {"index.html": template % {"title": title}})
    return (f"Halaman web '{title}' (jenis: {jenis}) dibuat di data/generated/web/{slug}/index.html "
            "— satu file utuh, buka langsung di browser atau hosting di mana saja.")


def list_generated():
    if not GEN_DIR.is_dir():
        return "Belum ada proyek hasil generate."
    items = []
    for kind in ("android", "web"):
        root = GEN_DIR / kind
        if root.is_dir():
            for child in sorted(root.iterdir()):
                if child.is_dir():
                    n = sum(1 for _ in child.rglob("*") if _.is_file())
                    items.append(f"- [{kind}] {child.name} ({n} file)")
    return "Proyek hasil generate:\n" + "\n".join(items) if items else "Belum ada proyek hasil generate."
