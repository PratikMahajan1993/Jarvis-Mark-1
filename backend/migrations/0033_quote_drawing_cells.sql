-- Description: confirmable drawing cells and send-gate overrides on quote revisions
-- Dependencies: 0007

ALTER TABLE quote_revisions ADD COLUMN drawing_cells_json TEXT;
ALTER TABLE quote_revisions ADD COLUMN send_gate_overrides_json TEXT;
ALTER TABLE quote_revisions ADD COLUMN quote_document_text TEXT;
