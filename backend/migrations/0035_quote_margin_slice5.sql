-- Description: margin hint + assumption mail (Slice 5)
-- Dependencies: 0007, 0034

ALTER TABLE quote_revisions ADD COLUMN primary_process TEXT;
ALTER TABLE quote_revisions ADD COLUMN tolerance_class TEXT;
ALTER TABLE quote_revisions ADD COLUMN cost_breakdown_json TEXT;
ALTER TABLE quote_revisions ADD COLUMN assumption_mail_log_json TEXT;
