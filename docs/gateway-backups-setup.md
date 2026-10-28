# Gateway backups: owner setup checklist

The steps only the owner does (accounts, DSM admin, keys). Design: [gateway-backups.md](gateway-backups.md). Account and share names are placeholders; the real ones are recorded in `private/` only.

## Accounts: three new, each with one job

| # | Where | Account | Can do | Can't do |
|---|---|---|---|---|
| 1 | Gateway | `<gateway-backup-account>` (local) | Log in to the API, list and download auto-backups | Manage admins or other UniFi apps. It **can** change network config: listing backups needs Network Full Management (tested 2026-10-28) |
| 2 | NAS | `<nas-job-user>` | Run the scheduled job; **write** to `gateway-backups`; **read** its own script and config | Log in to DSM, SMB or any other share; edit its own script |
| 3 | NAS | `<nas-reader-user>` | **Read** `gateway-backups` over SMB (the laptop's gate check) | Write anywhere; read the job's config or password |

Writer and reader are separate, so the laptop (and the agent on it) can check backups but never alter them. The job reads its script and config from a share it can't write to, so a compromised job can't rewrite itself.

## 1. Encryption key (laptop, about 5 min)

```
openssl req -x509 -newkey rsa:4096 -days 3650 -subj "/CN=gateway-backup" \
  -keyout gateway-backup-key.pem -out gateway-backup-cert.pem
```
- Set a passphrase when asked.
- Save **the key and its passphrase** in the password manager, then delete the local key file. Only `gateway-backup-cert.pem` (public) goes to the NAS.

## 2. Gateway account (UniFi OS console)

- [ ] Admins & Users → add a **local** admin `<gateway-backup-account>`, no remote/cloud access. Untick "Use a Predefined Role": Network **Full Management**, every other app **None**. (View Only, Viewer and Site Admin all get 403 when listing backups.)
- [ ] Get the gateway's TLS key pin (laptop):
  ```
  openssl s_client -connect <gateway-ip>:443 </dev/null 2>/dev/null | openssl x509 -pubkey -noout \
    | openssl pkey -pubin -outform der | openssl dgst -sha256 -binary | base64
  ```
  The config value is `sha256//<that output>`. It changes if the gateway's certificate is replaced; the job then fails closed until the pin is updated.

## 3. NAS (DSM)

- [ ] Package Center → install **Snapshot Replication**.
- [ ] Control Panel → Shared Folder → create **`gateway-backups`**: hidden from Network Places, recycle bin off.
  - Permissions: `<nas-job-user>` read/write, `<nas-reader-user>` read-only, everyone else no access.
- [ ] Create **`gateway-backup-job`**: hidden.
  - Permissions: `<nas-job-user>` **read-only**, `<nas-reader-user>` no access, everyone else no access. Only an admin can write here.
- [ ] Control Panel → User → create `<nas-job-user>` and `<nas-reader-user>` (strong random passwords, stored in the password manager).
  - Applications tab: deny everything for `<nas-job-user>`; for `<nas-reader-user>` allow SMB only.
  - Neither account is in `administrators`.
- [ ] As admin, put into `gateway-backup-job`:
  - `pull-gateway-backup.sh` from this repo (`scripts/nas/`)
  - `gateway-backup-cert.pem`
  - `gw-password`: only the `<gateway-backup-account>` password, one line
  - `job.conf`:
    ```
    GW_HOST=<gateway-ip>
    GW_USER=<gateway-backup-account>
    GW_PASSWORD_FILE=/volume1/gateway-backup-job/gw-password
    GW_PUBKEY_PIN=sha256//<pin>
    DEST=/volume1/gateway-backups
    CERT=/volume1/gateway-backup-job/gateway-backup-cert.pem
    KEEP=30
    ```
- [ ] Snapshot Replication → Snapshots → `gateway-backups` → Settings: daily at 02:30, keep 30 days, **immutable snapshots: 14 days**.
- [ ] Control Panel → Task Scheduler → Create → Scheduled Task → User-defined script.
  - User: `<nas-job-user>`. Daily at 01:30.
  - Command: `sh /volume1/gateway-backup-job/pull-gateway-backup.sh /volume1/gateway-backup-job/job.conf`
  - Settings: send run details by email **only when the script terminates abnormally**.

## 4. First run (bootstrap)

- [ ] Task Scheduler → select the task → **Run**. It pulls the newest existing weekly auto-backup without changing anything on the gateway.
- [ ] If it fails with HTTP 401/403 on the list or download step, check the account's role (Network Full Management) and that it is a local account.
- [ ] Check that `gateway-backups/manifest.json` exists and shows `"archive_check": "ok"`.

## 5. Laptop gate

No mount needed: the gate fetches the manifest and the latest backup over the DSM API, as a read-only NAS account with read access to the backup share.

- [ ] Get the NAS's TLS key pin (same command as the gateway's, with `<nas-ip>:5001`).
- [ ] In `private/change-window.conf`:
  ```
  BACKUP_NAS_URL=https://<nas-ip>:5001
  BACKUP_NAS_PIN='sha256//<pin>'
  BACKUP_NAS_USER=<read-only NAS account>
  BACKUP_NAS_PASSWORD_COMMAND='<absolute argv that prints its password>'
  BACKUP_NAS_DIR=/<backup share>
  ```
- [ ] `scripts/change-window.sh status` should now report a `nas` restore point.

(Alternative: mount the share read-only and set `BACKUP_MANIFEST=<mount>/manifest.json`.)

## 6. Daily schedule (agent, via change window)

The existing auto-backup is up to a week old, so the 3-day gate stays satisfied only until it ages out. Within that window, run the change window for "Daily gateway backups to the NAS" to switch the gateway's auto-backup from weekly to daily. From then on the pipeline keeps the restore point fresh.
