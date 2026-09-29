"use client";

import { useEffect } from "react";
import { useDesk } from "@/core/stores/deskStore";
import { handleDeskKey, initDesk, maybeAnnounceGoogle, reconcileOpenTurn } from "./controller";

/** Mounts the desk controller once: boot, effect runners, global keys, focus reconcile. */
export function DeskController() {
  useEffect(() => initDesk(), []);

  useEffect(() => {
    const onFocus = () => void reconcileOpenTurn();
    window.addEventListener("focus", onFocus);
    window.addEventListener("keydown", handleDeskKey);
    return () => {
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("keydown", handleDeskKey);
    };
  }, []);

  const googleConnectOpen = useDesk((s) => s.googleConnectOpen);
  const googleStatus = useDesk((s) => s.googleStatus);
  useEffect(() => {
    if (!googleConnectOpen || !googleStatus) return;
    // Defer past bootstrap silence() / session restore so the line is not swallowed.
    const timer = window.setTimeout(maybeAnnounceGoogle, 450);
    return () => window.clearTimeout(timer);
  }, [googleConnectOpen, googleStatus]);

  return null;
}
