"""SQLite storage. One file, no server, every table readable in any SQLite browser."""
import json
import sqlite3
import threading
from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS departments (code TEXT PRIMARY KEY, name TEXT, name_kn TEXT, color TEXT, pilot INTEGER);
CREATE TABLE IF NOT EXISTS line_departments (id INTEGER PRIMARY KEY, dept_code TEXT, name TEXT, name_kn TEXT, n_real INTEGER);
CREATE TABLE IF NOT EXISTS services (id INTEGER PRIMARY KEY, line_id INTEGER, dept_code TEXT, name TEXT, full_name TEXT, name_kn TEXT,
  sakala INTEGER, n_real INTEGER, role TEXT, role_share REAL, role_support INTEGER);
CREATE TABLE IF NOT EXISTS grievance_types (id INTEGER PRIMARY KEY, service_id INTEGER, name TEXT, n_real INTEGER);
CREATE TABLE IF NOT EXISTS officers (id TEXT PRIMARY KEY, name TEXT, short TEXT, dept_code TEXT, level TEXT, role TEXT,
  taluk TEXT, gp TEXT, up_id TEXT, data_name TEXT, seen_in_data INTEGER, n_real INTEGER, district TEXT);
CREATE TABLE IF NOT EXISTS gazetteer (village TEXT, gp TEXT, taluk TEXT, district TEXT, n_real INTEGER, PRIMARY KEY (village, gp, taluk));
CREATE TABLE IF NOT EXISTS ipgrs_records (gid TEXT PRIMARY KEY, text_masked TEXT, dept TEXT, dept_code TEXT, line TEXT, service TEXT,
  grievance TEXT, service_type TEXT, district TEXT, taluk TEXT, gp TEXT, village TEXT, created TEXT, status TEXT, role TEXT,
  officer TEXT, officer_role TEXT, source TEXT, service_id INTEGER);
CREATE TABLE IF NOT EXISTS sakala_services (key TEXT PRIMARY KEY, name TEXT, name_kn TEXT, dept_code TEXT, days INTEGER,
  do_role TEXT, co TEXT, aa TEXT, checklist TEXT);
CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, kind TEXT, text TEXT, masked TEXT, summary TEXT, src TEXT, lang TEXT,
  district TEXT, taluk TEXT, gp TEXT, village TEXT, dept_code TEXT, line TEXT, service TEXT, service_id INTEGER, grievance TEXT,
  conf REAL, why TEXT, engine TEXT, vulnerable INTEGER, vuln_reason TEXT, owner TEXT, level TEXT, level_since TEXT, created TEXT,
  status TEXT, real INTEGER, synthetic INTEGER, route_basis TEXT, sakala TEXT, atr TEXT, atr_score INTEGER, atr_reason TEXT,
  session TEXT, linked_to TEXT);
CREATE TABLE IF NOT EXISTS case_events (id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT, t TEXT, who TEXT, what TEXT, color TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, officer_id TEXT, t TEXT, msg TEXT);
CREATE TABLE IF NOT EXISTS chat_sessions (id TEXT PRIMARY KEY, state TEXT, updated TEXT);
CREATE TABLE IF NOT EXISTS chat_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session TEXT, t TEXT, me INTEGER, payload TEXT);
CREATE TABLE IF NOT EXISTS citizen_msgs (id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT, session TEXT, t TEXT, officer_id TEXT, kind TEXT, text TEXT, delivered INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS ai_log (id INTEGER PRIMARY KEY AUTOINCREMENT, t TEXT, task TEXT, engine TEXT, ms INTEGER, ok INTEGER, detail TEXT);
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
CREATE INDEX IF NOT EXISTS ix_cases_owner ON cases(owner);
CREATE INDEX IF NOT EXISTS ix_events_case ON case_events(case_id);
CREATE INDEX IF NOT EXISTS ix_rec_taluk ON ipgrs_records(taluk);
"""

_lock = threading.RLock()
_conn = None


def conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.executescript(SCHEMA)
        migrate(_conn)
    return _conn


def migrate(c=None):
    """Columns added after the first schema (the pristine snapshot may predate them)."""
    c = c or conn()
    cols = {r[1] for r in c.execute("PRAGMA table_info(cases)").fetchall()}
    if "audit" not in cols:
        c.execute("ALTER TABLE cases ADD COLUMN audit TEXT")
    if "doc" not in cols:                                    # the document door: extraction + complainant details (JSON)
        c.execute("ALTER TABLE cases ADD COLUMN doc TEXT")
    ocols = {r[1] for r in c.execute("PRAGMA table_info(officers)").fetchall()}
    if "district" not in ocols:
        c.execute("ALTER TABLE officers ADD COLUMN district TEXT")
        c.execute("UPDATE officers SET district='Mysuru' WHERE district IS NULL")
    c.execute("CREATE INDEX IF NOT EXISTS ix_officers_taluk ON officers(taluk, role)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_cases_district ON cases(district)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_rec_district ON ipgrs_records(district)")


def q(sql, args=()):
    with _lock:
        return [dict(r) for r in conn().execute(sql, args).fetchall()]


def q1(sql, args=()):
    r = q(sql, args)
    return r[0] if r else None


def run(sql, args=()):
    with _lock:
        return conn().execute(sql, args)


def many(sql, rows):
    with _lock:
        c = conn()
        c.execute("BEGIN")
        c.executemany(sql, rows)
        c.execute("COMMIT")


def kv_get(k, default=None):
    r = q1("SELECT v FROM kv WHERE k=?", (k,))
    return json.loads(r["v"]) if r else default


def kv_set(k, v):
    run("INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, json.dumps(v)))


def reset():
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None
        for suffix in ("", "-wal", "-shm"):
            p = DB_PATH.with_name(DB_PATH.name + suffix)
            if p.exists():
                p.unlink()
