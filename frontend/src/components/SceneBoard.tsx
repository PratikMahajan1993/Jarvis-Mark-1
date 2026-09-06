import type { Scene } from "@/lib/types";
import { WidgetCard } from "./Widgets";

export function SceneBoard({ scene, dense }: { scene: Scene; dense?: boolean }) {
  if (!scene.title && !scene.widgets.length) return null;
  const kpis = scene.widgets.filter((widget) => widget.type === "kpi");
  const rest = scene.widgets.filter((widget) => widget.type !== "kpi");
  return (
    <section className="mx-auto min-h-0 w-full max-w-5xl overflow-auto px-6">
      {scene.title ? (
        <header className="mb-10">
          <h1 className="font-display text-5xl tracking-wide text-white md:text-6xl">{scene.title}</h1>
          {scene.subtitle ? <p className="mt-2 text-white/40">{scene.subtitle}</p> : null}
        </header>
      ) : null}
      {kpis.length ? (
        <div className={`mb-8 grid gap-8 ${dense ? "grid-cols-2 xl:grid-cols-4" : "grid-cols-2 md:grid-cols-3"}`}>
          {kpis.map((widget, index) => (
            <WidgetCard key={`kpi-${index}`} widget={widget} />
          ))}
        </div>
      ) : null}
      <div className="grid gap-8">
        {rest.map((widget, index) => (
          <WidgetCard key={`w-${index}`} widget={widget} />
        ))}
      </div>
    </section>
  );
}
