"use client";

import { api } from "@/lib/api";
import ElectricBorder from "@/components/react-bits/ElectricBorder";

export type GoogleConnectStatus = {
  configured: boolean;
  connected: boolean;
  calendar?: boolean;
  calendar_list?: boolean;
  sheets?: boolean;
  account: string;
};

export function googleServicesIncomplete(status: GoogleConnectStatus | null): boolean {
  if (!status) return false;
  if (!status.configured) return true;
  if (!status.connected) return true;
  if (!status.calendar) return true;
  if (!status.sheets) return true;
  return false;
}

export function googleConnectPrompt(status: GoogleConnectStatus): {
  title: string;
  summary: string;
  actionLabel: string;
  showConnect: boolean;
} {
  if (!status.configured) {
    return {
      title: "Google is not configured",
      summary:
        "Jarvis isn't connected to your Google account yet — open Preferences to finish setup.",
      actionLabel: "Open preferences",
      showConnect: false,
    };
  }
  if (!status.connected) {
    return {
      title: "Connect Google",
      summary:
        "I'm not linked to Gmail yet. Connect your Google account so I can read mail, use Calendar, Drive, and Sheets on your desk.",
      actionLabel: "Connect Gmail",
      showConnect: true,
    };
  }
  if (!status.calendar) {
    return {
      title: "Add Calendar access",
      summary: "Gmail is connected, but Calendar is not. Grant Calendar so briefings and scheduling work with your real calendar.",
      actionLabel: "Add Calendar",
      showConnect: true,
    };
  }
  if (!status.sheets) {
    return {
      title: "Add Sheets access",
      summary: "Almost there — connect Google Sheets so shop logs and quotes can use your live workbooks.",
      actionLabel: "Add Sheets",
      showConnect: true,
    };
  }
  return {
    title: "Google connected",
    summary: "",
    actionLabel: "Connect",
    showConnect: false,
  };
}

export function googleConnectSpeakLine(status: GoogleConnectStatus): string {
  if (!status.configured) {
    return "Google isn't configured on the API yet. Check preferences when the keys are in place.";
  }
  if (!status.connected) {
    return "I'm not connected to Google yet. Please connect Gmail so I can use live mail and calendar.";
  }
  if (!status.calendar) {
    return "Gmail is connected, but I still need Calendar access. Please finish Google setup.";
  }
  if (!status.sheets) {
    return "Please add Google Sheets access to finish connecting your account.";
  }
  return "";
}

export function ConnectGoogleModal({
  status,
  visible,
  onLater,
  onOpenPreferences,
  onPromptInteract,
}: {
  status: GoogleConnectStatus | null;
  visible: boolean;
  onLater: () => void;
  onOpenPreferences?: () => void;
  /** Retry speak after user gesture (browser autoplay policy). */
  onPromptInteract?: () => void;
}) {
  if (!status || !googleServicesIncomplete(status)) return null;
  const copy = googleConnectPrompt(status);

  return (
    <div
      className={[
        "orch-google-connect absolute inset-0 z-[25] flex items-center justify-center bg-black/45 backdrop-blur-sm transition-opacity duration-[600ms]",
        visible ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0",
      ].join(" ")}
      role="dialog"
      aria-modal="true"
      aria-labelledby="google-connect-title"
    >
      <ElectricBorder
        color="#7dffe0"
        speed={0.55}
        chaos={0.06}
        borderRadius={14}
        className={[
          "w-[520px] max-w-[calc(100vw-2rem)] transition-all duration-[600ms]",
          visible ? "translate-y-0 scale-100" : "translate-y-5 scale-95",
        ].join(" ")}
      >
        <div
          className="flex w-full flex-col items-center rounded-xl border border-[color:var(--border)] px-10 py-10 text-center shadow-[0_40px_80px_rgba(0,0,0,0.8)] backdrop-blur-[20px]"
          style={{ background: "rgba(14, 14, 16, 0.82)" }}
          onPointerDown={() => onPromptInteract?.()}
        >
          <p className="mb-4 font-mono text-[0.65rem] uppercase tracking-[0.14em] text-[color:var(--accent)]">
            Setup · Google services
          </p>
          <h2 id="google-connect-title" className="mb-3 font-display text-2xl font-normal text-[color:var(--fg)]">
            {copy.title}
          </h2>
          <p className="mb-8 max-w-md text-[0.95rem] leading-relaxed text-[color:var(--muted)]">{copy.summary}</p>
          <div className="flex w-full gap-3">
            <button
              type="button"
              className="flex-1 rounded-md border border-[color:var(--border)] bg-transparent py-3 text-[0.9rem] font-medium text-[color:var(--fg)] transition hover:border-[color:var(--muted)] hover:bg-[color:var(--surface)]"
              onClick={onLater}
            >
              Not now
            </button>
            {copy.showConnect ? (
              <button
                type="button"
                className="flex-1 rounded-md border border-[color:var(--accent)]/50 bg-[color:var(--accent)]/15 py-3 text-[0.9rem] font-medium text-[color:var(--accent)] transition hover:bg-[color:var(--accent)]/25"
                onClick={() => {
                  window.location.href = api.googleAuthUrl();
                }}
              >
                {copy.actionLabel}
              </button>
            ) : (
              <button
                type="button"
                className="flex-1 rounded-md border border-[color:var(--accent)]/50 bg-[color:var(--accent)]/15 py-3 text-[0.9rem] font-medium text-[color:var(--accent)] transition hover:bg-[color:var(--accent)]/25"
                onClick={onOpenPreferences}
              >
                {copy.actionLabel}
              </button>
            )}
          </div>
        </div>
      </ElectricBorder>
    </div>
  );
}
