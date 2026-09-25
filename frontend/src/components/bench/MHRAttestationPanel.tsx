"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Rate = {
  id: string;
  machine_type: string;
  floor_inr: number;
  attested_by: string;
  attested_at: string;
  status: string;
};

const STATUS: Record<string, string> = {
  attested: "✓ Attested",
  demo_seed: "○ Demo seed",
  needs_attestation: "⚠ Needs attestation",
};

export function MHRAttestationPanel() {
  const [rates, setRates] = useState<Rate[]>([]);
  const [openId, setOpenId] = useState("");
  const [who, setWho] = useState("");
  const [floor, setFloor] = useState("");
  const [note, setNote] = useState("");

  function reload() {
    void api.mhrRates().then((result) => setRates(result.rates || [])).catch(() => setNote("Could not load rates."));
  }

  useEffect(() => {
    reload();
  }, []);

  return (
    <section className="space-y-2" data-mhr-panel>
      <h3 className="font-mono text-[9px] uppercase tracking-[0.18em] text-[color:var(--muted)]/75">
        Machine hour rates
      </h3>
      {rates.length === 0 ? (
        <p className="font-mono text-[10px] text-[color:var(--muted)]">No rates loaded.</p>
      ) : (
        <ul className="space-y-1">
          {rates.map((rate) => (
            <li key={rate.id || rate.machine_type} className="font-mono text-[10px] text-[color:var(--fg)]">
              <div className="flex items-center justify-between gap-2">
                <span>
                  {rate.machine_type} · ₹{rate.floor_inr}/hr · {STATUS[rate.status] || rate.status}
                  {rate.attested_by ? ` · ${rate.attested_by}` : ""}
                </span>
                <button
                  type="button"
                  className="uppercase tracking-[0.12em] text-[color:var(--accent)]"
                  onClick={() => {
                    setOpenId(rate.id || rate.machine_type);
                    setFloor(String(rate.floor_inr));
                    setNote("");
                  }}
                >
                  Attest
                </button>
              </div>
              {openId === (rate.id || rate.machine_type) ? (
                <form
                  className="mt-1 grid gap-1"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void api.attestMhr(rate.machine_type, who, floor, rate.id).then((result) => {
                      setNote(result.ok ? "Rate attested." : result.message || "Could not attest.");
                      if (result.ok) {
                        setOpenId("");
                        reload();
                      }
                    });
                  }}
                >
                  <p>Attest this rate?</p>
                  <input
                    aria-label="Attested by"
                    placeholder="Your name"
                    value={who}
                    onChange={(event) => setWho(event.target.value)}
                    className="rounded border border-[color:var(--border)] bg-transparent px-1 py-0.5"
                  />
                  <input
                    aria-label="Floor INR per hour"
                    placeholder="Floor INR/hr, not the demo seed"
                    value={floor}
                    onChange={(event) => setFloor(event.target.value)}
                    className="rounded border border-[color:var(--border)] bg-transparent px-1 py-0.5"
                  />
                  <button type="submit" className="w-fit uppercase tracking-[0.12em]">
                    Confirm attest
                  </button>
                </form>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {note ? <p className="font-mono text-[10px] text-[color:var(--muted)]" data-mhr-note>{note}</p> : null}
    </section>
  );
}
