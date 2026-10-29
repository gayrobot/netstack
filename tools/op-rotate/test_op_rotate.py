"""Offline tests for op-rotate, with fake `op`, `security` and notifier. Run: python3 -I test_op_rotate.py"""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "op_rotate.py")
TOKEN = "ops_FAKEtokenFAKEtokenFAKEtoken0123456789"

# Fake op: logs argv, then creates a token or reads an item depending on FAKE_OP.
FAKE_OP = r'''#!/usr/bin/env python3
import os, sys
d = os.environ["FAKE_DIR"]
with open(os.path.join(d, "op.argv"), "a") as f:
    f.write(" ".join(sys.argv[1:]) + "\n")
mode = os.environ.get("FAKE_OP", "ok")
args = [a for a in sys.argv[1:]]
if "service-account" in args:
    if mode == "deny":
        sys.stderr.write("[ERROR] authorization prompt dismissed\n"); sys.exit(1)
    print("ops_garbage!" if mode == "badtoken" else "''' + TOKEN + r'''")
elif args[:1] == ["read"]:
    if mode == "noread" or not os.environ.get("OP_SERVICE_ACCOUNT_TOKEN", "").startswith("ops_"):
        sys.stderr.write("[ERROR] not found\n"); sys.exit(1)
    sys.stdout.write("pw")
'''

# Fake security: one item, stored in a file. `-i` takes the command on stdin.
FAKE_SECURITY = r'''#!/usr/bin/env python3
import os, shlex, sys
d = os.environ["FAKE_DIR"]
store = os.path.join(d, "keychain")
with open(os.path.join(d, "security.argv"), "a") as f:
    f.write(" ".join(sys.argv[1:]) + "\n")
if sys.argv[1:] == ["-i"]:
    words = shlex.split(sys.stdin.read())
    if os.environ.get("FAKE_SECURITY") == "fail":
        sys.exit(1)
    open(store, "w").write(words[words.index("-w") + 1])
elif sys.argv[1] == "find-generic-password":
    if not os.path.exists(store):
        sys.exit(44)
    print(open(store).read())
'''

FAKE_NOTIFY = r'''#!/bin/sh
printf '%s\n' "$1" >> "$FAKE_DIR/notify.out"
'''

CONFIG = """base_name=testRO
vault=testRO
keychain_service=test-op-token
verify_ref=op://testRO/item/password
"""


class RotateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        self.state = os.path.join(self.d, "state")
        os.makedirs(self.state)
        for name, body in (("op", FAKE_OP), ("security", FAKE_SECURITY), ("notifier", FAKE_NOTIFY)):
            p = os.path.join(self.d, name)
            with open(p, "w") as f:
                f.write(body)
            os.chmod(p, 0o755)
        with open(os.path.join(self.state, "config"), "w") as f:
            f.write(CONFIG)
        with open(os.path.join(self.d, "keychain"), "w") as f:
            f.write("ops_OLDtokenOLDtokenOLDtokenOLD")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, today="2027-01-20", **env):
        e = dict(os.environ, FAKE_DIR=self.d, OP_ROTATE_DIR=self.state, OP_ROTATE_TODAY=today,
                 OP_ROTATE_OP=os.path.join(self.d, "op"), OP_ROTATE_SECURITY=os.path.join(self.d, "security"),
                 OP_ROTATE_NOTIFY=os.path.join(self.d, "notifier"), **env)
        return subprocess.run([sys.executable, "-I", SCRIPT, *args], env=e, capture_output=True, text=True)

    def read(self, name):
        p = os.path.join(self.d, name) if name in ("keychain", "op.argv", "security.argv", "notify.out") \
            else os.path.join(self.state, name)
        return open(p).read() if os.path.exists(p) else ""

    def seed(self, expires="2027-01-27"):
        self.assertEqual(self.run_cli("seed", "testRO-20261029", expires).returncode, 0)

    def assert_token_not_leaked(self):
        for name in ("op.argv", "security.argv", "notify.out", "state", "rotate.log"):
            self.assertNotIn(TOKEN, self.read(name), name)

    def test_not_due_does_nothing(self):
        self.seed()
        r = self.run_cli("check", today="2026-12-01")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read("op.argv"), "")
        self.assertEqual(self.read("notify.out"), "")

    def test_due_rotates(self):
        self.seed()
        r = self.run_cli("check")  # 7 days left
        self.assertEqual(r.returncode, 0, r.stderr)
        argv = self.read("op.argv").splitlines()
        self.assertEqual(argv[0], "service-account create testRO-20270120 --vault testRO:read_items "
                                  "--expires-in 90d --raw")
        self.assertEqual(argv[1], "read --no-newline op://testRO/item/password")
        self.assertEqual(self.read("keychain"), TOKEN)
        state = self.read("state")
        self.assertIn("name=testRO-20270120", state)
        self.assertIn("expires=2027-04-20", state)
        self.assertIn("previous=testRO-20261029", state)
        self.assertIn("last_result=ok", state)
        self.assertIn("approve the 1Password prompt", self.read("notify.out"))
        self.assertIn("testRO-20261029 in the 1Password web app", self.read("notify.out"))
        self.assert_token_not_leaked()

    def test_account_flag(self):
        self.seed()
        with open(os.path.join(self.state, "config"), "a") as f:
            f.write("account=my.1password.com\n")
        self.assertEqual(self.run_cli("check").returncode, 0)
        self.assertTrue(self.read("op.argv").startswith("--account my.1password.com service-account create"))

    def test_rotate_now_marker(self):
        self.seed()
        open(os.path.join(self.state, "rotate-now"), "w").close()
        self.assertEqual(self.run_cli("check", today="2026-10-30").returncode, 0)
        self.assertEqual(self.read("keychain"), TOKEN)
        self.assertFalse(os.path.exists(os.path.join(self.state, "rotate-now")))

    def test_denied_prompt_keeps_old_token(self):
        self.seed()
        r = self.run_cli("check", FAKE_OP="deny")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.read("keychain"), "ops_OLDtokenOLDtokenOLDtokenOLD")
        self.assertIn("last_result=failed: could not create", self.read("state"))
        self.assertIn("expires=2027-01-27", self.read("state"))
        self.assertIn("prompt dismissed", self.read("rotate.log"))
        self.assertIn("tries again tomorrow", self.read("notify.out"))

    def test_bad_token_not_saved(self):
        self.seed()
        self.assertEqual(self.run_cli("check", FAKE_OP="badtoken").returncode, 1)
        self.assertEqual(self.read("keychain"), "ops_OLDtokenOLDtokenOLDtokenOLD")

    def test_new_token_that_cannot_read_is_not_saved(self):
        self.seed()
        self.assertEqual(self.run_cli("check", FAKE_OP="noread").returncode, 1)
        self.assertEqual(self.read("keychain"), "ops_OLDtokenOLDtokenOLDtokenOLD")
        self.assertIn("could not read the check item", self.read("state"))
        self.assert_token_not_leaked()

    def test_keychain_write_failure(self):
        self.seed()
        self.assertEqual(self.run_cli("check", FAKE_SECURITY="fail").returncode, 1)
        self.assertIn("could not save the new token", self.read("state"))
        self.assertIn("expires=2027-01-27", self.read("state"))

    def test_status_hook(self):
        self.assertEqual(self.run_cli("status", "--hook").stdout, "")  # not set up: silent
        self.seed()
        self.assertEqual(self.run_cli("status", "--hook", today="2026-12-01").stdout, "")
        self.assertIn("expires in 7 days", self.run_cli("status", "--hook").stdout)
        self.assertIn("EXPIRED", self.run_cli("status", "--hook", today="2027-02-01").stdout)
        self.run_cli("check", FAKE_OP="deny")
        self.assertIn("Last attempt: failed", self.run_cli("status", "--hook").stdout)

    def test_bad_config_refused(self):
        with open(os.path.join(self.state, "config"), "w") as f:
            f.write(CONFIG.replace("vault=testRO", 'vault=x" -w "evil'))
        r = self.run_cli("rotate")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.read("op.argv"), "")

    def test_plist(self):
        r = self.run_cli("plist")
        self.assertIn("<string>check</string>", r.stdout)
        self.assertIn("local.netstack.op-rotate", r.stdout)


if __name__ == "__main__":
    unittest.main()
