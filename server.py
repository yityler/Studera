#!/usr/bin/env python3
from http import HTTPStatus
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import base64
from email.message import EmailMessage
import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import smtplib
import sqlite3
import time

ROOT = os.path.dirname(os.path.abspath(__file__))


def configured_path(env_name, fallback):
    value = os.environ.get(env_name, "").strip()
    if not value:
        return fallback
    return os.path.abspath(os.path.expanduser(value))


DB_PATH = configured_path("STUDERA_DB_PATH", os.path.join(ROOT, "studera.db"))
INSTITUTIONS_PATH = os.path.join(ROOT, "institutions.json")
UPLOADS_DIR = configured_path("STUDERA_UPLOADS_DIR", os.path.join(ROOT, "uploads"))
SESSION_COOKIE = "studera_session"
THEME_CHOICE_COOKIE = "studera_theme_choice"
THEME_RENDER_COOKIE = "studera_theme_render"
COLOR_THEME_COOKIE = "studera_color_theme"
PUBLIC_LIGHT_HTML = {"", "index.html", "about.html", "contact.html"}
VALID_THEME_CHOICES = {"light", "dark", "system"}
VALID_RENDER_THEMES = {"light", "dark"}
VALID_COLOR_THEMES = {"studera", "github", "ayu", "monokai-pro", "min", "everforest", "amethyst", "better-solarized"}
CRITICAL_THEME_STYLE = (
    '<style id="studera-theme-critical">'
    'html[data-theme="dark"],html[data-theme="dark"] body{background:#0E1622;color:#E5EAF2;color-scheme:dark;}'
    'html[data-theme="light"],html[data-theme="light"] body{background:#F8FAFC;color:#1E293B;color-scheme:light;}'
    '</style>'
)
INSTITUTIONS_CACHE = None
RATE_LIMITS = {}
ALL_CURRICULA = ["AP Curriculum", "IB Diploma", "A-Levels", "SAT / ACT", "GCSE", "Research"]
SECTIONS_BY_CURRICULUM = {
    "AP Curriculum": [
        "AP Biology", "AP Chemistry", "AP Physics 1", "AP Physics C: Mechanics",
        "AP Calculus AB", "AP Calculus BC", "AP Statistics", "AP Computer Science A",
        "AP English Language", "AP English Literature", "AP US History", "AP World History",
    ],
    "IB Diploma": [
        "Biology HL", "Chemistry HL", "Physics HL", "Mathematics AA HL", "Mathematics AI HL",
        "English A", "History HL", "Economics HL", "Theory of Knowledge", "Extended Essay",
    ],
    "A-Levels": ["Mathematics", "Further Mathematics", "Physics", "Chemistry", "Biology", "Economics", "English Literature", "History"],
    "SAT / ACT": ["SAT Reading and Writing", "SAT Math", "ACT English", "ACT Math", "ACT Reading", "ACT Science"],
    "GCSE": ["Mathematics", "English Language", "English Literature", "Combined Science", "Biology", "Chemistry", "Physics", "History", "Geography"],
    "Research": ["Research Methods", "Literature Review", "Data Analysis", "Citation and Sources", "Abstract Writing", "Presentation"],
}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
SESSION_MAX_AGE = 7 * 24 * 60 * 60
COOKIE_SECURE = os.environ.get("STUDERA_COOKIE_SECURE", "0") == "1"
PASSWORD_MIN_LENGTH = int(os.environ.get("STUDERA_PASSWORD_MIN_LENGTH", "6"))
PASSWORD_MAX_LENGTH = 256
PASSWORD_HASH_ALGORITHM = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 600_000
LEGACY_PASSWORD_HASH_ITERATIONS = 120_000
PASSWORD_PEPPER = os.environ.get("STUDERA_PASSWORD_PEPPER", "")
SMTP_USER = os.environ.get("STUDERA_SMTP_USER", "studeraadmin@gmail.com").strip()
SMTP_HOST = os.environ.get("STUDERA_SMTP_HOST", "smtp.gmail.com" if SMTP_USER.endswith("@gmail.com") else "").strip()
SMTP_PORT = int(os.environ.get("STUDERA_SMTP_PORT", "587"))
SMTP_PASSWORD = os.environ.get("STUDERA_SMTP_PASSWORD", os.environ.get("STUDERA_GMAIL_APP_PASSWORD", ""))
SMTP_FROM = os.environ.get("STUDERA_SMTP_FROM", SMTP_USER or "no-reply@studera.local").strip()
SMTP_USE_TLS = os.environ.get("STUDERA_SMTP_TLS", "1") != "0"
EMAIL_DEV_LOG = os.environ.get("STUDERA_EMAIL_DEV_LOG", "0") == "1"
def bootstrap_site_admin_accounts():
    accounts = {}
    primary_email = os.environ.get("STUDERA_SITE_ADMIN_EMAIL", "").strip().lower()
    primary_password = os.environ.get("STUDERA_SITE_ADMIN_PASSWORD", "")
    secondary_email = os.environ.get("STUDERA_SECONDARY_SITE_ADMIN_EMAIL", "studeraadmin@gmail.com").strip().lower()
    secondary_password = os.environ.get("STUDERA_SECONDARY_SITE_ADMIN_PASSWORD", "")
    if primary_email and primary_password:
        accounts[primary_email] = {
            "name": os.environ.get("STUDERA_SITE_ADMIN_NAME", "Studera Site Admin"),
            "password": primary_password,
        }
    if secondary_email and secondary_password:
        accounts[secondary_email] = {
            "name": os.environ.get("STUDERA_SECONDARY_SITE_ADMIN_NAME", "Studera Site Admin"),
            "password": secondary_password,
        }
    return accounts
SITE_ADMIN_INSTITUTION = "Studera Platform"
SITE_ADMIN_DOMAIN = "studera.local"

CURATED_SCHOOLS = [
    {"name": "Singapore American School", "country": "Singapore", "domain": "sas.edu.sg", "curricula": ["AP Curriculum", "SAT / ACT"], "source": "College Board AP Course Ledger"},
    {"name": "United World College of South East Asia", "country": "Singapore", "domain": "uwcsea.edu.sg", "curricula": ["IB Diploma"], "source": "IB World Schools"},
    {"name": "Tanglin Trust School", "country": "Singapore", "domain": "tts.edu.sg", "curricula": ["A-Levels", "GCSE"], "source": "Cambridge/British curriculum registry"},
    {"name": "Dulwich College Singapore", "country": "Singapore", "domain": "dulwich-singapore.edu.sg", "curricula": ["IB Diploma", "GCSE"], "source": "IB World Schools"},
    {"name": "Stamford American International School", "country": "Singapore", "domain": "sais.edu.sg", "curricula": ["IB Diploma", "AP Curriculum", "SAT / ACT"], "source": "IB World Schools / AP Course Ledger"},
    {"name": "Anglo-Chinese School (Independent)", "country": "Singapore", "domain": "acsindep.moe.edu.sg", "curricula": ["IB Diploma"], "source": "IB World Schools"},
    {"name": "School of the Arts Singapore", "country": "Singapore", "domain": "sota.edu.sg", "curricula": ["IB Diploma"], "source": "IB World Schools"},
    {"name": "Hwa Chong Institution", "country": "Singapore", "domain": "hci.edu.sg", "curricula": ["A-Levels"], "source": "Singapore Ministry of Education"},
    {"name": "Raffles Institution", "country": "Singapore", "domain": "ri.edu.sg", "curricula": ["A-Levels"], "source": "Singapore Ministry of Education"},
    {"name": "Nanyang Junior College", "country": "Singapore", "domain": "nyjc.moe.edu.sg", "curricula": ["A-Levels"], "source": "Singapore Ministry of Education"},
    {"name": "International School of Geneva", "country": "Switzerland", "domain": "ecolint.ch", "curricula": ["IB Diploma"], "source": "IB World Schools"},
    {"name": "Zurich International School", "country": "Switzerland", "domain": "zis.ch", "curricula": ["IB Diploma", "AP Curriculum"], "source": "IB World Schools / AP Course Ledger"},
    {"name": "TASIS The American School in Switzerland", "country": "Switzerland", "domain": "tasis.ch", "curricula": ["AP Curriculum", "IB Diploma", "SAT / ACT"], "source": "AP Course Ledger / IB World Schools"},
    {"name": "Sevenoaks School", "country": "United Kingdom", "domain": "sevenoaksschool.org", "curricula": ["IB Diploma", "GCSE"], "source": "IB World Schools"},
    {"name": "King's College School Wimbledon", "country": "United Kingdom", "domain": "kcs.org.uk", "curricula": ["IB Diploma", "A-Levels", "GCSE"], "source": "IB World Schools"},
    {"name": "American School in London", "country": "United Kingdom", "domain": "asl.org", "curricula": ["AP Curriculum", "SAT / ACT"], "source": "College Board AP Course Ledger"},
    {"name": "Phillips Academy Andover", "country": "United States", "domain": "andover.edu", "curricula": ["AP Curriculum", "SAT / ACT"], "source": "College Board AP Course Ledger"},
    {"name": "Phillips Exeter Academy", "country": "United States", "domain": "exeter.edu", "curricula": ["AP Curriculum", "SAT / ACT"], "source": "College Board AP Course Ledger"},
    {"name": "The Lawrenceville School", "country": "United States", "domain": "lawrenceville.org", "curricula": ["AP Curriculum", "SAT / ACT"], "source": "College Board AP Course Ledger"},
    {"name": "United Nations International School", "country": "United States", "domain": "unis.org", "curricula": ["IB Diploma"], "source": "IB World Schools"},
    {"name": "Shanghai American School", "country": "China", "domain": "saschina.org", "curricula": ["AP Curriculum", "SAT / ACT"], "source": "College Board AP Course Ledger"},
    {"name": "International School of Beijing", "country": "China", "domain": "isb.cn", "curricula": ["IB Diploma", "AP Curriculum", "SAT / ACT"], "source": "IB World Schools / AP Course Ledger"},
    {"name": "Western Academy of Beijing", "country": "China", "domain": "wab.edu", "curricula": ["IB Diploma"], "source": "IB World Schools"},
    {"name": "Hong Kong International School", "country": "Hong Kong", "domain": "hkis.edu.hk", "curricula": ["AP Curriculum", "SAT / ACT"], "source": "College Board AP Course Ledger"},
    {"name": "Chinese International School", "country": "Hong Kong", "domain": "cis.edu.hk", "curricula": ["IB Diploma"], "source": "IB World Schools"},
    {"name": "Taipei American School", "country": "Taiwan", "domain": "tas.edu.tw", "curricula": ["AP Curriculum", "IB Diploma", "SAT / ACT"], "source": "AP Course Ledger / IB World Schools"},
    {"name": "Seoul Foreign School", "country": "South Korea", "domain": "seoulforeign.org", "curricula": ["IB Diploma", "AP Curriculum", "SAT / ACT"], "source": "IB World Schools / AP Course Ledger"},
    {"name": "Korea International School", "country": "South Korea", "domain": "kis.or.kr", "curricula": ["AP Curriculum", "SAT / ACT"], "source": "College Board AP Course Ledger"},
    {"name": "The American School in Japan", "country": "Japan", "domain": "asij.ac.jp", "curricula": ["AP Curriculum", "SAT / ACT"], "source": "College Board AP Course Ledger"},
    {"name": "Canadian Academy", "country": "Japan", "domain": "canacad.ac.jp", "curricula": ["IB Diploma"], "source": "IB World Schools"},
    {"name": "International School Bangkok", "country": "Thailand", "domain": "isb.ac.th", "curricula": ["IB Diploma", "AP Curriculum", "SAT / ACT"], "source": "IB World Schools / AP Course Ledger"},
    {"name": "Bangkok Patana School", "country": "Thailand", "domain": "patana.ac.th", "curricula": ["IB Diploma", "A-Levels", "GCSE"], "source": "IB World Schools / Cambridge curriculum registry"},
    {"name": "NIST International School", "country": "Thailand", "domain": "nist.ac.th", "curricula": ["IB Diploma"], "source": "IB World Schools"},
    {"name": "Jakarta Intercultural School", "country": "Indonesia", "domain": "jisedu.or.id", "curricula": ["IB Diploma", "AP Curriculum", "SAT / ACT"], "source": "IB World Schools / AP Course Ledger"},
    {"name": "British School Jakarta", "country": "Indonesia", "domain": "bsj.sch.id", "curricula": ["IB Diploma", "GCSE"], "source": "IB World Schools"},
    {"name": "International School Manila", "country": "Philippines", "domain": "ismanila.org", "curricula": ["IB Diploma", "AP Curriculum", "SAT / ACT"], "source": "IB World Schools / AP Course Ledger"},
    {"name": "Brent International School Manila", "country": "Philippines", "domain": "brent.edu.ph", "curricula": ["IB Diploma", "AP Curriculum", "SAT / ACT"], "source": "IB World Schools / AP Course Ledger"},
    {"name": "Dubai American Academy", "country": "United Arab Emirates", "domain": "gemsaa-dubai.com", "curricula": ["IB Diploma", "AP Curriculum", "SAT / ACT"], "source": "IB World Schools / AP Course Ledger"},
    {"name": "American School of Dubai", "country": "United Arab Emirates", "domain": "asdubai.org", "curricula": ["AP Curriculum", "SAT / ACT"], "source": "College Board AP Course Ledger"},
    {"name": "American School of Paris", "country": "France", "domain": "asparis.org", "curricula": ["IB Diploma", "AP Curriculum", "SAT / ACT"], "source": "IB World Schools / AP Course Ledger"},
    {"name": "Frankfurt International School", "country": "Germany", "domain": "fis.edu", "curricula": ["IB Diploma", "AP Curriculum", "SAT / ACT"], "source": "IB World Schools / AP Course Ledger"},
    {"name": "American School of Madrid", "country": "Spain", "domain": "asmadrid.org", "curricula": ["IB Diploma", "AP Curriculum", "SAT / ACT"], "source": "IB World Schools / AP Course Ledger"},
    {"name": "St. John's International School", "country": "Belgium", "domain": "stjohns.be", "curricula": ["IB Diploma", "AP Curriculum", "SAT / ACT"], "source": "IB World Schools / AP Course Ledger"},
    {"name": "American School of The Hague", "country": "Netherlands", "domain": "ash.nl", "curricula": ["IB Diploma", "AP Curriculum", "SAT / ACT"], "source": "IB World Schools / AP Course Ledger"},
]


def db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def password_mode():
    return "peppered" if PASSWORD_PEPPER else "plain"


def password_material(password, mode=None):
    text = str(password or "")
    if mode == "peppered":
        return hmac.new(PASSWORD_PEPPER.encode(), text.encode(), hashlib.sha256).digest()
    return text.encode()


def pbkdf2_digest(password, salt, iterations, mode=None):
    return hashlib.pbkdf2_hmac("sha256", password_material(password, mode), salt.encode(), iterations).hex()


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    mode = password_mode()
    digest = f"{PASSWORD_HASH_ALGORITHM}${PASSWORD_HASH_ITERATIONS}${mode}${pbkdf2_digest(password, salt, PASSWORD_HASH_ITERATIONS, mode)}"
    return salt, digest


def verify_password(password, salt, digest):
    digest = str(digest or "")
    if digest.startswith(f"{PASSWORD_HASH_ALGORITHM}$"):
        try:
            _, iterations_text, mode, expected = digest.split("$", 3)
            iterations = int(iterations_text)
        except (ValueError, TypeError):
            return False
        attempt = pbkdf2_digest(password, salt, iterations, mode)
        return hmac.compare_digest(attempt, expected)
    attempt = pbkdf2_digest(password, salt, LEGACY_PASSWORD_HASH_ITERATIONS, "plain")
    return hmac.compare_digest(attempt, digest)


def password_needs_rehash(digest):
    digest = str(digest or "")
    if not digest.startswith(f"{PASSWORD_HASH_ALGORITHM}$"):
        return True
    try:
        _, iterations_text, mode, _ = digest.split("$", 3)
        return int(iterations_text) < PASSWORD_HASH_ITERATIONS or mode != password_mode()
    except (ValueError, TypeError):
        return True


def password_policy_error(password):
    password = str(password or "")
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Password must be at least {PASSWORD_MIN_LENGTH} characters."
    if len(password) > PASSWORD_MAX_LENGTH:
        return f"Password must be {PASSWORD_MAX_LENGTH} characters or fewer."
    lowered = password.lower()
    common_fragments = ["password", "123456", "qwerty", "letmein", "adminadmin", "studeraadmin"]
    if any(fragment in lowered for fragment in common_fragments):
        return "Choose a less predictable password."
    return ""


