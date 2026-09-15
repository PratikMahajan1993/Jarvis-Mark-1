"use client";

import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Preferences } from "@/lib/types";
import SpotlightCard from "@/components/react-bits/SpotlightCard";
import GradientText from "@/components/react-bits/GradientText";

function GoogleConnect() {
  const [status, setStatus] = useState<{
    configured: boolean;
    connected: boolean;
    calendar?: boolean;
    calendar_list?: boolean;
    sheets?: boolean;
    account: string;
  } | null>(null);

  useEffect(() => {
    api.googleStatus().then(setStatus).catch(() => setStatus(null));
  }, []);

  if (!status) return null;

  const calendarOn = Boolean(status.calendar);
  const allCalendars = Boolean(status.calendar_list);
  const sheetsOn = Boolean(status.sheets);
  const extras = [
    calendarOn ? "Calendar on" : status.connected ? "Calendar needs reconnect" : "",
    status.connected && calendarOn && !allCalendars ? "primary only" : "",
    status.connected ? (sheetsOn ? "Sheets on" : "Sheets needs reconnect") : "",
  ].filter(Boolean);

  return (
    <div className="border-t border-[color:var(--border)] pt-4">
      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-[color:var(--accent)]">Google</p>
      <p className="mt-2 text-sm text-[color:var(--muted)]">
        {status.connected
          ? `Connected as ${status.account}${extras.length ? ` · ${extras.join(" · ")}` : ""}`
          : status.configured
            ? "Not connected — connect to use live Gmail, Calendar, Drive, and Sheets."
            : "Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to .env on the API machine."}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {status.configured && !status.connected ? (
          <button
            type="button"
            className="rounded-full border border-[color:var(--accent)]/40 bg-[color:var(--accent)]/10 px-4 py-1.5 font-mono text-[11px] uppercase tracking-[0.12em] text-[color:var(--accent)] transition hover:bg-[color:var(--accent)]/20"
            onClick={() => {
              window.location.href = api.googleAuthUrl();
            }}
          >
            Connect Gmail
          </button>
        ) : null}
        {status.connected && !calendarOn ? (
          <button
            type="button"
            className="rounded-full border border-[color:var(--accent)]/40 bg-[color:var(--accent)]/10 px-4 py-1.5 font-mono text-[11px] uppercase tracking-[0.12em] text-[color:var(--accent)] transition hover:bg-[color:var(--accent)]/20"
            onClick={() => {
              window.location.href = api.googleAuthUrl();
            }}
          >
            Add Calendar
          </button>
        ) : null}
        {status.connected && calendarOn && !allCalendars ? (
          <button
            type="button"
            className="rounded-full border border-[color:var(--border)] px-4 py-1.5 font-mono text-[11px] uppercase tracking-[0.12em] text-[color:var(--muted)] transition hover:border-[color:var(--accent)]/30 hover:text-[color:var(--accent)]"
            onClick={() => {
              window.location.href = api.googleAuthUrl();
            }}
          >
            Allow all calendars
          </button>
        ) : null}
        {status.connected && !sheetsOn ? (
          <button
            type="button"
            className="rounded-full border border-[color:var(--accent)]/40 bg-[color:var(--accent)]/10 px-4 py-1.5 font-mono text-[11px] uppercase tracking-[0.12em] text-[color:var(--accent)] transition hover:bg-[color:var(--accent)]/20"
            onClick={() => {
              window.location.href = api.googleAuthUrl();
            }}
          >
            Add Sheets
          </button>
        ) : null}
      </div>
    </div>
  );
}

function SettingsForm({
  prefs,
  onSave,
}: {
  prefs: Preferences;
  onSave: (next: Partial<Preferences>) => Promise<void>;
}) {
  const [draft, setDraft] = useState(prefs);
  useEffect(() => setDraft(prefs), [prefs]);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void onSave(draft);
  }

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      {(
        [
          ["display_name", "What I call you"],
          ["assistant_name", "What you call me"],
          ["timezone", "Timezone"],
        ] as const
      ).map(([key, label]) => (
        <label key={key} className="block text-sm">
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-[color:var(--muted)]">{label}</span>
          <input
            value={String(draft[key])}
            onChange={(event) => setDraft({ ...draft, [key]: event.target.value })}
            className="mt-1.5 w-full rounded-lg border border-[color:var(--border)] bg-black/30 px-3 py-2 text-sm text-white outline-none transition focus:border-[color:var(--accent)]/50"
          />
        </label>
      ))}
      {(
        [
          ["voice_enabled", "Speak aloud"],
          ["email_enabled", "Mail tools"],
          ["calendar_enabled", "Calendar tools"],
          ["files_enabled", "Files"],
          ["research_enabled", "Research"],
        ] as const
      ).map(([key, label]) => (
        <label key={key} className="flex items-center justify-between gap-4 text-sm text-[color:var(--muted)]">
          {label}
          <input
            type="checkbox"
            checked={Boolean(draft[key])}
            onChange={(event) => setDraft({ ...draft, [key]: event.target.checked })}
            className="h-4 w-4 accent-[color:var(--accent)]"
          />
        </label>
      ))}
      <GoogleConnect />
      <button
        type="submit"
        className="mt-2 w-full rounded-full border border-[color:var(--accent)]/40 bg-[color:var(--accent)]/10 py-2 font-mono text-[11px] uppercase tracking-[0.14em] text-[color:var(--accent)] transition hover:bg-[color:var(--accent)]/20"
      >
        Save preferences
      </button>
    </form>
  );
}

export function PreferencesPanel({
  open,
  prefs,
  onClose,
  onSave,
}: {
  open: boolean;
  prefs: Preferences | null;
  onClose: () => void;
  onSave: (next: Partial<Preferences>) => Promise<void>;
}) {
  if (!open) return null;

  return (
    <div className="pointer-events-auto fixed inset-0 z-[30] bg-black/55 backdrop-blur-sm" onClick={onClose}>
      <div
        className="ml-auto flex h-full w-full max-w-md flex-col p-4 sm:p-6"
        onClick={(event) => event.stopPropagation()}
      >
        <SpotlightCard
          className="flex h-full min-h-0 flex-col rounded-2xl border border-[color:var(--border)] bg-black/45 backdrop-blur-md"
          bodyClassName="flex min-h-0 flex-1 flex-col overflow-y-auto p-6"
        >
          <div className="mb-4 flex items-start justify-between gap-3">
            <div>
              <GradientText className="font-mono text-[10px] uppercase tracking-[0.2em]" animationSpeed={9}>
                Configuration
              </GradientText>
              <h2 className="mt-1 font-display text-lg text-white">Preferences</h2>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-full border border-[color:var(--border)] px-3 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-[color:var(--muted)] transition hover:border-[color:var(--accent)]/30 hover:text-[color:var(--accent)]"
            >
              Close
            </button>
          </div>
          {prefs ? (
            <SettingsForm prefs={prefs} onSave={onSave} />
          ) : (
            <p className="text-sm text-[color:var(--muted)]">Could not load preferences. Is the API running?</p>
          )}
        </SpotlightCard>
      </div>
    </div>
  );
}
