"use client";

import type { Scene, Widget } from "@/lib/types";
import { WidgetCard } from "@/components/Widgets";
import GlareHover from "@/components/react-bits/GlareHover";
import GradientText from "@/components/react-bits/GradientText";
import SpotlightCard from "@/components/react-bits/SpotlightCard";

const PANEL =
  "rounded-2xl border border-[color:var(--border)] bg-black/35 backdrop-blur-md";

function nonAttachmentWidgets(widgets: Widget[]): Widget[] {
  return widgets.filter((w) => w.type !== "attachments");
}

export function QuoteStack({ scene }: { scene: Scene }) {
  const widgets = nonAttachmentWidgets(scene.widgets || []);
  const checklists = widgets.filter((w) => w.type === "checklist");
  const kpis = widgets.filter((w) => w.type === "kpi");
  const rest = widgets.filter((w) => w.type !== "kpi" && w.type !== "checklist");

  if (!widgets.length) {
    return (
      <div className={`${PANEL} flex flex-1 items-center justify-center px-6 py-10 text-center`}>
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[color:var(--muted)]/70">
          Quote and strategy will appear here when the job loads.
        </p>
      </div>
    );
  }

  return (
    <SpotlightCard
      className={`${PANEL} min-h-0 flex-1`}
      bodyClassName="max-h-full overflow-y-auto p-4"
    >
      <p className="mb-3 font-mono text-[10px] uppercase tracking-[0.22em]">
        <GradientText className="font-mono text-[10px] uppercase tracking-[0.22em]" animationSpeed={9}>
          Quote & strategy
        </GradientText>
      </p>
      {checklists.length ? (
        <div className="mb-3 space-y-2">
          {checklists.map((widget, index) => (
            <GlareHover key={`checklist-${index}`} className="rounded-xl">
              <div className="rounded-xl border border-[#7dffe0]/25 bg-black/40 p-3">
                <WidgetCard widget={widget} />
              </div>
            </GlareHover>
          ))}
        </div>
      ) : null}
      {kpis.length ? (
        <div className="mb-3 grid grid-cols-2 gap-2">
          {kpis.map((widget, index) => (
            <GlareHover key={`kpi-${index}`} className="rounded-xl">
              <div className="rounded-xl border border-[color:var(--border)] bg-black/30 px-3 py-2.5">
                <WidgetCard widget={widget} />
              </div>
            </GlareHover>
          ))}
        </div>
      ) : null}
      <div className="grid gap-3">
        {rest.map((widget, index) => (
          <GlareHover key={`w-${index}`} className="rounded-xl">
            <div className="rounded-xl border border-[color:var(--border)] bg-black/30 p-3">
              <WidgetCard widget={widget} />
            </div>
          </GlareHover>
        ))}
      </div>
    </SpotlightCard>
  );
}
