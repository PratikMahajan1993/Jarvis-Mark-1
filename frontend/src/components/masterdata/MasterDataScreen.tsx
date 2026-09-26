"use client";

import { useState } from "react";

import { CustomerTable } from "./CustomerTable";
import { MHRFloorTable } from "./MHRFloorTable";
import { MachineTable } from "./MachineTable";
import { MaterialTable } from "./MaterialTable";
import { OutsourceVendorTable } from "./OutsourceVendorTable";
import { SupplierTable } from "./SupplierTable";

const TABS = ["Customers", "Machines", "Materials", "Suppliers", "MHR Floors", "Outsource Vendors"] as const;

export function MasterDataScreen() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Customers");
  return (
    <main className="min-h-screen bg-ink px-6 py-8 text-white">
      <header className="mb-6">
        <p className="text-xs uppercase tracking-[0.2em] text-cyan">Master data</p>
        <h1 className="font-display text-3xl">Shop records</h1>
        <p className="mt-2 max-w-2xl text-sm text-white/60">
          Customers, machines, materials, suppliers, hour floors, and outsource vendors. Replace a row to supersede it. Nothing here is hard-deleted.
        </p>
      </header>
      <nav className="mb-6 flex flex-wrap gap-2">
        {TABS.map((name) => (
          <button
            key={name}
            type="button"
            className={`rounded-full px-3 py-1 text-sm ${tab === name ? "bg-cyan text-ink" : "bg-white/5 text-white/70"}`}
            onClick={() => setTab(name)}
          >
            {name}
          </button>
        ))}
      </nav>
      {tab === "Customers" ? <CustomerTable /> : null}
      {tab === "Machines" ? <MachineTable /> : null}
      {tab === "Materials" ? <MaterialTable /> : null}
      {tab === "Suppliers" ? <SupplierTable /> : null}
      {tab === "MHR Floors" ? <MHRFloorTable /> : null}
      {tab === "Outsource Vendors" ? <OutsourceVendorTable /> : null}
    </main>
  );
}
