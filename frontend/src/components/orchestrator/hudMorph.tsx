"use client";

import type { ReactNode } from "react";
import {
  chromeOn,
  presenceOn,
  presenceVisible,
  type HudLayers,
  type HudWorkspace,
} from "./hudWorkspace";

export function HudPresence({
  id,
  layers,
  children,
  keepMounted = false,
}: {
  id: HudWorkspace;
  layers: HudLayers;
  children: ReactNode;
  keepMounted?: boolean;
}) {
  const visible = presenceVisible(id, layers);
  if (!keepMounted && !visible) return null;
  const lit = presenceOn(id, layers);
  // Outgoing keeps opacity during the presence overlap so orb/eye/bench crossfade
  // instead of snapping to black when incoming takes over.
  const visibleOpacity = lit || layers.outgoing === id;
  return (
    <div
      className={["hud-presence", visibleOpacity ? "hud-presence-on" : ""].join(" ")}
      data-hud-presence={id}
      aria-hidden={!lit}
    >
      {children}
    </div>
  );
}

export function HudChrome({
  id,
  layers,
  children,
  className = "",
}: {
  id: HudWorkspace;
  layers: HudLayers;
  children: ReactNode;
  className?: string;
}) {
  if (!presenceVisible(id, layers)) return null;
  const on = chromeOn(id, layers);
  return (
    <div
      className={["hud-chrome", on ? "hud-chrome-on" : "", className].filter(Boolean).join(" ")}
      data-hud-chrome={id}
    >
      {children}
    </div>
  );
}
