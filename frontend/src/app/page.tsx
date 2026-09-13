"use client";

import dynamic from "next/dynamic";

const OrchestratorShell = dynamic(
  () =>
    import("@/components/orchestrator/OrchestratorShell").then((mod) => ({
      default: mod.OrchestratorShell,
    })),
  {
    ssr: false,
    loading: () => <div className="orch-root relative h-screen overflow-hidden" />,
  },
);

export default function HomePage() {
  return <OrchestratorShell />;
}
