#!/usr/bin/env python3
import http.cookiejar
import base64
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server


class Client:
    def __init__(self, base):
        self.base = base
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def request(self, method, path, payload=None):
        body = None if payload is None else json.dumps(payload).encode()
        req = urllib.request.Request(
            self.base + path,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with self.opener.open(req, timeout=5) as response:
                return response.status, json.loads(response.read().decode() or "{}")
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read().decode() or "{}")


class StuderaPrivacyTests(unittest.TestCase):
    SITE_ADMIN_EMAIL = "admin@studera.local"
    SITE_ADMIN_PASSWORD = "test-site-admin-password"

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["STUDERA_SITE_ADMIN_EMAIL"] = cls.SITE_ADMIN_EMAIL
        os.environ["STUDERA_SITE_ADMIN_PASSWORD"] = cls.SITE_ADMIN_PASSWORD
        os.environ["STUDERA_SECONDARY_SITE_ADMIN_EMAIL"] = "studeraadmin@gmail.com"
        os.environ["STUDERA_SECONDARY_SITE_ADMIN_PASSWORD"] = "test-secondary-site-admin-password"
        server.DB_PATH = os.path.join(cls.tmp.name, "studera-test.db")
        server.UPLOADS_DIR = os.path.join(cls.tmp.name, "uploads")
        server.EMAIL_DEV_LOG = True
        server.RATE_LIMITS.clear()
        server.init_db()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def register_verified(self, email, institution, domain="", curricula="AP Curriculum|SAT / ACT"):
        client = Client(self.base)
        status, data = client.request("POST", "/api/auth/register", {
            "name": email.split("@")[0],
            "email": email,
            "password": "strongpass123",
            "institution": institution,
            "institution_country": "Test",
            "institution_domain": domain,
            "curricula": curricula,
            "role": "student",
        })
        self.assertEqual(status, 200, data)
        self.assertTrue(data["requires_verification"])
        with server.db() as conn:
            token = conn.execute(
                "SELECT token FROM pending_registrations WHERE email = ?",
                (email,),
            ).fetchone()["token"]
        status, data = client.request("POST", "/api/auth/verify", {"token": token})
        self.assertEqual(status, 200, data)
        return client

    def test_site_admin_cannot_access_forums(self):
        client = Client(self.base)
        status, data = client.request("POST", "/api/auth/login", {
            "email": self.SITE_ADMIN_EMAIL,
            "password": self.SITE_ADMIN_PASSWORD,
        })
        self.assertEqual(status, 200, data)
        status, data = client.request("GET", "/api/threads")
        self.assertEqual(status, 403)
        self.assertIn("Site admins cannot access school forums", data["error"])

    def test_password_hashes_are_versioned_and_legacy_hashes_upgrade(self):
        salt, digest = server.hash_password("complex-passphrase-123")
        self.assertTrue(digest.startswith(f"{server.PASSWORD_HASH_ALGORITHM}${server.PASSWORD_HASH_ITERATIONS}$"))
        self.assertTrue(server.verify_password("complex-passphrase-123", salt, digest))

        self.register_verified("legacy-hash@example-r.edu", "Example R School", "example-r.edu")
        legacy_salt = "legacytestsalt"
        legacy_digest = server.pbkdf2_digest("strongpass123", legacy_salt, server.LEGACY_PASSWORD_HASH_ITERATIONS, "plain")
        with server.db() as conn:
            conn.execute(
                "UPDATE users SET salt = ?, password_hash = ? WHERE email = ?",
                (legacy_salt, legacy_digest, "legacy-hash@example-r.edu"),
            )
        client = Client(self.base)
        status, data = client.request("POST", "/api/auth/login", {
            "email": "legacy-hash@example-r.edu",
            "password": "strongpass123",
        })
        self.assertEqual(status, 200, data)
        with server.db() as conn:
            row = conn.execute("SELECT password_hash FROM users WHERE email = ?", ("legacy-hash@example-r.edu",)).fetchone()
        self.assertTrue(row["password_hash"].startswith(f"{server.PASSWORD_HASH_ALGORITHM}${server.PASSWORD_HASH_ITERATIONS}$"))

    def test_unverified_user_cannot_login_until_email_verified(self):
        client = Client(self.base)
        status, data = client.request("POST", "/api/auth/register", {
            "name": "Unverified User",
            "email": "unverified@example-m.edu",
            "password": "strongpass123",
            "institution": "Example M School",
            "institution_country": "Test",
            "institution_domain": "example-m.edu",
            "curricula": "AP Curriculum",
            "role": "student",
        })
        self.assertEqual(status, 200, data)
        self.assertTrue(data["requires_verification"])

        status, data = client.request("POST", "/api/auth/login", {
            "email": "unverified@example-m.edu",
            "password": "strongpass123",
        })
        self.assertEqual(status, 401, data)

        status, data = client.request("GET", "/api/session")
        self.assertEqual(status, 200, data)
        self.assertIsNone(data["user"])

        with server.db() as conn:
            self.assertIsNone(conn.execute("SELECT id FROM users WHERE email = ?", ("unverified@example-m.edu",)).fetchone())
            token = conn.execute(
                "SELECT token FROM pending_registrations WHERE email = ?",
                ("unverified@example-m.edu",),
            ).fetchone()["token"]
        status, data = client.request("POST", "/api/auth/verify", {"token": token})
        self.assertEqual(status, 200, data)
        self.assertTrue(data["user"]["email_verified"])

        status, data = client.request("GET", "/api/session")
        self.assertEqual(status, 200, data)
        self.assertEqual(data["user"]["email"], "unverified@example-m.edu")

    def test_new_accounts_are_never_school_admins_by_email(self):
        client = Client(self.base)
        status, data = client.request("POST", "/api/auth/register", {
            "name": "Tyler Yi",
            "email": "yi46635@sas.edu.sg",
            "password": "strongpass123",
            "institution": "Singapore American School",
            "institution_country": "Singapore",
            "institution_domain": "sas.edu.sg",
            "curricula": "AP Curriculum|SAT / ACT",
            "role": "student",
        })
        self.assertEqual(status, 200, data)
        self.assertTrue(data["requires_verification"])
        with server.db() as conn:
            self.assertIsNone(conn.execute(
                "SELECT id FROM users WHERE email = ?",
                ("yi46635@sas.edu.sg",),
            ).fetchone())
            token = conn.execute(
                "SELECT token FROM pending_registrations WHERE email = ?",
                ("yi46635@sas.edu.sg",),
            ).fetchone()["token"]
        status, data = client.request("POST", "/api/auth/verify", {"token": token})
        self.assertEqual(status, 200, data)
        with server.db() as conn:
            row = conn.execute(
                "SELECT is_school_admin, is_site_admin, email_verified FROM users WHERE email = ?",
                ("yi46635@sas.edu.sg",),
            ).fetchone()
        self.assertEqual(row["is_school_admin"], 0)
        self.assertEqual(row["is_site_admin"], 0)
        self.assertEqual(row["email_verified"], 1)

    def test_users_cannot_cross_school_read_threads(self):
        school_a = self.register_verified("alice@example-a.edu", "Example A School", "example-a.edu")
        status, data = school_a.request("POST", "/api/threads", {
            "title": "School A thread",
            "body": "Only School A should see this.",
            "curriculum": "AP Curriculum",
            "section": "AP Biology",
        })
        self.assertEqual(status, 200, data)
        thread_id = data["thread"]["id"]

        school_b = self.register_verified("bob@example-b.edu", "Example B School", "example-b.edu", "IB Diploma")
        status, data = school_b.request("GET", f"/api/threads/{thread_id}")
        self.assertEqual(status, 404)

    def test_thread_uploads_are_served_from_configured_upload_directory(self):
        client = self.register_verified("upload-author@example-v.edu", "Example V School", "example-v.edu")
        encoded = base64.b64encode(b"Studera upload fixture").decode()
        status, data = client.request("POST", "/api/threads", {
            "title": "Upload fixture",
            "body": "Testing upload serving.",
            "curriculum": "AP Curriculum",
            "section": "AP Biology",
            "files": [{
                "file_name": "fixture.txt",
                "file_data": f"data:text/plain;base64,{encoded}",
            }],
        })
        self.assertEqual(status, 200, data)
        path = data["thread"]["attachments"][0]["path"]
        self.assertTrue(path.startswith("uploads/"))
        self.assertTrue(os.path.exists(os.path.join(server.UPLOADS_DIR, os.path.basename(path))))
        with urllib.request.urlopen(f"{self.base}/{path}", timeout=5) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), b"Studera upload fixture")

    def test_school_admin_cannot_moderate_other_school(self):
        school_a = self.register_verified("moderated@example-c.edu", "Example C School", "example-c.edu")
        status, data = school_a.request("POST", "/api/threads", {
            "title": "Protected thread",
            "body": "Another school admin must not delete this.",
            "curriculum": "AP Curriculum",
            "section": "AP Biology",
        })
        self.assertEqual(status, 200, data)
        thread_id = data["thread"]["id"]

        other_admin = self.register_verified("admin@example-d.edu", "Example D School", "example-d.edu")
        with server.db() as conn:
            conn.execute("UPDATE users SET is_school_admin = 1 WHERE email = ?", ("admin@example-d.edu",))
        status, data = other_admin.request("DELETE", f"/api/threads/{thread_id}")
        self.assertEqual(status, 403)

    def test_school_admin_can_delete_member_with_delete_confirmation(self):
        member = self.register_verified("member-delete@example-s.edu", "Example S School", "example-s.edu")
        status, data = member.request("POST", "/api/threads", {
            "title": "Delete cleanup thread",
            "body": "This content should be removed with the account.",
            "curriculum": "AP Curriculum",
            "section": "AP Biology",
        })
        self.assertEqual(status, 200, data)
        thread_id = data["thread"]["id"]
        admin = self.register_verified("delete-admin@example-s.edu", "Example S School", "example-s.edu")
        with server.db() as conn:
            conn.execute("UPDATE users SET is_school_admin = 1 WHERE email = ?", ("delete-admin@example-s.edu",))

        status, data = admin.request("POST", "/api/admin/members/delete", {
            "email": "member-delete@example-s.edu",
            "confirm": "delete",
        })
        self.assertEqual(status, 400)

        status, data = admin.request("POST", "/api/admin/members/delete", {
            "email": "member-delete@example-s.edu",
            "confirm": "DELETE",
        })
        self.assertEqual(status, 200, data)
        with server.db() as conn:
            self.assertIsNone(conn.execute("SELECT id FROM users WHERE email = ?", ("member-delete@example-s.edu",)).fetchone())
            self.assertIsNone(conn.execute("SELECT id FROM threads WHERE id = ?", (thread_id,)).fetchone())
            audit = conn.execute("SELECT action FROM audit_logs WHERE action = 'delete_member_account'").fetchone()
        self.assertIsNotNone(audit)

    def test_school_admin_cannot_delete_cross_school_member(self):
        self.register_verified("cross-delete@example-t.edu", "Example T School", "example-t.edu")
        admin = self.register_verified("delete-admin@example-u.edu", "Example U School", "example-u.edu")
        with server.db() as conn:
            conn.execute("UPDATE users SET is_school_admin = 1 WHERE email = ?", ("delete-admin@example-u.edu",))
        status, data = admin.request("POST", "/api/admin/members/delete", {
            "email": "cross-delete@example-t.edu",
            "confirm": "DELETE",
        })
        self.assertEqual(status, 403)

    def test_thread_author_cannot_lock_or_reopen_thread(self):
        author = self.register_verified("author@example-e.edu", "Example E School", "example-e.edu")
        status, data = author.request("POST", "/api/threads", {
            "title": "Author owned thread",
            "body": "The author can mark a solution, but cannot lock the thread.",
            "curriculum": "AP Curriculum",
            "section": "AP Biology",
        })
        self.assertEqual(status, 200, data)
        thread_id = data["thread"]["id"]

        status, data = author.request("POST", f"/api/threads/{thread_id}/status", {"status": "locked"})
        self.assertEqual(status, 403)

    def test_school_admin_can_lock_and_reopen_thread(self):
        author = self.register_verified("student@example-f.edu", "Example F School", "example-f.edu")
        status, data = author.request("POST", "/api/threads", {
            "title": "Admin managed thread",
            "body": "School admins can lock and reopen this.",
            "curriculum": "AP Curriculum",
            "section": "AP Biology",
        })
        self.assertEqual(status, 200, data)
        thread_id = data["thread"]["id"]

        admin = self.register_verified("admin@example-f.edu", "Example F School", "example-f.edu")
        with server.db() as conn:
            conn.execute("UPDATE users SET is_school_admin = 1 WHERE email = ?", ("admin@example-f.edu",))
        status, data = admin.request("POST", f"/api/threads/{thread_id}/status", {"status": "locked"})
        self.assertEqual(status, 200, data)
        status, data = admin.request("POST", f"/api/threads/{thread_id}/status", {"status": "open"})
        self.assertEqual(status, 200, data)

    def test_report_thread_and_admin_queue_status(self):
        author = self.register_verified("report-author@example-n.edu", "Example N School", "example-n.edu")
        status, data = author.request("POST", "/api/threads", {
            "title": "Reportable thread",
            "body": "This is reportable content for testing.",
            "curriculum": "AP Curriculum",
            "section": "AP Biology",
        })
        self.assertEqual(status, 200, data)
        thread_id = data["thread"]["id"]

        reporter = self.register_verified("reporter@example-n.edu", "Example N School", "example-n.edu")
        status, data = reporter.request("POST", "/api/reports", {
            "target_type": "thread",
            "target_id": thread_id,
            "reason": "Spam or vandalism\nThis looks like a test report.",
        })
        self.assertEqual(status, 200, data)

        admin = self.register_verified("report-admin@example-n.edu", "Example N School", "example-n.edu")
        with server.db() as conn:
            conn.execute("UPDATE users SET is_school_admin = 1 WHERE email = ?", ("report-admin@example-n.edu",))
        status, data = admin.request("GET", "/api/admin/reports")
        self.assertEqual(status, 200, data)
        self.assertEqual(len(data["reports"]), 1)
        self.assertEqual(data["reports"][0]["thread_id"], thread_id)
        self.assertIn("Spam or vandalism", data["reports"][0]["reason"])

        report_id = data["reports"][0]["id"]
        status, data = admin.request("POST", "/api/admin/reports/status", {
            "id": report_id,
            "status": "reviewing",
        })
        self.assertEqual(status, 200, data)

        status, data = admin.request("GET", "/api/admin/reports")
        self.assertEqual(status, 200, data)
        self.assertEqual(data["reports"][0]["status"], "reviewing")

    def test_report_reply_and_cross_school_report_blocked(self):
        author = self.register_verified("reply-report-author@example-o.edu", "Example O School", "example-o.edu")
        status, data = author.request("POST", "/api/threads", {
            "title": "Reply report thread",
            "body": "A thread with a reply.",
            "curriculum": "AP Curriculum",
            "section": "AP Biology",
        })
        self.assertEqual(status, 200, data)
        thread_id = data["thread"]["id"]
        status, data = author.request("POST", f"/api/threads/{thread_id}/replies", {
            "body": "This reply can be reported.",
        })
        self.assertEqual(status, 200, data)
        with server.db() as conn:
            reply_id = conn.execute("SELECT id FROM replies WHERE thread_id = ? ORDER BY id DESC", (thread_id,)).fetchone()["id"]

        reporter = self.register_verified("reply-reporter@example-o.edu", "Example O School", "example-o.edu")
        status, data = reporter.request("POST", "/api/reports", {
            "target_type": "reply",
            "target_id": reply_id,
            "reason": "Inappropriate\nThis reply should be reviewed.",
        })
        self.assertEqual(status, 200, data)

        other_school = self.register_verified("other-reporter@example-p.edu", "Example P School", "example-p.edu")
        status, data = other_school.request("POST", "/api/reports", {
            "target_type": "reply",
            "target_id": reply_id,
            "reason": "Something else\nTrying to report outside my school.",
        })
        self.assertEqual(status, 403)
        self.assertIn("own school", data["error"])

    def test_threads_stay_with_original_school_after_author_moves(self):
        author = self.register_verified("moving-author@example-g.edu", "Example G School", "example-g.edu")
        status, data = author.request("POST", "/api/threads", {
            "title": "Original school thread",
            "body": "This should remain in Example G.",
            "curriculum": "AP Curriculum",
            "section": "AP Biology",
        })
        self.assertEqual(status, 200, data)
        thread_id = data["thread"]["id"]

        status, data = author.request("POST", "/api/settings/school", {
            "institution": "Example H School",
            "institution_country": "Test",
            "institution_domain": "example-h.edu",
            "curricula": "IB Diploma",
        })
        self.assertEqual(status, 200, data)

        old_school_peer = self.register_verified("peer@example-g.edu", "Example G School", "example-g.edu")
        status, data = old_school_peer.request("GET", f"/api/threads/{thread_id}")
        self.assertEqual(status, 200, data)

        status, data = author.request("GET", f"/api/threads/{thread_id}")
        self.assertEqual(status, 404)

    def test_only_school_admin_cannot_change_school_or_delete_account(self):
        admin = self.register_verified("only-admin@example-i.edu", "Example I School", "example-i.edu")
        with server.db() as conn:
            conn.execute("UPDATE users SET is_school_admin = 1 WHERE email = ?", ("only-admin@example-i.edu",))

        status, data = admin.request("POST", "/api/settings/school", {
            "institution": "Example J School",
            "institution_country": "Test",
            "institution_domain": "example-j.edu",
            "curricula": "IB Diploma",
        })
        self.assertEqual(status, 403)
        self.assertIn("Assign another school admin", data["error"])

        status, data = admin.request("POST", "/api/settings/delete-account", {"confirm": "DELETE"})
        self.assertEqual(status, 403)
        self.assertIn("Assign another school admin", data["error"])

    def test_school_admin_can_define_custom_curriculum_sections(self):
        admin = self.register_verified("custom-admin@example-l.edu", "Example L School", "example-l.edu")
        with server.db() as conn:
            conn.execute("UPDATE users SET is_school_admin = 1 WHERE email = ?", ("custom-admin@example-l.edu",))

        status, data = admin.request("POST", "/api/admin/school", {
            "curricula": ["AP Curriculum"],
            "custom_curricula": [
                {"name": "SAS Independent Study", "sections": ["Robotics Lab", "Advanced Journalism"]},
            ],
            "guidelines": "",
        })
        self.assertEqual(status, 200, data)
        self.assertIn("SAS Independent Study", data["school"]["curricula"])
        self.assertEqual(data["school"]["custom_curricula"][0]["sections"], ["Robotics Lab", "Advanced Journalism"])

        status, data = admin.request("GET", "/api/session")
        self.assertEqual(status, 200, data)
        self.assertIn("SAS Independent Study", data["user"]["curricula"])
        self.assertEqual(data["school"]["custom_curricula"][0]["name"], "SAS Independent Study")

        status, data = admin.request("POST", "/api/threads", {
            "title": "Robotics build notes",
            "body": "Can we compare drivetrain tradeoffs?",
            "curriculum": "SAS Independent Study",
            "section": "Robotics Lab",
        })
        self.assertEqual(status, 200, data)

        status, data = admin.request("POST", "/api/threads", {
            "title": "Wrong class",
            "body": "This should fail.",
            "curriculum": "SAS Independent Study",
            "section": "Unlisted Seminar",
        })
        self.assertEqual(status, 403)
        self.assertIn("Choose a section", data["error"])

    def test_site_admin_cannot_revoke_only_school_admin(self):
        self.register_verified("sole-school-admin@example-k.edu", "Example K School", "example-k.edu")
        with server.db() as conn:
            conn.execute("UPDATE users SET is_school_admin = 1 WHERE email = ?", ("sole-school-admin@example-k.edu",))
        site_admin = Client(self.base)
        status, data = site_admin.request("POST", "/api/auth/login", {
            "email": self.SITE_ADMIN_EMAIL,
            "password": self.SITE_ADMIN_PASSWORD,
        })
        self.assertEqual(status, 200, data)

        status, data = site_admin.request("POST", "/api/site-admin/school-admins/revoke", {
            "email": "sole-school-admin@example-k.edu",
        })
        self.assertEqual(status, 403)
        self.assertIn("Assign another school admin", data["error"])

    def test_only_site_admin_cannot_delete_account(self):
        with server.db() as conn:
            conn.execute("UPDATE users SET is_site_admin = 0 WHERE email = ?", ("studeraadmin@gmail.com",))
        client = Client(self.base)
        status, data = client.request("POST", "/api/auth/login", {
            "email": self.SITE_ADMIN_EMAIL,
            "password": self.SITE_ADMIN_PASSWORD,
        })
        self.assertEqual(status, 200, data)

        status, data = client.request("POST", "/api/settings/delete-account", {"confirm": "DELETE"})
        self.assertEqual(status, 403)
        self.assertIn("Assign another site admin", data["error"])


if __name__ == "__main__":
    unittest.main()
