-- O1 durable /api/metrics series: indexes for ledger aggregates (data stays in existing tables).

CREATE INDEX IF NOT EXISTS turns_metrics_stage ON turns(stage);
CREATE INDEX IF NOT EXISTS quote_proofs_blockers ON quote_proofs(blockers);
CREATE INDEX IF NOT EXISTS external_effects_dedupe_lookup ON external_effects(provider, request_hash);
