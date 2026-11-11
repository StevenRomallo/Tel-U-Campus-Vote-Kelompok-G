"""Tel-U Campus Vote. Python standard library only; run one backend process."""
import argparse
import json
import hashlib
import hmac
import os
import random
import re
import secrets
import shutil
import tempfile
import threading
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie, CookieError
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
UTC = timezone.utc
MAX_BODY = 65536
THANK_YOU = "terimakasih sudah menggunakan hak pilih anda, hak pilih anda sangat berguna bagi Universitas ini"
COOKIE_NAME = "campus_vote_session"


class APIError(Exception):
    def __init__(self, status, message, details=None):
        self.status, self.message = status, message
        self.details = details or {}


def now():
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def parse_time(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError("Timezone required")
        return result.astimezone(UTC)
    except (ValueError, TypeError, AttributeError):
        raise APIError(400, "Waktu harus berupa ISO 8601 dengan zona waktu.")


def validate_vote(body, historical=False):
    if not isinstance(body, dict):
        raise APIError(400, "Isi permintaan harus berupa objek JSON.")
    if body.get("option") not in ("A", "B"):
        raise APIError(400, "Pilih kandidat A atau B.")
    faculty = next((f for f in CONFIG["faculties"] if f["name"] == body.get("faculty")), None)
    if faculty is None or body.get("program") not in faculty["programs"]:
        raise APIError(400, "Fakultas dan program studi tidak sesuai konfigurasi.")
    if type(body.get("cohort")) is not int or body["cohort"] not in CONFIG["cohorts"]:
        raise APIError(400, "Angkatan tidak valid.")
    campus = body.get("campus", "Bandung")
    if not isinstance(campus, str) or (not historical and campus != "Bandung"):
        raise APIError(400, "Pemilihan ini khusus Telkom University Bandung.")
    return dict({key: body[key] for key in ("option", "faculty", "program", "cohort")}, campus=campus)


def normalize_nim(value):
    if not isinstance(value, str) or not re.fullmatch(r"1010[0-9]{8}", value.strip()):
        raise APIError(400, "NIM harus 12 digit: 1010 diikuti delapan angka.")
    return value.strip()


def nim_digest(nim, key):
    return hmac.new(key.encode(), ("campus-vote:nim:" + normalize_nim(nim)).encode(), hashlib.sha256).hexdigest()


class VoteStore:
    def __init__(self, directory, hmac_secret):
        if not isinstance(hmac_secret, str) or len(hmac_secret) < 32:
            raise ValueError("NIM_HMAC_SECRET minimal 32 karakter; jalankan tools/setup_secrets.py.")
        self.key_id = hmac.new(hmac_secret.encode(), b"campus-vote:key-check:v1", hashlib.sha256).hexdigest()
        self.path = Path(directory) / "votes.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.changed = threading.Condition(self.lock)
        self.revision = 0
        self.instance_id = uuid4().hex
        with self.lock:
            if not self.path.exists():
                self._write(self.empty_document())
            else:
                self._read_document()  # Validate/migrate before accepting requests.

    def empty_document(self):
        return {"schema_version": 2, "hmac_key_id": self.key_id, "votes": [], "used_nims": {}}

    def _validate_rows(self, rows):
        if not isinstance(rows, list):
            raise ValueError("Expected votes array")
        ids = set()
        for row in rows:
            validate_vote(row, historical=True)
            if not isinstance(row.get("id"), str) or row["id"] in ids:
                raise ValueError("Invalid/duplicate record ID")
            ids.add(row["id"])
            parse_time(row["created_at"])
            if type(row.get("is_demo")) is not bool:
                raise ValueError("Missing demo marker")

    def _read_document(self):
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(document, list):
                self._validate_rows(document)
                backup = self.path.with_name("votes.legacy-" + uuid4().hex + ".json")
                shutil.copy2(self.path, backup)
                migrated = self.empty_document()
                migrated["votes"] = document
                self._write(migrated)
                document = migrated
            if not isinstance(document, dict) or document.get("schema_version") != 2:
                raise ValueError("Unsupported storage schema")
            if not hmac.compare_digest(str(document.get("hmac_key_id", "")), self.key_id):
                raise APIError(500, "Secret NIM berbeda dari penyimpanan. Pulihkan secret yang sama; penanda hak pilih tidak direset.")
            self._validate_rows(document["votes"])
            if not isinstance(document["used_nims"], dict):
                raise ValueError("Invalid participation ledger")
            for digest, status in document["used_nims"].items():
                if not re.fullmatch(r"[0-9a-f]{64}", digest) or set(status) != {"voted_at"}:
                    raise ValueError("Invalid participation record")
                parse_time(status["voted_at"])
            return document
        except (OSError, ValueError, KeyError, TypeError, APIError) as exc:
            if isinstance(exc, APIError) and "Secret NIM berbeda" in exc.message:
                raise
            raise APIError(500, "File suara tidak dapat dibaca atau rusak. Data tidak direset; periksa backup dan log server.") from exc

    def _write(self, document):
        filename = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", dir=self.path.parent, prefix=".votes-", suffix=".tmp", encoding="utf-8", delete=False) as stream:
                filename = stream.name
                json.dump(document, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(filename, self.path)
        finally:
            if filename and os.path.exists(filename):
                os.unlink(filename)

    def snapshot(self):
        with self.lock:
            return self._read_document()["votes"]

    def status(self, digest):
        with self.lock:
            used = self._read_document()["used_nims"].get(digest)
            return {"has_voted": bool(used), "voted_at": used["voted_at"] if used else None, "message": THANK_YOU if used else "Hak pilih Anda masih tersedia."}

    def notify_change(self):
        # Called with the store lock held, only after a successful durable write.
        self.revision += 1
        self.changed.notify_all()

    def add(self, body, digest):
        with self.lock:
            document = self._read_document()
            used = document["used_nims"].get(digest)
            if used:
                raise APIError(409, "NIM ini sudah menggunakan hak pilih.", {"has_voted": True, "voted_at": used["voted_at"], "message": THANK_YOU})
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("An authenticated NIM digest is required")
            clean = validate_vote(body)
            row = dict(clean, id=str(uuid4()), created_at=now(), is_demo=False)
            document["votes"].append(row)
            document["used_nims"][digest] = {"voted_at": row["created_at"]}
            self._write(document)
            self.notify_change()
        return row

    def delete(self, index, expected_id=None):
        with self.lock:
            document = self._read_document()
            rows = document["votes"]
            if index < 0 or index >= len(rows):
                raise APIError(404, "Indeks catatan tidak ditemukan.")
            if expected_id is not None and rows[index]["id"] != expected_id:
                raise APIError(409, "Data telah berubah. Muat ulang daftar sebelum menghapus.")
            removed = rows.pop(index)
            self._write(document)  # The NIM ledger intentionally survives deletion.
            self.notify_change()
            return removed

    def seed_demo(self):
        with self.lock:
            document = self._read_document()
            rows = document["votes"]
            if rows or document["used_nims"]:
                raise APIError(409, "Data demonstrasi hanya dapat dimasukkan ketika penyimpanan kosong agar tidak bercampur dengan suara lain.")
            rng = random.Random(42)
            start = datetime.now(UTC) - timedelta(hours=11)
            for i in range(120):
                faculty = rng.choice(CONFIG["faculties"])
                rows.append(dict(id=str(uuid4()), option="A" if i % 10 < 6 else "B", faculty=faculty["name"], program=rng.choice(faculty["programs"]), cohort=rng.choice(CONFIG["cohorts"][-5:]), campus="Bandung", created_at=(start + timedelta(seconds=i * 330)).isoformat().replace("+00:00", "Z"), is_demo=True))
            # Fixtures have no real/student NIM and cannot reserve a student's identity.
            self._write(document)
            self.notify_change()
            return len(rows)


def percentages(rows):
    counts = Counter(row["option"] for row in rows)
    total = len(rows)
    return {"total": total, "A": counts["A"], "B": counts["B"], "percent_A": round(counts["A"] * 100 / total, 2) if total else 0, "percent_B": round(counts["B"] * 100 / total, 2) if total else 0}


def aggregate(rows):
    summary = percentages(rows)
    summary.update(leader=None if summary["A"] == summary["B"] else ("A" if summary["A"] > summary["B"] else "B"), margin=abs(summary["A"] - summary["B"]), faculties=len({r["faculty"] for r in rows}), programs=len({r["program"] for r in rows}), cohorts=len({r["cohort"] for r in rows}), demo_count=sum(r["is_demo"] for r in rows))
    groups = {}
    for field in ("faculty", "program", "cohort"):
        buckets = {}
        for row in rows:
            buckets.setdefault(row[field], []).append(row)
        groups[field] = [dict(label=key, **percentages(bucket), contribution=round(len(bucket) * 100 / len(rows), 2)) for key, bucket in sorted(buckets.items(), key=lambda item: (-len(item[1]), str(item[0])))]
    # UTC hour buckets; frontend formats their labels in Asia/Jakarta.
    times = {}
    for row in rows:
        hour = parse_time(row["created_at"]).replace(minute=0, second=0, microsecond=0)
        times[hour] = times.get(hour, 0) + 1
    trend = []
    if times:
        first, last = min(times), max(times)
        # Use daily bins for longer ranges, including zero-vote days.
        if (last - first).days > 3:
            daily = Counter()
            for row in rows:
                dt = parse_time(row["created_at"]).astimezone(timezone(timedelta(hours=7)))
                daily[dt.replace(hour=0, minute=0, second=0, microsecond=0)] += 1
            current, last_day = min(daily), max(daily)
            while current <= last_day:
                trend.append({"time": current.isoformat(), "total": daily.get(current, 0)})
                current += timedelta(days=1)
        else:
            current = first
            while current <= last:
                trend.append({"time": current.isoformat(), "total": times.get(current, 0)})
                current += timedelta(hours=1)
    return {"summary": summary, "groups": groups, "trend": trend, "trend_interval": "day" if times and (max(times) - min(times)).days > 3 else "hour"}


def public_vote(row, index=None):
    """Allowlist: never publish a person's name, profile, or individual choice."""
    public = {"id": row["id"], "alias": "Pemilih #" + row["id"].replace("-", "")[:8].upper(), "created_at": row["created_at"], "is_demo": row["is_demo"]}
    if index is not None:
        public["index"] = index
    return public


def results(rows, query):
    allowed = {"faculty", "program", "cohort", "from", "to"}
    if set(query) - allowed or any(len(v) != 1 for v in query.values()):
        raise APIError(400, "Parameter filter tidak valid atau berulang.")
    filters = {k: v[0] for k, v in query.items() if v[0]}
    for key in ("faculty", "program", "cohort"):
        if key not in filters:
            continue
        choices = {"faculty": [f["name"] for f in CONFIG["faculties"]], "program": [p for f in CONFIG["faculties"] for p in f["programs"]], "cohort": [str(c) for c in CONFIG["cohorts"]]}[key]
        if filters[key] not in choices:
            raise APIError(400, "Nilai filter tidak tersedia dalam konfigurasi.")
    lower = parse_time(filters["from"]) if "from" in filters else None
    upper = parse_time(filters["to"]) if "to" in filters else None
    if lower and upper and lower > upper:
        raise APIError(400, "Awal rentang waktu harus sebelum akhir rentang.")
    filtered = []
    for i, row in enumerate(rows):
        if row.get("campus", "Bandung") != "Bandung":
            continue
        if any(str(row[key]) != filters[key] for key in ("faculty", "program", "cohort") if key in filters):
            continue
        timestamp = parse_time(row["created_at"])
        if (lower and timestamp < lower) or (upper and timestamp > upper):
            continue
        filtered.append(dict(row, index=i))
    return dict(aggregate(filtered), votes=[public_vote(row, row["index"]) for row in filtered], filters=filters, storage_total=len(rows), historical_excluded=sum(row.get("campus", "Bandung") != "Bandung" for row in rows), generated_at=now())


class Sessions:
    def __init__(self, lifetime=8 * 3600):
        self.lifetime = lifetime
        self.entries = {}
        self.lock = threading.Lock()

    @staticmethod
    def token_hash(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def create(self, digest):
        token = secrets.token_urlsafe(32)
        entry = {"digest": digest, "csrf": secrets.token_urlsafe(24), "expires": time.time() + self.lifetime}
        with self.lock:
            self.entries = {key: value for key, value in self.entries.items() if value["expires"] > time.time()}
            self.entries[self.token_hash(token)] = entry
        return token, entry

    def get(self, token):
        with self.lock:
            entry = self.entries.get(self.token_hash(token))
            if entry and entry["expires"] <= time.time():
                self.entries.pop(self.token_hash(token), None)
                return None
            return entry

    def remove(self, token):
        with self.lock:
            self.entries.pop(self.token_hash(token), None)


class Handler(SimpleHTTPRequestHandler):
    server_version = "CampusVote/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "frontend"), **kwargs)

    def send_json(self, status, payload, cookie=None):
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(encoded)

    def read_json(self):
        if self.headers.get_content_type() != "application/json":
            raise APIError(415, "Gunakan Content-Type: application/json.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise APIError(400, "Content-Length tidak valid.")
        if length <= 0 or length > MAX_BODY:
            raise APIError(413 if length > MAX_BODY else 400, "Ukuran isi permintaan tidak valid.")
        try:
            return json.loads(self.request_body.decode("utf-8"))
        except (ValueError, UnicodeError):
            raise APIError(400, "JSON tidak valid.")

    def session_token(self):
        try:
            cookies = SimpleCookie(self.headers.get("Cookie", ""))
            return cookies[COOKIE_NAME].value if COOKIE_NAME in cookies else ""
        except CookieError:
            return ""

    def require_session(self, csrf=False):
        entry = self.server.sessions.get(self.session_token())
        if not entry:
            raise APIError(401, "Silakan login dengan NIM untuk menggunakan hak pilih.")
        if csrf and not hmac.compare_digest(self.headers.get("X-CSRF-Token", "").encode(), entry["csrf"].encode()):
            raise APIError(403, "Sesi formulir tidak valid. Muat ulang bilik suara.")
        return entry

    def require_admin(self):
        expected = self.server.admin_token
        supplied = self.headers.get("X-Admin-Token", "")
        if not expected or not hmac.compare_digest(supplied.encode(), expected.encode()):
            raise APIError(403, "Token pengelolaan diperlukan. Login pemilih tidak memberi hak admin.")

    def session_cookie(self, token, clear=False):
        cookies = SimpleCookie()
        cookies[COOKIE_NAME] = token
        item = cookies[COOKIE_NAME]
        item["httponly"] = True
        item["samesite"] = "Lax"
        item["path"] = "/"
        item["max-age"] = 0 if clear else self.server.sessions.lifetime
        if self.server.cookie_secure or self.headers.get("X-Forwarded-Proto") == "https":
            item["secure"] = True
        return item.OutputString()

    def stream_events(self):
        """Push change notifications immediately. Heartbeats carry no vote data."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        self.connection.settimeout(30)
        store = self.server.store
        seen = -1
        try:
            self.wfile.write(b"retry: 1000\n\n")
            self.wfile.flush()
            while True:
                with store.changed:
                    store.changed.wait_for(lambda: store.revision != seen, timeout=15)
                    revision = store.revision
                if revision != seen:
                    token = f"{store.instance_id}:{revision}"
                    message = f"id: {token}\nevent: votes-changed\ndata: {json.dumps({'revision': token})}\n\n"
                    self.wfile.write(message.encode("utf-8"))
                    seen = revision
                else:
                    # Connection keepalive only; never triggers a dashboard fetch.
                    self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            return

    def dispatch(self):
        path = urlsplit(self.path).path
        query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
        method = self.command
        if path == "/auth/login" and method == "POST":
            body = self.read_json()
            if not isinstance(body, dict):
                raise APIError(400, "Isi login harus berupa objek JSON.")
            nim = normalize_nim(body.get("nim"))
            password = body.get("password")
            if not isinstance(password, str) or not hmac.compare_digest(password.encode(), self.server.login_password.encode()):
                raise APIError(401, "NIM atau password tidak valid.")
            digest = nim_digest(nim, self.server.hmac_secret)
            status = self.server.store.status(digest)
            self.server.sessions.remove(self.session_token())
            token, entry = self.server.sessions.create(digest)
            self.send_json(200, dict(status, authenticated=True, csrf_token=entry["csrf"]), self.session_cookie(token))
        elif path == "/auth/me" and method == "GET":
            entry = self.require_session()
            self.send_json(200, dict(self.server.store.status(entry["digest"]), authenticated=True, csrf_token=entry["csrf"]))
        elif path == "/auth/logout" and method == "POST":
            self.require_session(csrf=True)
            self.server.sessions.remove(self.session_token())
            self.send_json(200, {"message": "Anda telah keluar."}, self.session_cookie("", clear=True))
        elif path == "/events" and method == "GET":
            self.stream_events()
        elif path == "/config" and method in ("GET", "HEAD"):
            self.send_json(200, dict(CONFIG, demo_tools=self.server.demo_tools))
        elif path == "/health" and method in ("GET", "HEAD"):
            rows = self.server.store.snapshot()
            self.send_json(200, {"status": "ok", "storage": "readable", "total": len(rows), "time": now()})
        elif path == "/votes" and method in ("GET", "HEAD"):
            self.send_json(200, results(self.server.store.snapshot(), query))
        elif path == "/votes" and method == "POST":
            entry = self.require_session(csrf=True)
            row = self.server.store.add(self.read_json(), entry["digest"])
            self.send_json(201, {"message": THANK_YOU, "has_voted": True, "voted_at": row["created_at"], "vote": public_vote(row)})
        elif path == "/votes" and method == "DELETE":
            self.require_admin()
            if set(query) - {"index", "id"} or len(query.get("index", [])) != 1 or ("id" in query and len(query["id"]) != 1):
                raise APIError(400, "Sertakan satu parameter index yang valid.")
            try:
                value = query["index"][0]
                if not value.isascii() or not value.isdecimal():
                    raise ValueError()
                index = int(value)
            except ValueError:
                raise APIError(400, "Indeks harus bilangan bulat non-negatif.")
            row = self.server.store.delete(index, query.get("id", [None])[0])
            self.send_json(200, {"message": "Catatan suara dihapus.", "deleted_id": row["id"]})
        elif path == "/demo-votes" and method == "POST" and self.server.demo_tools:
            self.require_admin()
            self.read_json()
            self.send_json(201, {"message": "120 suara demonstrasi ditambahkan.", "created": self.server.store.seed_demo()})
        elif path in ("/votes", "/config", "/health", "/events", "/auth/login", "/auth/me", "/auth/logout"):
            raise APIError(405, "Metode HTTP tidak didukung.")
        elif method in ("GET", "HEAD") and self.server.serve_frontend:
            if path.endswith("/") and path != "/":
                raise APIError(404, "Halaman tidak ditemukan.")
            # Disable directory listings and deny dotfiles even in local preview.
            if any(part.startswith(".") for part in path.split("/") if part):
                raise APIError(404, "Halaman tidak ditemukan.")
            if method == "HEAD":
                super().do_HEAD()
            else:
                super().do_GET()
        else:
            raise APIError(404, "Endpoint tidak ditemukan.")

    def list_directory(self, path):
        self.send_json(404, {"error": "Halaman tidak ditemukan."})
        return None

    def handle_api(self):
        self.connection.settimeout(15)
        try:
            # Consume bounded bodies before replying, including invalid routes/methods.
            # Closing a socket with unread POST bytes can reset it before the error arrives.
            if self.headers.get('Transfer-Encoding'):
                raise APIError(400, "Transfer-Encoding tidak didukung; sertakan Content-Length.")
            try:
                length = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                raise APIError(400, "Content-Length tidak valid.")
            if length < 0 or length > MAX_BODY:
                raise APIError(413 if length > MAX_BODY else 400, "Ukuran isi permintaan tidak valid.")
            self.request_body = self.rfile.read(length) if length else b''
            if len(self.request_body) != length:
                raise APIError(400, "Isi permintaan tidak lengkap.")
            if self.command in ("POST", "DELETE", "PUT", "PATCH"):
                origin = self.headers.get("Origin")
                if self.headers.get("Sec-Fetch-Site") == "cross-site" or (origin and urlsplit(origin).netloc != self.headers.get("Host")):
                    raise APIError(403, "Permintaan harus berasal dari aplikasi ini.")
            self.dispatch()
        except APIError as exc:
            self.send_json(exc.status, dict(error=exc.message, **exc.details))
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            self.log_error("%s: %s", type(exc).__name__, str(exc))
            self.send_json(500, {"error": "Kesalahan internal server. Periksa log; data tidak direset."})

    do_GET = do_POST = do_DELETE = do_HEAD = do_PUT = do_PATCH = handle_api

    def log_request(self, code="-", size="-"):
        # Do not log queries, request bodies, cookies, credentials, or NIM paths.
        path = urlsplit(self.path).path
        known = {"/auth/login", "/auth/me", "/auth/logout", "/votes", "/events", "/health", "/config", "/demo-votes"}
        self.log_message("%s %s %s", self.command, path if path in known else "[static]", str(code))


def make_server(host="127.0.0.1", port=8000, data_dir=None, serve_frontend=False, demo_tools=False, hmac_secret=None, login_password=None, admin_token=None, cookie_secure=None):
    key = hmac_secret if hmac_secret is not None else os.environ.get("NIM_HMAC_SECRET", "")
    store = VoteStore(data_dir or os.environ.get("DATA_DIR", str(ROOT / "data")), key)
    server = ThreadingHTTPServer((host, port), Handler)
    server.store = store
    server.hmac_secret = key
    server.login_password = login_password if login_password is not None else os.environ.get("LOGIN_PASSWORD", "12345678")
    server.admin_token = admin_token if admin_token is not None else os.environ.get("ADMIN_TOKEN", "")
    server.cookie_secure = cookie_secure if cookie_secure is not None else os.environ.get("COOKIE_SECURE", "false").lower() == "true"
    server.sessions = Sessions()
    server.serve_frontend = serve_frontend
    server.demo_tools = demo_tools
    server.daemon_threads = True
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    parser.add_argument("--data-dir", default=os.environ.get("DATA_DIR"))
    parser.add_argument("--serve-frontend", action="store_true", help="Local preview only; Docker uses Nginx")
    parser.add_argument("--demo-tools", action="store_true", default=os.environ.get("ENABLE_DEMO_TOOLS", "false").lower() == "true")
    args = parser.parse_args()
    server = make_server(args.host, args.port, args.data_dir, args.serve_frontend, args.demo_tools)
    print(f"Tel-U Campus Vote: http://{args.host}:{args.port} | storage: {server.store.path}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
