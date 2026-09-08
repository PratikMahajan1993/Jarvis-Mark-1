"use client";

import dynamic from "next/dynamic";

const HudShell = dynamic(
  () => import("@/components/HudShell").then((mod) => ({ default: mod.HudShell })),
  {
    ssr: false,
    loading: () => <div className="hud-bg relative flex h-screen flex-col overflow-hidden" />,
  },
);

export default function HomePage() {
  return <HudShell />;
}
