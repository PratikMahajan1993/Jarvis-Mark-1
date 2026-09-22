"use client";

import { useCallback, useEffect, useState } from "react";
import GradientText from "@/components/react-bits/GradientText";
import SpotlightCard from "@/components/react-bits/SpotlightCard";

type ConsentPayload = {
  enabled: boolean;
  customer_id?: string;
  allow_cloud_vision?: boolean;
  nda?: boolean;
  vision_consent_by?: string;
  vision_consent_at?: string;
  attested?: boolean;
};

function apiBase(): string {
  const fallback = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  if (typeof window === "undefined") return fallback;
  try {
    const configured = new URL(fallback, window.location.origin);
    const pageHost = window.location.hostname;
    const loopback = configured.hostname === "localhost" || configured.hostname === "127.0.0.1";
    if (loopback && pageHost !== "localhost" && pageHost !== "127.0.0.1") {
      return `${window.location.protocol}//${pageHost}:8000`;
    }
    return configured.origin;
  } catch {
    return fallback;
  }
}

export function CustomerVisionConsent() {
  const [featureOn, setFeatureOn] = useState(false);
  const [customerId, setCustomerId] = useState("");
  const [allow, setAllow] = useState(false);
  const [nda, setNda] = useState(false);
  const [attestedBy, setAttestedBy] = useState("");
  const [consentMeta, setConsentMeta] = useState<{ by: string; at: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const probeEnabled = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase()}/api/masterdata/vision-consent`);
      if (!res.ok) {
        setFeatureOn(false);
        return;
      }
      const data = (await res.json()) as ConsentPayload;
      setFeatureOn(Boolean(data.enabled));
    } catch {
      setFeatureOn(false);
    }
  }, []);

  useEffect(() => {
    void probeEnabled();
  }, [probeEnabled]);

  const loadCustomer = useCallback(async (cid: string) => {
    const trimmed = cid.trim();
    if (!trimmed) return;
    try {
      const res = await fetch(
        `${apiBase()}/api/masterdata/vision-consent?customer_id=${encodeURIComponent(trimmed)}`,
      );
      if (!res.ok) return;
      const data = (await res.json()) as ConsentPayload;
      if (!data.enabled) {
        setFeatureOn(false);
        return;
      }
      setAllow(Boolean(data.allow_cloud_vision));
      setNda(Boolean(data.nda));
      if (data.vision_consent_by) {
        setConsentMeta({
          by: data.vision_consent_by,
          at: data.vision_consent_at || "",
        });
      } else {
        setConsentMeta(null);
      }
    } catch {
      /* ignore */
    }
  }, []);

  const onSave = async () => {
    setMessage(null);
    const cid = customerId.trim();
    const who = attestedBy.trim();
    if (!cid || !who) {
      setMessage("Customer id and attested-by are required.");
      return;
    }
    setBusy(true);
    try {
      const res = await fetch(`${apiBase()}/api/masterdata/vision-consent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customer_id: cid,
          allow,
          nda,
          attested_by: who,
        }),
      });
      const data = (await res.json()) as ConsentPayload & { ok?: boolean; error?: string };
      if (!data.enabled) {
        setFeatureOn(false);
        return;
      }
      if (!data.ok) {
        setMessage(data.error || "Could not save consent.");
        return;
      }
      setMessage("Vision consent saved.");
      await loadCustomer(cid);
    } catch {
      setMessage("Could not reach the API.");
    } finally {
      setBusy(false);
    }
  };

  if (!featureOn) return null;

  return (
    <SpotlightCard
      className="shrink-0 rounded-2xl border border-[color:var(--border)] bg-black/40 backdrop-blur-md"
      bodyClassName="p-4"
    >
      <p className="mb-2 font-mono text-[10px] uppercase tracking-[0.22em]">
        <GradientText className="font-mono text-[10px] uppercase tracking-[0.22em]" animationSpeed={9}>
          Cloud vision consent
        </GradientText>
      </p>
      <p className="mb-3 text-xs text-[color:var(--muted)]">
        Gate 1: drawings go to a cloud model only when allow is on, NDA is off, and you attest below.
        The vision bench analyse button cannot override an NDA or grant consent by itself.
      </p>
      <label className="mb-2 block font-mono text-[10px] uppercase tracking-[0.14em] text-[color:var(--muted)]">
        Customer id
        <input
          type="text"
          value={customerId}
          onChange={(e) => setCustomerId(e.target.value)}
          onBlur={() => void loadCustomer(customerId)}
          className="mt-1 w-full rounded-lg border border-[color:var(--border)] bg-black/50 px-3 py-2 font-display text-sm text-[color:var(--fg)]"
          placeholder="customers.id"
        />
      </label>
      <label className="mb-2 flex items-center gap-2 text-sm text-[color:var(--fg)]/90">
        <input
          type="checkbox"
          checked={allow}
          onChange={(e) => setAllow(e.target.checked)}
          className="rounded border-[color:var(--border)]"
        />
        Allow cloud vision
      </label>
      <label className="mb-2 flex items-center gap-2 text-sm text-[color:var(--fg)]/90">
        <input
          type="checkbox"
          checked={nda}
          onChange={(e) => setNda(e.target.checked)}
          className="rounded border-[color:var(--border)]"
        />
        NDA on file (blocks cloud vision)
      </label>
      {nda ? (
        <p className="mb-2 text-xs text-amber-200/90">
          NDA is set — analyse on the vision queue will not send this customer&apos;s drawings to a cloud
          model until NDA is cleared here.
        </p>
      ) : null}
      <label className="mb-3 block font-mono text-[10px] uppercase tracking-[0.14em] text-[color:var(--muted)]">
        Attested by
        <input
          type="text"
          value={attestedBy}
          onChange={(e) => setAttestedBy(e.target.value)}
          className="mt-1 w-full rounded-lg border border-[color:var(--border)] bg-black/50 px-3 py-2 font-display text-sm text-[color:var(--fg)]"
          placeholder="Owner name"
        />
      </label>
      {consentMeta ? (
        <p className="mb-2 font-mono text-[10px] text-[color:var(--muted)]/80">
          Last attested by {consentMeta.by}
          {consentMeta.at ? ` · ${consentMeta.at}` : ""}
        </p>
      ) : null}
      {message ? <p className="mb-2 text-xs text-[color:var(--fg)]/85">{message}</p> : null}
      <button
        type="button"
        disabled={busy}
        onClick={() => void onSave()}
        className="rounded-lg border border-[#7dffe0]/35 bg-[#7dffe0]/10 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.08em] text-[color:var(--fg)] transition hover:bg-[#7dffe0]/20 disabled:opacity-50"
      >
        Save attestation
      </button>
    </SpotlightCard>
  );
}
