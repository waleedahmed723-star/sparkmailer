#!/usr/bin/env python3
"""
SparK Mailer - Backend v5
Full-stack email marketing tool: SMTP sending, open/click tracking, contacts, agents.
Run locally:  python spark_server.py
Run on cloud: Deploy to Railway/Render - auto-detects RAILWAY_PUBLIC_DOMAIN env var
Requires: pip install dnspython  (optional, improves MX lookup)
"""

import json, smtplib, ssl, time, random, sqlite3, os, re, socket, html
import threading, hashlib, secrets, urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr, formatdate, make_msgid
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle each request in a separate thread - critical for tracking pixel latency."""
    daemon_threads = True

PORT    = int(os.environ.get("PORT", 5055))
# Use /data for persistent storage on Railway, fallback to local
_data_dir = "/data" if os.path.exists("/data") else os.path.dirname(os.path.abspath(__file__))
DB_FILE   = os.path.join(_data_dir, "spark_data.db")
SEND_JOBS = {}
JOBS_LOCK = threading.Lock()
VERSION   = "5.0"

# ── Cloud Pixel Tracker (optional) ───────────────────────────
# Deploy tracker.py to Railway/Render for permanent tracking.
# Set these after deploying:
CLOUD_TRACKER_URL = os.environ.get("CLOUD_TRACKER_URL", "")  # e.g. https://your-app.railway.app
CLOUD_API_KEY     = os.environ.get("CLOUD_API_KEY", "spark_track_2024")

# ── Detect public IP once at startup for tracking URLs ──────
def _detect_public_ip():
    for svc in ["https://api.ipify.org","https://ifconfig.me/ip","https://icanhazip.com"]:
        try:
            with urllib.request.urlopen(svc, timeout=4) as r:
                ip = r.read().decode().strip()
                if re.match(r'^\d+\.\d+\.\d+\.\d+$', ip):
                    return ip
        except Exception:
            continue
    return None

_public_ip = _detect_public_ip()

# ── URL Resolution ─────────────────────────────────────────────────────────
# Detects Railway deployment automatically, supports manual overrides.
import sys as _sys
_cli_base = None
for _i, _a in enumerate(_sys.argv[1:], 0):
    if _a in ("--base-url", "-b") and _i + 1 < len(_sys.argv) - 1:
        _cli_base = _sys.argv[_i + 2]; break
    if _a.startswith("--base-url="):
        _cli_base = _a.split("=", 1)[1]; break

_railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
_app_url        = os.environ.get("APP_URL", "")

if CLOUD_TRACKER_URL:
    _resolved = CLOUD_TRACKER_URL.rstrip("/")
elif _railway_domain:
    _resolved = f"https://{_railway_domain}"
elif _app_url:
    _resolved = _app_url.rstrip("/")
elif _cli_base:
    _resolved = _cli_base.rstrip("/")
elif os.environ.get("BASE_URL"):
    _resolved = os.environ["BASE_URL"].rstrip("/")
elif _public_ip:
    _resolved = f"http://{_public_ip}:{PORT}"
else:
    _resolved = f"http://localhost:{PORT}"

BASE_URL     = _resolved
TRACKING_URL = _resolved

import json, smtplib, ssl, time, random, sqlite3, os, re, socket, html
import threading, hashlib, secrets, urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr, formatdate, make_msgid
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle each request in a separate thread - critical for tracking pixel latency."""
    daemon_threads = True

PORT    = int(os.environ.get("PORT", 5055))
# Use /data for persistent storage on Railway, fallback to local
_data_dir = "/data" if os.path.exists("/data") else os.path.dirname(os.path.abspath(__file__))
DB_FILE   = os.path.join(_data_dir, "spark_data.db")
SEND_JOBS = {}
JOBS_LOCK = threading.Lock()
VERSION   = "5.0"

# ── Cloud Pixel Tracker (optional) ───────────────────────────
# Deploy tracker.py to Railway/Render for permanent tracking.
# Set these after deploying:
CLOUD_TRACKER_URL = os.environ.get("CLOUD_TRACKER_URL", "")  # e.g. https://your-app.railway.app
CLOUD_API_KEY     = os.environ.get("CLOUD_API_KEY", "spark_track_2024")

# ── Detect public IP once at startup for tracking URLs ──────
def _detect_public_ip():
    for svc in ["https://api.ipify.org","https://ifconfig.me/ip","https://icanhazip.com"]:
        try:
            with urllib.request.urlopen(svc, timeout=4) as r:
                ip = r.read().decode().strip()
                if re.match(r'^\d+\.\d+\.\d+\.\d+$', ip):
                    return ip
        except Exception:
            continue
    return None

_public_ip = _detect_public_ip()

# ── BASE_URL: always localhost - used for serving the app to your browser ──
BASE_URL = f"http://localhost:{PORT}"

# ── TRACKING_URL: public URL embedded inside email pixels ──────────────────
# If CLOUD_TRACKER_URL is set, use it for pixels (always available, no ngrok needed)
# Priority: --base-url arg > BASE_URL env var > auto-detected IP > localhost
# Usage: python spark_server.py --base-url https://YOUR.ngrok-free.app
import sys as _sys
_cli_base = None
for _i, _a in enumerate(_sys.argv[1:], 0):
    if _a in ("--base-url", "-b") and _i + 1 < len(_sys.argv) - 1:
        _cli_base = _sys.argv[_i + 2]; break
    if _a.startswith("--base-url="):
        _cli_base = _a.split("=", 1)[1]; break

if CLOUD_TRACKER_URL:
    # Cloud tracker takes highest priority - permanent, always available
    TRACKING_URL = CLOUD_TRACKER_URL.rstrip("/")
elif _cli_base:
    TRACKING_URL = _cli_base.rstrip("/")
elif os.environ.get("BASE_URL"):
    TRACKING_URL = os.environ["BASE_URL"].rstrip("/")
elif _public_ip:
    TRACKING_URL = f"http://{_public_ip}:{PORT}"
else:
    TRACKING_URL = f"http://localhost:{PORT}"

DISPOSABLE_DOMAINS = {
    'mailinator.com','guerrillamail.com','temp-mail.org','throwaway.email',
    'yopmail.com','dispostable.com','fakeinbox.com','tempmail.com',
    'sharklasers.com','guerrillamailblock.com','trashmail.com','mailnull.com',
    'spamgourmet.com','mytrashmail.com','discard.email','spamfree24.org',
    'maildrop.cc','nwldx.com','spamgob.com','spam4.me','boun.cr',
    'spamhereplease.com','inboxbear.com','getairmail.com','mailnesia.com',
    'spamoff.de','trashmail.at','trashmail.io','trashmail.me','trashmail.net',
    'tempinbox.com','tempr.email','tempemail.co','crazymailing.com',
}

TRANSPARENT_GIF = (
    b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff'
    b'\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00'
    b'\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
)

