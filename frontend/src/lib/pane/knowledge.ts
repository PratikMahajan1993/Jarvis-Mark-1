export type DrawingIdentity = {
  ok?: boolean;
  kind?: string | null;
  part_revision_id?: string | null;
  prior_part_revision_id?: string | null;
  changed_fields?: string[];
  change_details?: { field: string; prior_value: string; current_value: string }[];
  banner?: string;
  summary?: string;
};

export type RecallPayload = {
  enabled?: boolean;
  ok?: boolean;
  found?: boolean;
  entity_id?: string;
  summary?: string;
  gaps?: string[];
  confirmed?: { field: string; label: string; value: string }[];
  updated_at?: string | null;
  stale?: boolean;
  latencies_ms?: { sql?: number | null; card?: number | null; corpus?: number | null };
};

export type ShopFloorItem = {
  kind?: string;
  machine_id?: string;
  machine_name?: string;
  vendor?: string;
  component_id?: string;
  status?: string;
  last_downtime_min?: number | null;
  last_downtime_reason?: string;
  oee_pct?: number | null;
  last_scrap?: number | null;
  on_hand?: number | null;
  allocated?: number | null;
  available?: number | null;
  unit?: string;
  last_days?: number | null;
  avg_days?: number | null;
  last_delivery?: string;
  updated_at?: string;
  stale?: boolean;
  as_of?: string;
  points?: { ts: string; machine_id?: string | null; oee_pct?: number | null }[];
};

export type ShopFloorPayload = {
  ok?: boolean;
  machines: ShopFloorItem[];
  vendors: ShopFloorItem[];
  stock: ShopFloorItem[];
  oee: ShopFloorItem;
};
