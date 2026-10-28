# Gateway backups to the NAS

**Status:** design approved 2026-10-26; job script and gate in this repo, device setup pending. Every step that changes a device is a proposal in [changes.md](changes.md).

## Goal

Get a current, verified, tamper-resistant copy of the gateway config off the gateway every day, without giving the agent or the backup job more access than it needs. `change-window.sh open` then gates on that copy instead of on a manual download.

## Current state (verified 2026-10-26)

- The gateway auto-backs up weekly (Sunday), keeps 7 copies, and **stores them only on itself**. Cloud backup is off.
- NAS: DSM 7.4, Btrfs volume (snapshots supported), no backup share yet.
- Internal → Gateway HTTPS is already allowed, so the NAS can reach the gateway without any firewall change.

## Design

```
gateway (daily auto-backup, on-box)
   │  HTTPS, read-only pull, dedicated account
   ▼
NAS Task Scheduler job (runs as a dedicated non-admin user)
   │  verify → encrypt → write + manifest
   ▼
gateway-backups share ── immutable daily snapshots (14 days locked, 30 kept)
   │  read-only SMB mount
   ▼
admin laptop: change-window.sh open checks the manifest's age and hash
```

**Pull, don't push.** The job downloads the newest existing auto-backup. It never triggers a backup on the gateway, so the gateway account doesn't need write access.

## Controls

| Risk | Control |
|---|---|
| Backup job credentials are stolen | Dedicated gateway account with the **lowest role that can download backups** (test View Only first); a password file readable only by the job user (mode 600); the job user can't log in to DSM or SMB |
| Job, malware or the agent deletes or overwrites backups | **Immutable Btrfs snapshots** on the share: no one can delete them before they expire, admin included. The job user can write only to this one share |
| A backup file leaks (it holds Wi-Fi passphrases, VPN keys, admin hashes, under a well-known static encryption key) | Encrypt each file to a **public key** (`openssl cms` with an X.509 cert) before writing. The NAS never holds the private key; it lives offline in the password manager |
| A corrupt or truncated backup goes unnoticed | Before encrypting, the job decrypts the `.unf` with the static key and checks it's a valid archive containing the database. Bad files are rejected and the job exits non-zero |
| The job silently stops | DSM emails on abnormal exit; the gate refuses to open when the manifest is stale; `change-window.sh status` reports the age |
| The agent gains standing access to backups | The laptop mounts the share **read-only** with a separate read-only user. It can read `manifest.json` and hash files, nothing more |
| Backups exist but don't restore | Quarterly test restore into a throwaway controller container. The date of the last good restore goes in `manifest.json` |

## Manifest

`manifest.json` in the share, written by the job:

```json
{
  "latest": {
    "file": "gateway-YYYYMMDD-HHMM.unf.cms",
    "source_created": "2026-10-25T05:30:00Z",
    "pulled": "2026-10-26T06:10:00Z",
    "sha256": "<of the encrypted file>",
    "plain_sha256": "<of the original .unf>",
    "archive_check": "ok",
    "controller_version": "10.6.109"
  },
  "last_restore_test": null
}
```

## Gate change

`open` checks, in order: the share is mounted, the manifest parses, `latest.source_created` is newer than `BACKUP_MAX_AGE_DAYS`, the encrypted file exists and matches `sha256`, and `archive_check` is `ok`. The manual `backup <file>` record stays as a fallback for the bootstrap and for when the NAS is down.

## Build order

1. **Bootstrap restore point (manual):** download one backup by hand and record it, so the first change window is allowed.
2. **Gateway:** create the backup account (owner, in the console). Test whether View Only can download auto-backups.
3. **NAS:** create the share, the job user and the read-only user; install Snapshot Replication; set immutable snapshots (owner, in DSM).
4. **Job script:** done, versioned in this repo (`scripts/nas/pull-gateway-backup.sh`), deployed to the NAS, scheduled daily after the gateway's backup time.
5. **Gateway:** change auto-backup from weekly to daily. This is a gateway config change, so it goes through a change window, which step 1 makes possible.
6. **Gate:** done. `change-window.sh` reads the manifest when `BACKUP_MANIFEST` is set and falls back to the manual record. Owner steps: [gateway-backups-setup.md](gateway-backups-setup.md).

## Couldn't verify yet

- Which gateway role can download auto-backups, and the exact download endpoint on this firmware. Tested 2026-10-28: listing backups returns 403 for **View Only** and **Site Admin**. **Full Management works** (tested 2026-10-28: list and download both succeed, without super admin).
  - **Accepted by the owner 2026-10-28:** with Full Management, the backup account can rewrite the whole network, and its password sits on the NAS. Choices: accept that, keep it local-only, and protect the job folder; download backups by hand before tier-2 changes; or look for a narrower route
- Whether this DSM build allows immutable snapshots on this volume
- Whether DSM's `openssl` supports `cms -encrypt` (it should; this needs checking on the box)