# ── Database ─────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS sends (
        id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL,
        campaign TEXT, recipient TEXT, status TEXT, error TEXT, sent_at TEXT)""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sends_job ON sends(job_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sends_recipient ON sends(recipient)")
    c.execute("""CREATE TABLE IF NOT EXISTS campaigns (
        id TEXT PRIMARY KEY, name TEXT, subject TEXT, body TEXT,
        from_email TEXT, sent_count INTEGER DEFAULT 0, fail_count INTEGER DEFAULT 0, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS opens (
        id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL, campaign TEXT,
        job_id TEXT, user_agent TEXT, ip TEXT, opened_at TEXT NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_opens_email ON opens(email)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_opens_campaign ON opens(campaign)")
    c.execute("""CREATE TABLE IF NOT EXISTS clicks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL, campaign TEXT,
        job_id TEXT, url TEXT, user_agent TEXT, ip TEXT, clicked_at TEXT NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_clicks_email ON clicks(email)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_clicks_campaign ON clicks(campaign)")
    c.execute("""CREATE TABLE IF NOT EXISTS agents (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'agent',
        color TEXT DEFAULT '#6680f5', active INTEGER DEFAULT 1, created_at TEXT NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS contacts (
        id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT, company TEXT,
        phone TEXT, tags TEXT DEFAULT '[]', notes TEXT DEFAULT '', status TEXT DEFAULT 'active',
        assigned_to TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        FOREIGN KEY(assigned_to) REFERENCES agents(id))""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_contacts_assigned ON contacts(assigned_to)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email)")
    c.execute("""CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY, agent_id TEXT NOT NULL,
        created_at TEXT NOT NULL, expires_at TEXT NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS assignment_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, contact_id TEXT, contact_email TEXT,
        from_agent TEXT, to_agent TEXT, assigned_by TEXT, assigned_at TEXT)""")
    conn.commit()
    if conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0] == 0:
        conn.execute("""INSERT INTO agents (id,name,email,password_hash,role,color,active,created_at)
            VALUES (?,?,?,?,?,?,?,?)""",
            ("agent_admin","Admin","admin@sparkmailer.local",_hash_pw(os.environ.get("ADMIN_PASSWORD","admin123")),
             "admin","#ff4060",1,datetime.now().isoformat()))
        conn.commit()
        print("Default admin → admin@sparkmailer.local / admin123")
    conn.close()

def _hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

def _db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# ── Auth ─────────────────────────────────────────────────────
def create_session(agent_id):
    token = secrets.token_hex(32)
    exp   = datetime.fromtimestamp(time.time() + 86400*7).isoformat()
    with _db() as conn:
        conn.execute("INSERT INTO sessions (token,agent_id,created_at,expires_at) VALUES (?,?,?,?)",
            (token, agent_id, datetime.now().isoformat(), exp))
    return token

def get_agent_from_token(token):
    if not token: return None
    with _db() as conn:
        row = conn.execute("""SELECT a.* FROM sessions s JOIN agents a ON s.agent_id=a.id
            WHERE s.token=? AND s.expires_at>? AND a.active=1""",
            (token, datetime.now().isoformat())).fetchone()
    return dict(row) if row else None

def token_from_headers(headers):
    auth = headers.get("Authorization","")
    return auth[7:] if auth.startswith("Bearer ") else None

# ── Agent CRUD ───────────────────────────────────────────────
def db_agents(include_inactive=False):
    with _db() as conn:
        q = "SELECT id,name,email,role,color,active,created_at FROM agents"
        if not include_inactive: q += " WHERE active=1"
        rows = conn.execute(q+" ORDER BY created_at").fetchall()
    return [dict(r) for r in rows]

def db_create_agent(name, email, pw, role="agent", color="#6680f5"):
    aid = f"agent_{int(time.time()*1000)}_{random.randint(100,999)}"
    with _db() as conn:
        conn.execute("INSERT INTO agents (id,name,email,password_hash,role,color,active,created_at) VALUES (?,?,?,?,?,?,1,?)",
            (aid, name, email, _hash_pw(pw), role, color, datetime.now().isoformat()))
    return aid

def db_update_agent(aid, fields):
    allowed = {"name","email","role","color","active"}
    sets = [f"{k}=?" for k in fields if k in allowed]
    vals = [v for k,v in fields.items() if k in allowed]
    if "password" in fields: sets.append("password_hash=?"); vals.append(_hash_pw(fields["password"]))
    if not sets: return
    vals.append(aid)
    with _db() as conn: conn.execute(f"UPDATE agents SET {', '.join(sets)} WHERE id=?", vals)

def db_delete_agent(aid):
    with _db() as conn:
        conn.execute("UPDATE contacts SET assigned_to=NULL WHERE assigned_to=?", (aid,))
        conn.execute("UPDATE agents SET active=0 WHERE id=?", (aid,))

# ── Contact CRUD ─────────────────────────────────────────────
def db_contacts(agent_id=None, role="admin", search="", status_f="", limit=500):
    with _db() as conn:
        q    = "SELECT c.*, a.name as agent_name, a.color as agent_color FROM contacts c LEFT JOIN agents a ON c.assigned_to=a.id"
        cond = []; vals = []
        if role == "agent":
            cond.append("c.assigned_to=?"); vals.append(agent_id)
        elif agent_id == "__none__":
            cond.append("c.assigned_to IS NULL")
        elif agent_id:
            cond.append("c.assigned_to=?"); vals.append(agent_id)
        if search:
            cond.append("(c.email LIKE ? OR c.name LIKE ? OR c.company LIKE ?)")
            s = f"%{search}%"; vals += [s,s,s]
        if status_f:
            cond.append("c.status=?"); vals.append(status_f)
        if cond: q += " WHERE "+" AND ".join(cond)
        q += " ORDER BY c.updated_at DESC LIMIT ?"; vals.append(limit)
        rows = conn.execute(q, vals).fetchall()
    return [dict(r) for r in rows]

def db_get_contact(cid):
    with _db() as conn:
        row = conn.execute("""SELECT c.*, a.name as agent_name, a.color as agent_color
            FROM contacts c LEFT JOIN agents a ON c.assigned_to=a.id WHERE c.id=?""", (cid,)).fetchone()
    return dict(row) if row else None

def db_create_contact(email, name="", company="", phone="", tags=None, notes="", assigned_to=None):
    cid = f"ct_{int(time.time()*1000)}_{random.randint(100,999)}"
    now = datetime.now().isoformat()
    with _db() as conn:
        conn.execute("""INSERT OR IGNORE INTO contacts
            (id,email,name,company,phone,tags,notes,status,assigned_to,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,'active',?,?,?)""",
            (cid, email.strip().lower(), name, company, phone,
             json.dumps(tags or []), notes, assigned_to, now, now))
    return cid

def db_update_contact(cid, fields):
    allowed = {"name","email","company","phone","tags","notes","status","assigned_to"}
    sets = [f"{k}=?" for k in fields if k in allowed]
    vals = [v for k,v in fields.items() if k in allowed]
    if not sets: return
    sets.append("updated_at=?"); vals.append(datetime.now().isoformat()); vals.append(cid)
    with _db() as conn: conn.execute(f"UPDATE contacts SET {', '.join(sets)} WHERE id=?", vals)

def db_assign(cid, to_agent, by_agent):
    with _db() as conn:
        old   = conn.execute("SELECT assigned_to,email FROM contacts WHERE id=?", (cid,)).fetchone()
        from_ = old["assigned_to"] if old else None
        email = old["email"] if old else ""
        conn.execute("UPDATE contacts SET assigned_to=?,updated_at=? WHERE id=?",
            (to_agent, datetime.now().isoformat(), cid))
        conn.execute("INSERT INTO assignment_log (contact_id,contact_email,from_agent,to_agent,assigned_by,assigned_at) VALUES (?,?,?,?,?,?)",
            (cid, email, from_, to_agent, by_agent, datetime.now().isoformat()))

def db_bulk_assign(cids, to_agent, by_agent):
    for cid in cids: db_assign(cid, to_agent, by_agent)

def db_import_contacts(items, assigned_to=None):
    created = skipped = 0
    for item in items:
        if isinstance(item, str): email = item.strip().lower(); name = ""
        else: email = item.get("email","").strip().lower(); name = item.get("name","")
        if not email or "@" not in email: skipped += 1; continue
        try: db_create_contact(email=email, name=name, assigned_to=assigned_to); created += 1
        except: skipped += 1
    return created, skipped

def db_contact_stats(agent_id=None):
    with _db() as conn:
        if agent_id:
            total  = conn.execute("SELECT COUNT(*) FROM contacts WHERE assigned_to=?", (agent_id,)).fetchone()[0]
            active = conn.execute("SELECT COUNT(*) FROM contacts WHERE assigned_to=? AND status='active'", (agent_id,)).fetchone()[0]
            unassigned = 0
        else:
            total      = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
            active     = conn.execute("SELECT COUNT(*) FROM contacts WHERE status='active'").fetchone()[0]
            unassigned = conn.execute("SELECT COUNT(*) FROM contacts WHERE assigned_to IS NULL").fetchone()[0]
    return {"total":total,"active":active,"unassigned":unassigned}

def db_assignment_log(limit=100):
    with _db() as conn:
        rows = conn.execute("""SELECT al.*,fa.name as from_name,ta.name as to_name,ba.name as by_name
            FROM assignment_log al
            LEFT JOIN agents fa ON al.from_agent=fa.id
            LEFT JOIN agents ta ON al.to_agent=ta.id
            LEFT JOIN agents ba ON al.assigned_by=ba.id
            ORDER BY al.assigned_at DESC LIMIT ?""", (limit,)).fetchall()
    return [dict(r) for r in rows]

# ── Send/Open/Click DB helpers ───────────────────────────────
def db_log_send(job_id, campaign, recipient, status, error=""):
    with _db() as conn:
        conn.execute("INSERT INTO sends (job_id,campaign,recipient,status,error,sent_at) VALUES (?,?,?,?,?,?)",
            (job_id, campaign, recipient, status, error or "", datetime.now().isoformat()))

def db_save_campaign(cid, name, subject, body, from_email, sent, failed):
    with _db() as conn:
        conn.execute("INSERT OR REPLACE INTO campaigns (id,name,subject,body,from_email,sent_count,fail_count,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (cid, name, subject, body, from_email, sent, failed, datetime.now().isoformat()))

def db_log_open(email, campaign, job_id, ua, ip):
    with _db() as conn:
        conn.execute("INSERT INTO opens (email,campaign,job_id,user_agent,ip,opened_at) VALUES (?,?,?,?,?,?)",
            (email, campaign, job_id or "", ua or "", ip or "", datetime.now().isoformat()))

def db_log_click(email, campaign, job_id, url, ua, ip):
    with _db() as conn:
        conn.execute("INSERT INTO clicks (email,campaign,job_id,url,user_agent,ip,clicked_at) VALUES (?,?,?,?,?,?,?)",
            (email, campaign, job_id or "", url or "", ua or "", ip or "", datetime.now().isoformat()))

def db_get_history(limit=200):
    with _db() as conn:
        rows = conn.execute("SELECT job_id,campaign,recipient,status,error,sent_at FROM sends ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [{"job_id":r[0],"campaign":r[1],"recipient":r[2],"status":r[3],"error":r[4],"sent_at":r[5]} for r in rows]

def db_get_opens_summary(campaign=None, job_id=None):
    with _db() as conn:
        if job_id:
            # Most precise: filter by job_id so each campaign's opens are separate
            rows = conn.execute(
                "SELECT email,COUNT(*) as cnt,MAX(opened_at) as last,job_id,MAX(user_agent) as ua FROM opens WHERE job_id=? GROUP BY email",
                (job_id,)).fetchall()
        elif campaign:
            rows = conn.execute(
                "SELECT email,COUNT(*) as cnt,MAX(opened_at) as last,job_id,MAX(user_agent) as ua FROM opens WHERE campaign=? GROUP BY email",
                (campaign,)).fetchall()
        else:
            # No filter: return per (email, job_id) so different campaigns don't collide
            rows = conn.execute(
                "SELECT email,COUNT(*) as cnt,MAX(opened_at) as last,job_id,MAX(user_agent) as ua FROM opens GROUP BY email,job_id"
            ).fetchall()
    return [{"email":r[0],"count":r[1],"last_opened":r[2],"job_id":r[3],"ua":r[4] or ""} for r in rows]

def db_get_clicks_summary(campaign=None):
    with _db() as conn:
        if campaign:
            rows = conn.execute("SELECT email,url,COUNT(*) as cnt FROM clicks WHERE campaign=? GROUP BY email,url", (campaign,)).fetchall()
        else:
            rows = conn.execute("SELECT email,url,COUNT(*) as cnt FROM clicks GROUP BY email,url").fetchall()
    return [{"email":r[0],"url":r[1],"count":r[2]} for r in rows]

# ── Email verification (full SMTP handshake) ─────────────────
def verify_email(email, timeout=8):
    email = email.strip().lower()
    if not re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email):
        return {"email":email,"status":"invalid","reason":"Invalid format"}
    domain = email.split('@')[1]
    if domain in DISPOSABLE_DOMAINS:
        return {"email":email,"status":"invalid","reason":"Disposable email provider"}
    # MX lookup
    mx_hosts = []
    try:
        try:
            import dns.resolver
            answers = dns.resolver.resolve(domain, 'MX')
            mx_hosts = sorted([(r.preference, str(r.exchange).rstrip('.')) for r in answers])
        except ImportError:
            mx_hosts = [(10, domain)]
    except Exception as e:
        return {"email":email,"status":"risky","reason":f"DNS error: {str(e)[:60]}"}
    if not mx_hosts:
        return {"email":email,"status":"invalid","reason":"No MX records found"}
    # SMTP handshake - try top 2 MX
    last_error = "Unknown error"
    for _, mx in mx_hosts[:2]:
        try:
            with smtplib.SMTP(timeout=timeout) as smtp:
                smtp.connect(mx, 25)
                smtp.ehlo_or_helo_if_needed()
                smtp.mail('verify@sparkmailer.local')
                code, msg = smtp.rcpt(email)
                smtp.quit()
                if code == 250:
                    return {"email":email,"status":"valid","reason":f"Accepted by {mx}"}
                elif code == 550:
                    return {"email":email,"status":"invalid","reason":"Rejected (550): mailbox does not exist"}
                elif code in (421,450,451,452):
                    return {"email":email,"status":"risky","reason":f"Temp error ({code})"}
                elif code == 552:
                    return {"email":email,"status":"invalid","reason":"Mailbox full / over quota"}
                else:
                    return {"email":email,"status":"risky","reason":f"Uncertain response: {code}"}
        except smtplib.SMTPConnectError:
            last_error = f"Cannot connect to {mx}:25"; continue
        except smtplib.SMTPServerDisconnected:
            last_error = f"Server disconnected ({mx})"; continue
        except socket.timeout:
            last_error = f"Timeout ({mx})"; continue
        except smtplib.SMTPRecipientsRefused as e:
            code = list(e.recipients.values())[0][0]
            msg  = list(e.recipients.values())[0][1].decode(errors='ignore')
            if code == 550:
                return {"email":email,"status":"invalid","reason":f"Rejected (550): {msg[:80]}"}
            return {"email":email,"status":"risky","reason":f"Refused ({code}): {msg[:80]}"}
        except Exception as e:
            last_error = str(e)[:80]; continue
    return {"email":email,"status":"risky","reason":f"Could not verify: {last_error}"}

# ── Professional HTML email builder ─────────────────────────
def build_html_email(body_html, pixel_html, from_name=""):
    """
    Wraps body in a professional HTML email template.
    Uses correct DOCTYPE and structure so Gmail/Outlook auto-load images.
    The pixel is placed immediately after <body> open tag - loads first.
    """
    return f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
</head>
<body style="margin:0;padding:0;background-color:#ffffff;">
{pixel_html}
<table border="0" cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;">
<tr><td align="center" style="padding:20px 10px;">
<table border="0" cellpadding="0" cellspacing="0" width="600" style="border-collapse:collapse;max-width:600px;width:100%;">
<tr><td style="font-family:Arial,Helvetica,sans-serif;font-size:15px;color:#222222;line-height:1.7;padding:10px 0;">
{body_html}
</td></tr>
</table>
</td></tr>
</table>
{pixel_html}
</body>
</html>"""

# ── Tracking injection ───────────────────────────────────────
def inject_tracking(body, is_html, email, campaign, job_id, track_opens=True, track_clicks=True):
    """Returns (body, pixel_html). pixel_html is '' when tracking disabled."""
    pixel_html = ""
    if track_opens:
        params = urlencode({'email':email,'campaign':campaign,'job':job_id})
        # Use both standard img pixel AND a table-based pixel for maximum compatibility
        pixel_url = TRACKING_URL + '/track?' + params
        pixel_html = (
            # Standard 1x1 tracking pixel - clean, no problematic CSS
            '<img src="' + pixel_url + '"'
            ' width="1" height="1" border="0" alt=""'
            ' style="height:1px!important;width:1px!important;border-width:0!important;'
            'margin-top:0!important;margin-bottom:0!important;'
            'margin-right:0!important;margin-left:0!important;'
            'padding-top:0!important;padding-bottom:0!important;'
            'padding-right:0!important;padding-left:0!important;" />'
        )
    if is_html:
        if track_clicks:
            def replace_link(m):
                u = m.group(1)
                if u.startswith(('mailto:','javascript:',TRACKING_URL,BASE_URL,'#')): return m.group(0)
                p = urlencode({'url':u,'email':email,'campaign':campaign,'job':job_id})
                return f'href="{TRACKING_URL}/click?{p}"'
            body = re.sub(r'href=["\']([^"\']*)["\']', replace_link, body)
        if pixel_html:
            # Place pixel at TOP (inside <body>) AND bottom for maximum load chance
            if '<body' in body.lower():
                body = re.sub(r'(<body[^>]*>)', r'\1' + pixel_html, body, flags=re.IGNORECASE)
            else:
                body = pixel_html + body
            # Also place at bottom
            if '</body>' in body.lower():
                body = re.sub(r'</body>', pixel_html + '</body>', body, flags=re.IGNORECASE)
            else:
                body = body + pixel_html
    return body, pixel_html

# ── SMTP send worker ─────────────────────────────────────────
def send_worker(job_id, payload):
    recipients   = payload["recipients"]
    subject      = payload["subject"]
    body         = payload["body"]
    from_email   = payload["from_email"]
    from_name    = payload.get("from_name","")
    app_pw       = payload["app_password"]
    reply_to     = payload.get("reply_to", from_email)
    smtp_host    = payload.get("smtp_host","smtp.gmail.com")
    smtp_port    = int(payload.get("smtp_port",587))
    campaign     = payload.get("campaign","Campaign")
    delay_min    = float(payload.get("delay_min",5))
    delay_max    = float(payload.get("delay_max",10))
    is_html      = payload.get("is_html",False)
    track_opens  = payload.get("track_opens",True)
    track_clicks = payload.get("track_clicks",True)

    with JOBS_LOCK:
        SEND_JOBS[job_id].update({"total":len(recipients),"status":"running","results":[],"log":[]})

    def log(msg, lvl="info"):
        with JOBS_LOCK:
            SEND_JOBS[job_id]["log"].append({"time":datetime.now().strftime("%H:%M:%S"),"msg":msg,"level":lvl})

    def db_log_async(jid, camp, rcpt, st, err=""):
        threading.Thread(target=db_log_send, args=(jid,camp,rcpt,st,err), daemon=True).start()

    MAX_RETRIES = 2
    t0 = time.time()

    def make_smtp():
        ctx  = ssl.create_default_context()
        conn = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
        conn.ehlo(); conn.starttls(context=ctx); conn.ehlo()
        conn.login(from_email, app_pw)
        return conn

    def is_alive(conn):
        try:
            conn.sock.settimeout(3)
            ok = conn.noop()[0] == 250
            conn.sock.settimeout(10)
            return ok
        except Exception:
            return False

    log(f"Connecting to {smtp_host}:{smtp_port}…")
    try:
        server = make_smtp()
        log(f"✓ Authenticated as {from_email} ({time.time()-t0:.1f}s)", "success")
    except smtplib.SMTPAuthenticationError:
        log("✗ Authentication failed. Check email + app password.", "error")
        with JOBS_LOCK: SEND_JOBS[job_id].update({"status":"error","error":"Authentication failed"})
        return
    except (smtplib.SMTPConnectError, ConnectionRefusedError, socket.timeout) as e:
        log(f"✗ Cannot connect: {e}", "error")
        with JOBS_LOCK: SEND_JOBS[job_id].update({"status":"error","error":str(e)[:200]})
        return
    except Exception as e:
        log(f"✗ Error: {e}", "error")
        with JOBS_LOCK: SEND_JOBS[job_id].update({"status":"error","error":str(e)[:200]})
        return

    sent_count = failed_count = 0
    just_connected = True

    try:
        for i, recipient in enumerate(recipients):
            with JOBS_LOCK:
                if SEND_JOBS[job_id].get("cancel"):
                    log("⚡ Send cancelled by user.", "warn"); break

            local   = recipient.split("@")[0]
            cleaned = re.sub(r'[\._\-\+]', ' ', local)
            parts   = [p.capitalize() for p in cleaned.split() if p]
            first   = parts[0] if parts else local.capitalize()

            personalized = body.replace("{{name}}",first).replace("{{first_name}}",first).replace("{{email}}",recipient)
            tracked_body, pixel_html = inject_tracking(personalized, is_html, recipient, campaign, job_id, track_opens, track_clicks)

            success = False; last_err = ""
            for attempt in range(MAX_RETRIES):
                try:
                    if not just_connected and not is_alive(server):
                        log(f"  ↻ Reconnecting…", "warn")
                        try: server.quit()
                        except: pass
                        server = make_smtp()
                    just_connected = False

                    msg = MIMEMultipart("alternative")
                    msg["Subject"]    = subject
                    msg["From"]       = formataddr((from_name, from_email))
                    msg["To"]         = recipient
                    msg["Reply-To"]   = reply_to
                    msg["Date"]       = formatdate(localtime=True)
                    msg["Message-ID"] = make_msgid(domain=from_email.split("@")[-1])
                    msg["X-Mailer"]   = "Mozilla Thunderbird 115.0"
                    msg["X-Priority"] = "3"

                    # Always attach plain text part first (fallback for text-only clients)
                    if is_html:
                        plain_text = re.sub(r'<[^>]+>','', tracked_body)
                        plain_text = re.sub(r'\n{3,}','\n\n', plain_text).strip()
                    else:
                        plain_text = tracked_body
                    msg.attach(MIMEText(plain_text, "plain", "utf-8"))

                    # Always attach a proper HTML part.
                    # When tracking is on, this is the only reliable way to load
                    # the pixel on Gmail/Outlook/Apple Mail across all devices.
                    # Plain text body is converted to HTML so the email reads correctly.
                    if is_html:
                        html_body = tracked_body
                        # Ensure proper HTML structure
                        if '<html' not in html_body.lower():
                            html_body = build_html_email(html_body, pixel_html, from_name)
                        elif pixel_html:
                            # Inject pixel at top of body
                            html_body = re.sub(r'(<body[^>]*>)', r'\1' + pixel_html, html_body, flags=re.IGNORECASE)
                            html_body = re.sub(r'(</body>)', pixel_html + r'\1', html_body, flags=re.IGNORECASE)
                    else:
                        # Convert plain text to HTML email
                        body_as_html = html.escape(plain_text).replace('\n', '<br>\n')
                        html_body = build_html_email(body_as_html, pixel_html, from_name)

                    msg.attach(MIMEText(html_body, "html", "utf-8"))

                    t1 = time.time()
                    server.sendmail(from_email, recipient, msg.as_string())
                    log(f"✓ [{i+1}/{len(recipients)}] Sent → {recipient} ({time.time()-t1:.1f}s)", "success")
                    success = True; break

                except smtplib.SMTPRecipientsRefused as e:
                    last_err = f"Rejected: {e}"; break
                except smtplib.SMTPDataError as e:
                    last_err = f"Data error: {e}"; break
                except smtplib.SMTPAuthenticationError as e:
                    last_err = f"Auth error: {e}"; break
                except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, ConnectionRefusedError, socket.timeout) as e:
                    last_err = f"Connection error: {e}"
                    log(f"  ↻ Connection lost, reconnecting (attempt {attempt+1})…", "warn")
                    try: server.quit()
                    except: pass
                    try: server = make_smtp(); just_connected = True
                    except Exception as re_err: last_err = f"Reconnect failed: {re_err}"
                    if attempt < MAX_RETRIES - 1: time.sleep(1)
                except Exception as e:
                    last_err = str(e)
                    if attempt < MAX_RETRIES - 1: time.sleep(1)

            with JOBS_LOCK:
                if success:
                    SEND_JOBS[job_id]["results"].append({"email":recipient,"status":"sent"})
                    SEND_JOBS[job_id]["progress"] = i+1
                    sent_count += 1
                    db_log_async(job_id, campaign, recipient, "sent")
                else:
                    et = "bounced" if any(c in last_err for c in ['550','551','553','5.1.']) else "failed"
                    SEND_JOBS[job_id]["results"].append({"email":recipient,"status":et,"error":last_err})
                    SEND_JOBS[job_id]["progress"] = i+1
                    failed_count += 1
                    log(f"✗ [{i+1}/{len(recipients)}] {et.title()} {recipient}: {last_err[:80]}", "error")
                    db_log_async(job_id, campaign, recipient, et, last_err[:200])

            if i < len(recipients)-1:
                with JOBS_LOCK: cancelled = SEND_JOBS[job_id].get("cancel")
                if not cancelled:
                    delay = max(0, random.uniform(max(0,delay_min), max(delay_min,delay_max)) + random.uniform(-0.3,0.3))
                    if delay > 0:
                        log(f"  ↻ Waiting {delay:.1f}s before next send…")
                        time.sleep(delay)
    finally:
        try: server.quit()
        except: pass

    log(f"━━━ Done. {sent_count} sent, {failed_count} failed. ━━━", "success")
    db_save_campaign(job_id, campaign, subject, body, from_email, sent_count, failed_count)
    with JOBS_LOCK: SEND_JOBS[job_id].update({"status":"done","sent":sent_count,"failed":failed_count})

def verify_worker(vid, emails):
    results = []
    for e in emails:
        results.append(verify_email(e))
        with JOBS_LOCK: SEND_JOBS[vid].update({"results":results,"progress":len(results)})
    with JOBS_LOCK: SEND_JOBS[vid]["status"] = "done"

# ── HTTP Handler ─────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type,Authorization")
        self.send_header("ngrok-skip-browser-warning","true")  # bypass ngrok interstitial

    def do_OPTIONS(self):
        self.send_response(200); self._cors(); self.end_headers()

    def _agent(self): return get_agent_from_token(token_from_headers(self.headers))
    def _auth(self):
        a = self._agent()
        if not a: self._json({"ok":False,"error":"Unauthorized"},401)
        return a
    def _admin(self):
        a = self._auth()
        if a and a["role"] != "admin": self._json({"ok":False,"error":"Admin only"},403); return None
        return a

    def do_GET(self):
        parsed = urlparse(self.path); path = parsed.path; qs = parse_qs(parsed.query)

        # Serve HTML app
        if path in ("/","/index.html"):
            html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spark_mailer_v5.html")
            if os.path.exists(html_path):
                with open(html_path,"rb") as f: content = f.read()
                self.send_response(200)
                self.send_header("Content-Type","text/html; charset=utf-8")
                self.send_header("Content-Length",str(len(content)))
                self._cors(); self.end_headers(); self.wfile.write(content)
            else:
                self.send_response(404); self.end_headers()
                self.wfile.write(b"spark_mailer_v5.html not found")
            return

        if path == "/ping":
            self._json({"ok":True,"version":VERSION,"base_url":BASE_URL,"tracking_url":TRACKING_URL})

        elif path == "/status":
            # FIX: deep-copy under lock to avoid race condition
            jid = qs.get("job",[None])[0]
            snapshot = None
            with JOBS_LOCK:
                job = SEND_JOBS.get(jid)
                if job:
                    snapshot = {
                        "status":   job["status"],
                        "progress": job["progress"],
                        "total":    job["total"],
                        "sent":     job.get("sent",0),
                        "failed":   job.get("failed",0),
                        "error":    job.get("error",""),
                        "log":      list(job["log"]),
                        "results":  list(job["results"]),
                    }
            if snapshot is not None: self._json(snapshot)
            else: self._json({"error":"job not found"},404)

        elif path == "/history":
            self._json({"history": db_get_history(int(qs.get("limit",["200"])[0]))})

        elif path == "/cancel":
            jid = qs.get("job",[None])[0]
            with JOBS_LOCK:
                if jid in SEND_JOBS: SEND_JOBS[jid]["cancel"]=True; self._json({"ok":True})
                else: self._json({"error":"not found"},404)

        elif path == "/track":
            email=qs.get("email",[""])[0]; campaign=qs.get("campaign",[""])[0]; jid=qs.get("job",[""])[0]
            ip=self.client_address[0]; ua=self.headers.get("User-Agent","")
            print(f"[OPEN] {email} | campaign={campaign} | job={jid} | ip={ip} | ua={ua[:60]}")
            if email:
                try: db_log_open(email,campaign,jid,ua,ip)
                except Exception as e: print(f"[OPEN DB ERROR] {e}")
            self.send_response(200)
            self.send_header("Content-Type","image/gif")
            self.send_header("Content-Length",str(len(TRANSPARENT_GIF)))
            self.send_header("Cache-Control","no-cache,no-store,must-revalidate")
            self.send_header("Pragma","no-cache"); self.send_header("Expires","0")
            self.send_header("ngrok-skip-browser-warning","true")
            self.send_header("Access-Control-Allow-Origin","*")
            self._cors(); self.end_headers(); self.wfile.write(TRANSPARENT_GIF)

        elif path == "/click":
            url=qs.get("url",[""])[0]; email=qs.get("email",[""])[0]
            campaign=qs.get("campaign",[""])[0]; jid=qs.get("job",[""])[0]
            ua=self.headers.get("User-Agent",""); ip=self.client_address[0]
            if email and url:
                try: db_log_click(email,campaign,jid,url,ua,ip)
                except: pass
                # Also mark as opened - click = definitely opened the email
                try:
                    db_log_open(email,campaign,jid,ua,ip)
                    print(f"[CLICK→OPEN] {email} | campaign={campaign} | url={url[:60]}")
                except: pass
            self.send_response(302); self.send_header("Location",url or "/"); self._cors(); self.end_headers()

        elif path == "/opens":
            jid  = qs.get("job",      [None])[0]
            camp = qs.get("campaign", [None])[0]
            # Get opens from local DB
            local_opens = db_get_opens_summary(campaign=camp, job_id=jid)
            # Also sync from cloud tracker if configured
            if CLOUD_TRACKER_URL:
                try:
                    url = CLOUD_TRACKER_URL.rstrip("/") + "/opens"
                    params = []
                    if jid:   params.append(f"job={jid}")
                    if camp:  params.append(f"campaign={camp}")
                    if params: url += "?" + "&".join(params)
                    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {CLOUD_API_KEY}"})
                    with urllib.request.urlopen(req, timeout=5) as r:
                        cloud_data = json.loads(r.read())
                    cloud_opens = cloud_data.get("opens", [])
                    # Merge: write cloud opens into local DB so they persist
                    for o in cloud_opens:
                        try: db_log_open(o["email"], camp or "cloud", o.get("job_id",""), o.get("ua",""), "cloud-sync")
                        except: pass
                    # Re-fetch merged local opens
                    local_opens = db_get_opens_summary(campaign=camp, job_id=jid)
                except Exception as e:
                    pass  # Cloud sync failed silently, use local data
            self._json({"opens": local_opens})

        elif path == "/proxy-pixel":
            # Test: server fetches the tracking pixel through ngrok with proper headers
            # This confirms the full external path works (browser -> server -> ngrok -> DB)
            test_job = qs.get("job", ["proxytest_" + str(int(time.time()))])[0]
            pixel_url = TRACKING_URL + "/track?email=proxytest%40sparkmailer.local&campaign=proxytest&job=" + test_job
            try:
                import urllib.request as _ur
                req = _ur.Request(pixel_url, headers={
                    "ngrok-skip-browser-warning": "true",
                    "User-Agent": "SparK-Pixel-Test/1.0"
                })
                with _ur.urlopen(req, timeout=8) as resp:
                    status = resp.status
                # Wait briefly then check DB
                time.sleep(1)
                with _db() as conn:
                    cnt = conn.execute(
                        "SELECT COUNT(*) FROM opens WHERE campaign='proxytest'").fetchone()[0]
                if cnt > 0:
                    self._json({"ok": True, "recorded": True,
                        "message": f"Full path works! Pixel reached server via ngrok and was recorded ({cnt} test opens in DB).",
                        "pixel_url": pixel_url})
                else:
                    self._json({"ok": True, "recorded": False,
                        "message": "Pixel URL responded but was not recorded in DB. Check terminal for errors.",
                        "pixel_url": pixel_url, "http_status": status})
            except Exception as e:
                self._json({"ok": False, "recorded": False,
                    "message": f"Could not reach pixel URL via ngrok: {str(e)[:200]}",
                    "pixel_url": pixel_url})

        elif path == "/track-test":
            # Self-test: fire a pixel and confirm DB write in one request
            test_email = "tracktest@sparkmailer.local"
            try:
                db_log_open(test_email, "tracktest", "tracktest_job", "SparK-Self-Test", self.client_address[0])
                with _db() as conn:
                    cnt = conn.execute("SELECT COUNT(*) FROM opens WHERE email=?", (test_email,)).fetchone()[0]
                self._json({"ok": True, "message": f"Pixel test successful - {cnt} test opens recorded", "count": cnt})
            except Exception as e:
                self._json({"ok": False, "error": str(e)})

        elif path == "/debug":
            # Diagnostic endpoint - open in browser to verify tracking is working
            with _db() as conn:
                recent_opens  = conn.execute("SELECT email,campaign,job_id,ip,opened_at FROM opens ORDER BY id DESC LIMIT 20").fetchall()
                total_opens   = conn.execute("SELECT COUNT(*) FROM opens").fetchone()[0]
                recent_sends  = conn.execute("SELECT recipient,campaign,status,sent_at FROM sends ORDER BY id DESC LIMIT 5").fetchall()
            html_out = f"""<!DOCTYPE html><html><head><title>SparK Debug</title>
<style>body{{font-family:monospace;background:#0f0f17;color:#eee;padding:30px}}
h2{{color:#ff4060}}table{{border-collapse:collapse;width:100%}}
th{{background:#1c1c28;padding:8px;text-align:left;color:#aaa;font-size:12px}}
td{{padding:8px;border-bottom:1px solid #252535;font-size:13px}}
.ok{{color:#20c55a}}.warn{{color:#f5a623}}.info{{color:#6680f5}}</style></head>
<body>
<h2>SparK Mailer v{VERSION} - Debug Panel</h2>
<p class='info'>Tracking URL (in emails): <strong>{TRACKING_URL}</strong></p><p class='info'>Backend URL (app): <strong>{BASE_URL}</strong></p>
<p class='info'>Total opens in DB: <strong>{total_opens}</strong></p>
<p>To test pixel: open <a href='{TRACKING_URL}/track?email=test@test.com&campaign=debug&job=test' style='color:#6680f5'>{TRACKING_URL}/track?email=test@test.com&campaign=debug&job=test</a> in a browser</p>
<h2>Last 20 Open Events</h2>
<table><tr><th>Email</th><th>Campaign</th><th>Job ID</th><th>IP</th><th>Opened At</th></tr>
{''.join(f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[4]}</td></tr>" for r in recent_opens) or '<tr><td colspan=5 style=color:#888>No opens recorded yet</td></tr>'}
</table>
<h2>Last 5 Sends</h2>
<table><tr><th>Recipient</th><th>Campaign</th><th>Status</th><th>Sent At</th></tr>
{''.join(f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td></tr>" for r in recent_sends) or '<tr><td colspan=4 style=color:#888>No sends yet</td></tr>'}
</table>
</body></html>"""
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Content-Length",str(len(html_out.encode())))
            self._cors(); self.end_headers()
            self.wfile.write(html_out.encode())

        elif path == "/clicks":
            self._json({"clicks": db_get_clicks_summary(qs.get("campaign",[None])[0])})

        elif path == "/agents":
            a = self._auth()
            if not a: return
            self._json({"ok":True,"agents":db_agents()})

        elif path == "/agents/me":
            a = self._auth()
            if not a: return
            self._json({"ok":True,"agent":{k:v for k,v in a.items() if k!="password_hash"}})

        elif path == "/agents/assignment-log":
            a = self._admin()
            if not a: return
            self._json({"ok":True,"log":db_assignment_log()})

        elif path == "/contacts":
            a = self._auth()
            if not a: return
            af=qs.get("agent",[None])[0]; search=qs.get("search",[""])[0]
            sf=qs.get("status",[""])[0]; limit=int(qs.get("limit",["500"])[0])
            contacts = db_contacts(agent_id=a["id"] if a["role"]=="agent" else af,
                role=a["role"],search=search,status_f=sf,limit=limit)
            stats = db_contact_stats(a["id"] if a["role"]=="agent" else None)
            self._json({"ok":True,"contacts":contacts,"stats":stats})

        elif path.startswith("/contacts/"):
            a = self._auth()
            if not a: return
            cid = path[10:]
            contact = db_get_contact(cid)
            if not contact: self._json({"ok":False,"error":"Not found"},404); return
            if a["role"]=="agent" and contact["assigned_to"]!=a["id"]:
                self._json({"ok":False,"error":"Access denied"},403); return
            self._json({"ok":True,"contact":contact})

        else: self._json({"error":"not found"},404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length",0))
        raw    = self.rfile.read(length)
        try: payload = json.loads(raw) if raw else {}
        except: self._json({"error":"invalid JSON"},400); return
        path = urlparse(self.path).path

        if path == "/auth/login":
            email=payload.get("email","").strip().lower(); pw=payload.get("password","")
            if not email or not pw: self._json({"ok":False,"error":"Email and password required"}); return
            with _db() as conn:
                row = conn.execute("SELECT * FROM agents WHERE email=? AND active=1",(email,)).fetchone()
            if not row or row["password_hash"]!=_hash_pw(pw):
                self._json({"ok":False,"error":"Invalid email or password"}); return
            token = create_session(row["id"])
            self._json({"ok":True,"token":token,"agent":{k:v for k,v in dict(row).items() if k!="password_hash"}})

        elif path == "/auth/logout":
            t = token_from_headers(self.headers)
            if t:
                with _db() as conn: conn.execute("DELETE FROM sessions WHERE token=?",(t,))
            self._json({"ok":True})

        elif path == "/agents":
            admin = self._admin()
            if not admin: return
            name=payload.get("name","").strip(); email=payload.get("email","").strip().lower()
            pw=payload.get("password",""); role=payload.get("role","agent"); color=payload.get("color","#6680f5")
            if not name or not email or not pw:
                self._json({"ok":False,"error":"name, email, and password required"}); return
            try: aid=db_create_agent(name,email,pw,role,color); self._json({"ok":True,"agent_id":aid})
            except sqlite3.IntegrityError: self._json({"ok":False,"error":"Email already exists"})

        elif path == "/contacts":
            a = self._auth()
            if not a: return
            email=payload.get("email","").strip().lower()
            if not email: self._json({"ok":False,"error":"email required"}); return
            at = payload.get("assigned_to") or (a["id"] if a["role"]=="agent" else None)
            cid = db_create_contact(email=email,name=payload.get("name",""),
                company=payload.get("company",""),phone=payload.get("phone",""),
                tags=payload.get("tags",[]),notes=payload.get("notes",""),assigned_to=at)
            self._json({"ok":True,"contact_id":cid})

        elif path == "/contacts/import":
            a = self._auth()
            if not a: return
            at = payload.get("assigned_to") or (a["id"] if a["role"]=="agent" else None)
            created,skipped = db_import_contacts(payload.get("emails",[]),assigned_to=at)
            self._json({"ok":True,"created":created,"skipped":skipped})

        elif path == "/contacts/bulk-assign":
            admin = self._admin()
            if not admin: return
            cids=payload.get("contact_ids",[]); to_agent=payload.get("agent_id")
            if not cids: self._json({"ok":False,"error":"contact_ids required"}); return
            db_bulk_assign(cids,to_agent,admin["id"])
            self._json({"ok":True,"assigned":len(cids)})

        elif path.endswith("/assign") and "/contacts/" in path:
            admin = self._admin()
            if not admin: return
            cid = path.split("/contacts/")[1].replace("/assign","")
            db_assign(cid,payload.get("agent_id"),admin["id"])
            self._json({"ok":True})

        elif path == "/send":
            required = ["recipients","subject","body","from_email","app_password"]
            for f in required:
                if not payload.get(f): self._json({"ok":False,"error":f"missing: {f}"},400); return
            if not isinstance(payload["recipients"],list) or not payload["recipients"]:
                self._json({"ok":False,"error":"recipients must be non-empty list"},400); return
            if len(payload["recipients"]) > 2000:
                self._json({"ok":False,"error":"Maximum 2000 recipients per job"},400); return
            jid = f"job_{int(time.time()*1000)}_{random.randint(1000,9999)}"
            with JOBS_LOCK:
                SEND_JOBS[jid] = {"status":"queued","progress":0,"total":0,"results":[],"log":[],"cancel":False,"sent":0,"failed":0}
            threading.Thread(target=send_worker,args=(jid,payload),daemon=True).start()
            self._json({"ok":True,"job_id":jid})

        elif path == "/test":
            host=payload.get("smtp_host","smtp.gmail.com"); port=int(payload.get("smtp_port",587))
            email=payload.get("from_email",""); pw=payload.get("app_password","")
            if not email or not pw: self._json({"ok":False,"message":"Email and password required"}); return
            try:
                ctx = ssl.create_default_context()
                with smtplib.SMTP(host,port,timeout=12) as s:
                    s.ehlo(); s.starttls(context=ctx); s.ehlo(); s.login(email,pw)
                self._json({"ok":True,"message":f"Connected & authenticated as {email}"})
            except smtplib.SMTPAuthenticationError:
                self._json({"ok":False,"message":"Authentication failed - check email & app password"})
            except smtplib.SMTPConnectError:
                self._json({"ok":False,"message":f"Cannot connect to {host}:{port}"})
            except socket.timeout:
                self._json({"ok":False,"message":f"Timeout connecting to {host}:{port}"})
            except Exception as e:
                self._json({"ok":False,"message":str(e)})

        elif path == "/verify-single":
            email = payload.get("email","").strip()
            if not email: self._json({"ok":False,"error":"email required"},400); return
            result = verify_email(email)
            self._json({"ok":True,**result})

        elif path == "/verify-bulk":
            emails = payload.get("emails",[])
            if not isinstance(emails,list) or not emails:
                self._json({"ok":False,"error":"emails list required"},400); return
            if len(emails) > 500:
                self._json({"ok":False,"error":"Maximum 500 emails per bulk verify"},400); return
            if len(emails) <= 10:
                self._json({"ok":True,"results":[verify_email(e) for e in emails]})
            else:
                vid = f"verify_{int(time.time()*1000)}"
                with JOBS_LOCK: SEND_JOBS[vid]={"status":"running","progress":0,"total":len(emails),"results":[]}
                threading.Thread(target=verify_worker,args=(vid,emails),daemon=True).start()
                self._json({"ok":True,"job_id":vid,"total":len(emails)})

        elif path == "/deduplicate":
            # Remove duplicates from a list of emails (case-insensitive)
            raw_list = payload.get("emails",[])
            if not isinstance(raw_list,list):
                self._json({"ok":False,"error":"emails must be a list"},400); return
            seen = set(); unique = []; dupes = []
            for e in raw_list:
                norm = e.strip().lower()
                if not norm: continue
                if norm in seen: dupes.append(e.strip())
                else: seen.add(norm); unique.append(e.strip())
            self._json({"ok":True,"unique":unique,"duplicates":dupes,
                "original_count":len(raw_list),"unique_count":len(unique),"removed":len(dupes)})

        elif path == "/extract-emails":
            # Extract all email addresses from free-form text/HTML
            text = payload.get("text","")
            if not text: self._json({"ok":False,"error":"text required"},400); return
            found = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)
            # Deduplicate while preserving order, normalise to lowercase
            seen = set(); unique = []
            for e in found:
                norm = e.lower()
                if norm not in seen: seen.add(norm); unique.append(norm)
            self._json({"ok":True,"emails":unique,"count":len(unique)})

        else: self._json({"ok":False,"error":"endpoint not found"},404)

    def do_PUT(self):
        length=int(self.headers.get("Content-Length",0)); raw=self.rfile.read(length)
        try: payload=json.loads(raw) if raw else {}
        except: self._json({"error":"invalid JSON"},400); return
        path = urlparse(self.path).path
        if path.startswith("/agents/"):
            admin = self._admin()
            if not admin: return
            db_update_agent(path[8:],payload); self._json({"ok":True})
        elif path.startswith("/contacts/"):
            a = self._auth()
            if not a: return
            cid=path[10:]; contact=db_get_contact(cid)
            if not contact: self._json({"ok":False,"error":"Not found"},404); return
            if a["role"]=="agent" and contact["assigned_to"]!=a["id"]:
                self._json({"ok":False,"error":"Access denied"},403); return
            if a["role"]=="agent" and "assigned_to" in payload: del payload["assigned_to"]
            db_update_contact(cid,payload); self._json({"ok":True})
        else: self._json({"error":"not found"},404)

    def do_DELETE(self):
        path = urlparse(self.path).path
        if path.startswith("/agents/"):
            admin = self._admin()
            if not admin: return
            aid = path[8:]
            if aid==admin["id"]: self._json({"ok":False,"error":"Cannot delete yourself"}); return
            db_delete_agent(aid); self._json({"ok":True})
        elif path.startswith("/contacts/"):
            a = self._auth()
            if not a: return
            cid=path[10:]; contact=db_get_contact(cid)
            if not contact: self._json({"ok":False,"error":"Not found"},404); return
            if a["role"]=="agent" and contact["assigned_to"]!=a["id"]:
                self._json({"ok":False,"error":"Access denied"},403); return
            with _db() as conn: conn.execute("DELETE FROM contacts WHERE id=?",(cid,))
            self._json({"ok":True})
        else: self._json({"error":"not found"},404)

    def _json(self,data,code=200):
        body = json.dumps(data,ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(body)))
        self._cors(); self.end_headers(); self.wfile.write(body)


