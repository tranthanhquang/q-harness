# Local Backup and Restore

Back up PostgreSQL metadata and the artifact directory as one offline snapshot.
Stop the service and worker first; wait for active executions to finish or cancel
them explicitly. Keep them stopped until the snapshot finishes. Repository source
files, workspace configs, templates outside the package and secrets require their
own backups; this snapshot does not contain those files.

## PostgreSQL 18 Storage

The Compose named volume mounts `/var/lib/postgresql`; PostgreSQL 18 stores its
cluster at `/var/lib/postgresql/18/docker`. Earlier Q-Harness Compose files mounted
only `/var/lib/postgresql/data`, leaving the actual cluster in an anonymous volume.
If upgrading that configuration, do not recreate the existing container before
backing up its database and recording its mounts with `docker inspect`.

Stop Q-Harness writes, take and verify the snapshot below, and test the restore in
a separate PostgreSQL instance using the corrected mount. Switch the database URL
only after the restored instance passes the drill. Retain the old container and
all its volumes until cutover is verified; `docker compose down -v` destroys named
volumes and must not be used to migrate existing data.

## Requirements

- Active Q-Harness Python 3.12 environment and PostgreSQL 18 clients on `PATH`.
- `QH_DATABASE_URL` selects the source database. `QH_DATA_DIR/artifacts` is the
  default artifact root; set `QH_ARTIFACT_ROOT` if needed.
- Use a new destination outside the artifact directory. Symlinks are rejected.
- Store snapshots with access restricted to the operator: database contents and
  reports can contain private project information. Snapshots are not encrypted.

## Take a Snapshot

```bash
export QH_PYTHON="$PWD/.venv/bin/python"
umask 077
bash scripts/backup-local.sh /absolute/new/snapshot-directory
```

The snapshot contains `database.dump` (PostgreSQL custom format), `artifacts/`
and a versioned SHA-256 `manifest.json`. Files are staged next to the destination
and renamed into place only after successful creation. An existing destination is
never overwritten. A manifest detects accidental modification, not malicious
replacement of both the backup and its manifest.

## Restore to a Separate Empty Database

Create an empty database using PostgreSQL administration tools. Keep the current
database and artifact directory intact until the restore drill succeeds.

```bash
export QH_RESTORE_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@127.0.0.1:55432/qh_restore'
export QH_RESTORE_ARTIFACT_ROOT='/absolute/new/restored-artifacts'
bash scripts/restore-local.sh /absolute/existing/snapshot-directory
```

Supply real credentials via your local environment, not committed files. The
database must exist and contain no user tables; the artifact destination must not
exist. Restore verifies every checksum before loading the dump, runs PostgreSQL
restore in one transaction and publishes copied artifacts afterward. A filesystem
publication failure after the database commits can leave a restored database
without published artifacts; keep the service stopped and diagnose before cutover.

## Drill and Cutover

1. Restore into separate targets and compare `qh project list --json` using the
   restored database. Check representative task timelines and report metadata.
2. Compare artifact checksums with `manifest.json` and reopen a DOCX/XLSX.
3. Configure `QH_DATABASE_URL` for the restored database. Set `QH_DATA_DIR` to the
   parent of the restored `artifacts` directory. Existing artifact records store
   absolute paths: restoring on another path/host requires an explicit metadata
   migration before those old report paths can be used.
4. Verify repository paths still resolve, refresh knowledge, then restart service
   and worker. Preserve the original targets until acceptance is complete.

The automated drill creates disposable source and target databases, restores a
Project and artifact file, rejects modified backups and rejects a second restore
over existing state:

```bash
pytest -q tests/integration/test_backup_restore.py
```

This test proves the backup mechanism; operational cutover must also check actual
repository locations and existing absolute artifact paths. Scheduled backups and
automatic path relocation are outside the MVP.
