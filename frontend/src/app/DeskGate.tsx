"use client";

import dynamic from "next/dynamic";

const Desk = dynamic(() => import("@/core/desk/Desk").then((mod) => ({ default: mod.Desk })), {
  ssr: false,
  loading: () => null,
});

/** Desk stays client-only. The landing first frame is rendered by the server page. */
export function DeskGate() {
  return <Desk />;
}
