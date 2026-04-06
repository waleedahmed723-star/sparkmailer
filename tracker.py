#!/usr/bin/env python3
"""
SparK Pixel Tracker — Cloud Server
Deploy this to Railway.app or Render.com for FREE permanent pixel tracking.
This handles ONLY tracking pixels - your main spark_server.py stays on your laptop.

Deploy steps:
  Railway: railway up (or connect GitHub repo)
  Render:  connect repo, build command: pip install -r requirements.txt, start: python tracker.py
"""

import os, json, sqlite3, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
from datetime import datetime

PORT    = int(os.environ.get("PORT", 8080))
DB_FILE = "/tmp/spark_opens.db"   # /tmp persists during session on Railway/Render

# Tiny 1x1 transparent GIF
PIXEL = (
    b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00'
    b'\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00'
    b'\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
)

# API key to protect /opens endpoint (set this as env var on Railway/Render)
API_KEY = os.environ.get("SPARK_API_KEY", "spark_track_2024")

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS opens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            campaign TEXT,
            job_id TEXT,
            user_agent TEXT,
            ip TEXT,
            opened_at TEXT
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_opens_job ON opens(job_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_opens_email ON opens(email)")

def log_open(email, campaign, job_id, ua, ip):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "INSERT INTO opens (email,campaign,job_id,user_agent,ip,opened_at) VALUES (?,?,?,?,?,?)",
            (email, campaign, job_id or "", ua or "", ip or "", datetime.now().isoformat())
        )
    print(f"[OPEN] {email} | campaign={campaign} | job={job_id} | ip={ip} | ua={ua[:50]}")

def get_opens(job_id=None, campaign=None):
    with sqlite3.connect(DB_FILE) as conn:
        if job_id:
            rows = conn.execute(
                "SELECT email,COUNT(*) as cnt,MAX(opened_at),job_id,MAX(user_agent) FROM opens WHERE job_id=? GROUP BY email",
                (job_id,)).fetchall()
        elif campaign:
            rows = conn.execute(
                "SELECT email,COUNT(*) as cnt,MAX(opened_at),job_id,MAX(user_agent) FROM opens WHERE campaign=? GROUP BY email",
                (campaign,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT email,COUNT(*) as cnt,MAX(opened_at),job_id,MAX(user_agent) FROM opens GROUP BY email,job_id"
            ).fetchall()
    return [{"email":r[0],"count":r[1],"last_opened":r[2],"job_id":r[3],"ua":r[4] or ""} for r in rows]

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass  # silence default logs

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization")
        self.send_header("ngrok-skip-browser-warning", "true")

    def _json(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors(); self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors(); self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path
        qs     = parse_qs(parsed.query)

        if path == "/ping":
            self._json({"ok": True, "version": "1.0", "service": "SparK Pixel Tracker"})

        elif path == "/track":
            email    = qs.get("email",    [""])[0]
            campaign = qs.get("campaign", [""])[0]
            job_id   = qs.get("job",      [""])[0]
            ip       = self.client_address[0]
            ua       = self.headers.get("User-Agent", "")
            if email:
                try: log_open(email, campaign, job_id, ua, ip)
                except Exception as e: print(f"[DB ERROR] {e}")
            self.send_response(200)
            self.send_header("Content-Type",   "image/gif")
            self.send_header("Content-Length", str(len(PIXEL)))
            self.send_header("Cache-Control",  "no-cache,no-store,must-revalidate")
            self.send_header("Pragma",         "no-cache")
            self.send_header("Expires",        "0")
            self._cors(); self.end_headers()
            self.wfile.write(PIXEL)

        elif path == "/opens":
            # Requires API key for security
            auth = self.headers.get("Authorization","")
            key  = qs.get("key",[""])[0]
            if auth != f"Bearer {API_KEY}" and key != API_KEY:
                self._json({"error": "Unauthorized"}, 401); return
            job_id   = qs.get("job",      [None])[0]
            campaign = qs.get("campaign", [None])[0]
            self._json({"opens": get_opens(job_id=job_id, campaign=campaign)})

        elif path == "/":
            total = 0
            try:
                with sqlite3.connect(DB_FILE) as conn:
                    total = conn.execute("SELECT COUNT(*) FROM opens").fetchone()[0]
            except: pass
            self._json({"ok": True, "service": "SparK Pixel Tracker", "total_opens": total})

        else:
            self.send_response(404); self._cors(); self.end_headers()

if __name__ == "__main__":
    init_db()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"SparK Pixel Tracker running on port {PORT}")
    print(f"API Key: {API_KEY}")
    server.serve_forever()
