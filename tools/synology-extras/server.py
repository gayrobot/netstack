#!/usr/bin/env python3
"""synology-extras: DSM tools the third-party Synology MCP doesn't have.

Scope rule: only gaps. If upstream mcp-server-synology adds an equivalent tool, the
overlap is settled in the upgrade PR (docs/vetting/synology-mcp-upgrades.md). Tools
today: Package Center list and upgrade.

Stdlib only, stdio transport (newline-delimited JSON-RPC). Talks to one NAS, set by
the environment, never by a tool argument. Every request goes through curl with TLS
pinned to the NAS's public key, the same way scripts/change-window.sh does it.

Environment:
  NAS_URL               https://<nas>:5001
  NAS_PIN               sha256//<base64 SPKI hash>
  NAS_USER              DSM account (package management needs an administrator)
  NAS_PASSWORD_COMMAND  argv that prints the password, run without a shell (e.g. op read <ref>)

Run with: python3 -I server.py
"""
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.parse

PROTOCOL_VERSION = "2025-06-18"
PACKAGE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")
# Downloads are only accepted from Synology's own package servers.
DOWNLOAD_HOST = re.compile(r"(^|\.)synology\.com$")
DOWNLOAD_TIMEOUT_S = 900


class DSMError(Exception):
    pass


def config():
    cfg = {k: os.environ.get(k, "") for k in ("NAS_URL", "NAS_PIN", "NAS_USER", "NAS_PASSWORD_COMMAND")}
    if not (cfg["NAS_URL"].startswith("https://") and cfg["NAS_PIN"].startswith("sha256//")
            and cfg["NAS_USER"] and cfg["NAS_PASSWORD_COMMAND"]):
        raise DSMError("NAS_URL (https), NAS_PIN (sha256//...), NAS_USER and NAS_PASSWORD_COMMAND are required")
    return cfg


class DSM:
    def __init__(self, cfg):
        self.api = cfg["NAS_URL"].rstrip("/") + "/webapi/entry.cgi"
        self.pin = cfg["NAS_PIN"]
        self.user = cfg["NAS_USER"]
        self.pwcmd = shlex.split(cfg["NAS_PASSWORD_COMMAND"])
        self.sid = None

    def call(self, params):
        # Parameters (and the password, at login) travel on stdin, never in argv.
        if self.sid:
            params = dict(params, _sid=self.sid)
        curl = ["curl", "-sS", "--fail", "--max-time", "60", "--insecure", "--pinnedpubkey", self.pin,
                self.api, "--data-binary", "@-"]
        r = subprocess.run(curl, input=urllib.parse.urlencode(params).encode(), capture_output=True)
        if r.returncode != 0:
            raise DSMError(f"curl exit {r.returncode}: {r.stderr.decode(errors='replace').strip()}")
        body = json.loads(r.stdout)
        if not body.get("success"):
            raise DSMError(f"{params.get('api')} {params.get('method')}: DSM error {body.get('error', {}).get('code')}")
        return body.get("data") or {}

    def __enter__(self):
        pw = subprocess.run(self.pwcmd, capture_output=True, check=True).stdout.decode().rstrip("\n")
        data = self.call({"api": "SYNO.API.Auth", "version": "6", "method": "login", "account": self.user,
                          "passwd": pw, "session": "synology-extras", "format": "sid"})
        self.sid = data["sid"]
        return self

    def __exit__(self, *exc):
        try:
            self.call({"api": "SYNO.API.Auth", "version": "6", "method": "logout", "session": "synology-extras"})
        except DSMError:
            pass


def version_key(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or ""))


def installed(dsm):
    data = dsm.call({"api": "SYNO.Core.Package", "version": "2", "method": "list",
                     "additional": json.dumps(["status"])})
    return {p["id"]: p for p in data.get("packages", [])}


def available(dsm):
    data = dsm.call({"api": "SYNO.Core.Package.Server", "version": "2", "method": "list",
                     "blforcereload": "true", "blloadothers": "false"})
    return {p["id"]: p for p in data.get("packages", []) if "id" in p}


def package_list(_args):
    with DSM(config()) as dsm:
        inst, avail = installed(dsm), available(dsm)
    rows = []
    for pid, p in sorted(inst.items()):
        new = avail.get(pid, {}).get("version")
        rows.append({"id": pid, "name": p.get("name", pid), "version": p.get("version"),
                     "status": (p.get("additional") or {}).get("status"),
                     "available": new,
                     "upgrade_available": bool(new) and version_key(new) > version_key(p.get("version"))})
    return rows


