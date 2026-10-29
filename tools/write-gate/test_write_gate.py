"""Offline tests for write-gate, against a fake MCP server. Run: python3 -I test_write_gate.py"""
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import write_gate  # noqa: E402

GATE = os.path.join(HERE, "write_gate.py")
NAME = "test-write"

# A stand-in for the real write server: logs each launch, then serves one tool.
FAKE_SERVER = r'''
import json, sys
with open(sys.argv[1], "a") as f:
    f.write("launched\n")
if len(sys.argv) > 2 and sys.argv[2] == "die":
    sys.exit(1)
for line in sys.stdin:
    msg = json.loads(line)
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:
        continue
    if method == "initialize":
        result = {"protocolVersion": msg["params"]["protocolVersion"], "capabilities": {"tools": {}},
                  "serverInfo": {"name": "fake", "version": "1"}}
    elif method == "tools/list":
        result = {"tools": [{"name": "rename_device", "inputSchema": {"type": "object"}}]}
    elif method == "tools/call":
        result = {"content": [{"type": "text", "text": "renamed"}]}
    else:
        result = {}
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": result}) + "\n")
    sys.stdout.flush()
'''


class StateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"WRITE_GATE_DIR": os.path.join(self.tmp.name, "gate")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_off_by_default(self):
        self.assertIsNone(write_gate.on_until(NAME))

    def test_on_then_off(self):
        until = write_gate.turn_on(NAME, 30)
        self.assertAlmostEqual(until, time.time() + 1800, delta=5)
        self.assertEqual(write_gate.read_window(NAME), (until, None))
        write_gate.turn_off()
        self.assertIsNone(write_gate.on_until(NAME))

    def test_window_for_one_session(self):
        until = write_gate.turn_on(NAME, 5, session=4242)
        self.assertEqual(write_gate.read_window(NAME), (until, 4242))

    def test_window_expires(self):
        until = write_gate.turn_on(NAME, 1)
        self.assertIsNone(write_gate.on_until(NAME, now=until + 1))

    def test_limits_and_names(self):
        for bad in (0, -5, write_gate.MAX_MINUTES + 1):
            with self.assertRaises(ValueError):
                write_gate.turn_on(NAME, bad)
        for bad in ("../x", "", "Has Caps", "a/b"):
            with self.assertRaises(ValueError):
                write_gate.turn_on(bad, 5)

    def test_garbage_state_is_off(self):
        os.makedirs(write_gate.state_dir())
        with open(write_gate.path(NAME, "on-until"), "w") as f:
            f.write("not a number")
        self.assertIsNone(write_gate.on_until(NAME))


class LiveGateTest(unittest.TestCase):
    """Runs the gate as the client would, with a fake real server behind it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = os.path.join(self.tmp.name, "gate")
        self.launches = os.path.join(self.tmp.name, "launches")
        self.fake = os.path.join(self.tmp.name, "fake.py")
        with open(self.fake, "w") as f:
            f.write(FAKE_SERVER)
        self.env = mock.patch.dict(os.environ, {"WRITE_GATE_DIR": self.dir})
        self.env.start()
        self.gate = None

    def tearDown(self):
        if self.gate:
            self.gate.stdin.close()
            self.gate.wait(timeout=15)
        self.env.stop()
        self.tmp.cleanup()

    def start(self, *fake_args, session="111"):
        env = dict(os.environ, WRITE_GATE_DIR=self.dir, WRITE_GATE_POLL_S="0.05", WRITE_GATE_SESSION=session)
        self.gate = subprocess.Popen([sys.executable, "-I", GATE, "run", "--name", NAME, "--",
                                      sys.executable, "-I", self.fake, self.launches, *fake_args],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env)
        self.out = queue.Queue()
        threading.Thread(target=lambda: [self.out.put(json.loads(l)) for l in self.gate.stdout], daemon=True).start()
        self.request(1, "initialize", {"protocolVersion": "2025-03-26"})
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def send(self, msg):
        self.gate.stdin.write(json.dumps(msg) + "\n")
        self.gate.stdin.flush()

    def next(self, timeout=5):
        return self.out.get(timeout=timeout)

    def request(self, mid, method, params=None):
        self.send({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}})
        reply = self.next()
        self.assertEqual(reply.get("id"), mid, reply)
        return reply

    def launch_count(self):
        try:
            with open(self.launches) as f:
                return len(f.readlines())
        except FileNotFoundError:
            return 0

    def tools(self, mid):
        return [t["name"] for t in self.request(mid, "tools/list")["result"]["tools"]]

    def test_off_is_a_stand_in(self):
        self.start()
        self.assertEqual(self.tools(2), [])
        self.assertIn("error", self.request(3, "tools/call", {"name": "rename_device"}))
        time.sleep(0.3)
        self.assertEqual(self.launch_count(), 0)

    def test_on_swaps_in_real_server_then_off_removes_it(self):
        self.start()
        self.assertEqual(self.tools(2), [])
        write_gate.turn_on(NAME, 5, session=111)
        self.assertEqual(self.next()["method"], "notifications/tools/list_changed")
        self.assertEqual(self.tools(3), ["rename_device"])
        reply = self.request(4, "tools/call", {"name": "rename_device", "arguments": {}})
        self.assertEqual(reply["result"]["content"][0]["text"], "renamed")
        self.assertEqual(write_gate.read_status(NAME)[0], "ready")
        write_gate.turn_off(NAME)
        self.assertEqual(self.next()["method"], "notifications/tools/list_changed")
        self.assertEqual(self.tools(5), [])
        self.assertEqual(self.launch_count(), 1)

    def test_window_for_another_session_does_nothing(self):
        self.start(session="111")
        write_gate.turn_on(NAME, 5, session=222)
        time.sleep(0.5)
        self.assertEqual(self.launch_count(), 0)
        self.assertEqual(self.tools(2), [])

    def test_failed_start_is_not_retried_in_the_same_window(self):
        self.start("die")
        write_gate.turn_on(NAME, 5, session=111)
        time.sleep(0.8)
        self.assertEqual(self.launch_count(), 1)
        self.assertEqual(write_gate.read_status(NAME)[0], "failed")
        self.assertEqual(self.tools(2), [])


class CliTest(unittest.TestCase):
    def test_status_on_off(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, WRITE_GATE_DIR=tmp)

            def run(*args):
                return subprocess.run([sys.executable, "-I", GATE, *args], capture_output=True, text=True,
                                      env=env, timeout=10).stdout

            self.assertIn("No write connections", run("status"))
            self.assertRegex(run("on", NAME, "15"), r"writes on until \d\d:\d\d for (session \d+|every open session)")
            self.assertIn("writes on until", run("status"))
            run("off")
            self.assertIn(f"{NAME}: writes off", run("status"))


if __name__ == "__main__":
    unittest.main()