if __name__ == "__main__":
    init_db()
    try: import dns.resolver; dns_ok="✓ dnspython"
    except ImportError: dns_ok="✗ pip install dnspython"
    if _railway_domain or _app_url or CLOUD_TRACKER_URL:
        tracking = f"✓ {TRACKING_URL}  (cloud deployment - always available)"
    elif _cli_base or os.environ.get("BASE_URL"):
        tracking = f"✓ {TRACKING_URL}  (custom URL - tracking active)"
    elif _public_ip:
        tracking = f"? {TRACKING_URL}  (auto-detected - port {PORT} must be open in router)"
    else:
        tracking = f"✗ localhost only - start with: python start.py"
    server = ThreadingHTTPServer(("0.0.0.0",PORT),Handler)
    print(f"""
╔══════════════════════════════════════════════════════════╗
║         SparK Mailer - Backend v5                        ║
╠══════════════════════════════════════════════════════════╣
║  Open app   →  http://localhost:{PORT}                      ║
║  Database      spark_data.db                             ║
║  DNS/MX        {dns_ok:<42}║
║  Tracking   →  {tracking:<42}║
║  Admin login:  admin@sparkmailer.local / admin123        ║
║  Press Ctrl+C to stop                                    ║
╚══════════════════════════════════════════════════════════╝
""")
    try: server.serve_forever()
    except KeyboardInterrupt: print("\nServer stopped.")
