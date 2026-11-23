#!/usr/bin/env python3
"""
APK FACTORY (v8) — proyek Android hasil generator dibangun jadi APK asli.

Alur: proyek dikirim ke repo GitHub yang sama (folder factory/<slug>/ +
factory/current.json) lewat Git Data API. Workflow .github/workflows/
factory-apk.yml di repo itu menyala otomatis, membangun APK dengan Gradle,
dan menerbitkannya sebagai Release "apk-<slug>" — link unduhnya publik dan
polanya tetap, jadi bisa dibagikan ke pengguna saat itu juga.

Butuh env GITHUB_TOKEN (fine-grained PAT: repo your-agent, Contents RW).
Tanpa token, skill membalas pesan ramah — tidak crash.
"""
import base64
import json
import os
import urllib.error
import urllib.request

REPO = os.environ.get("FACTORY_REPO", "jawaadalah/your-agent")
API = "https://api.github.com"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def _token():
    return os.environ.get("GITHUB_TOKEN", "").strip()


def release_url(slug):
    return f"https://github.com/{REPO}/releases/download/apk-{slug}/{slug}.apk"


def actions_url():
    return f"https://github.com/{REPO}/actions/workflows/factory-apk.yml"


def _gh(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        API + path, data=data, method=method,
        headers={"Authorization": f"Bearer {_token()}",
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json",
                 "User-Agent": UA,
                 "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:200]
        raise RuntimeError(f"GitHub API {method} {path} -> {e.code}: {detail}")


def push_project(slug, title, pkg, files):
    """Kirim proyek ke factory/<slug>/ + current.json dalam satu commit.
    Mengembalikan dict info build. Raise RuntimeError bila gagal."""
    if not _token():
        raise RuntimeError("GITHUB_TOKEN belum terpasang di server")
    ref = _gh("GET", f"/repos/{REPO}/git/ref/heads/main")
    head_sha = ref["object"]["sha"]
    head = _gh("GET", f"/repos/{REPO}/git/commits/{head_sha}")
    base_tree = head["tree"]["sha"]

    items = []
    all_files = {f"factory/{slug}/{rel}": content for rel, content in files.items()}
    all_files["factory/current.json"] = json.dumps(
        {"slug": slug, "name": title, "package": pkg}, ensure_ascii=False, indent=1)
    for path, content in sorted(all_files.items()):
        blob = _gh("POST", f"/repos/{REPO}/git/blobs",
                   {"content": base64.b64encode(content.encode("utf-8")).decode(),
                    "encoding": "base64"})
        items.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    tree = _gh("POST", f"/repos/{REPO}/git/trees", {"base_tree": base_tree, "tree": items})
    commit = _gh("POST", f"/repos/{REPO}/git/commits",
                 {"message": f"Factory: buat APK {title} ({slug})",
                  "tree": tree["sha"], "parents": [head_sha]})
    _gh("PATCH", f"/repos/{REPO}/git/refs/heads/main", {"sha": commit["sha"]})
    return {"slug": slug, "title": title, "package": pkg,
            "apk_url": release_url(slug), "actions_url": actions_url(),
            "commit": commit["sha"][:7]}


def check_apk(slug):
    """True bila file APK di Release sudah bisa diunduh (HEAD ke link publik)."""
    req = urllib.request.Request(release_url(slug), method="HEAD",
                                 headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise
