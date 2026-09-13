import type { OrchestratorMode } from "@/lib/orchestrator";

export function JarvisCore({ mode }: { mode: OrchestratorMode }) {
  const active = mode === "busy" || mode === "listening";
  const hitl = mode === "hitl";
  return (
    <>
      <div className="pointer-events-none absolute left-1/2 top-1/2 z-0 flex h-[600px] w-[600px] -translate-x-1/2 -translate-y-1/2 items-center justify-center">
        <div
          className={[
            "orch-core h-full w-full rounded-full",
            active ? "orch-core-active" : "",
            hitl ? "orch-core-hitl" : "",
          ]
            .filter(Boolean)
            .join(" ")}
        />
      </div>
      <div
        className={[
          "orch-hud pointer-events-none absolute left-1/2 top-1/2 z-0 h-[400px] w-[400px] -translate-x-1/2 -translate-y-1/2",
          active ? "orch-hud-active" : "",
          hitl ? "orch-hud-hitl" : "",
        ]
          .filter(Boolean)
          .join(" ")}
      >
        <div className="orch-ring orch-ring-1" />
        <div className="orch-ring orch-ring-2" />
        <div className="orch-ring orch-ring-3" />
      </div>
    </>
  );
}
