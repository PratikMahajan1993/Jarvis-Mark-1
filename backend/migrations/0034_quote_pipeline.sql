-- Description: quote pipeline state on revisions (Slice 3)
-- Dependencies: 0007, 0033

ALTER TABLE quote_revisions ADD COLUMN pipeline_state TEXT DEFAULT 'on_desk';
ALTER TABLE quote_revisions ADD COLUMN pipeline_step TEXT;
ALTER TABLE quote_revisions ADD COLUMN detour_return_state TEXT;
ALTER TABLE quote_revisions ADD COLUMN rate_snapshot_json TEXT;

UPDATE quote_revisions SET pipeline_state = 'on_desk' WHERE pipeline_state IS NULL;
