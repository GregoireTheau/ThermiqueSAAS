# Backup and restore runbook

This runbook covers the private beta SQLite database deployed on Railway and
backed up to the Cloudflare R2 bucket `thermal-twin-backup`.

## Automated backups

The Railway service `thermal-saas-backup` runs daily at `0 3 * * *` (03:00 UTC)
and calls the authenticated `POST /admin/backups` endpoint. The web service
creates a consistent SQLite snapshot, compresses it, and uploads it under:

```text
thermal-saas/sqlite/thermal_saas-<UTC timestamp>.sqlite.gz
```

A successful cron execution must end with `Backup completed` in its Railway
logs. A non-zero exit indicates that the endpoint or upload failed.

## Cloudflare R2 retention

In Cloudflare, open **R2 Object Storage**, select `thermal-twin-backup`, then
open **Settings**. Under **Object Lifecycle Rules**, add an enabled rule with:

```text
Name: Delete SQLite backups after 30 days
Prefix: thermal-saas/sqlite/
Action: Delete objects
Age: 30 days
```

The prefix is important: it limits deletion to SQLite backups if the bucket is
later used for other files. Cloudflare generally deletes expired objects within
24 hours of their expiration time.

## Manual backup

Trigger a fresh backup without printing the admin token:

```bash
curl --fail-with-body \
  --request POST \
  --header "X-Thermal-Admin-Token: ${THERMAL_ADMIN_TOKEN}" \
  "https://thermaltwin.up.railway.app/admin/backups"
```

Record the returned object key. Never commit or paste the token or R2
credentials into logs, tickets, or documentation.

## Restore verification

Prerequisites: the Railway CLI must be linked to the production web service and
the AWS CLI must be installed locally.

Replace `<object-key>` with the key returned by the backup endpoint:

```bash
railway run sh -c '
AWS_ACCESS_KEY_ID="$THERMAL_BACKUP_S3_ACCESS_KEY_ID" \
AWS_SECRET_ACCESS_KEY="$THERMAL_BACKUP_S3_SECRET_ACCESS_KEY" \
AWS_DEFAULT_REGION="$THERMAL_BACKUP_S3_REGION" \
aws s3 cp \
"s3://$THERMAL_BACKUP_S3_BUCKET/<object-key>" \
"$HOME/Downloads/thermal_saas-restore.sqlite.gz" \
--endpoint-url "$THERMAL_BACKUP_S3_ENDPOINT"
'
```

Restore only to a temporary local path, never over the production database:

```bash
mkdir -p /tmp/thermaltwin-restore-test
gzip -dc ~/Downloads/thermal_saas-restore.sqlite.gz \
  > /tmp/thermaltwin-restore-test/thermal_saas.sqlite

sqlite3 /tmp/thermaltwin-restore-test/thermal_saas.sqlite \
  "PRAGMA integrity_check; SELECT count(*) FROM projects; SELECT count(*) FROM simulation_runs;"
```

Success requires `PRAGMA integrity_check` to return `ok`. Compare the row counts
with production or with the values recorded when the backup was created.

## Restore test record

Database-level restoration was verified on 2026-08-03 with:

```text
Object: thermal-saas/sqlite/thermal_saas-20260803T191344Z.sqlite.gz
Compressed size: 12,335,577 bytes
SQLite integrity check: ok
Projects recovered: 2
Simulation runs recovered: 6
Production database modified: no
```

This proves that an archive can be created, downloaded, decompressed, and read
as a valid SQLite database. A separate staging deployment from a restored copy
should be tested before the public launch to validate the complete application
startup and user workflow.
