"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ShopFloorItem, ShopFloorPayload } from "@/lib/pane/knowledge";
import { FreshnessBadge } from "./FreshnessBadge";

type FloorTab = "machines" | "vendors" | "stock" | "oee";

const EMPTY: ShopFloorPayload = {
  machines: [],
  vendors: [],
  stock: [],
  oee: { points: [], stale: true },
};

function num(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return String(value);
}

export function ShopFloorPanel() {
  const [tab, setTab] = useState<FloorTab>("machines");
  const [body, setBody] = useState<ShopFloorPayload>(EMPTY);

  const refresh = useCallback(async () => {
    try {
      setBody(await api.shopFloor());
    } catch {
      setBody(EMPTY);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const tabs: { id: FloorTab; label: string }[] = [
    { id: "machines", label: "Machines" },
    { id: "vendors", label: "Vendors" },
    { id: "stock", label: "Stock" },
    { id: "oee", label: "OEE" },
  ];

  return (
    <section className="space-y-3" data-shop-floor>
      <div className="flex gap-3 font-mono text-[10px] uppercase tracking-[0.16em]" role="tablist" aria-label="Shop floor">
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            className={tab === item.id ? "text-[color:var(--accent)]" : "text-[color:var(--muted)]"}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {tab === "machines" ? <MachineList rows={body.machines} /> : null}
      {tab === "vendors" ? <VendorList rows={body.vendors} /> : null}
      {tab === "stock" ? <StockList rows={body.stock} /> : null}
      {tab === "oee" ? <OeeBlock row={body.oee} /> : null}
    </section>
  );
}

function EmptyNote() {
  return <p className="font-mono text-[11px] text-[color:var(--muted)]">No shop events logged yet.</p>;
}

function MachineList({ rows }: { rows: ShopFloorItem[] }) {
  if (!rows.length) return <EmptyNote />;
  return (
    <ul className="space-y-2">
      {rows.map((row) => (
        <li key={row.machine_id || row.as_of} className="rounded border border-[color:var(--border)] px-2 py-1.5">
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono text-[11px]">{row.machine_name || row.machine_id}</span>
            <FreshnessBadge updatedAt={row.updated_at} stale={row.stale} />
          </div>
          <p className="font-mono text-[10px] text-[color:var(--muted)]">
            {row.status || "status unknown"} · downtime {num(row.last_downtime_min)} min
            {row.last_downtime_reason ? ` · ${row.last_downtime_reason}` : ""}
            {row.oee_pct != null ? ` · OEE ${num(row.oee_pct)}` : ""}
          </p>
        </li>
      ))}
    </ul>
  );
}

function VendorList({ rows }: { rows: ShopFloorItem[] }) {
  if (!rows.length) return <EmptyNote />;
  return (
    <ul className="space-y-2">
      {rows.map((row) => (
        <li key={row.vendor || row.updated_at || "vendor"} className="rounded border border-[color:var(--border)] px-2 py-1.5">
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono text-[11px]">{row.vendor}</span>
            <FreshnessBadge updatedAt={row.updated_at} stale={row.stale} />
          </div>
          <p className="font-mono text-[10px] text-[color:var(--muted)]">
            avg {num(row.avg_days)} days · last delivery {row.last_delivery || "—"}
          </p>
        </li>
      ))}
    </ul>
  );
}

function StockList({ rows }: { rows: ShopFloorItem[] }) {
  if (!rows.length) return <EmptyNote />;
  return (
    <ul className="space-y-2">
      {rows.map((row) => (
        <li key={row.component_id} className="rounded border border-[color:var(--border)] px-2 py-1.5">
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono text-[11px]">{row.component_id}</span>
            <FreshnessBadge updatedAt={row.updated_at} stale={row.stale} />
          </div>
          <p className="font-mono text-[10px] text-[color:var(--muted)]">
            on hand {num(row.on_hand)} · allocated {num(row.allocated)} · available {num(row.available)} {row.unit || ""}
          </p>
        </li>
      ))}
    </ul>
  );
}

function OeeBlock({ row }: { row: ShopFloorItem }) {
  const points = row.points || [];
  if (!points.length) return <EmptyNote />;
  return (
    <div className="space-y-2">
      <FreshnessBadge updatedAt={row.updated_at} stale={row.stale} />
      <ul className="space-y-1">
        {points.map((point) => (
          <li key={`${point.ts}-${point.machine_id || ""}`} className="font-mono text-[11px]">
            {point.machine_id || "machine"} · {num(point.oee_pct)} · {point.ts}
          </li>
        ))}
      </ul>
    </div>
  );
}