def init_db():
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              email TEXT NOT NULL UNIQUE,
              institution TEXT NOT NULL,
              institution_country TEXT DEFAULT '',
              institution_domain TEXT DEFAULT '',
              curricula TEXT DEFAULT '',
              role TEXT NOT NULL CHECK(role IN ('student', 'teacher', 'staff')),
              profile_title TEXT DEFAULT '',
              bio TEXT DEFAULT '',
              avatar_path TEXT DEFAULT '',
              profile_visibility TEXT DEFAULT 'school',
              show_school INTEGER DEFAULT 1,
              show_email INTEGER DEFAULT 0,
              email_replies INTEGER DEFAULT 1,
              email_digest INTEGER DEFAULT 0,
              email_verified INTEGER DEFAULT 0,
              last_login_at INTEGER DEFAULT 0,
              is_school_admin INTEGER DEFAULT 0,
              is_site_admin INTEGER DEFAULT 0,
              salt TEXT NOT NULL,
              password_hash TEXT NOT NULL,
              created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS school_settings (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              institution TEXT NOT NULL,
              institution_country TEXT DEFAULT '',
              institution_domain TEXT DEFAULT '',
              curricula TEXT DEFAULT '',
              custom_curricula TEXT DEFAULT '[]',
              join_key_hash TEXT DEFAULT '',
              join_key_salt TEXT DEFAULT '',
              guidelines TEXT DEFAULT '',
              join_key_plain TEXT DEFAULT '',
              updated_at INTEGER NOT NULL,
              UNIQUE(institution, institution_domain)
            );
            CREATE TABLE IF NOT EXISTS sessions (
              token TEXT PRIMARY KEY,
              user_id INTEGER NOT NULL,
              created_at INTEGER NOT NULL,
              FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS threads (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              title TEXT NOT NULL,
              body TEXT NOT NULL,
              curriculum TEXT NOT NULL,
              section TEXT NOT NULL,
              school TEXT DEFAULT '',
              school_country TEXT DEFAULT '',
              school_domain TEXT DEFAULT '',
              image_path TEXT DEFAULT '',
              image_name TEXT DEFAULT '',
              attachment_path TEXT DEFAULT '',
              attachment_name TEXT DEFAULT '',
              attachment_type TEXT DEFAULT '',
              status TEXT DEFAULT 'open',
              answered_reply_id INTEGER DEFAULT 0,
              locked_at INTEGER DEFAULT 0,
              created_at INTEGER NOT NULL,
              FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS replies (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              thread_id INTEGER NOT NULL,
              user_id INTEGER NOT NULL,
              parent_reply_id INTEGER DEFAULT 0,
              body TEXT NOT NULL,
              image_path TEXT DEFAULT '',
              image_name TEXT DEFAULT '',
              attachment_path TEXT DEFAULT '',
              attachment_name TEXT DEFAULT '',
              attachment_type TEXT DEFAULT '',
              created_at INTEGER NOT NULL,
              FOREIGN KEY(thread_id) REFERENCES threads(id) ON DELETE CASCADE,
              FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS attachments (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              parent_type TEXT NOT NULL CHECK(parent_type IN ('thread', 'reply')),
              parent_id INTEGER NOT NULL,
              path TEXT NOT NULL,
              name TEXT NOT NULL,
              mime_type TEXT DEFAULT '',
              created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS supports (
              thread_id INTEGER NOT NULL,
              user_id INTEGER NOT NULL,
              PRIMARY KEY(thread_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS bookmarks (
              thread_id INTEGER NOT NULL,
              user_id INTEGER NOT NULL,
              PRIMARY KEY(thread_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS reply_supports (
              reply_id INTEGER NOT NULL,
              user_id INTEGER NOT NULL,
              PRIMARY KEY(reply_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS schema_migrations (
              version INTEGER PRIMARY KEY,
              name TEXT NOT NULL,
              applied_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_logs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              actor_user_id INTEGER,
              actor_email TEXT DEFAULT '',
              actor_scope TEXT DEFAULT '',
              action TEXT NOT NULL,
              target_type TEXT DEFAULT '',
              target_id TEXT DEFAULT '',
              school TEXT DEFAULT '',
              details TEXT DEFAULT '',
              created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reports (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              reporter_user_id INTEGER NOT NULL,
              target_type TEXT NOT NULL CHECK(target_type IN ('thread', 'reply')),
              target_id INTEGER NOT NULL,
              thread_id INTEGER NOT NULL,
              school TEXT DEFAULT '',
              reason TEXT DEFAULT '',
              status TEXT DEFAULT 'open',
              resolved_by INTEGER DEFAULT 0,
              resolved_at INTEGER DEFAULT 0,
              created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS auth_tokens (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              token TEXT NOT NULL UNIQUE,
              purpose TEXT NOT NULL CHECK(purpose IN ('verify_email', 'password_reset')),
              expires_at INTEGER NOT NULL,
              used_at INTEGER DEFAULT 0,
              created_at INTEGER NOT NULL,
              FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS pending_registrations (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              email TEXT NOT NULL UNIQUE,
              token TEXT NOT NULL UNIQUE,
              name TEXT NOT NULL,
              institution TEXT NOT NULL,
              institution_country TEXT DEFAULT '',
              institution_domain TEXT DEFAULT '',
              curricula TEXT DEFAULT '',
              role TEXT NOT NULL CHECK(role IN ('student', 'teacher', 'staff')),
              salt TEXT NOT NULL,
              password_hash TEXT NOT NULL,
              expires_at INTEGER NOT NULL,
              created_at INTEGER NOT NULL
            );
            """
        )
        role_schema = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'users'").fetchone()
        if role_schema and "'staff'" not in (role_schema["sql"] or ""):
            conn.executescript(
                """
                PRAGMA foreign_keys = OFF;
                CREATE TABLE users_new (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  email TEXT NOT NULL UNIQUE,
                  institution TEXT NOT NULL,
                  institution_country TEXT DEFAULT '',
                  institution_domain TEXT DEFAULT '',
                  curricula TEXT DEFAULT '',
                  role TEXT NOT NULL CHECK(role IN ('student', 'teacher', 'staff')),
                  profile_title TEXT DEFAULT '',
                  bio TEXT DEFAULT '',
                  avatar_path TEXT DEFAULT '',
                  profile_visibility TEXT DEFAULT 'school',
                  show_school INTEGER DEFAULT 1,
                  show_email INTEGER DEFAULT 0,
                  email_replies INTEGER DEFAULT 1,
                  email_digest INTEGER DEFAULT 0,
                  is_school_admin INTEGER DEFAULT 0,
                  is_site_admin INTEGER DEFAULT 0,
                  salt TEXT NOT NULL,
                  password_hash TEXT NOT NULL,
                  created_at INTEGER NOT NULL
                );
                INSERT INTO users_new (
                  id, name, email, institution, institution_country, institution_domain,
                  curricula, role, profile_title, bio, avatar_path, profile_visibility, show_school, show_email,
                  email_replies, email_digest, is_school_admin, is_site_admin, salt, password_hash, created_at
                )
                SELECT
                  id, name, email, institution,
                  COALESCE(institution_country, ''),
                  COALESCE(institution_domain, ''),
                  COALESCE(curricula, ''),
                  CASE WHEN role IN ('student', 'teacher', 'staff') THEN role ELSE 'student' END,
                  '',
                  '',
                  '',
                  'school',
                  1,
                  0,
                  1,
                  0,
                  0,
                  0,
                  salt, password_hash, created_at
                FROM users;
                DROP TABLE users;
                ALTER TABLE users_new RENAME TO users;
                PRAGMA foreign_keys = ON;
                """
            )
        for column in ("institution_country TEXT DEFAULT ''", "institution_domain TEXT DEFAULT ''", "curricula TEXT DEFAULT ''"):
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {column}")
            except sqlite3.OperationalError:
                pass
        for column in (
            "profile_title TEXT DEFAULT ''",
            "bio TEXT DEFAULT ''",
            "avatar_path TEXT DEFAULT ''",
            "profile_visibility TEXT DEFAULT 'school'",
            "show_school INTEGER DEFAULT 1",
            "show_email INTEGER DEFAULT 0",
            "email_replies INTEGER DEFAULT 1",
            "email_digest INTEGER DEFAULT 0",
            "email_verified INTEGER DEFAULT 1",
            "last_login_at INTEGER DEFAULT 0",
            "is_school_admin INTEGER DEFAULT 0",
            "is_site_admin INTEGER DEFAULT 0",
        ):
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {column}")
            except sqlite3.OperationalError:
                pass
        for table in ("threads", "replies"):
            for column in (
                "image_path TEXT DEFAULT ''",
                "image_name TEXT DEFAULT ''",
                "attachment_path TEXT DEFAULT ''",
                "attachment_name TEXT DEFAULT ''",
                "attachment_type TEXT DEFAULT ''",
            ):
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column}")
                except sqlite3.OperationalError:
                    pass
        try:
            conn.execute("ALTER TABLE replies ADD COLUMN parent_reply_id INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        for column in (
            "status TEXT DEFAULT 'open'",
            "answered_reply_id INTEGER DEFAULT 0",
            "locked_at INTEGER DEFAULT 0",
        ):
            try:
                conn.execute(f"ALTER TABLE threads ADD COLUMN {column}")
            except sqlite3.OperationalError:
                pass
        for column in (
            "school TEXT DEFAULT ''",
            "school_country TEXT DEFAULT ''",
            "school_domain TEXT DEFAULT ''",
        ):
            try:
                conn.execute(f"ALTER TABLE threads ADD COLUMN {column}")
            except sqlite3.OperationalError:
                pass
        try:
            conn.execute("ALTER TABLE school_settings ADD COLUMN join_key_plain TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE school_settings ADD COLUMN custom_curricula TEXT DEFAULT '[]'")
        except sqlite3.OperationalError:
            pass
        conn.execute("UPDATE users SET email_verified = 1 WHERE email_verified IS NULL")
        conn.execute("DELETE FROM pending_registrations WHERE expires_at < ?", (now(),))
        old_unverified = conn.execute(
            """
            SELECT *
            FROM users
            WHERE COALESCE(email_verified, 0) = 0
              AND COALESCE(is_site_admin, 0) = 0
            """
        ).fetchall()
        for row in old_unverified:
            token_row = conn.execute(
                """
                SELECT token, expires_at, created_at
                FROM auth_tokens
                WHERE user_id = ? AND purpose = 'verify_email' AND used_at = 0 AND expires_at >= ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (row["id"], now()),
            ).fetchone()
            verify_token = token_row["token"] if token_row else secrets.token_urlsafe(32)
            expires_at = token_row["expires_at"] if token_row else now() + 7 * 24 * 60 * 60
            created_at = token_row["created_at"] if token_row else now()
            conn.execute(
                """
                INSERT INTO pending_registrations (
                  email, token, name, institution, institution_country, institution_domain,
                  curricula, role, salt, password_hash, expires_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                  token = excluded.token,
                  name = excluded.name,
                  institution = excluded.institution,
                  institution_country = excluded.institution_country,
                  institution_domain = excluded.institution_domain,
                  curricula = excluded.curricula,
                  role = excluded.role,
                  salt = excluded.salt,
                  password_hash = excluded.password_hash,
                  expires_at = excluded.expires_at,
                  created_at = excluded.created_at
                """,
                (
                    row["email"],
                    verify_token,
                    row["name"],
                    row["institution"],
                    row["institution_country"] or "",
                    row["institution_domain"] or "",
                    row["curricula"] or "",
                    row["role"] if row["role"] in ("student", "teacher", "staff") else "student",
                    row["salt"],
                    row["password_hash"],
                    expires_at,
                    created_at,
                ),
            )
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (row["id"],))
            conn.execute("DELETE FROM auth_tokens WHERE user_id = ?", (row["id"],))
            conn.execute("DELETE FROM users WHERE id = ?", (row["id"],))
        conn.execute("UPDATE threads SET status = 'open' WHERE status IS NULL OR status = ''")
        conn.execute("""
            UPDATE threads
            SET school = COALESCE((SELECT institution FROM users WHERE users.id = threads.user_id), ''),
                school_country = COALESCE((SELECT institution_country FROM users WHERE users.id = threads.user_id), ''),
                school_domain = COALESCE((SELECT institution_domain FROM users WHERE users.id = threads.user_id), '')
            WHERE school IS NULL OR school = ''
        """)
        record_migration(conn, 1, "baseline community schema")
        record_migration(conn, 2, "admin audit reports auth hardening")
        rows = conn.execute("SELECT id, institution, institution_country, curricula FROM users WHERE curricula IS NULL OR curricula = ''").fetchall()
        for row in rows:
            inferred = "|".join(curricula_for_school(row["institution"], row["institution_country"] or ""))
            conn.execute("UPDATE users SET curricula = ? WHERE id = ?", (inferred, row["id"]))
        for email, account in bootstrap_site_admin_accounts().items():
            if not email:
                continue
            existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if not existing:
                salt, digest = hash_password(account["password"])
                conn.execute(
                    """
                    INSERT INTO users (
                      name, email, institution, institution_country, institution_domain,
                      curricula, role, email_verified, is_school_admin, is_site_admin, salt, password_hash, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        account["name"],
                        email,
                        SITE_ADMIN_INSTITUTION,
                        "Global",
                        SITE_ADMIN_DOMAIN,
                        "",
                        "staff",
                        1,
                        0,
                        1,
                        salt,
                        digest,
                        now(),
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE users
                    SET is_site_admin = 1,
                        is_school_admin = 0,
                        email_verified = 1,
                        institution = ?,
                        institution_country = ?,
                        institution_domain = ?,
                        curricula = '',
                        role = 'staff'
                    WHERE email = ?
                    """,
                    (SITE_ADMIN_INSTITUTION, "Global", SITE_ADMIN_DOMAIN, email),
                )


def load_institutions():
    global INSTITUTIONS_CACHE
    if INSTITUTIONS_CACHE is not None:
        return INSTITUTIONS_CACHE
    try:
        with open(INSTITUTIONS_PATH, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except FileNotFoundError:
        raw = []
    institutions = list(CURATED_SCHOOLS)
    seen = set()
    for item in institutions:
        seen.add((item["name"].lower(), item["country"].lower()))
    for item in raw:
        name = item.get("name", "").strip()
        country = item.get("country", "").strip()
        domains = item.get("domains") or []
        if not name:
            continue
        key = (name.lower(), country.lower())
        if key in seen:
            continue
        seen.add(key)
        institutions.append({
            "name": name,
            "country": country,
            "domain": domains[0] if domains else "",
            "curricula": infer_curricula(name, country),
            "source": "University domains registry",
        })
    INSTITUTIONS_CACHE = institutions
    return INSTITUTIONS_CACHE


def infer_curricula(name, country):
    text = f"{name} {country}".lower()
    curricula = []
    if any(term in text for term in ["american", "united states", "college board"]):
        curricula.extend(["AP Curriculum", "SAT / ACT"])
    if any(term in text for term in ["international baccalaureate", "world college", "uwc"]):
        curricula.append("IB Diploma")
    if any(term in text for term in ["british", "england", "united kingdom", "grammar"]):
        curricula.extend(["A-Levels", "GCSE"])
    if any(term in text for term in ["university", "institute", "polytechnic", "research"]):
        curricula.append("Research")
    return list(dict.fromkeys(curricula)) or ["Research"]


def curricula_for_school(name, country=""):
    for school in CURATED_SCHOOLS:
        if school["name"].lower() == (name or "").lower():
            return school["curricula"]
    return ALL_CURRICULA


def normalize_school_name(name):
    return " ".join(str(name or "").strip().lower().split())


def same_school(left, right):
    left_domain = str(left.get("institution_domain") or "").strip().lower()
    right_domain = str(right.get("institution_domain") or "").strip().lower()
    if left_domain and right_domain:
        return left_domain == right_domain
    return normalize_school_name(left.get("institution")) == normalize_school_name(right.get("institution"))


def school_filter(alias, user):
    domain = str(user.get("institution_domain") or "").strip()
    if domain:
        return f"LOWER({alias}.institution_domain) = LOWER(?)", [domain]
    return (
        f"LOWER({alias}.institution) = LOWER(?) AND COALESCE({alias}.institution_domain, '') = ''",
        [user.get("institution", "")],
    )


def school_admin_count(conn, user):
    clause, values = school_filter("users", user)
    return conn.execute(
        f"""
        SELECT COUNT(*) count
        FROM users
        WHERE is_site_admin = 0
          AND is_school_admin = 1
          AND {clause}
        """,
        values,
    ).fetchone()["count"]


def site_admin_count(conn):
    return conn.execute("SELECT COUNT(*) count FROM users WHERE is_site_admin = 1").fetchone()["count"]


def thread_school_filter(alias, user):
    domain = str(user.get("institution_domain") or "").strip()
    if domain:
        return f"LOWER({alias}.school_domain) = LOWER(?)", [domain]
    return (
        f"LOWER({alias}.school) = LOWER(?) AND COALESCE({alias}.school_domain, '') = ''",
        [user.get("institution", "")],
    )


def reconcile_custom_curriculum_tags(conn, user, old_custom, new_custom):
    """Carry admin renames through to existing thread curriculum and class tags."""
    if not old_custom:
        return []
    clause, values = thread_school_filter("threads", user)
    updates = []
    matched_new_indexes = set()

    for old_index, old_item in enumerate(old_custom):
        old_name = str(old_item.get("name", "")).strip()
        if not old_name:
            continue
        new_index = next(
            (
                index
                for index, item in enumerate(new_custom)
                if str(item.get("name", "")).strip().lower() == old_name.lower()
            ),
            None,
        )
        if new_index is None and old_index < len(new_custom) and old_index not in matched_new_indexes:
            new_index = old_index
        if new_index is None or new_index >= len(new_custom):
            continue
        matched_new_indexes.add(new_index)
        new_item = new_custom[new_index]
        new_name = str(new_item.get("name", "")).strip()
        if not new_name:
            continue

        old_sections = [str(section).strip() for section in (old_item.get("sections", []) or []) if str(section).strip()]
        new_sections = [str(section).strip() for section in (new_item.get("sections", []) or []) if str(section).strip()]
        matched_section_indexes = set()
        for old_section_index, old_section in enumerate(old_sections):
            if not old_section:
                continue
            new_section_index = next(
                (index for index, section in enumerate(new_sections) if section.lower() == old_section.lower()),
                None,
            )
            if new_section_index is None and old_section_index < len(new_sections) and old_section_index not in matched_section_indexes:
                new_section_index = old_section_index
            if new_section_index is None or new_section_index >= len(new_sections):
                continue
            matched_section_indexes.add(new_section_index)
            new_section = new_sections[new_section_index]
            if new_section and new_section != old_section:
                conn.execute(
                    f"""
                    UPDATE threads
                    SET section = ?
                    WHERE {clause}
                      AND LOWER(curriculum) IN (LOWER(?), LOWER(?))
                      AND LOWER(section) = LOWER(?)
                    """,
                    [new_section] + values + [old_name, new_name, old_section],
                )
                updates.append({"type": "section", "from": old_section, "to": new_section, "curriculum": old_name})

        if len(old_sections) == 1 and len(new_sections) == 1 and old_sections[0] != new_sections[0]:
            conn.execute(
                f"""
                UPDATE threads
                SET section = ?
                WHERE {clause}
                  AND LOWER(curriculum) IN (LOWER(?), LOWER(?))
                  AND LOWER(section) != LOWER(?)
                """,
                [new_sections[0]] + values + [old_name, new_name, new_sections[0]],
            )
            updates.append({
                "type": "section_fallback",
                "from": old_sections[0],
                "to": new_sections[0],
                "curriculum": old_name,
            })

        if new_name != old_name:
            conn.execute(
                f"""
                UPDATE threads
                SET curriculum = ?
                WHERE {clause}
                  AND LOWER(curriculum) = LOWER(?)
                """,
                [new_name] + values + [old_name],
            )
            updates.append({"type": "curriculum", "from": old_name, "to": new_name})
    return updates


def school_from_thread_row(row, prefix="author"):
    school = safe_row_value(row, "thread_school", safe_row_value(row, "school", ""))
    school_country = safe_row_value(row, "thread_school_country", safe_row_value(row, "school_country", ""))
    school_domain = safe_row_value(row, "thread_school_domain", safe_row_value(row, "school_domain", ""))
    if school or school_domain:
        return {
            "institution": school,
            "institution_country": school_country,
            "institution_domain": school_domain,
        }
    return {
        "institution": row[f"{prefix}_institution"],
        "institution_country": row[f"{prefix}_institution_country"],
        "institution_domain": row[f"{prefix}_institution_domain"],
    }


def school_settings_for(conn, institution, domain=""):
    row = None
    if domain:
        row = conn.execute(
            "SELECT * FROM school_settings WHERE LOWER(institution_domain) = LOWER(?)",
            (domain,),
        ).fetchone()
    if not row:
        row = conn.execute(
            "SELECT * FROM school_settings WHERE LOWER(institution) = LOWER(?) AND COALESCE(institution_domain, '') = COALESCE(?, '')",
            (institution, domain or ""),
        ).fetchone()
    return row


def pipe_list(value):
    raw = value if isinstance(value, list) else str(value or "").split("|")
    clean = []
    seen = set()
    for item in raw:
        text = str(item or "").strip()
        key = text.lower()
        if text and key not in seen:
            clean.append(text)
            seen.add(key)
    return clean


def parse_custom_curricula(value):
    if not value:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if not isinstance(value, list):
        return []
    custom = []
    seen_names = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()[:80]
        key = name.lower()
        if not name or key in seen_names or name in ALL_CURRICULA:
            continue
        sections = pipe_list(item.get("sections", []))[:80]
        if not sections:
            continue
        custom.append({"name": name, "sections": sections})
        seen_names.add(key)
    return custom


def custom_curriculum_sections(school_row, curriculum):
    if not school_row:
        return []
    for item in parse_custom_curricula(safe_row_value(school_row, "custom_curricula", "[]")):
        if item["name"] == curriculum:
            return item["sections"]
    return []


def public_school_settings(row, fallback=None):
    fallback = fallback or {}
    custom = parse_custom_curricula(safe_row_value(row, "custom_curricula", "[]") if row else fallback.get("custom_curricula", []))
    curricula = pipe_list(row["curricula"] if row else fallback.get("curricula", "") or "")
    for item in custom:
        if item["name"] not in curricula:
            curricula.append(item["name"])
    join_key_plain = safe_row_value(row, "join_key_plain") if row else ""
    return {
        "institution": row["institution"] if row else fallback.get("institution", ""),
        "institution_country": row["institution_country"] if row else fallback.get("institution_country", ""),
        "institution_domain": row["institution_domain"] if row else fallback.get("institution_domain", ""),
        "curricula": curricula or ALL_CURRICULA,
        "custom_curricula": custom,
        "has_join_key": bool(row and row["join_key_hash"]),
        "join_key": join_key_plain,
        "guidelines": row["guidelines"] if row else "",
    }


def apply_school_settings_to_institution(conn, school):
    settings = school_settings_for(conn, school.get("name", ""), school.get("domain", ""))
    if not settings:
        return school
    updated = dict(school)
    updated["curricula"] = public_school_settings(settings, school)["curricula"] or school.get("curricula", ALL_CURRICULA)
    updated["source"] = "Studera school admin settings"
    return updated


def hash_join_key(join_key):
    return hash_password(str(join_key or ""))


def make_join_key():
    return f"studera-{secrets.token_urlsafe(9).replace('_', '').replace('-', '')[:10].lower()}"


def create_auth_token(conn, user_id, purpose, ttl_seconds):
    token = secrets.token_urlsafe(32)
    conn.execute(
        """
        INSERT INTO auth_tokens (user_id, token, purpose, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, token, purpose, now() + ttl_seconds, now()),
    )
    return token


def send_email(to_email, subject, body):
    if not SMTP_HOST:
        if EMAIL_DEV_LOG:
            print(f"[Studera email dev] To: {to_email}\nSubject: {subject}\n\n{body}\n", flush=True)
            return True
        raise RuntimeError("Email is not configured. Set STUDERA_SMTP_HOST, STUDERA_SMTP_USER, and STUDERA_SMTP_PASSWORD.")
    if SMTP_USER and not SMTP_PASSWORD:
        if EMAIL_DEV_LOG:
            print(f"[Studera email dev] To: {to_email}\nSubject: {subject}\n\n{body}\n", flush=True)
            return True
        raise RuntimeError("Email is not configured. Set STUDERA_SMTP_PASSWORD to the Gmail app password for studeraadmin@gmail.com.")
    message = EmailMessage()
    message["From"] = SMTP_FROM
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=12) as smtp:
        if SMTP_USE_TLS:
            smtp.starttls()
        if SMTP_USER:
            smtp.login(SMTP_USER, SMTP_PASSWORD)
        refused = smtp.send_message(message)
        if refused:
            refused_list = ", ".join(refused.keys())
            raise RuntimeError(f"Email provider refused recipient: {refused_list}")
    print(f"[Studera email] Sent '{subject}' to {to_email}", flush=True)
    return True


def send_verification_email(user_row, token):
    name = safe_row_value(user_row, "name", "Studera member")
    email = safe_row_value(user_row, "email", "")
    body = (
        f"Hello {name},\n\n"
        "Enter this Studera verification code to confirm your institutional email:\n\n"
        f"{token}\n\n"
        "This code expires in 7 days. If you did not create a Studera account, you can ignore this email.\n\n"
        "Studera Academic Press"
    )
    try:
        return send_email(email, "Verify your Studera email", body)
    except Exception as exc:
        print(f"[Studera email error] Could not send verification email to {email}: {exc}", flush=True)
        return False


def send_password_reset_email(user_row, token):
    name = safe_row_value(user_row, "name", "Studera member")
    email = safe_row_value(user_row, "email", "")
    body = (
        f"Hello {name},\n\n"
        "Enter this Studera password reset code to choose a new password:\n\n"
        f"{token}\n\n"
        "This code expires in 1 hour. If you did not request a password reset, you can ignore this email.\n\n"
        "Studera Academic Press"
    )
    try:
        return send_email(email, "Reset your Studera password", body)
    except Exception as exc:
        print(f"[Studera email error] Could not send password reset email to {email}: {exc}", flush=True)
        return False


def verification_delivery_error():
    if SMTP_USER.endswith("@gmail.com") and not SMTP_PASSWORD:
        return (
            "Email sending is not configured yet. Create a Gmail app password for "
            f"{SMTP_USER}, then restart the server with STUDERA_SMTP_PASSWORD set."
        )
    return "Verification email could not be sent. Check the Studera SMTP settings and try again."


def record_migration(conn, version, name):
    conn.execute(
        """
        INSERT OR IGNORE INTO schema_migrations (version, name, applied_at)
        VALUES (?, ?, ?)
        """,
        (version, name, now()),
    )


def actor_scope(user):
    if not user:
        return "system"
    if user.get("is_site_admin"):
        return "site_admin"
    if user.get("is_school_admin"):
        return "school_admin"
    return "member"


def log_audit(conn, actor, action, target_type="", target_id="", school="", details=None):
    details_text = json.dumps(details or {}, sort_keys=True)
    conn.execute(
        """
        INSERT INTO audit_logs (
          actor_user_id, actor_email, actor_scope, action, target_type, target_id, school, details, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            actor.get("id") if actor else 0,
            actor.get("email", "") if actor else "",
            actor_scope(actor),
            action,
            target_type,
            str(target_id or ""),
            school or (actor.get("institution", "") if actor else ""),
            details_text,
            now(),
        ),
    )


def delete_user_account_records(conn, target, actor=None, audit_action="delete_account"):
    target_user = public_user(target)
    user_id = target["id"]
    owned_thread_ids = [row["id"] for row in conn.execute("SELECT id FROM threads WHERE user_id = ?", (user_id,)).fetchall()]
    if owned_thread_ids:
        placeholders = ",".join("?" for _ in owned_thread_ids)
        reply_ids = [row["id"] for row in conn.execute(
            f"SELECT id FROM replies WHERE user_id = ? OR thread_id IN ({placeholders})",
            [user_id] + owned_thread_ids,
        ).fetchall()]
    else:
        reply_ids = [row["id"] for row in conn.execute("SELECT id FROM replies WHERE user_id = ?", (user_id,)).fetchall()]
    if owned_thread_ids:
        placeholders = ",".join("?" for _ in owned_thread_ids)
        conn.execute(f"DELETE FROM attachments WHERE parent_type = 'thread' AND parent_id IN ({placeholders})", owned_thread_ids)
        conn.execute(f"DELETE FROM supports WHERE thread_id IN ({placeholders}) OR user_id = ?", owned_thread_ids + [user_id])
        conn.execute(f"DELETE FROM bookmarks WHERE thread_id IN ({placeholders}) OR user_id = ?", owned_thread_ids + [user_id])
        conn.execute(f"DELETE FROM reports WHERE thread_id IN ({placeholders}) OR reporter_user_id = ? OR resolved_by = ?", owned_thread_ids + [user_id, user_id])
    else:
        conn.execute("DELETE FROM supports WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM bookmarks WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM reports WHERE reporter_user_id = ? OR resolved_by = ?", (user_id, user_id))
    if reply_ids:
        placeholders = ",".join("?" for _ in reply_ids)
        conn.execute(f"DELETE FROM attachments WHERE parent_type = 'reply' AND parent_id IN ({placeholders})", reply_ids)
        conn.execute(f"DELETE FROM reply_supports WHERE reply_id IN ({placeholders}) OR user_id = ?", reply_ids + [user_id])
        conn.execute(f"DELETE FROM reports WHERE target_type = 'reply' AND target_id IN ({placeholders})", reply_ids)
    else:
        conn.execute("DELETE FROM reply_supports WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM replies WHERE user_id = ?", (user_id,))
    if owned_thread_ids:
        placeholders = ",".join("?" for _ in owned_thread_ids)
        conn.execute(f"DELETE FROM replies WHERE thread_id IN ({placeholders})", owned_thread_ids)
        conn.execute(f"DELETE FROM threads WHERE id IN ({placeholders})", owned_thread_ids)
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM auth_tokens WHERE user_id = ?", (user_id,))
    log_audit(conn, actor or target_user, audit_action, "user", user_id, target_user.get("institution", ""), {"email": target_user.get("email", "")})
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    delete_upload(target_user.get("avatar_path", ""))


def verify_join_key(join_key, settings_row):
    if not settings_row or not settings_row["join_key_hash"]:
        return True
    if not join_key:
        return False
    return verify_password(str(join_key), settings_row["join_key_salt"], settings_row["join_key_hash"])


def fallback_school(raw_query):
    name = " ".join((raw_query or "").split())
    if not name:
        return None
    return {
        "name": name,
        "country": "Unverified school",
        "domain": "",
        "curricula": ALL_CURRICULA,
        "source": "Manual school entry - all curricula enabled",
    }


def now():
    return int(time.time())


def rate_limited(key, limit=8, window=60):
    current = now()
    hits = [ts for ts in RATE_LIMITS.get(key, []) if current - ts < window]
    if len(hits) >= limit:
        RATE_LIMITS[key] = hits
        return True
    hits.append(current)
    RATE_LIMITS[key] = hits
    return False


def safe_row_value(row, key, default=""):
    try:
        value = row[key]
    except (IndexError, KeyError):
        return default
    return value if value is not None else default


def safe_extension(original_name, mime):
    _, ext = os.path.splitext(os.path.basename(str(original_name or "")))
    ext = re.sub(r"[^a-zA-Z0-9.]", "", ext.lower())[:16]
    if ext:
        return ext
    guessed = mimetypes.guess_extension(mime or "")
    return guessed if guessed and re.match(r"^\.[a-zA-Z0-9]+$", guessed) else ".bin"


def save_upload(data_url, original_name=""):
    if not data_url:
        return "", "", ""
    match = re.match(r"^data:([^;,]+)?(?:;[^,]*)?;base64,(.+)$", str(data_url), re.DOTALL)
    if not match:
        raise ValueError("Attachment could not be read.")
    mime, encoded = match.groups()
    mime = mime or "application/octet-stream"
    try:
        blob = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError("Attachment could not be read.") from exc
    if len(blob) > MAX_UPLOAD_BYTES:
        raise ValueError("Attachments must be 15 MB or smaller.")
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    filename = f"{secrets.token_urlsafe(18)}{safe_extension(original_name, mime)}"
    path = os.path.join(UPLOADS_DIR, filename)
    with open(path, "wb") as handle:
        handle.write(blob)
    clean_name = os.path.basename(str(original_name or "Attachment")).strip()[:160]
    return f"uploads/{filename}", clean_name or "Attachment", mime


def save_avatar(data_url, original_name=""):
    if not data_url:
        return ""
    path, _name, mime = save_upload(data_url, original_name or "profile-picture")
    allowed = {"image/png", "image/jpeg", "image/webp", "image/gif"}
    if str(mime or "").lower() not in allowed:
        delete_upload(path)
        raise ValueError("Profile picture must be a PNG, JPEG, WebP, or GIF image.")
    return path


def upload_disk_path(relative_path):
    normalized = os.path.normpath(str(relative_path or "").lstrip("/"))
    if normalized == "uploads":
        return UPLOADS_DIR
    if normalized.startswith("uploads/"):
        filename = normalized[len("uploads/"):]
        if filename and not filename.startswith("../"):
            return os.path.join(UPLOADS_DIR, filename)
    return None


def upload_payloads(data):
    files = data.get("files")
    if not isinstance(files, list):
        files = []
    payloads = []
    for item in files[:10]:
        if not isinstance(item, dict):
            continue
        payloads.append((item.get("file_data"), item.get("file_name", "")))
    if data.get("file_data") or data.get("image_data"):
        payloads.insert(0, (
            data.get("file_data") or data.get("image_data"),
            data.get("file_name") or data.get("image_name", ""),
        ))
    return payloads[:10]


def save_uploads(data):
    saved = []
    try:
        for file_data, file_name in upload_payloads(data):
            path, name, mime_type = save_upload(file_data, file_name)
            if path:
                saved.append({"path": path, "name": name, "mime_type": mime_type})
    except ValueError:
        for item in saved:
            delete_upload(item["path"])
        raise
    return saved


def insert_attachments(conn, parent_type, parent_id, uploads):
    for upload in uploads:
        conn.execute(
            """
            INSERT INTO attachments (parent_type, parent_id, path, name, mime_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (parent_type, parent_id, upload["path"], upload["name"], upload["mime_type"], now()),
        )


def attachment_json(row):
    return {
        "path": row["path"],
        "name": row["name"],
        "type": row["mime_type"] or "application/octet-stream",
    }


def audit_json(row):
    try:
        details = json.loads(row["details"] or "{}")
    except json.JSONDecodeError:
        details = {}
    return {
        "id": row["id"],
        "actor_email": row["actor_email"],
        "actor_scope": row["actor_scope"],
        "action": row["action"],
        "target_type": row["target_type"],
        "target_id": row["target_id"],
        "school": row["school"],
        "details": details,
        "created_at": fmt(row["created_at"]),
    }


def legacy_attachment_from_row(row):
    path = safe_row_value(row, "attachment_path") or safe_row_value(row, "image_path")
    if not path:
        return None
    name = safe_row_value(row, "attachment_name") or safe_row_value(row, "image_name") or "Attachment"
    mime_type = safe_row_value(row, "attachment_type")
    if not mime_type:
        mime_type = "image/*" if safe_row_value(row, "image_path") else "application/octet-stream"
    return {"path": path, "name": name, "type": mime_type}


def merge_attachments(row, attachments=None):
    merged = []
    seen = set()
    legacy = legacy_attachment_from_row(row)
    if legacy:
        merged.append(legacy)
        seen.add(legacy["path"])
    for item in attachments or []:
        clean = attachment_json(item)
        if clean["path"] in seen:
            continue
        merged.append(clean)
        seen.add(clean["path"])
    return merged


def delete_upload(relative_path):
    if not relative_path:
        return
    path = upload_disk_path(relative_path)
    if not path:
        return
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


def public_user(row):
    if not row:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "institution": row["institution"],
        "institution_country": row["institution_country"],
        "institution_domain": row["institution_domain"],
        "curricula": [item for item in (row["curricula"] or "").split("|") if item],
        "role": row["role"],
        "profile_title": row["profile_title"] or "",
        "bio": row["bio"] or "",
        "avatar_path": safe_row_value(row, "avatar_path", ""),
        "profile_visibility": row["profile_visibility"] or "school",
        "show_school": bool(row["show_school"]),
        "show_email": bool(row["show_email"]),
        "email_replies": bool(row["email_replies"]),
        "email_digest": bool(row["email_digest"]),
        "email_verified": bool(safe_row_value(row, "email_verified", 1)),
        "is_school_admin": bool(safe_row_value(row, "is_school_admin", 0)),
        "is_site_admin": bool(safe_row_value(row, "is_site_admin", 0)),
    }


def fmt(ts):
    return time.strftime("%b %d, %Y %H:%M", time.localtime(ts))


def session_cookie(value="", max_age=SESSION_MAX_AGE):
    parts = [f"{SESSION_COOKIE}={value}", "Path=/", f"Max-Age={max_age}", "HttpOnly", "SameSite=Strict"]
    if COOKIE_SECURE:
        parts.append("Secure")
    return "; ".join(parts)


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        parsed = urlparse(path)
        clean = parsed.path.lstrip("/") or "index.html"
        upload_path = upload_disk_path(clean)
        if upload_path:
            return upload_path
        return os.path.join(ROOT, clean)

    def send_json(self, data, status=HTTPStatus.OK, cookie=None):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def send_icon_file(self, relative_path, content_type="image/png"):
        path = os.path.join(ROOT, relative_path)
        if not os.path.isfile(path):
            return False
        try:
            with open(path, "rb") as handle:
                body = handle.read()
        except OSError:
            return False
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return True

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        super().end_headers()

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode())

    def cookie_value(self, name):
        cookie = self.headers.get("Cookie", "")
        for part in cookie.split(";"):
            key, _, value = part.strip().partition("=")
            if key == name:
                return value
        return None

    def cookie_token(self):
        return self.cookie_value(SESSION_COOKIE)

    def theme_for_html(self, parsed):
        filename = os.path.basename(parsed.path) or "index.html"
        color_theme = self.cookie_value(COLOR_THEME_COOKIE) or "studera"
        if color_theme not in VALID_COLOR_THEMES:
            color_theme = "studera"
        if filename in PUBLIC_LIGHT_HTML:
            return "light", "light", color_theme
        choice = self.cookie_value(THEME_CHOICE_COOKIE) or "dark"
        if choice not in VALID_THEME_CHOICES:
            choice = "dark"
        render = self.cookie_value(THEME_RENDER_COOKIE)
        if render not in VALID_RENDER_THEMES:
            render = "light" if choice == "light" else "dark"
        return choice, render, color_theme

    def inject_theme_into_html(self, html, parsed):
        choice, render, color_theme = self.theme_for_html(parsed)
        if "<html" in html:
            html = re.sub(
                r"<html[^>]*>",
                (
                    f'<html lang="en" data-theme-choice="{choice}" data-theme="{render}" data-color-theme="{color_theme}" '
                    f'style="background: {"#0E1622" if render == "dark" else "#F8FAFC"}; '
                    f'color: {"#E5EAF2" if render == "dark" else "#1E293B"}; color-scheme: {render}">'
                ),
                html,
                count=1,
            )
        if "studera-theme-critical" not in html:
            html = html.replace("<head>", f"<head>\n    {CRITICAL_THEME_STYLE}", 1)
        return html

    def send_themed_html(self, parsed):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            path = os.path.join(path, "index.html")
        if not path.endswith(".html") or not os.path.isfile(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as handle:
                html = handle.read()
        except OSError:
            return False
        body = self.inject_theme_into_html(html, parsed).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return True

    def current_user(self):
        token = self.cookie_token()
        if not token:
            return None
        with db() as conn:
            row = conn.execute(
                """
                SELECT users.*, sessions.created_at session_created_at FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token = ?
                """,
                (token,),
            ).fetchone()
            if row and row["session_created_at"] + SESSION_MAX_AGE < now():
                conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
                return None
            if row and not safe_row_value(row, "email_verified", 1):
                conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
                return None
        return public_user(row)

    def require_user(self):
        user = self.current_user()
        if not user:
            self.send_json({"error": "Sign in required."}, HTTPStatus.UNAUTHORIZED)
            return None
        return user

    def require_forum_user(self):
        user = self.require_user()
        if not user:
            return None
        if user.get("is_site_admin"):
            self.send_json({"error": "Site admins cannot access school forums."}, HTTPStatus.FORBIDDEN)
            return None
        if not user.get("email_verified"):
            self.send_json({"error": "Verify your institutional email before posting or interacting."}, HTTPStatus.FORBIDDEN)
            return None
        return user

    def require_school_admin(self):
        user = self.require_user()
        if not user:
            return None
        if user.get("is_site_admin"):
            self.send_json({"error": "Site admins use the global console, not school forums."}, HTTPStatus.FORBIDDEN)
            return None
        if not user.get("is_school_admin"):
            self.send_json({"error": "School admin access required."}, HTTPStatus.FORBIDDEN)
            return None
        return user

    def require_site_admin(self):
        user = self.require_user()
        if not user:
            return None
        if not user.get("is_site_admin"):
            self.send_json({"error": "Site admin access required."}, HTTPStatus.FORBIDDEN)
            return None
        return user

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/favicon.ico":
            return self.send_icon_file("assets/studera-wordmark-favicon-32.png")
        if parsed.path == "/apple-touch-icon.png":
            return self.send_icon_file("assets/studera-wordmark-apple-touch-icon.png")
        if parsed.path == "/api/session":
            user = self.current_user()
            school = None
            if user and not user.get("is_site_admin"):
                with db() as conn:
                    settings = school_settings_for(conn, user.get("institution", ""), user.get("institution_domain", ""))
                    school = public_school_settings(settings, user)
            return self.send_json({"user": user, "school": school})
        if parsed.path == "/api/threads":
            return self.list_threads(parsed)
        if parsed.path == "/api/institutions":
            return self.search_institutions(parsed)
        if parsed.path == "/api/admin/school":
            return self.admin_school()
        if parsed.path == "/api/admin/reports":
            return self.admin_reports()
        if parsed.path == "/api/admin/audit":
            return self.admin_audit()
        if parsed.path == "/api/admin/export":
            return self.admin_export()
        if parsed.path == "/api/site-admin":
            return self.site_admin_overview()
        if parsed.path == "/api/site-admin/audit":
            return self.site_admin_audit()
        if parsed.path == "/api/site-admin/backup":
            return self.site_admin_backup()
        if parsed.path.startswith("/api/users/"):
            parts = parsed.path.strip("/").split("/")
            if len(parts) == 3 and parts[2].isdigit():
                return self.user_profile(int(parts[2]))
        if parsed.path.startswith("/api/threads/"):
            parts = parsed.path.strip("/").split("/")
            if len(parts) == 3 and parts[2].isdigit():
                return self.get_thread(int(parts[2]))
        if parsed.path.startswith("/api/"):
            return self.send_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)
        if self.send_themed_html(parsed):
            return
        return super().do_GET()

    def search_institutions(self, parsed):
        raw_query = parse_qs(parsed.query).get("q", [""])[0].strip()
        query = raw_query.lower()
        if len(query) < 1:
            return self.send_json({"institutions": []})
        terms = [term for term in query.split() if term]
        matches = []
        seen = set()
        with db() as conn:
            rows = conn.execute(
                "SELECT DISTINCT institution, curricula FROM users WHERE is_site_admin = 0 AND LOWER(institution) LIKE ? ORDER BY institution LIMIT 8",
                (f"%{query}%",),
            ).fetchall()
            for row in rows:
                name = row["institution"]
                seen.add(name.lower())
                curated = next((school for school in CURATED_SCHOOLS if school["name"].lower() == name.lower()), None)
                if curated:
                    matches.append(apply_school_settings_to_institution(conn, curated))
                else:
                    curricula = [item for item in (row["curricula"] or "").split("|") if item] or ["Research"]
                    school = {"name": name, "country": "Studera registry", "domain": "", "curricula": curricula, "source": "Registered Studera school"}
                    matches.append(apply_school_settings_to_institution(conn, school))
            for school in load_institutions():
                if school["name"].lower() in seen:
                    continue
                haystack = f"{school['name']} {school['country']} {school['domain']} {school.get('source', '')} {' '.join(school.get('curricula', []))}".lower()
                if all(term in haystack for term in terms):
                    matches.append(apply_school_settings_to_institution(conn, school))
                    seen.add(school["name"].lower())
                if len(matches) >= 12:
                    break
        exact_match = any(school["name"].lower() == query for school in matches)
        if not exact_match and len(raw_query) >= 3:
            fallback = fallback_school(raw_query)
            if fallback and fallback["name"].lower() not in seen:
                matches.append(fallback)
        return self.send_json({"institutions": matches})

    def user_profile(self, user_id):
        viewer = self.current_user()
        if viewer and viewer.get("is_site_admin"):
            return self.send_json({"error": "Site admins cannot access school profiles."}, HTTPStatus.FORBIDDEN)
        with db() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ? AND is_site_admin = 0", (user_id,)).fetchone()
            if not row:
                return self.send_json({"error": "Profile not found."}, HTTPStatus.NOT_FOUND)
            profile = public_user(row)
            visibility = profile.get("profile_visibility", "school")
            same = viewer and same_school(viewer, profile)
            if visibility == "private" and (not viewer or viewer["id"] != user_id):
                return self.send_json({"error": "Profile is private."}, HTTPStatus.FORBIDDEN)
            if visibility == "school" and not same and (not viewer or viewer["id"] != user_id):
                return self.send_json({"error": "Profile is available to the school community only."}, HTTPStatus.FORBIDDEN)
            threads = conn.execute(
                """
                SELECT threads.*, users.name author_name, users.role author_role,
                  users.avatar_path author_avatar_path,
                  users.institution author_institution,
                  users.institution_country author_institution_country,
                  users.institution_domain author_institution_domain,
                  (SELECT COUNT(*) FROM replies WHERE replies.thread_id = threads.id) replies,
                  (SELECT COUNT(*) FROM supports WHERE supports.thread_id = threads.id) supports,
                  0 supported,
                  0 bookmarked
                FROM threads
                JOIN users ON users.id = threads.user_id
                WHERE threads.user_id = ?
                ORDER BY threads.created_at DESC
                LIMIT 20
                """,
                (user_id,),
            ).fetchall()
            replies = conn.execute(
                """
                SELECT replies.id, replies.thread_id, replies.body, replies.created_at, threads.title thread_title
                FROM replies
                JOIN threads ON threads.id = replies.thread_id
                WHERE replies.user_id = ?
                ORDER BY replies.created_at DESC
                LIMIT 20
                """,
                (user_id,),
            ).fetchall()
        if not profile.get("show_email") and (not viewer or not (viewer.get("is_school_admin") and same)):
            profile["email"] = ""
        if not profile.get("show_school") and (not viewer or viewer["id"] != user_id):
            profile["institution"] = ""
            profile["institution_domain"] = ""
        return self.send_json({
            "profile": profile,
            "threads": [self.thread_json(thread) for thread in threads],
            "replies": [
                {
                    "id": row["id"],
                    "thread_id": row["thread_id"],
                    "thread_title": row["thread_title"],
                    "body": row["body"],
                    "created_at": fmt(row["created_at"]),
                }
                for row in replies
            ],
        })

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/auth/register":
            return self.register()
        if parsed.path == "/api/auth/login":
            return self.login()
        if parsed.path == "/api/auth/logout":
            return self.logout()
        if parsed.path == "/api/auth/request-verification":
            return self.request_verification()
        if parsed.path == "/api/auth/resend-verification":
            return self.resend_verification()
        if parsed.path == "/api/auth/verify":
            return self.verify_email()
        if parsed.path == "/api/auth/request-password-reset":
            return self.request_password_reset()
        if parsed.path == "/api/auth/reset-password":
            return self.reset_password()
        if parsed.path == "/api/settings":
            return self.update_settings()
        if parsed.path == "/api/settings/school":
            return self.change_school()
        if parsed.path == "/api/settings/delete-account":
            return self.delete_account()
        if parsed.path == "/api/admin/school":
            return self.update_admin_school()
        if parsed.path == "/api/admin/grant":
            return self.grant_admin()
        if parsed.path == "/api/admin/revoke":
            return self.revoke_admin()
        if parsed.path == "/api/admin/members/name":
            return self.rename_school_member()
        if parsed.path == "/api/admin/members/delete":
            return self.delete_school_member()
        if parsed.path == "/api/admin/reports/status":
            return self.admin_update_report()
        if parsed.path == "/api/reports":
            return self.create_report()
        if parsed.path == "/api/site-admin/schools":
            return self.site_admin_save_school()
        if parsed.path == "/api/site-admin/school-admins":
            return self.site_admin_grant_school_admin()
        if parsed.path == "/api/site-admin/school-admins/revoke":
            return self.site_admin_revoke_school_admin()
        if parsed.path == "/api/site-admin/site-admins":
            return self.site_admin_grant_site_admin()
        if parsed.path == "/api/site-admin/site-admins/revoke":
            return self.site_admin_revoke_site_admin()
        if parsed.path == "/api/threads":
            return self.create_thread()
        parts = parsed.path.strip("/").split("/")
        if len(parts) == 4 and parts[:2] == ["api", "threads"] and parts[2].isdigit():
            if parts[3] == "support":
                return self.toggle_join("supports", int(parts[2]))
            if parts[3] == "bookmark":
                return self.toggle_join("bookmarks", int(parts[2]))
            if parts[3] == "replies":
                return self.create_reply(int(parts[2]))
            if parts[3] == "status":
                return self.update_thread_status(int(parts[2]))
        if len(parts) == 4 and parts[:2] == ["api", "replies"] and parts[2].isdigit() and parts[3] == "support":
            return self.toggle_reply_support(int(parts[2]))
        return self.send_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)

    def do_DELETE(self):
        parts = urlparse(self.path).path.strip("/").split("/")
        if len(parts) == 3 and parts[:2] == ["api", "threads"] and parts[2].isdigit():
            return self.delete_thread(int(parts[2]))
        if len(parts) == 3 and parts[:2] == ["api", "replies"] and parts[2].isdigit():
            return self.delete_reply(int(parts[2]))
        return self.send_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)

    def do_PATCH(self):
        parts = urlparse(self.path).path.strip("/").split("/")
        if len(parts) == 3 and parts[:2] == ["api", "threads"] and parts[2].isdigit():
            return self.edit_thread(int(parts[2]))
        if len(parts) == 3 and parts[:2] == ["api", "replies"] and parts[2].isdigit():
            return self.edit_reply(int(parts[2]))
        return self.send_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)

    def register(self):
        data = self.read_json()
        required = ["name", "email", "institution", "role", "password"]
        if any(not str(data.get(key, "")).strip() for key in required):
            return self.send_json({"error": "All profile fields are required."}, HTTPStatus.BAD_REQUEST)
        password_error = password_policy_error(data["password"])
        if password_error:
            return self.send_json({"error": password_error}, HTTPStatus.BAD_REQUEST)
        email = str(data.get("email", "")).strip().lower()
        role = data["role"] if data["role"] in ("student", "teacher", "staff") else "student"
        curricula = str(data.get("curricula", "")).strip()
        if not curricula:
            return self.send_json({"error": "Choose your school from the suggestions so Studera can assign its curriculum."}, HTTPStatus.BAD_REQUEST)
        salt, digest = hash_password(data["password"])
        with db() as conn:
            existing = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if existing and safe_row_value(existing, "email_verified", 1):
                return self.send_json({"error": "That email is already registered. Sign in instead."}, HTTPStatus.CONFLICT)
            if existing:
                delete_user_account_records(conn, existing, audit_action="delete_unverified_registration")
            school = school_settings_for(conn, data["institution"].strip(), str(data.get("institution_domain", "")).strip())
            if school:
                curricula = school["curricula"] or curricula
            if school and not verify_join_key(data.get("join_key", ""), school):
                return self.send_json({"error": "That school requires a valid join key."}, HTTPStatus.FORBIDDEN)
            verify_token = secrets.token_urlsafe(32)
            pending = {
                "name": data["name"].strip(),
                "email": email,
            }
            conn.execute(
                """
                INSERT INTO pending_registrations (
                  email, token, name, institution, institution_country, institution_domain,
                  curricula, role, salt, password_hash, expires_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                  token = excluded.token,
                  name = excluded.name,
                  institution = excluded.institution,
                  institution_country = excluded.institution_country,
                  institution_domain = excluded.institution_domain,
                  curricula = excluded.curricula,
                  role = excluded.role,
                  salt = excluded.salt,
                  password_hash = excluded.password_hash,
                  expires_at = excluded.expires_at,
                  created_at = excluded.created_at
                """,
                (
                    email,
                    verify_token,
                    data["name"].strip(),
                    data["institution"].strip(),
                    str(data.get("institution_country", "")).strip(),
                    str(data.get("institution_domain", "")).strip(),
                    curricula,
                    role,
                    salt,
                    digest,
                    now() + 7 * 24 * 60 * 60,
                    now(),
                ),
            )
        if not send_verification_email(pending, verify_token):
            with db() as conn:
                conn.execute("DELETE FROM pending_registrations WHERE token = ?", (verify_token,))
            return self.send_json({"error": verification_delivery_error()}, HTTPStatus.BAD_GATEWAY)
        return self.send_json({
            "requires_verification": True,
            "verification_email": email,
            "message": "We sent a verification code. Your profile will be created after verification.",
        })

    def login(self):
        data = self.read_json()
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        if rate_limited(f"login:{self.client_address[0]}:{email}", 10, 120):
            return self.send_json({"error": "Too many login attempts. Try again shortly."}, HTTPStatus.TOO_MANY_REQUESTS)
        with db() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if not row or not verify_password(password, row["salt"], row["password_hash"]):
                return self.send_json({"error": "Invalid email or password."}, HTTPStatus.UNAUTHORIZED)
            if password_needs_rehash(row["password_hash"]):
                salt, digest = hash_password(password)
                conn.execute("UPDATE users SET salt = ?, password_hash = ? WHERE id = ?", (salt, digest, row["id"]))
            if not safe_row_value(row, "email_verified", 1):
                conn.execute("DELETE FROM sessions WHERE user_id = ?", (row["id"],))
                verify_token = create_auth_token(conn, row["id"], "verify_email", 7 * 24 * 60 * 60)
                if not send_verification_email(row, verify_token):
                    conn.execute("DELETE FROM auth_tokens WHERE token = ? AND purpose = 'verify_email'", (verify_token,))
                    return self.send_json({"error": verification_delivery_error()}, HTTPStatus.BAD_GATEWAY)
                return self.send_json({
                    "requires_verification": True,
                    "verification_email": row["email"],
                    "message": "Verify your email before entering Studera.",
                })
            token = secrets.token_urlsafe(32)
            conn.execute("INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)", (token, row["id"], now()))
            conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now(), row["id"]))
            row = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()
        cookie = session_cookie(token)
        return self.send_json({"user": public_user(row)}, cookie=cookie)

    def logout(self):
        token = self.cookie_token()
        if token:
            with db() as conn:
                conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        cookie = session_cookie("", 0)
        return self.send_json({"ok": True}, cookie=cookie)

    def request_verification(self):
        user = self.require_user()
        if not user:
            return
        if user.get("email_verified"):
            return self.send_json({"ok": True, "already_verified": True})
        with db() as conn:
            token = create_auth_token(conn, user["id"], "verify_email", 7 * 24 * 60 * 60)
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
        if not send_verification_email(row, token):
            with db() as conn:
                conn.execute("DELETE FROM auth_tokens WHERE token = ? AND purpose = 'verify_email'", (token,))
            return self.send_json({"error": verification_delivery_error()}, HTTPStatus.BAD_GATEWAY)
        return self.send_json({"ok": True, "sent": True, "email": user.get("email", "")})

    def resend_verification(self):
        data = self.read_json()
        email = str(data.get("email", "")).strip().lower()
        if not email:
            return self.send_json({"error": "Email is required."}, HTTPStatus.BAD_REQUEST)
        if rate_limited(f"verify-resend:{self.client_address[0]}:{email}", 3, 300):
            return self.send_json({"error": "Too many verification email requests. Try again in a few minutes."}, HTTPStatus.TOO_MANY_REQUESTS)
        with db() as conn:
            pending = conn.execute("SELECT * FROM pending_registrations WHERE email = ?", (email,)).fetchone()
            if pending:
                token = secrets.token_urlsafe(32)
                conn.execute(
                    "UPDATE pending_registrations SET token = ?, expires_at = ?, created_at = ? WHERE id = ?",
                    (token, now() + 7 * 24 * 60 * 60, now(), pending["id"]),
                )
                row = conn.execute("SELECT * FROM pending_registrations WHERE id = ?", (pending["id"],)).fetchone()
            else:
                row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
                if not row or safe_row_value(row, "email_verified", 1):
                    return self.send_json({
                        "ok": True,
                        "sent": False,
                        "message": "If that pending registration exists, a new verification code has been emailed.",
                    })
                token = create_auth_token(conn, row["id"], "verify_email", 7 * 24 * 60 * 60)
        if not send_verification_email(row, token):
            with db() as conn:
                conn.execute("DELETE FROM pending_registrations WHERE token = ?", (token,))
                conn.execute("DELETE FROM auth_tokens WHERE token = ? AND purpose = 'verify_email'", (token,))
            return self.send_json({"error": verification_delivery_error()}, HTTPStatus.BAD_GATEWAY)
        return self.send_json({"ok": True, "sent": True, "email": email})

    def verify_pending_registration(self, conn, pending):
        cur = conn.execute(
            """
            INSERT INTO users (
              name, email, institution, institution_country, institution_domain,
              curricula, role, email_verified, is_school_admin, is_site_admin,
              salt, password_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pending["name"],
                pending["email"],
                pending["institution"],
                pending["institution_country"],
                pending["institution_domain"],
                pending["curricula"],
                pending["role"],
                1,
                0,
                0,
                pending["salt"],
                pending["password_hash"],
                now(),
            ),
        )
        user_id = cur.lastrowid
        conn.execute("DELETE FROM pending_registrations WHERE id = ?", (pending["id"],))
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    def verify_email(self):
        data = self.read_json()
        token = str(data.get("token", "")).strip()
        if not token:
            return self.send_json({"error": "Verification token is required."}, HTTPStatus.BAD_REQUEST)
        with db() as conn:
            pending = conn.execute(
                "SELECT * FROM pending_registrations WHERE token = ?",
                (token,),
            ).fetchone()
            if pending:
                if pending["expires_at"] < now():
                    conn.execute("DELETE FROM pending_registrations WHERE id = ?", (pending["id"],))
                    return self.send_json({"error": "Verification link is invalid or expired."}, HTTPStatus.BAD_REQUEST)
                existing = conn.execute("SELECT id FROM users WHERE email = ?", (pending["email"],)).fetchone()
                if existing:
                    conn.execute("DELETE FROM pending_registrations WHERE id = ?", (pending["id"],))
                    return self.send_json({"error": "That email is already registered. Sign in instead."}, HTTPStatus.CONFLICT)
                user_row = self.verify_pending_registration(conn, pending)
                session_token = secrets.token_urlsafe(32)
                conn.execute("INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)", (session_token, user_row["id"], now()))
                cookie = session_cookie(session_token)
                return self.send_json({"ok": True, "user": public_user(user_row)}, cookie=cookie)
            row = conn.execute(
                """
                SELECT * FROM auth_tokens
                WHERE token = ? AND purpose = 'verify_email' AND used_at = 0
                """,
                (token,),
            ).fetchone()
            if not row or row["expires_at"] < now():
                return self.send_json({
                    "error": "Verification link is invalid or expired."
                }, HTTPStatus.BAD_REQUEST)
            conn.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (row["user_id"],))
            conn.execute("UPDATE auth_tokens SET used_at = ? WHERE id = ?", (now(), row["id"]))
            user_row = conn.execute("SELECT * FROM users WHERE id = ?", (row["user_id"],)).fetchone()
            session_token = secrets.token_urlsafe(32)
            conn.execute("INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)", (session_token, row["user_id"], now()))
        cookie = session_cookie(session_token)
        return self.send_json({"ok": True, "user": public_user(user_row)}, cookie=cookie)

    def request_password_reset(self):
        data = self.read_json()
        email = str(data.get("email", "")).strip().lower()
        if not email:
            return self.send_json({"error": "Email is required."}, HTTPStatus.BAD_REQUEST)
        if rate_limited(f"reset:{self.client_address[0]}:{email}", 5, 300):
            return self.send_json({"error": "Too many reset requests. Try again shortly."}, HTTPStatus.TOO_MANY_REQUESTS)
        token = ""
        with db() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if row:
                token = create_auth_token(conn, row["id"], "password_reset", 60 * 60)
                if not send_password_reset_email(row, token):
                    conn.execute("DELETE FROM auth_tokens WHERE token = ? AND purpose = 'password_reset'", (token,))
                    return self.send_json({"error": verification_delivery_error()}, HTTPStatus.BAD_GATEWAY)
        return self.send_json({"ok": True, "sent": bool(token)})

    def reset_password(self):
        data = self.read_json()
        token = str(data.get("token", "")).strip()
        password = str(data.get("password", ""))
        password_error = password_policy_error(password)
        if not token or password_error:
            return self.send_json({"error": password_error or f"Token and a {PASSWORD_MIN_LENGTH} character password are required."}, HTTPStatus.BAD_REQUEST)
        with db() as conn:
            row = conn.execute(
                """
                SELECT * FROM auth_tokens
                WHERE token = ? AND purpose = 'password_reset' AND used_at = 0
                """,
                (token,),
            ).fetchone()
            if not row or row["expires_at"] < now():
                return self.send_json({"error": "Reset link is invalid or expired."}, HTTPStatus.BAD_REQUEST)
            salt, digest = hash_password(password)
            conn.execute("UPDATE users SET salt = ?, password_hash = ? WHERE id = ?", (salt, digest, row["user_id"]))
            conn.execute("UPDATE auth_tokens SET used_at = ? WHERE id = ?", (now(), row["id"]))
        return self.send_json({"ok": True})

    def school_console_row(self, conn, school):
        institution = school["institution"]
        country = school["institution_country"] or ""
        domain = school["institution_domain"] or ""
        curricula = [item for item in (school["curricula"] or "").split("|") if item] or ALL_CURRICULA
        if domain:
            user_where = "LOWER(institution_domain) = LOWER(?)"
            user_values = [domain]
        else:
            user_where = "LOWER(institution) = LOWER(?) AND COALESCE(institution_domain, '') = ''"
            user_values = [institution]
        if domain:
            thread_where = "LOWER(school_domain) = LOWER(?)"
            thread_values = [domain]
        else:
            thread_where = "LOWER(school) = LOWER(?) AND COALESCE(school_domain, '') = ''"
            thread_values = [institution]
        member_count = conn.execute(
            f"SELECT COUNT(*) count FROM users WHERE is_site_admin = 0 AND {user_where}",
            user_values,
        ).fetchone()["count"]
        school_admin_count = conn.execute(
            f"SELECT COUNT(*) count FROM users WHERE is_site_admin = 0 AND is_school_admin = 1 AND {user_where}",
            user_values,
        ).fetchone()["count"]
        thread_count = conn.execute(
            f"""
            SELECT COUNT(*) count
            FROM threads
            WHERE {thread_where}
            """,
            thread_values,
        ).fetchone()["count"]
        reply_count = conn.execute(
            f"""
            SELECT COUNT(*) count
            FROM replies
            JOIN threads ON threads.id = replies.thread_id
            WHERE {thread_where.replace('school_domain', 'threads.school_domain').replace('school)', 'threads.school)')}
            """,
            thread_values,
        ).fetchone()["count"]
        return {
            "institution": institution,
            "institution_country": country,
            "institution_domain": domain,
            "curricula": curricula,
            "has_join_key": bool(school["join_key_hash"]),
            "guidelines": school["guidelines"] or "",
            "updated_at": fmt(school["updated_at"]),
            "member_count": member_count,
            "school_admin_count": school_admin_count,
            "thread_count": thread_count,
            "reply_count": reply_count,
        }

    def site_admin_overview(self):
        user = self.require_site_admin()
        if not user:
            return
        with db() as conn:
            settings_rows = conn.execute(
                """
                SELECT * FROM school_settings
                ORDER BY institution ASC
                """
            ).fetchall()
            schools = {}
            for row in settings_rows:
                schools[(normalize_school_name(row["institution"]), row["institution_domain"] or "")] = row
            user_school_rows = conn.execute(
                """
                SELECT institution, institution_country, institution_domain, curricula
                FROM users
                WHERE is_site_admin = 0
                GROUP BY institution, institution_domain
                ORDER BY institution ASC
                """
            ).fetchall()
            for row in user_school_rows:
                key = (normalize_school_name(row["institution"]), row["institution_domain"] or "")
                if key not in schools:
                    conn.execute(
                        """
                        INSERT INTO school_settings (
                          institution, institution_country, institution_domain, curricula, updated_at
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            row["institution"],
                            row["institution_country"] or "",
                            row["institution_domain"] or "",
                            row["curricula"] or "|".join(ALL_CURRICULA),
                            now(),
                        ),
                    )
            settings_rows = conn.execute("SELECT * FROM school_settings ORDER BY institution ASC").fetchall()
            school_admins = conn.execute(
                """
                SELECT id, name, email, role, institution, institution_country, institution_domain, created_at
                FROM users
                WHERE is_site_admin = 0 AND is_school_admin = 1
                ORDER BY institution ASC, name ASC
                """
            ).fetchall()
            site_admins = conn.execute(
                """
                SELECT id, name, email, created_at
                FROM users
                WHERE is_site_admin = 1
                ORDER BY email ASC
                """
            ).fetchall()
            totals = {
                "schools": len(settings_rows),
                "members": conn.execute("SELECT COUNT(*) count FROM users WHERE is_site_admin = 0").fetchone()["count"],
                "school_admins": len(school_admins),
                "site_admins": len(site_admins),
                "threads": conn.execute("SELECT COUNT(*) count FROM threads").fetchone()["count"],
                "replies": conn.execute("SELECT COUNT(*) count FROM replies").fetchone()["count"],
            }
            school_payload = [self.school_console_row(conn, row) for row in settings_rows]
        return self.send_json({
            "totals": totals,
            "schools": school_payload,
            "school_admins": [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "email": row["email"],
                    "role": row["role"],
                    "institution": row["institution"],
                    "institution_country": row["institution_country"],
                    "institution_domain": row["institution_domain"],
                    "created_at": fmt(row["created_at"]),
                }
                for row in school_admins
            ],
            "site_admins": [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "email": row["email"],
                    "created_at": fmt(row["created_at"]),
                    "is_self": row["id"] == user["id"],
                }
                for row in site_admins
            ],
            "privacy": {
                "forum_access": "blocked",
                "thread_content": "not available to site admins",
                "scope": "aggregate school metrics and account administration only",
            },
        })

    def site_admin_audit(self):
        user = self.require_site_admin()
        if not user:
            return
        with db() as conn:
            platform_rows = conn.execute(
                """
                SELECT * FROM audit_logs
                WHERE actor_scope IN ('site_admin', 'system')
                ORDER BY created_at DESC
                LIMIT 200
                """
            ).fetchall()
            school_rows = conn.execute(
                """
                SELECT * FROM audit_logs
                WHERE actor_scope = 'school_admin'
                ORDER BY created_at DESC
                LIMIT 200
                """
            ).fetchall()
        platform_logs = [audit_json(row) for row in platform_rows]
        school_logs = [audit_json(row) for row in school_rows]
        return self.send_json({
            "logs": platform_logs,
            "platform_logs": platform_logs,
            "school_logs": school_logs,
        })

    def site_admin_backup(self):
        user = self.require_site_admin()
        if not user:
            return
        with db() as conn:
            schools = conn.execute(
                """
                SELECT institution, institution_country, institution_domain, curricula,
                  CASE WHEN join_key_hash != '' THEN 1 ELSE 0 END has_join_key,
                  updated_at
                FROM school_settings
                ORDER BY institution ASC
                """
            ).fetchall()
            admins = conn.execute(
                """
                SELECT name, email, institution, institution_domain, is_school_admin, is_site_admin, created_at
                FROM users
                WHERE is_school_admin = 1 OR is_site_admin = 1
                ORDER BY is_site_admin DESC, institution ASC, email ASC
                """
            ).fetchall()
            totals = {
                "users": conn.execute("SELECT COUNT(*) count FROM users").fetchone()["count"],
                "schools": conn.execute("SELECT COUNT(*) count FROM school_settings").fetchone()["count"],
                "threads": conn.execute("SELECT COUNT(*) count FROM threads").fetchone()["count"],
                "replies": conn.execute("SELECT COUNT(*) count FROM replies").fetchone()["count"],
                "reports": conn.execute("SELECT COUNT(*) count FROM reports").fetchone()["count"],
            }
            log_audit(conn, user, "generate_site_backup", "platform", "studera", "", totals)
        return self.send_json({
            "generated_at": fmt(now()),
            "privacy": "Thread and reply bodies are intentionally excluded from site-admin backups.",
            "totals": totals,
            "schools": [dict(row) | {"updated_at": fmt(row["updated_at"])} for row in schools],
            "admins": [dict(row) | {"created_at": fmt(row["created_at"])} for row in admins],
        })

    def site_admin_save_school(self):
        user = self.require_site_admin()
        if not user:
            return
        data = self.read_json()
        institution = str(data.get("institution", "")).strip()
        country = str(data.get("institution_country", "")).strip()
        domain = str(data.get("institution_domain", "")).strip().lower()
        guidelines = str(data.get("guidelines", "")).strip()[:1200]
        curricula = data.get("curricula")
        if not isinstance(curricula, list):
            curricula = []
        curricula = [item for item in ALL_CURRICULA if item in curricula]
        if not institution:
            return self.send_json({"error": "School name is required."}, HTTPStatus.BAD_REQUEST)
        if not curricula:
            return self.send_json({"error": "Choose at least one curriculum."}, HTTPStatus.BAD_REQUEST)
        join_key = str(data.get("join_key", "")).strip()
        clear_join_key = bool(data.get("clear_join_key"))
        regenerate_join_key = bool(data.get("regenerate_join_key"))
        with db() as conn:
            school = school_settings_for(conn, institution, domain)
            if clear_join_key:
                join_salt, join_hash, join_plain = "", "", ""
            elif regenerate_join_key:
                join_plain = make_join_key()
                join_salt, join_hash = hash_join_key(join_plain)
            elif join_key:
                join_salt, join_hash = hash_join_key(join_key)
                join_plain = join_key
            else:
                join_salt = school["join_key_salt"] if school else ""
                join_hash = school["join_key_hash"] if school else ""
                join_plain = safe_row_value(school, "join_key_plain") if school else ""
            conn.execute(
                """
                INSERT INTO school_settings (
                  institution, institution_country, institution_domain, curricula,
                  join_key_hash, join_key_salt, join_key_plain, guidelines, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(institution, institution_domain) DO UPDATE SET
                  institution_country = excluded.institution_country,
                  curricula = excluded.curricula,
                  join_key_hash = excluded.join_key_hash,
                  join_key_salt = excluded.join_key_salt,
                  join_key_plain = excluded.join_key_plain,
                  guidelines = excluded.guidelines,
                  updated_at = excluded.updated_at
                """,
                (institution, country, domain, "|".join(curricula), join_hash, join_salt, join_plain, guidelines, now()),
            )
            conn.execute(
                """
                UPDATE users
                SET curricula = ?
                WHERE is_site_admin = 0 AND (
                  (LOWER(institution_domain) = LOWER(?) AND ? != '')
                  OR (LOWER(institution) = LOWER(?) AND COALESCE(institution_domain, '') = COALESCE(?, ''))
                )
                """,
                ("|".join(curricula), domain, domain, institution, domain),
            )
            log_audit(conn, user, "save_school", "school", institution, institution, {
                "domain": domain,
                "curricula": curricula,
                "join_key_changed": bool(join_key or regenerate_join_key),
                "join_key_cleared": clear_join_key,
            })
        return self.send_json({"ok": True, "join_key": join_plain})

    def site_admin_grant_school_admin(self):
        user = self.require_site_admin()
        if not user:
            return
        data = self.read_json()
        email = str(data.get("email", "")).strip().lower()
        institution = str(data.get("institution", "")).strip()
        country = str(data.get("institution_country", "")).strip()
        domain = str(data.get("institution_domain", "")).strip().lower()
        curricula = data.get("curricula")
        if not isinstance(curricula, list):
            curricula = []
        curricula = [item for item in ALL_CURRICULA if item in curricula]
        if not email or not institution:
            return self.send_json({"error": "Email and school are required."}, HTTPStatus.BAD_REQUEST)
        if not curricula:
            curricula = curricula_for_school(institution, country)
        with db() as conn:
            target = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if not target:
                return self.send_json({"error": "No account found for that email."}, HTTPStatus.NOT_FOUND)
            if safe_row_value(target, "is_site_admin", 0):
                return self.send_json({"error": "Site admins cannot also be school admins."}, HTTPStatus.BAD_REQUEST)
            conn.execute(
                """
                INSERT INTO school_settings (
                  institution, institution_country, institution_domain, curricula, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(institution, institution_domain) DO UPDATE SET
                  institution_country = excluded.institution_country,
                  curricula = excluded.curricula,
                  updated_at = excluded.updated_at
                """,
                (institution, country, domain, "|".join(curricula), now()),
            )
            conn.execute(
                """
                UPDATE users
                SET is_school_admin = 1,
                    institution = ?,
                    institution_country = ?,
                    institution_domain = ?,
                    curricula = ?
                WHERE email = ?
                """,
                (institution, country, domain, "|".join(curricula), email),
            )
            log_audit(conn, user, "grant_school_admin", "user", target["id"], institution, {"email": email})
        return self.send_json({"ok": True})

    def site_admin_revoke_school_admin(self):
        user = self.require_site_admin()
        if not user:
            return
        data = self.read_json()
        email = str(data.get("email", "")).strip().lower()
        if not email:
            return self.send_json({"error": "Email is required."}, HTTPStatus.BAD_REQUEST)
        with db() as conn:
            target = conn.execute("SELECT * FROM users WHERE email = ? AND is_site_admin = 0", (email,)).fetchone()
            if not target:
                return self.send_json({"error": "No school account found for that email."}, HTTPStatus.NOT_FOUND)
            if not safe_row_value(target, "is_school_admin", 0):
                return self.send_json({"error": "That account is not a school admin."}, HTTPStatus.BAD_REQUEST)
            if school_admin_count(conn, public_user(target)) <= 1:
                return self.send_json(
                    {"error": "Assign another school admin before removing this admin. This is the only admin for that school."},
                    HTTPStatus.FORBIDDEN,
                )
            conn.execute("UPDATE users SET is_school_admin = 0 WHERE id = ?", (target["id"],))
            log_audit(conn, user, "revoke_school_admin", "user", target["id"], safe_row_value(target, "institution", ""), {"email": email})
        return self.send_json({"ok": True})

    def site_admin_grant_site_admin(self):
        user = self.require_site_admin()
        if not user:
            return
        data = self.read_json()
        email = str(data.get("email", "")).strip().lower()
        if not email:
            return self.send_json({"error": "Email is required."}, HTTPStatus.BAD_REQUEST)
        with db() as conn:
            target = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if not target:
                return self.send_json({"error": "Create the account before granting site admin access."}, HTTPStatus.NOT_FOUND)
            conn.execute(
                """
                UPDATE users
                SET is_site_admin = 1,
                    is_school_admin = 0,
                    institution = ?,
                    institution_country = ?,
                    institution_domain = ?,
                    curricula = '',
                    role = 'staff'
                WHERE email = ?
                """,
                (SITE_ADMIN_INSTITUTION, "Global", SITE_ADMIN_DOMAIN, email),
            )
            log_audit(conn, user, "grant_site_admin", "user", target["id"], "", {"email": email})
        return self.send_json({"ok": True})

    def site_admin_revoke_site_admin(self):
        user = self.require_site_admin()
        if not user:
            return
        data = self.read_json()
        email = str(data.get("email", "")).strip().lower()
        if not email:
            return self.send_json({"error": "Email is required."}, HTTPStatus.BAD_REQUEST)
        if email == user["email"]:
            return self.send_json({"error": "You cannot revoke your own site admin access."}, HTTPStatus.BAD_REQUEST)
        with db() as conn:
            target = conn.execute("SELECT * FROM users WHERE email = ? AND is_site_admin = 1", (email,)).fetchone()
            if not target:
                return self.send_json({"error": "No site admin account found for that email."}, HTTPStatus.NOT_FOUND)
            if site_admin_count(conn) <= 1:
                return self.send_json(
                    {"error": "Assign another site admin before removing this admin. This is the only site admin."},
                    HTTPStatus.FORBIDDEN,
                )
            conn.execute("UPDATE users SET is_site_admin = 0 WHERE id = ?", (target["id"],))
            log_audit(conn, user, "revoke_site_admin", "user", email, "", {"email": email})
        return self.send_json({"ok": True})

    def update_settings(self):
        user = self.require_user()
        if not user:
            return
        data = self.read_json()
        name = str(data.get("name", "")).strip()
        profile_title = str(data.get("profile_title", "")).strip()[:80]
        role = str(data.get("role", user.get("role", "student"))).strip()
        bio = str(data.get("bio", "")).strip()[:600]
        visibility = str(data.get("profile_visibility", "school")).strip()
        if role not in ("student", "teacher", "staff"):
            return self.send_json({"error": "Choose Student, Teacher, or Staff."}, HTTPStatus.BAD_REQUEST)
        if visibility not in ("public", "school", "private"):
            visibility = "school"
        if not name:
            return self.send_json({"error": "Display name is required."}, HTTPStatus.BAD_REQUEST)
        old_avatar = safe_row_value(user, "avatar_path", "")
        new_avatar = old_avatar
        uploaded_avatar = ""
        try:
            if data.get("remove_avatar"):
                new_avatar = ""
            if data.get("avatar_file_data"):
                uploaded_avatar = save_avatar(data.get("avatar_file_data"), data.get("avatar_file_name", "profile-picture"))
                new_avatar = uploaded_avatar
        except ValueError as exc:
            return self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        with db() as conn:
            conn.execute(
                """
                UPDATE users
                SET name = ?, profile_title = ?, role = ?, bio = ?, avatar_path = ?, profile_visibility = ?,
                    show_school = ?, show_email = ?, email_replies = ?, email_digest = ?
                WHERE id = ?
                """,
                (
                    name,
                    profile_title,
                    role,
                    bio,
                    new_avatar,
                    visibility,
                    1 if data.get("show_school") else 0,
                    1 if data.get("show_email") else 0,
                    1 if data.get("email_replies") else 0,
                    1 if data.get("email_digest") else 0,
                    user["id"],
                ),
            )
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
        if old_avatar and old_avatar != new_avatar:
            delete_upload(old_avatar)
        return self.send_json({"user": public_user(row)})

    def change_school(self):
        user = self.require_user()
        if not user:
            return
        if user.get("is_site_admin"):
            return self.send_json({"error": "Site admins do not belong to school forums."}, HTTPStatus.FORBIDDEN)
        data = self.read_json()
        institution = str(data.get("institution", "")).strip()
        country = str(data.get("institution_country", "")).strip()
        domain = str(data.get("institution_domain", "")).strip().lower()
        curricula = str(data.get("curricula", "")).strip()
        if not institution:
            return self.send_json({"error": "Choose your new school from the suggestions."}, HTTPStatus.BAD_REQUEST)
        if not curricula:
            inferred = curricula_for_school(institution, country)
            curricula = "|".join(inferred)
        destination = {"institution": institution, "institution_country": country, "institution_domain": domain}
        same_destination = same_school(user, destination)
        with db() as conn:
            if user.get("is_school_admin") and not same_destination and school_admin_count(conn, user) <= 1:
                return self.send_json(
                    {"error": "Assign another school admin before changing schools. You are the only admin for your current school."},
                    HTTPStatus.FORBIDDEN,
                )
            school = school_settings_for(conn, institution, domain)
            if school:
                curricula = school["curricula"] or curricula
                if not same_destination and not verify_join_key(data.get("join_key", ""), school):
                    return self.send_json({"error": "That school requires a valid join key."}, HTTPStatus.FORBIDDEN)
            was_admin = bool(user.get("is_school_admin"))
            conn.execute(
                """
                UPDATE users
                SET institution = ?, institution_country = ?, institution_domain = ?,
                    curricula = ?, is_school_admin = ?
                WHERE id = ?
                """,
                (
                    institution,
                    country,
                    domain,
                    curricula,
                    1 if was_admin and same_destination else 0,
                    user["id"],
                ),
            )
            log_audit(conn, user, "change_school", "user", user["id"], institution, {
                "from": user.get("institution", ""),
                "to": institution,
                "admin_revoked": bool(was_admin and not same_destination),
            })
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
        return self.send_json({"user": public_user(row)})

    def delete_account(self):
        user = self.require_user()
        if not user:
            return
        data = self.read_json()
        if str(data.get("confirm", "")).strip() != "DELETE":
            return self.send_json({"error": "Type DELETE to confirm account deletion."}, HTTPStatus.BAD_REQUEST)
        user_id = user["id"]
        with db() as conn:
            if user.get("is_site_admin") and site_admin_count(conn) <= 1:
                return self.send_json(
                    {"error": "Assign another site admin before deleting this account. You are the only site admin."},
                    HTTPStatus.FORBIDDEN,
                )
            if user.get("is_school_admin") and school_admin_count(conn, user) <= 1:
                return self.send_json(
                    {"error": "Assign another school admin before deleting this account. You are the only admin for your school."},
                    HTTPStatus.FORBIDDEN,
                )
            target = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            delete_user_account_records(conn, target, user, "delete_account")
        cookie = session_cookie("", 0)
        return self.send_json({"ok": True}, cookie=cookie)

    def admin_school(self):
        user = self.require_school_admin()
        if not user:
            return
        with db() as conn:
            school = school_settings_for(conn, user["institution"], user.get("institution_domain", ""))
            if not school:
                conn.execute(
                    """
                    INSERT INTO school_settings (
                      institution, institution_country, institution_domain, curricula, updated_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        user["institution"],
                        user.get("institution_country", ""),
                        user.get("institution_domain", ""),
                        "|".join(user.get("curricula") or ALL_CURRICULA),
                        now(),
                    ),
                )
                school = school_settings_for(conn, user["institution"], user.get("institution_domain", ""))
            members = conn.execute(
                """
                SELECT id, name, email, role, is_school_admin, created_at
                FROM users
                WHERE (LOWER(institution_domain) = LOWER(?) AND ? != '')
                   OR (LOWER(institution) = LOWER(?) AND COALESCE(institution_domain, '') = COALESCE(?, ''))
                ORDER BY is_school_admin DESC, name ASC
                """,
                (user.get("institution_domain", ""), user.get("institution_domain", ""), user["institution"], user.get("institution_domain", "")),
            ).fetchall()
            thread_clause, thread_values = thread_school_filter("threads", user)
            threads = conn.execute(
                f"""
                SELECT threads.*, users.name author_name, users.email author_email,
                  (SELECT COUNT(*) FROM replies WHERE replies.thread_id = threads.id) replies
                FROM threads
                JOIN users ON users.id = threads.user_id
                WHERE {thread_clause}
                ORDER BY threads.created_at DESC
                LIMIT 30
                """,
                thread_values,
            ).fetchall()
        return self.send_json({
            "school": public_school_settings(school, user),
            "members": [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "email": row["email"],
                    "role": row["role"],
                    "is_school_admin": bool(row["is_school_admin"]),
                    "created_at": fmt(row["created_at"]),
                }
                for row in members
            ],
            "threads": [
                {
                    "id": row["id"],
                    "title": row["title"],
                    "section": row["section"],
                    "author_name": row["author_name"],
                    "author_email": row["author_email"],
                    "replies": row["replies"],
                    "created_at": fmt(row["created_at"]),
                }
                for row in threads
            ],
        })

    def update_admin_school(self):
        user = self.require_school_admin()
        if not user:
            return
        data = self.read_json()
        curricula = data.get("curricula")
        if not isinstance(curricula, list):
            curricula = []
        curricula = [item for item in ALL_CURRICULA if item in curricula]
        custom_curricula = parse_custom_curricula(data.get("custom_curricula", []))
        custom_names = [item["name"] for item in custom_curricula]
        curricula = pipe_list(curricula + custom_names)
        if not curricula:
            return self.send_json({"error": "Choose at least one curriculum."}, HTTPStatus.BAD_REQUEST)
        guidelines = str(data.get("guidelines", "")).strip()[:1200]
        join_key = str(data.get("join_key", "")).strip()
        clear_join_key = bool(data.get("clear_join_key"))
        regenerate_join_key = bool(data.get("regenerate_join_key"))
        with db() as conn:
            school = school_settings_for(conn, user["institution"], user.get("institution_domain", ""))
            old_custom_curricula = parse_custom_curricula(safe_row_value(school, "custom_curricula", "[]")) if school else []
            if clear_join_key:
                join_salt, join_hash, join_plain = "", "", ""
            elif regenerate_join_key:
                join_plain = make_join_key()
                join_salt, join_hash = hash_join_key(join_plain)
            elif join_key:
                join_plain = join_key
                join_salt, join_hash = hash_join_key(join_key)
            else:
                join_salt = school["join_key_salt"] if school else ""
                join_hash = school["join_key_hash"] if school else ""
                join_plain = safe_row_value(school, "join_key_plain") if school else ""
            conn.execute(
                """
                INSERT INTO school_settings (
                  institution, institution_country, institution_domain, curricula, custom_curricula,
                  join_key_hash, join_key_salt, join_key_plain, guidelines, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(institution, institution_domain) DO UPDATE SET
                  curricula = excluded.curricula,
                  custom_curricula = excluded.custom_curricula,
                  join_key_hash = excluded.join_key_hash,
                  join_key_salt = excluded.join_key_salt,
                  join_key_plain = excluded.join_key_plain,
                  guidelines = excluded.guidelines,
                  updated_at = excluded.updated_at
                """,
                (
                    user["institution"],
                    user.get("institution_country", ""),
                    user.get("institution_domain", ""),
                    "|".join(curricula),
                    json.dumps(custom_curricula),
                    join_hash,
                    join_salt,
                    join_plain,
                    guidelines,
                    now(),
                ),
            )
            conn.execute(
                """
                UPDATE users
                SET curricula = ?
                WHERE (LOWER(institution_domain) = LOWER(?) AND ? != '')
                   OR (LOWER(institution) = LOWER(?) AND COALESCE(institution_domain, '') = COALESCE(?, ''))
                """,
                ("|".join(curricula), user.get("institution_domain", ""), user.get("institution_domain", ""), user["institution"], user.get("institution_domain", "")),
            )
            tag_updates = reconcile_custom_curriculum_tags(conn, user, old_custom_curricula, custom_curricula)
            school = school_settings_for(conn, user["institution"], user.get("institution_domain", ""))
            log_audit(conn, user, "update_school_settings", "school", user["institution"], user["institution"], {
                "curricula": curricula,
                "custom_curricula": custom_curricula,
                "tag_updates": tag_updates,
                "join_key_changed": bool(join_key or regenerate_join_key),
                "join_key_cleared": clear_join_key,
            })
        return self.send_json({"school": public_school_settings(school, user)})

    def grant_admin(self):
        user = self.require_school_admin()
        if not user:
            return
        data = self.read_json()
        email = str(data.get("email", "")).strip().lower()
        if not email:
            return self.send_json({"error": "Enter an account email."}, HTTPStatus.BAD_REQUEST)
        with db() as conn:
            target = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if not target:
                return self.send_json({"error": "No account found for that email."}, HTTPStatus.NOT_FOUND)
            if not same_school(user, public_user(target)):
                return self.send_json({"error": "Admins can only grant access within their own school."}, HTTPStatus.FORBIDDEN)
            conn.execute("UPDATE users SET is_school_admin = 1 WHERE id = ?", (target["id"],))
            log_audit(conn, user, "grant_school_admin", "user", target["id"], user["institution"], {"email": email})
        return self.send_json({"ok": True})

    def revoke_admin(self):
        user = self.require_school_admin()
        if not user:
            return
        data = self.read_json()
        email = str(data.get("email", "")).strip().lower()
        if not email:
            return self.send_json({"error": "Enter an account email."}, HTTPStatus.BAD_REQUEST)
        if email == user["email"]:
            return self.send_json({"error": "You cannot remove your own admin access."}, HTTPStatus.BAD_REQUEST)
        with db() as conn:
            target = conn.execute("SELECT * FROM users WHERE email = ? AND is_site_admin = 0", (email,)).fetchone()
            if not target:
                return self.send_json({"error": "No school account found for that email."}, HTTPStatus.NOT_FOUND)
            if not same_school(user, public_user(target)):
                return self.send_json({"error": "Admins can only revoke access within their own school."}, HTTPStatus.FORBIDDEN)
            if not safe_row_value(target, "is_school_admin", 0):
                return self.send_json({"error": "That account is not a school admin."}, HTTPStatus.BAD_REQUEST)
            if school_admin_count(conn, public_user(target)) <= 1:
                return self.send_json(
                    {"error": "Assign another school admin before removing this admin. This is the only admin for your school."},
                    HTTPStatus.FORBIDDEN,
                )
            conn.execute("UPDATE users SET is_school_admin = 0 WHERE id = ?", (target["id"],))
            log_audit(conn, user, "revoke_school_admin", "user", target["id"], user["institution"], {"email": email})
        return self.send_json({"ok": True})

    def rename_school_member(self):
        user = self.require_school_admin()
        if not user:
            return
        data = self.read_json()
        email = str(data.get("email", "")).strip().lower()
        name = " ".join(str(data.get("name", "")).strip().split())
        if not email:
            return self.send_json({"error": "Choose a member account to rename."}, HTTPStatus.BAD_REQUEST)
        if len(name) < 2:
            return self.send_json({"error": "Enter a display name with at least 2 characters."}, HTTPStatus.BAD_REQUEST)
        if len(name) > 80:
            return self.send_json({"error": "Display names must be 80 characters or fewer."}, HTTPStatus.BAD_REQUEST)
        with db() as conn:
            target = conn.execute("SELECT * FROM users WHERE email = ? AND is_site_admin = 0", (email,)).fetchone()
            if not target:
                return self.send_json({"error": "No school account found for that email."}, HTTPStatus.NOT_FOUND)
            target_user = public_user(target)
            if not same_school(user, target_user):
                return self.send_json({"error": "Admins can only rename accounts within their own school."}, HTTPStatus.FORBIDDEN)
            old_name = safe_row_value(target, "name", "")
            if old_name == name:
                return self.send_json({"ok": True, "name": name})
            conn.execute("UPDATE users SET name = ? WHERE id = ?", (name, target["id"]))
            log_audit(conn, user, "rename_member", "user", target["id"], user["institution"], {
                "email": email,
                "old_name": old_name,
                "new_name": name,
            })
        return self.send_json({"ok": True, "name": name})

    def delete_school_member(self):
        user = self.require_school_admin()
        if not user:
            return
        data = self.read_json()
        email = str(data.get("email", "")).strip().lower()
        if str(data.get("confirm", "")).strip() != "DELETE":
            return self.send_json({"error": "Type DELETE to confirm member account deletion."}, HTTPStatus.BAD_REQUEST)
        if not email:
            return self.send_json({"error": "Choose a member account to delete."}, HTTPStatus.BAD_REQUEST)
        if email == user["email"]:
            return self.send_json({"error": "Use Settings to delete your own account."}, HTTPStatus.BAD_REQUEST)
        with db() as conn:
            target = conn.execute("SELECT * FROM users WHERE email = ? AND is_site_admin = 0", (email,)).fetchone()
            if not target:
                return self.send_json({"error": "No school account found for that email."}, HTTPStatus.NOT_FOUND)
            target_user = public_user(target)
            if not same_school(user, target_user):
                return self.send_json({"error": "Admins can only delete accounts within their own school."}, HTTPStatus.FORBIDDEN)
            if target_user.get("is_school_admin") and school_admin_count(conn, target_user) <= 1:
                return self.send_json(
                    {"error": "Assign another school admin before deleting this account. This is the only admin for your school."},
                    HTTPStatus.FORBIDDEN,
                )
            delete_user_account_records(conn, target, user, "delete_member_account")
        return self.send_json({"ok": True})

    def admin_reports(self):
        user = self.require_school_admin()
        if not user:
            return
        clause, values = thread_school_filter("threads", user)
        with db() as conn:
            rows = conn.execute(
                f"""
                SELECT reports.*, reporter.name reporter_name,
                  threads.title thread_title, threads.status thread_status,
                  target_reply.body reply_body
                FROM reports
                JOIN users reporter ON reporter.id = reports.reporter_user_id
                JOIN threads ON threads.id = reports.thread_id
                LEFT JOIN replies target_reply ON reports.target_type = 'reply' AND target_reply.id = reports.target_id
                WHERE {clause}
                ORDER BY CASE reports.status WHEN 'open' THEN 0 WHEN 'reviewing' THEN 1 ELSE 2 END,
                  reports.created_at DESC
                """,
                values,
            ).fetchall()
        return self.send_json({"reports": [
            {
                "id": row["id"],
                "target_type": row["target_type"],
                "target_id": row["target_id"],
                "thread_id": row["thread_id"],
                "thread_title": row["thread_title"],
                "thread_status": row["thread_status"],
                "reply_body": row["reply_body"] or "",
                "reporter_name": row["reporter_name"],
                "reason": row["reason"],
                "status": row["status"],
                "created_at": fmt(row["created_at"]),
            }
            for row in rows
        ]})

    def admin_update_report(self):
        user = self.require_school_admin()
        if not user:
            return
        data = self.read_json()
        report_id = int(data.get("id") or 0)
        status = str(data.get("status", "")).strip()
        if status not in ("open", "reviewing", "resolved", "dismissed"):
            return self.send_json({"error": "Invalid report status."}, HTTPStatus.BAD_REQUEST)
        clause, values = thread_school_filter("threads", user)
        with db() as conn:
            report = conn.execute(
                f"""
                SELECT reports.*
                FROM reports
                JOIN threads ON threads.id = reports.thread_id
                WHERE reports.id = ? AND {clause}
                """,
                [report_id] + values,
            ).fetchone()
            if not report:
                return self.send_json({"error": "Report not found."}, HTTPStatus.NOT_FOUND)
            conn.execute(
                "UPDATE reports SET status = ?, resolved_by = ?, resolved_at = ? WHERE id = ?",
                (status, user["id"], now() if status in ("resolved", "dismissed") else 0, report_id),
            )
            log_audit(conn, user, "update_report", "report", report_id, user["institution"], {"status": status})
        return self.send_json({"ok": True})

    def admin_audit(self):
        user = self.require_school_admin()
        if not user:
            return
        with db() as conn:
            rows = conn.execute(
                """
                SELECT * FROM audit_logs
                WHERE school = ? AND actor_scope = 'school_admin'
                ORDER BY created_at DESC
                LIMIT 100
                """,
                (user["institution"],),
            ).fetchall()
        return self.send_json({"logs": [audit_json(row) for row in rows]})

    def admin_export(self):
        user = self.require_school_admin()
        if not user:
            return
        clause, values = thread_school_filter("threads", user)
        with db() as conn:
            threads = conn.execute(
                f"""
                SELECT threads.id, threads.title, threads.body, threads.curriculum, threads.section,
                  threads.status, threads.created_at, users.name author_name
                FROM threads
                JOIN users ON users.id = threads.user_id
                WHERE {clause}
                ORDER BY threads.created_at DESC
                """,
                values,
            ).fetchall()
            replies = conn.execute(
                f"""
                SELECT replies.id, replies.thread_id, replies.body, replies.created_at, users.name author_name
                FROM replies
                JOIN threads ON threads.id = replies.thread_id
                JOIN users ON users.id = replies.user_id
                WHERE {clause}
                ORDER BY replies.created_at ASC
                """,
                values,
            ).fetchall()
            log_audit(conn, user, "export_school_archive", "school", user["institution"], user["institution"], {"thread_count": len(threads)})
        return self.send_json({
            "school": user["institution"],
            "generated_at": fmt(now()),
            "threads": [dict(row) | {"created_at": fmt(row["created_at"])} for row in threads],
            "replies": [dict(row) | {"created_at": fmt(row["created_at"])} for row in replies],
        })

    def list_threads(self, parsed):
        user = self.current_user()
        if user and user.get("is_site_admin"):
            return self.send_json({"error": "Site admins cannot access school forums."}, HTTPStatus.FORBIDDEN)
        params = parse_qs(parsed.query)
        curriculum = params.get("curriculum", [""])[0]
        section = params.get("section", [""])[0]
        q = params.get("q", [""])[0]
        status = params.get("status", [""])[0]
        teacher_replied = params.get("teacher_replied", [""])[0] == "1"
        has_uploads = params.get("has_uploads", [""])[0] == "1"
        bookmarked = params.get("bookmarked", [""])[0] == "1"
        values = []
        where = []
        if curriculum:
            where.append("threads.curriculum = ?")
            values.append(curriculum)
        if section:
            where.append("threads.section = ?")
            values.append(section)
        if q:
            where.append("""
              (threads.title LIKE ? OR threads.body LIKE ? OR threads.section LIKE ?
               OR users.name LIKE ?
               OR EXISTS (SELECT 1 FROM attachments WHERE parent_type = 'thread' AND parent_id = threads.id AND name LIKE ?)
               OR EXISTS (
                 SELECT 1 FROM replies
                 LEFT JOIN attachments reply_attachments ON reply_attachments.parent_type = 'reply' AND reply_attachments.parent_id = replies.id
                 WHERE replies.thread_id = threads.id AND (replies.body LIKE ? OR reply_attachments.name LIKE ?)
               ))
            """)
            values.extend([f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"])
        if status in ("open", "answered", "archived", "locked"):
            where.append("threads.status = ?")
            values.append(status)
        if teacher_replied:
            where.append("""
              EXISTS (
                SELECT 1 FROM replies teacher_replies
                JOIN users reply_users ON reply_users.id = teacher_replies.user_id
                WHERE teacher_replies.thread_id = threads.id AND reply_users.role IN ('teacher', 'staff')
              )
            """)
        if has_uploads:
            where.append("""
              (EXISTS (SELECT 1 FROM attachments WHERE parent_type = 'thread' AND parent_id = threads.id)
               OR EXISTS (
                 SELECT 1 FROM replies
                 JOIN attachments reply_attachments ON reply_attachments.parent_type = 'reply' AND reply_attachments.parent_id = replies.id
                 WHERE replies.thread_id = threads.id
               ))
            """)
        if user:
            clause_part, clause_values = thread_school_filter("threads", user)
            where.append(clause_part)
            values.extend(clause_values)
        if bookmarked:
            if not user:
                return self.send_json({"threads": []})
            where.append("(threads.user_id = ? OR EXISTS (SELECT 1 FROM bookmarks WHERE bookmarks.thread_id = threads.id AND bookmarks.user_id = ?))")
            values.append(user["id"])
            values.append(user["id"])
        clause = "WHERE " + " AND ".join(where) if where else ""
        with db() as conn:
            rows = conn.execute(
                f"""
                SELECT threads.*, users.name author_name, users.role author_role,
                  users.avatar_path author_avatar_path,
                  users.institution author_institution,
                  users.institution_country author_institution_country,
                  users.institution_domain author_institution_domain,
                  (SELECT COUNT(*) FROM replies WHERE replies.thread_id = threads.id) replies,
                  (SELECT COUNT(*) FROM supports WHERE supports.thread_id = threads.id) supports,
                  EXISTS(SELECT 1 FROM supports WHERE supports.thread_id = threads.id AND supports.user_id = ?) supported,
                  (threads.user_id = ? OR EXISTS(SELECT 1 FROM bookmarks WHERE bookmarks.thread_id = threads.id AND bookmarks.user_id = ?)) bookmarked
                FROM threads
                JOIN users ON users.id = threads.user_id
                {clause}
                ORDER BY threads.created_at DESC
                """,
                ([user["id"] if user else 0, user["id"] if user else 0, user["id"] if user else 0] + values),
            ).fetchall()
        attachments_by_thread = {}
        if rows:
            ids = [row["id"] for row in rows]
            placeholders = ",".join("?" for _ in ids)
            with db() as conn:
                attachment_rows = conn.execute(
                    f"""
                    SELECT * FROM attachments
                    WHERE parent_type = 'thread' AND parent_id IN ({placeholders})
                    ORDER BY created_at ASC, id ASC
                    """,
                    ids,
                ).fetchall()
            for attachment in attachment_rows:
                attachments_by_thread.setdefault(attachment["parent_id"], []).append(attachment)
        threads = [self.thread_json(row, attachments_by_thread.get(row["id"], [])) for row in rows]
        return self.send_json({"threads": threads})

    def create_report(self):
        user = self.require_forum_user()
        if not user:
            return
        data = self.read_json()
        target_type = str(data.get("target_type", "")).strip()
        target_id = int(data.get("target_id") or 0)
        reason = str(data.get("reason", "")).strip()[:600]
        if target_type not in ("thread", "reply") or not target_id:
            return self.send_json({"error": "Choose a thread or reply to report."}, HTTPStatus.BAD_REQUEST)
        with db() as conn:
            if target_type == "thread":
                target = conn.execute(
                    """
                    SELECT threads.id thread_id,
                      threads.school thread_school,
                      threads.school_country thread_school_country,
                      threads.school_domain thread_school_domain,
                      users.institution author_institution,
                      users.institution_country author_institution_country,
                      users.institution_domain author_institution_domain
                    FROM threads
                    JOIN users ON users.id = threads.user_id
                    WHERE threads.id = ?
                    """,
                    (target_id,),
                ).fetchone()
            else:
                target = conn.execute(
                    """
                    SELECT replies.thread_id,
                      threads.school thread_school,
                      threads.school_country thread_school_country,
                      threads.school_domain thread_school_domain,
                      users.institution author_institution,
                      users.institution_country author_institution_country,
                      users.institution_domain author_institution_domain
                    FROM replies
                    JOIN threads ON threads.id = replies.thread_id
                    JOIN users ON users.id = threads.user_id
                    WHERE replies.id = ?
                    """,
                    (target_id,),
                ).fetchone()
            if not target:
                return self.send_json({"error": "Report target not found."}, HTTPStatus.NOT_FOUND)
            if not same_school(user, school_from_thread_row(target)):
                return self.send_json({"error": "You can only report content in your own school."}, HTTPStatus.FORBIDDEN)
            conn.execute(
                """
                INSERT INTO reports (reporter_user_id, target_type, target_id, thread_id, school, reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user["id"], target_type, target_id, target["thread_id"], user["institution"], reason or "No reason provided", now()),
            )
        return self.send_json({"ok": True})

    def update_thread_status(self, thread_id):
        user = self.require_forum_user()
        if not user:
            return
        data = self.read_json()
        status = str(data.get("status", "")).strip()
        answered_reply_id = int(data.get("answered_reply_id") or 0)
        if status not in ("open", "answered", "archived", "locked"):
            return self.send_json({"error": "Invalid thread status."}, HTTPStatus.BAD_REQUEST)
        with db() as conn:
            thread = conn.execute(
                """
                SELECT threads.*, users.institution author_institution,
                  users.institution_country author_institution_country,
                  users.institution_domain author_institution_domain
                FROM threads
                JOIN users ON users.id = threads.user_id
                WHERE threads.id = ?
                """,
                (thread_id,),
            ).fetchone()
            if not thread:
                return self.send_json({"error": "Thread not found."}, HTTPStatus.NOT_FOUND)
            thread_school = school_from_thread_row(thread)
            same_thread_school = same_school(user, thread_school)
            is_author = thread["user_id"] == user["id"]
            is_school_admin = bool(user.get("is_school_admin") and same_thread_school)
            if not same_thread_school:
                return self.send_json({"error": "You cannot change this thread status."}, HTTPStatus.FORBIDDEN)
            if status == "answered" and not is_author:
                return self.send_json({"error": "Only the person who started the thread can mark a response as the solution."}, HTTPStatus.FORBIDDEN)
            if status in ("open", "locked", "archived") and not is_school_admin:
                return self.send_json({"error": "Only a school admin can close or reopen this thread."}, HTTPStatus.FORBIDDEN)
            if status == "answered" and not answered_reply_id:
                return self.send_json({"error": "Choose a reply to mark as the solution."}, HTTPStatus.BAD_REQUEST)
            if answered_reply_id:
                reply = conn.execute("SELECT id FROM replies WHERE id = ? AND thread_id = ?", (answered_reply_id, thread_id)).fetchone()
                if not reply:
                    return self.send_json({"error": "Answered reply must belong to this thread."}, HTTPStatus.BAD_REQUEST)
            conn.execute(
                "UPDATE threads SET status = ?, answered_reply_id = ?, locked_at = ? WHERE id = ?",
                (status, answered_reply_id if status == "answered" else 0, now() if status in ("locked", "archived") else 0, thread_id),
            )
            log_audit(conn, user, "update_thread_status", "thread", thread_id, user["institution"], {"status": status})
        return self.send_json({"ok": True})

    def thread_json(self, row, attachments=None):
        preview = row["body"].replace("\n", " ")
        if len(preview) > 180:
            preview = preview[:177] + "..."
        merged_attachments = merge_attachments(row, attachments)
        first_attachment = merged_attachments[0] if merged_attachments else {}
        return {
            "id": row["id"],
            "title": row["title"],
            "body": row["body"],
            "preview": preview,
            "curriculum": row["curriculum"],
            "section": row["section"],
            "status": safe_row_value(row, "status", "open"),
            "answered_reply_id": safe_row_value(row, "answered_reply_id", 0),
            "author_id": row["user_id"],
            "author_name": row["author_name"],
            "author_role": row["author_role"],
            "author_avatar_path": safe_row_value(row, "author_avatar_path", ""),
            "created_at": fmt(row["created_at"]),
            "replies": row["replies"],
            "supports": row["supports"],
            "supported": bool(row["supported"]),
            "bookmarked": bool(row["bookmarked"]),
            "attachments": merged_attachments,
            "attachment_path": first_attachment.get("path", ""),
            "attachment_name": first_attachment.get("name", ""),
            "attachment_type": first_attachment.get("type", ""),
            "image_path": safe_row_value(row, "image_path"),
            "image_name": safe_row_value(row, "image_name"),
        }

    def get_thread(self, thread_id):
        user = self.current_user()
        if user and user.get("is_site_admin"):
            return self.send_json({"error": "Site admins cannot access school forums."}, HTTPStatus.FORBIDDEN)
        with db() as conn:
            row = conn.execute(
                """
                SELECT threads.*, users.name author_name, users.role author_role,
                  users.avatar_path author_avatar_path,
                  users.institution author_institution,
                  users.institution_country author_institution_country,
                  users.institution_domain author_institution_domain,
                  (SELECT COUNT(*) FROM replies WHERE replies.thread_id = threads.id) replies,
                  (SELECT COUNT(*) FROM supports WHERE supports.thread_id = threads.id) supports,
                  EXISTS(SELECT 1 FROM supports WHERE supports.thread_id = threads.id AND supports.user_id = ?) supported,
                  (threads.user_id = ? OR EXISTS(SELECT 1 FROM bookmarks WHERE bookmarks.thread_id = threads.id AND bookmarks.user_id = ?)) bookmarked
                FROM threads JOIN users ON users.id = threads.user_id
                WHERE threads.id = ?
                """,
                (user["id"] if user else 0, user["id"] if user else 0, user["id"] if user else 0, thread_id),
            ).fetchone()
            if not row:
                return self.send_json({"error": "Thread not found."}, HTTPStatus.NOT_FOUND)
            if user and not same_school(user, school_from_thread_row(row)):
                return self.send_json({"error": "Thread not found."}, HTTPStatus.NOT_FOUND)
            replies = conn.execute(
                """
                SELECT replies.*, users.name author_name, users.role author_role,
                  users.avatar_path author_avatar_path,
                  parent_replies.body reply_to_body,
                  parent_users.name reply_to_author_name,
                  (SELECT COUNT(*) FROM reply_supports WHERE reply_supports.reply_id = replies.id) supports,
                  EXISTS(SELECT 1 FROM reply_supports WHERE reply_supports.reply_id = replies.id AND reply_supports.user_id = ?) supported
                FROM replies
                JOIN users ON users.id = replies.user_id
                LEFT JOIN replies parent_replies ON parent_replies.id = replies.parent_reply_id
                  AND parent_replies.thread_id = replies.thread_id
                LEFT JOIN users parent_users ON parent_users.id = parent_replies.user_id
                WHERE replies.thread_id = ?
                ORDER BY replies.created_at ASC, replies.id ASC
                """,
                (user["id"] if user else 0, thread_id),
            ).fetchall()
            attachment_rows = conn.execute(
                """
                SELECT * FROM attachments
                WHERE (parent_type = 'thread' AND parent_id = ?)
                   OR (parent_type = 'reply' AND parent_id IN (SELECT id FROM replies WHERE thread_id = ?))
                ORDER BY created_at ASC, id ASC
                """,
                (thread_id, thread_id),
            ).fetchall()
        thread_attachments = [item for item in attachment_rows if item["parent_type"] == "thread"]
        reply_attachments = {}
        for item in attachment_rows:
            if item["parent_type"] == "reply":
                reply_attachments.setdefault(item["parent_id"], []).append(item)
        return self.send_json({
            "thread": self.thread_json(row, thread_attachments),
            "replies": [self.reply_json(reply, reply_attachments.get(reply["id"], [])) for reply in replies],
        })

    def create_thread(self):
        user = self.require_forum_user()
        if not user:
            return
        data = self.read_json()
        fields = ["title", "body", "curriculum", "section"]
        if any(not str(data.get(field, "")).strip() for field in fields):
            return self.send_json({"error": "Title, section, curriculum, and body are required."}, HTTPStatus.BAD_REQUEST)
        allowed = set(user.get("curricula") or [])
        if allowed and data["curriculum"].strip() not in allowed:
            return self.send_json({"error": "Your school does not have that curriculum enabled."}, HTTPStatus.FORBIDDEN)
        curriculum = data["curriculum"].strip()
        section = data["section"].strip()
        try:
            uploads = save_uploads(data)
        except ValueError as error:
            return self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        first_upload = uploads[0] if uploads else {}
        with db() as conn:
            school = school_settings_for(conn, user.get("institution", ""), user.get("institution_domain", ""))
            allowed_sections = custom_curriculum_sections(school, curriculum) or SECTIONS_BY_CURRICULUM.get(curriculum, [])
            if allowed_sections and section not in allowed_sections:
                return self.send_json({"error": "Choose a section from your school's configured classes."}, HTTPStatus.FORBIDDEN)
            cur = conn.execute(
                """
                INSERT INTO threads (
                  user_id, title, body, curriculum, section,
                  school, school_country, school_domain,
                  attachment_path, attachment_name, attachment_type, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user["id"], data["title"].strip(), data["body"].strip(),
                    curriculum, section,
                    user.get("institution", ""), user.get("institution_country", ""), user.get("institution_domain", ""),
                    first_upload.get("path", ""), first_upload.get("name", ""), first_upload.get("mime_type", ""), now(),
                ),
            )
            thread_id = cur.lastrowid
            insert_attachments(conn, "thread", thread_id, uploads)
        return self.get_thread(thread_id)

    def create_reply(self, thread_id):
        user = self.require_forum_user()
        if not user:
            return
        data = self.read_json()
        body = str(data.get("body", "")).strip()
        if not body:
            return self.send_json({"error": "Reply body is required."}, HTTPStatus.BAD_REQUEST)
        try:
            parent_reply_id = int(data.get("parent_reply_id") or 0)
        except (TypeError, ValueError):
            parent_reply_id = 0
        try:
            uploads = save_uploads(data)
        except ValueError as error:
            return self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        first_upload = uploads[0] if uploads else {}
        with db() as conn:
            thread = conn.execute(
                """
                SELECT threads.*, users.institution author_institution,
                  users.institution_country author_institution_country,
                  users.institution_domain author_institution_domain
                FROM threads
                JOIN users ON users.id = threads.user_id
                WHERE threads.id = ?
                """,
                (thread_id,),
            ).fetchone()
            if not thread:
                for upload in uploads:
                    delete_upload(upload["path"])
                return self.send_json({"error": "Thread not found."}, HTTPStatus.NOT_FOUND)
            if safe_row_value(thread, "status", "open") in ("locked", "archived"):
                for upload in uploads:
                    delete_upload(upload["path"])
                return self.send_json({"error": "This thread is locked or archived."}, HTTPStatus.FORBIDDEN)
            if not same_school(user, school_from_thread_row(thread)):
                for upload in uploads:
                    delete_upload(upload["path"])
                return self.send_json({"error": "You can only reply within your own school."}, HTTPStatus.FORBIDDEN)
            if parent_reply_id:
                parent_reply = conn.execute(
                    "SELECT id FROM replies WHERE id = ? AND thread_id = ?",
                    (parent_reply_id, thread_id),
                ).fetchone()
                if not parent_reply:
                    for upload in uploads:
                        delete_upload(upload["path"])
                    return self.send_json({"error": "Choose a reply from this thread."}, HTTPStatus.BAD_REQUEST)
            cur = conn.execute(
                """
                INSERT INTO replies (
                  thread_id, user_id, parent_reply_id, body, attachment_path, attachment_name, attachment_type, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    thread_id, user["id"], parent_reply_id, body,
                    first_upload.get("path", ""), first_upload.get("name", ""), first_upload.get("mime_type", ""), now(),
                ),
            )
            insert_attachments(conn, "reply", cur.lastrowid, uploads)
        return self.send_json({"ok": True})

    def edit_thread(self, thread_id):
        user = self.require_forum_user()
        if not user:
            return
        data = self.read_json()
        title = str(data.get("title", "")).strip()
        body = str(data.get("body", "")).strip()
        if not title or not body:
            return self.send_json({"error": "Title and body are required."}, HTTPStatus.BAD_REQUEST)
        with db() as conn:
            thread = conn.execute(
                """
                SELECT threads.*, users.institution author_institution,
                  users.institution_country author_institution_country,
                  users.institution_domain author_institution_domain
                FROM threads
                JOIN users ON users.id = threads.user_id
                WHERE threads.id = ?
                """,
                (thread_id,),
            ).fetchone()
            if not thread:
                return self.send_json({"error": "Thread not found."}, HTTPStatus.NOT_FOUND)
            thread_school = school_from_thread_row(thread)
            if thread["user_id"] != user["id"] and not (user.get("is_school_admin") and same_school(user, thread_school)):
                return self.send_json({"error": "You cannot edit this thread."}, HTTPStatus.FORBIDDEN)
            conn.execute("UPDATE threads SET title = ?, body = ? WHERE id = ?", (title, body, thread_id))
            if user.get("is_school_admin") and thread["user_id"] != user["id"]:
                log_audit(conn, user, "edit_thread", "thread", thread_id, user["institution"], {"title": title})
        return self.get_thread(thread_id)

    def edit_reply(self, reply_id):
        user = self.require_forum_user()
        if not user:
            return
        data = self.read_json()
        body = str(data.get("body", "")).strip()
        if not body:
            return self.send_json({"error": "Reply body is required."}, HTTPStatus.BAD_REQUEST)
        with db() as conn:
            reply = conn.execute(
                """
                SELECT replies.*,
                  threads.school thread_school,
                  threads.school_country thread_school_country,
                  threads.school_domain thread_school_domain,
                  thread_users.institution thread_institution,
                  thread_users.institution_country thread_institution_country,
                  thread_users.institution_domain thread_institution_domain
                FROM replies
                JOIN threads ON threads.id = replies.thread_id
                JOIN users thread_users ON thread_users.id = threads.user_id
                WHERE replies.id = ?
                """,
                (reply_id,),
            ).fetchone()
            if not reply:
                return self.send_json({"error": "Reply not found."}, HTTPStatus.NOT_FOUND)
            thread_school = school_from_thread_row(reply, "thread")
            if reply["user_id"] != user["id"] and not (user.get("is_school_admin") and same_school(user, thread_school)):
                return self.send_json({"error": "You cannot edit this reply."}, HTTPStatus.FORBIDDEN)
            conn.execute("UPDATE replies SET body = ? WHERE id = ?", (body, reply_id))
            if user.get("is_school_admin") and reply["user_id"] != user["id"]:
                log_audit(conn, user, "edit_reply", "reply", reply_id, user["institution"], {})
        return self.send_json({"ok": True})

    def delete_reply(self, reply_id):
        user = self.require_forum_user()
        if not user:
            return
        with db() as conn:
            reply = conn.execute(
                """
                SELECT replies.*,
                  threads.school thread_school,
                  threads.school_country thread_school_country,
                  threads.school_domain thread_school_domain,
                  thread_users.institution thread_institution,
                  thread_users.institution_country thread_institution_country,
                  thread_users.institution_domain thread_institution_domain
                FROM replies
                JOIN threads ON threads.id = replies.thread_id
                JOIN users thread_users ON thread_users.id = threads.user_id
                WHERE replies.id = ?
                """,
                (reply_id,),
            ).fetchone()
            if not reply:
                return self.send_json({"error": "Reply not found."}, HTTPStatus.NOT_FOUND)
            thread_school = school_from_thread_row(reply, "thread")
            if reply["user_id"] != user["id"] and not (user.get("is_school_admin") and same_school(user, thread_school)):
                return self.send_json({"error": "You can only delete your own replies."}, HTTPStatus.FORBIDDEN)
            attachment_rows = conn.execute(
                "SELECT path FROM attachments WHERE parent_type = 'reply' AND parent_id = ?",
                (reply_id,),
            ).fetchall()
            conn.execute("DELETE FROM attachments WHERE parent_type = 'reply' AND parent_id = ?", (reply_id,))
            conn.execute("DELETE FROM replies WHERE id = ?", (reply_id,))
            if user.get("is_school_admin") and reply["user_id"] != user["id"]:
                log_audit(conn, user, "delete_reply", "reply", reply_id, user["institution"], {})
        delete_upload(safe_row_value(reply, "attachment_path"))
        delete_upload(safe_row_value(reply, "image_path"))
        for attachment in attachment_rows:
            delete_upload(attachment["path"])
        return self.send_json({"ok": True})

    def delete_thread(self, thread_id):
        user = self.require_forum_user()
        if not user:
            return
        with db() as conn:
            thread = conn.execute(
                """
                SELECT threads.*, users.institution author_institution,
                  users.institution_country author_institution_country,
                  users.institution_domain author_institution_domain
                FROM threads
                JOIN users ON users.id = threads.user_id
                WHERE threads.id = ?
                """,
                (thread_id,),
            ).fetchone()
            if not thread:
                return self.send_json({"error": "Thread not found."}, HTTPStatus.NOT_FOUND)
            thread_school = school_from_thread_row(thread)
            if thread["user_id"] != user["id"] and not (user.get("is_school_admin") and same_school(user, thread_school)):
                return self.send_json({"error": "You can only delete your own threads."}, HTTPStatus.FORBIDDEN)
            upload_paths = [safe_row_value(thread, "attachment_path"), safe_row_value(thread, "image_path")]
            replies = conn.execute("SELECT id, image_path, attachment_path FROM replies WHERE thread_id = ?", (thread_id,)).fetchall()
            reply_ids = [row["id"] for row in replies]
            upload_paths.extend(safe_row_value(row, "attachment_path") for row in replies)
            upload_paths.extend(safe_row_value(row, "image_path") for row in replies)
            attachment_rows = conn.execute(
                """
                SELECT path FROM attachments
                WHERE (parent_type = 'thread' AND parent_id = ?)
                   OR (parent_type = 'reply' AND parent_id IN (SELECT id FROM replies WHERE thread_id = ?))
                """,
                (thread_id, thread_id),
            ).fetchall()
            upload_paths.extend(row["path"] for row in attachment_rows)
            if reply_ids:
                placeholders = ",".join("?" for _ in reply_ids)
                conn.execute(f"DELETE FROM reply_supports WHERE reply_id IN ({placeholders})", reply_ids)
            conn.execute(
                """
                DELETE FROM attachments
                WHERE (parent_type = 'thread' AND parent_id = ?)
                   OR (parent_type = 'reply' AND parent_id IN (SELECT id FROM replies WHERE thread_id = ?))
                """,
                (thread_id, thread_id),
            )
            conn.execute("DELETE FROM replies WHERE thread_id = ?", (thread_id,))
            conn.execute("DELETE FROM supports WHERE thread_id = ?", (thread_id,))
            conn.execute("DELETE FROM bookmarks WHERE thread_id = ?", (thread_id,))
            conn.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
            if user.get("is_school_admin") and thread["user_id"] != user["id"]:
                log_audit(conn, user, "delete_thread", "thread", thread_id, user["institution"], {"title": thread["title"]})
        for path in upload_paths:
            delete_upload(path)
        return self.send_json({"ok": True})

    def toggle_join(self, table, thread_id):
        user = self.require_forum_user()
        if not user:
            return
        with db() as conn:
            thread = conn.execute(
                """
                SELECT threads.*, users.institution author_institution,
                  users.institution_country author_institution_country,
                  users.institution_domain author_institution_domain
                FROM threads
                JOIN users ON users.id = threads.user_id
                WHERE threads.id = ?
                """,
                (thread_id,),
            ).fetchone()
            if not thread:
                return self.send_json({"error": "Thread not found."}, HTTPStatus.NOT_FOUND)
            if not same_school(user, school_from_thread_row(thread)):
                return self.send_json({"error": "You can only interact within your own school."}, HTTPStatus.FORBIDDEN)
            existing = conn.execute(f"SELECT 1 FROM {table} WHERE thread_id = ? AND user_id = ?", (thread_id, user["id"])).fetchone()
            if existing:
                conn.execute(f"DELETE FROM {table} WHERE thread_id = ? AND user_id = ?", (thread_id, user["id"]))
                active = False
            else:
                conn.execute(f"INSERT INTO {table} (thread_id, user_id) VALUES (?, ?)", (thread_id, user["id"]))
                active = True
        return self.send_json({"active": active})

    def toggle_reply_support(self, reply_id):
        user = self.require_forum_user()
        if not user:
            return
        with db() as conn:
            reply = conn.execute(
                """
                SELECT replies.id,
                  threads.school thread_school,
                  threads.school_country thread_school_country,
                  threads.school_domain thread_school_domain,
                  thread_users.institution thread_institution,
                  thread_users.institution_country thread_institution_country,
                  thread_users.institution_domain thread_institution_domain
                FROM replies
                JOIN threads ON threads.id = replies.thread_id
                JOIN users thread_users ON thread_users.id = threads.user_id
                WHERE replies.id = ?
                """,
                (reply_id,),
            ).fetchone()
            if not reply:
                return self.send_json({"error": "Reply not found."}, HTTPStatus.NOT_FOUND)
            thread_school = school_from_thread_row(reply, "thread")
            if not same_school(user, thread_school):
                return self.send_json({"error": "You can only interact within your own school."}, HTTPStatus.FORBIDDEN)
            existing = conn.execute("SELECT 1 FROM reply_supports WHERE reply_id = ? AND user_id = ?", (reply_id, user["id"])).fetchone()
            if existing:
                conn.execute("DELETE FROM reply_supports WHERE reply_id = ? AND user_id = ?", (reply_id, user["id"]))
                active = False
            else:
                conn.execute("INSERT INTO reply_supports (reply_id, user_id) VALUES (?, ?)", (reply_id, user["id"]))
                active = True
        return self.send_json({"active": active})

    def reply_json(self, row, attachments=None):
        merged_attachments = merge_attachments(row, attachments)
        first_attachment = merged_attachments[0] if merged_attachments else {}
        return {
            "id": row["id"],
            "thread_id": row["thread_id"],
            "author_id": row["user_id"],
            "author_name": row["author_name"],
            "author_role": row["author_role"],
            "author_avatar_path": safe_row_value(row, "author_avatar_path", ""),
            "body": row["body"],
            "reply_to": {
                "id": safe_row_value(row, "parent_reply_id", 0),
                "author_name": safe_row_value(row, "reply_to_author_name", ""),
                "body": safe_row_value(row, "reply_to_body", ""),
            } if safe_row_value(row, "parent_reply_id", 0) and safe_row_value(row, "reply_to_body", "") else None,
            "attachments": merged_attachments,
            "attachment_path": first_attachment.get("path", ""),
            "attachment_name": first_attachment.get("name", ""),
            "attachment_type": first_attachment.get("type", ""),
            "image_path": safe_row_value(row, "image_path"),
            "image_name": safe_row_value(row, "image_name"),
            "created_at": fmt(row["created_at"]),
            "supports": row["supports"],
            "supported": bool(row["supported"]),
        }


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "0.0.0.0")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Studera running at http://{host}:{port}/")
    server.serve_forever()
