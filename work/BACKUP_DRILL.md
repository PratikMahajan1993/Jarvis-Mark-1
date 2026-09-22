# Jarvis backup drill (O2)

Jarvis keeps one SQLite file (`data/jarvis.db`) plus sent quote PDFs under `exports/`. This drill rehearses recovering the database from a `VACUUM INTO` snapshot. Sent-quote PDFs are archived separately via `archive_sent_quote` (content-addressed under an operator-chosen directory).

## Nightly snapshot (operator / Task Scheduler)

From the repo root, with the API stopped or idle (no long-lived writers):

```powershell
cd D:\Cursor\Jarvis
.\.venv\Scripts\python.exe -c "from app.backup import backup_database; from pathlib import Path; p = backup_database(Path('data/backups'), keep=7); print(p)"
```

- Writes `data/backups/jarvis-<UTC-timestamp>.db`.
- Keeps the **7** newest `jarvis-*.db` files; older ones are deleted.
- Does **not** start a background thread; schedule this command externally if desired.

## Boot integrity check

Every `init_db()` (API startup) runs `PRAGMA integrity_check` on the open database. If the result is not `ok`, startup **raises** and the process should not serve traffic.

## Restore drill (rehearse once)

1. **Snapshot** — run the nightly command above (or call `backup_database` from a Python shell).
2. **Verify backup** — optional: `sqlite3 data\backups\jarvis-<stamp>.db "PRAGMA integrity_check;"` must return `ok`.
3. **Simulate loss** — stop the API; rename `data\jarvis.db` to `data\jarvis.db.broken` (do not delete until the restore succeeds).
4. **Restore** — copy the chosen backup over the live path:

   ```powershell
   cd D:\Cursor\Jarvis
   .\.venv\Scripts\python.exe -c "from app.backup import restore_database_from_backup; from pathlib import Path; restore_database_from_backup(Path('data/backups/jarvis-<stamp>.db'))"
   ```

5. **Boot** — start the API; `init_db` runs integrity check again. Confirm HUD/API health and spot-check quotes or mail as needed.
6. **Sent quotes** — database restore does not replace `exports/` PDFs. After a send, ensure `archive_sent_quote` has copied PDF + JSON payload into your archive directory (append-only, sha256 filenames).

Automated rehearsal: `backend/tests/test_backup.py::test_backup_and_restore_drill`.