def package_upgrade(args):
    pid = args.get("package_id", "")
    dry_run = args.get("dry_run", True) is not False
    if not PACKAGE_ID.match(pid):
        raise DSMError("package_id must be a DSM package id such as PHP8.2")
    with DSM(config()) as dsm:
        cur, new = installed(dsm).get(pid), available(dsm).get(pid)
        if not cur:
            raise DSMError(f"{pid} is not installed (this tool upgrades only; it never installs)")
        if not new or version_key(new.get("version")) <= version_key(cur.get("version")):
            return {"id": pid, "version": cur.get("version"), "result": "already current"}
        link = new.get("link", "")
        u = urllib.parse.urlparse(link)
        if u.scheme != "https" or not DOWNLOAD_HOST.search(u.hostname or ""):
            raise DSMError(f"refusing download from {u.hostname or link!r}: not a Synology package server")
        if not new.get("md5") or not new.get("size"):
            raise DSMError("package server entry has no checksum or size")
        plan = {"id": pid, "from": cur.get("version"), "to": new.get("version"), "source": u.hostname}
        if dry_run:
            return dict(plan, result="dry run: nothing downloaded or changed")
        task = dsm.call({"api": "SYNO.Core.Package.Installation", "version": "1", "method": "install",
                         "operation": "install", "type": "0", "blqinst": "true", "name": pid,
                         "url": link, "checksum": new["md5"], "filesize": str(new["size"])})["taskid"]
        deadline = time.monotonic() + DOWNLOAD_TIMEOUT_S
        while True:
            st = dsm.call({"api": "SYNO.Core.Package.Installation", "version": "1", "method": "status",
                           "task_id": task})
            if st.get("finished"):
                break
            if time.monotonic() > deadline:
                raise DSMError(f"download of {pid} did not finish in {DOWNLOAD_TIMEOUT_S} s")
            time.sleep(3)
        dsm.call({"api": "SYNO.Core.Package.Installation.Download", "version": "1", "method": "check",
                  "task_id": task})
        dsm.call({"api": "SYNO.Core.Package.Installation", "version": "1", "method": "upgrade",
                  "type": "0", "check_codesign": "true", "force": "false", "installrunpackage": "true",
                  "task_id": task, "extra_values": "{}"})
        after = installed(dsm).get(pid, {}).get("version")
    return dict(plan, result="upgraded" if after == new.get("version") else f"finished; installed version is now {after}")


TOOLS = {
    "package_list": (package_list, {
        "description": "List installed DSM packages with their versions and whether Package Center offers a newer one. Read only.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": {"readOnlyHint": True},
    }),
    "package_upgrade": (package_upgrade, {
        "description": "Upgrade one installed DSM package to the version Synology's package server offers. "
                       "Never installs, uninstalls or downgrades. dry_run defaults to true; pass false to apply.",
        "inputSchema": {"type": "object", "properties": {
            "package_id": {"type": "string", "description": "DSM package id, as package_list reports it"},
            "dry_run": {"type": "boolean", "default": True}},
            "required": ["package_id"], "additionalProperties": False},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
    }),
}

# The mcp-server-synology version each tool was last checked against for overlap.
# test_server.py fails if this differs from the pin in docs/vetting/locks/mcp-server-synology.in,
# so an upgrade of that MCP can't land without rechecking every tool here.
CHECKED_AGAINST = {
    "package_list": "1.8.0",
    "package_upgrade": "1.8.0",
}


def handle(msg):
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:
        return None  # notification
    if method == "initialize":
        result = {"protocolVersion": msg.get("params", {}).get("protocolVersion", PROTOCOL_VERSION),
                  "capabilities": {"tools": {}},
                  "serverInfo": {"name": "synology-extras", "version": "0.1.0"}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": [dict(spec, name=name) for name, (_, spec) in TOOLS.items()]}
    elif method == "tools/call":
        name = msg.get("params", {}).get("name")
        if name not in TOOLS:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"unknown tool {name}"}}
        try:
            out = TOOLS[name][0](msg["params"].get("arguments") or {})
            result = {"content": [{"type": "text", "text": json.dumps(out, indent=1)}], "isError": False}
        except (DSMError, subprocess.CalledProcessError, KeyError, ValueError) as e:
            result = {"content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}], "isError": True}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            reply = handle(json.loads(line))
        except json.JSONDecodeError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
