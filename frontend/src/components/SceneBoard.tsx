import type { MailAttachment, Scene } from "@/lib/types";
import { WidgetCard } from "./Widgets";

const ORCH_PANEL = "rounded-xl border border-[color:var(--border)] bg-black/35 backdrop-blur-md";

export function SceneBoard({
  scene,
  dense,
  compact,
  onSaveAttachments,
  onReplyAttachments,
  onViewAttachment,
  busy,
}: {
  scene: Scene;
  dense?: boolean;
  compact?: boolean;
  onSaveAttachments?: (emailId: string, attachmentIds: string[], filenames: string[]) => void;
  onReplyAttachments?: (emailId: string, attachmentIds: string[], filenames: string[]) => void;
  onViewAttachment?: (item: MailAttachment) => void;
  busy?: boolean;
}) {
  const widgets = scene.widgets || [];
  const title = (scene.title || "").trim();
  const decorativeTitle = !title || /^jarvis$/i.test(title);
  // Speak-only shells (empty/Jarvis title, no real widgets or quote-only) — VoiceLine owns the reply
  if (!widgets.length && decorativeTitle) return null;
  if (widgets.length && decorativeTitle && widgets.every((w) => w.type === "quote")) return null;
  const kpis = widgets.filter((widget) => widget.type === "kpi");
  const rest = widgets.filter((widget) => widget.type !== "kpi");
  const widgetProps = { onSaveAttachments, onReplyAttachments, onViewAttachment, busy };

  if (compact) {
    return (
      <section className="w-full px-0 pb-2">
        {scene.title ? (
          <header className="mb-3">
            <h1 className="font-display text-xl text-[color:var(--fg)]">{scene.title}</h1>
            {scene.subtitle ? <p className="mt-1 text-xs text-[color:var(--muted)]">{scene.subtitle}</p> : null}
          </header>
        ) : null}
        {kpis.length ? (
          <div className="mb-3 grid grid-cols-2 gap-3">
            {kpis.map((widget, index) => (
              <WidgetCard key={`kpi-${index}`} widget={widget} {...widgetProps} />
            ))}
          </div>
        ) : null}
        <div className="grid gap-3">
          {rest.map((widget, index) => (
            <WidgetCard key={`w-${index}`} widget={widget} {...widgetProps} />
          ))}
        </div>
      </section>
    );
  }

  return (
    <section className="mx-auto w-full max-w-5xl px-6 pb-8">
      {scene.title ? (
        <header className="mb-10">
          <h1 className="font-display text-5xl tracking-wide text-[color:var(--fg)] md:text-6xl">{scene.title}</h1>
          {scene.subtitle ? <p className="mt-2 text-[color:var(--muted)]">{scene.subtitle}</p> : null}
        </header>
      ) : null}
      {kpis.length ? (
        <div className={`mb-8 grid gap-4 ${dense ? "grid-cols-2 xl:grid-cols-4" : "grid-cols-2 md:grid-cols-3"}`}>
          {kpis.map((widget, index) => (
            <div key={`kpi-${index}`} className={`${ORCH_PANEL} px-5 py-4`}>
              <WidgetCard widget={widget} {...widgetProps} />
            </div>
          ))}
        </div>
      ) : null}
      <div className="grid gap-6">
        {rest.map((widget, index) => (
          <div key={`w-${index}`} className={`${ORCH_PANEL} p-5`}>
            <WidgetCard widget={widget} {...widgetProps} />
          </div>
        ))}
      </div>
    </section>
  );
}
