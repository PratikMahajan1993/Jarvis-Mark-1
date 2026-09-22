-- Feature → operation templates for geometry-true featurescan (§3.3 M4).

CREATE TABLE feature_process_rules (
  id TEXT PRIMARY KEY,
  feature_kind TEXT NOT NULL,
  predicate_json TEXT NOT NULL,
  operations_json TEXT NOT NULL,
  source_ref TEXT NOT NULL
);

INSERT INTO feature_process_rules (id, feature_kind, predicate_json, operations_json, source_ref) VALUES
(
  'fpr_pocket_prismatic',
  'pocket',
  '{"shape":"prismatic"}',
  '["Rough mill","Semi-finish","Finish"]',
  'manifest:3.3'
),
(
  'fpr_hole_free_lt12',
  'hole',
  '{"tolerance":"free","diameter_mm_lt":12}',
  '["Centre drill","Drill"]',
  'manifest:3.3'
),
(
  'fpr_hole_h7_h8',
  'hole',
  '{"tolerance_in":["H7","H8"]}',
  '["Drill","Bore or ream","Gauge inspection"]',
  'manifest:3.3'
),
(
  'fpr_bore_precision_gt25',
  'bore',
  '{"diameter_mm_gt":25,"finish_or_tolerance":"H6_or_Ra_lt_0.4"}',
  '["Bore","Hone or grinding (outsource)"]',
  'manifest:3.3'
),
(
  'fpr_thread',
  'thread',
  '{}',
  '["Tap or thread mill","Gauge inspection"]',
  'manifest:3.3'
),
(
  'fpr_face_flatness',
  'face',
  '{"flatness_mm_lt":0.01}',
  '["Grinding (outsource)"]',
  'manifest:3.3'
),
(
  'fpr_heat_treat',
  'note',
  '{"note_kind":"hardness_or_case_depth"}',
  '["Heat treat (outsource)","Post-HT finishing"]',
  'manifest:3.3'
),
(
  'fpr_plating',
  'note',
  '{"note_kind":"plating_or_coating"}',
  '["Plating (outsource)","Masking and pre-plate compensation"]',
  'manifest:3.3'
),
(
  'fpr_turned_ld',
  'turned',
  '{"ld_ratio_gt":8}',
  '["Steady or tailstock support","Reduced DOC","Between-centres if required"]',
  'manifest:3.3'
);
