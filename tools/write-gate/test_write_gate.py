"""Offline tests for write-gate. Run: python3 -I test_write_gate.py"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import write_gate  # noqa: E402

GATE = os.path.join(HERE, "write_gate.py")


class GateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.tmp.name, "sub", "writes-on-until")
        self.env = mock.patch.dict(os.environ, {"WRITE_GATE_FILE": self.state})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def run_gate(self, *args, stdin=""):
        env = dict(os.environ, WRITE_GATE_FILE=self.state)
        return subprocess.run([sys.executable, "-I", GATE, *args], input=stdin, capture_output=True,
                              text=True, env=env, timeout=10)

    def test_off_by_default(self):
        self.assertIsNone(write_gate.on_until())

    def test_on_then_off(self):
        until = write_gate.turn_on(30)
        self.assertAlmostEqual(until, time.time() + 1800, delta=5)
        self.assertEqual(write_gate.on_until(), until)
        write_gate.turn_off()
        self.assertIsNone(write_gate.on_until())

    def test_window_expires(self):
        until = write_gate.turn_on(1)
        self.assertIsNone(write_gate.on_until(now=until + 1))

    def test_limits(self):
        for bad in (0, -5, write_gate.MAX_MINUTES + 1):
            with self.assertRaises(ValueError):
                write_gate.turn_on(bad)

    def test_garbage_state_is_off(self):
        os.makedirs(os.path.dirname(self.state))
        with open(self.state, "w") as f:
            f.write("not a number")
        self.assertIsNone(write_gate.on_until())

    def test_off_serves_stand_in_without_running_command(self):
        marker = os.path.join(self.tmp.name, "ran")
        msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "anything"}}]
        out = self.run_gate("run", "--", "/usr/bin/touch", marker,
                            stdin="".join(json.dumps(m) + "\n" for m in msgs))
        replies = [json.loads(line) for line in out.stdout.splitlines()]
        self.assertEqual([r["id"] for r in replies], [1, 2, 3])
        self.assertEqual(replies[0]["result"]["protocolVersion"], "2025-03-26")
        self.assertIn("write-gate on", replies[0]["result"]["instructions"])
        self.assertEqual(replies[1]["result"], {"tools": []})
        self.assertIn("error", replies[2])
        self.assertFalse(os.path.exists(marker))

    def test_on_runs_real_command(self):
        write_gate.turn_on(5)
        marker = os.path.join(self.tmp.name, "ran")
        out = self.run_gate("run", "--", "/usr/bin/touch", marker)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertTrue(os.path.exists(marker))

    def test_cli_status(self):
        self.assertIn("off", self.run_gate("status").stdout)
        self.run_gate("on", "15")
        self.assertIn("on until", self.run_gate("status").stdout)
        self.run_gate("off")
        self.assertIn("off", self.run_gate("status").stdout)


if __name__ == "__main__":
    unittest.main()
