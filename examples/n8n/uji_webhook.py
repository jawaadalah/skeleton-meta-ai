#!/usr/bin/env python3
"""Server peniru n8n untuk uji lokal integrasi webhook Your Agent.

Meniru kontrak workflow contoh: POST /webhook/your-agent menerima JSON
{source, session_id, aksi, teks, waktu}, mencetaknya, lalu membalas
JSON {"pesan": ..., "diterima": true} seperti node Respond to Webhook.
Python stdlib saja. Jalankan: python3 uji_webhook.py [port]
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/webhook/your-agent":
            self._reply(404, {"error": "path tidak dikenal"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            self._reply(400, {"error": "JSON tidak valid"})
            return
        print("Payload diterima dari Your Agent:", json.dumps(payload, ensure_ascii=False))
        print("Header X-Webhook-Secret:", self.headers.get("X-Webhook-Secret") or "(tidak ada)")
        self._reply(200, {
            "pesan": f"Workflow n8n (peniru) menerima perintah: \"{payload.get('teks', '')}\"",
            "diterima": True,
        })

    def _reply(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5679
    print(f"Peniru n8n jalan: http://127.0.0.1:{port}/webhook/your-agent")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
