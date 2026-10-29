"""Offline tests: DSM responses are faked, nothing reaches a NAS. Run: python3 -I test_server.py"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server  # noqa: E402

ENV = {"NAS_URL": "https://nas.test:5001", "NAS_PIN": "sha256//AAAA", "NAS_USER": "agent",
       "NAS_PASSWORD_COMMAND": "/usr/bin/true"}
INSTALLED = {"packages": [{"id": "PHP8.2", "name": "PHP 8.2", "version": "8.2.30-0100",
                           "additional": {"status": "running"}},
                          {"id": "Calendar", "name": "Calendar", "version": "3.0.4-21435"}]}
SERVER = {"packages": [{"id": "PHP8.2", "version": "8.2.35-0171", "md5": "abc", "size": 123,
                        "link": "https://global.download.synology.com/download/Package/spk/PHP8.2.spk"},
                       {"id": "Calendar", "version": "3.0.4-21435", "md5": "def", "size": 9,
                        "link": "https://global.download.synology.com/x.spk"}]}


class FakeDSM:
    def __init__(self, server_list=SERVER):
        self.calls = []
        self.server_list = server_list
        self.upgraded = False

    def __call__(self, inst, params):
        key = (params["api"], params["method"])
        self.calls.append(key)
        if key == ("SYNO.Core.Package", "list"):
            if self.upgraded:
                return {"packages": [dict(INSTALLED["packages"][0], version="8.2.35-0171")]}
            return INSTALLED
        if key == ("SYNO.Core.Package.Server", "list"):
            return self.server_list
        if key == ("SYNO.Core.Package.Installation", "install"):
            return {"taskid": "t1"}
        if key == ("SYNO.Core.Package.Installation", "status"):
            return {"finished": True}
        if key == ("SYNO.Core.Package.Installation", "upgrade"):
            self.upgraded = True
        return {}


def run(fake, tool, args):
    with mock.patch.dict(os.environ, ENV), \
         mock.patch.object(server.DSM, "__enter__", lambda self: self), \
         mock.patch.object(server.DSM, "__exit__", lambda self, *e: None), \
         mock.patch.object(server.DSM, "call", lambda self, p: fake(self, p)):
        return server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                              "params": {"name": tool, "arguments": args}})["result"]


class Tests(unittest.TestCase):
    def test_tools_list_has_exactly_two_tools(self):
        r = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual(sorted(t["name"] for t in r["result"]["tools"]), ["package_list", "package_upgrade"])
        for t in r["result"]["tools"]:
            self.assertNotIn("base_url", str(t["inputSchema"]))

    def test_list_flags_upgrades(self):
        r = run(FakeDSM(), "package_list", {})
        self.assertFalse(r["isError"])
        self.assertIn('"upgrade_available": true', r["content"][0]["text"])

    def test_upgrade_defaults_to_dry_run(self):
        fake = FakeDSM()
        r = run(fake, "package_upgrade", {"package_id": "PHP8.2"})
        self.assertIn("dry run", r["content"][0]["text"])
        self.assertNotIn(("SYNO.Core.Package.Installation", "install"), fake.calls)

    def test_upgrade_applies_when_asked(self):
        fake = FakeDSM()
        r = run(fake, "package_upgrade", {"package_id": "PHP8.2", "dry_run": False})
        self.assertIn('"result": "upgraded"', r["content"][0]["text"])
        self.assertIn(("SYNO.Core.Package.Installation", "upgrade"), fake.calls)

    def test_current_package_is_left_alone(self):
        fake = FakeDSM()
        r = run(fake, "package_upgrade", {"package_id": "Calendar", "dry_run": False})
        self.assertIn("already current", r["content"][0]["text"])
        self.assertNotIn(("SYNO.Core.Package.Installation", "install"), fake.calls)

    def test_refuses_install_of_missing_package(self):
        r = run(FakeDSM(), "package_upgrade", {"package_id": "MailStation", "dry_run": False})
        self.assertTrue(r["isError"])
        self.assertIn("not installed", r["content"][0]["text"])

    def test_refuses_non_synology_download(self):
        evil = {"packages": [dict(SERVER["packages"][0], link="https://evil.example/synology.com.spk")]}
        r = run(FakeDSM(evil), "package_upgrade", {"package_id": "PHP8.2", "dry_run": False})
        self.assertTrue(r["isError"])
        self.assertIn("not a Synology package server", r["content"][0]["text"])

    def test_lookalike_host_refused(self):
        evil = {"packages": [dict(SERVER["packages"][0], link="https://notsynology.com/x.spk")]}
        r = run(FakeDSM(evil), "package_upgrade", {"package_id": "PHP8.2", "dry_run": False})
        self.assertTrue(r["isError"])

    def test_bad_package_id_refused(self):
        r = run(FakeDSM(), "package_upgrade", {"package_id": "../../etc"})
        self.assertTrue(r["isError"])

    def test_missing_config_refused(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            r = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                               "params": {"name": "package_list", "arguments": {}}})["result"]
        self.assertTrue(r["isError"])

    def test_every_tool_checked_against_pinned_upstream(self):
        # Tripwire for the overlap rule (docs/vetting/synology-mcp-upgrades.md): bump CHECKED_AGAINST only after rechecking overlap.
        lock_in = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "..", "docs", "vetting", "locks", "mcp-server-synology.in")
        with open(lock_in) as f:
            pins = [l.split("==", 1)[1].strip() for l in f if l.startswith("mcp-server-synology==")]
        self.assertEqual(len(pins), 1, "expected exactly one mcp-server-synology== pin")
        self.assertEqual(set(server.CHECKED_AGAINST), set(server.TOOLS), "every tool needs a CHECKED_AGAINST entry")
        stale = {t: v for t, v in server.CHECKED_AGAINST.items() if v != pins[0]}
        self.assertFalse(stale, f"mcp-server-synology is pinned at {pins[0]}; recheck these tools for overlap "
                                f"(docs/vetting/synology-mcp-upgrades.md), then bump CHECKED_AGAINST: {stale}")

    def test_version_compare(self):
        self.assertGreater(server.version_key("8.2.35-0171"), server.version_key("8.2.30-0100"))
        self.assertGreater(server.version_key("30000002.3.19-20333"), server.version_key("30000002.3.18-20000"))


if __name__ == "__main__":
    unittest.main()
