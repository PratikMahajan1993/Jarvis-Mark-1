# Migration standards

Schema changes ship as numbered SQL under `backend/migrations/` plus a row in `schema_migrations`. `backend/app/db.py` applies files in numeric order. `TEMPLATE.sql` is not numbered, so the runner skips it.

## Rules

- **Forward-only.** No down migrations. Do not `DROP TABLE` authoritative master data (`customers`, `machines`, `materials`, `suppliers`, `machine_hour_rates`, `supplier_rm_quotes`, `outsource_quotes`, `outsource_vendors`).
- **Backfills live in the migration script**, not in request handlers.
- **Idempotent.** `INSERT OR IGNORE` or an existence check before insert. Re-applying a statement must not destroy a row the owner already edited.
- **Provenance on priced rows.** Keep `source_kind`, `source_ref`, `attested_by`, `attested_at`, and `shipped_seed_value_minor`. Demo/seed values stay unsendable until attested and different from the shipped seed.
- **Temporal rates.** `effective_from` / `effective_to` on rate tables. Query as-of a business date. Supersede by inserting a new row and end-dating the old one. Do not `UPDATE` the price in place.
- **Money** is integer minor units plus an ISO currency code. **Timestamps** are UTC ISO-8601 from `db.utc_now()`.
- **No `BEGIN`/`COMMIT` in the file.** The runner executes each semicolon-separated statement on its own. SQLite also auto-commits DDL.

## New file

Copy `backend/migrations/TEMPLATE.sql` to `backend/migrations/NNNN_short_name.sql`. The header must include:

```sql
-- Description: what this migration does
-- Dependencies: migration numbers
```

`backend/tests/test_migration_standards.py` checks every numbered migration from `0024` upward.
