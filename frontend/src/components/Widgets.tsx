import type { Widget } from "@/lib/types";

function Kpi({ widget }: { widget: Widget }) {
  return (
    <div>
      <p className="text-[11px] tracking-[0.25em] uppercase text-white/35">{widget.label}</p>
      <p className="mt-1 font-display text-5xl leading-none text-white">{widget.value ?? "—"}</p>
    </div>
  );
}

function TableCard({ widget }: { widget: Widget }) {
  return (
    <div className="overflow-auto">
      {widget.title ? <h3 className="mb-3 text-sm text-white/40">{widget.title}</h3> : null}
      <table className="w-full text-left text-sm">
        <thead className="text-[11px] uppercase tracking-widest text-white/30">
          <tr>
            {(widget.columns || []).map((col) => (
              <th key={col} className="pb-2 pr-6 font-medium">{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {(widget.rows || []).map((row, index) => (
            <tr key={index} className="border-t border-white/5">
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} className="py-2.5 pr-6 text-white/75">{String(cell)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MarkdownCard({ widget }: { widget: Widget }) {
  return (
    <div>
      {widget.title ? <h3 className="mb-2 text-sm text-white/40">{widget.title}</h3> : null}
      <div className="whitespace-pre-wrap leading-relaxed text-white/70">{widget.text}</div>
    </div>
  );
}

function ChartCard({ widget }: { widget: Widget }) {
  const points = widget.points || [];
  const max = Math.max(1, ...points.map((point) => Number(point.value) || 0));
  return (
    <div>
      {widget.title ? <h3 className="mb-4 text-sm text-white/40">{widget.title}</h3> : null}
      <div className="flex h-32 items-end gap-3">
        {points.map((point) => (
          <div key={point.label} className="flex flex-1 flex-col items-center gap-2">
            <div className="w-full rounded-t bg-cyan/70" style={{ height: `${(Number(point.value) / max) * 100}%` }} />
            <span className="text-[11px] text-white/35">{point.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Timeline({ widget }: { widget: Widget }) {
  return (
    <div>
      {widget.title ? <h3 className="mb-4 text-sm text-white/40">{widget.title}</h3> : null}
      <ol className="space-y-3">
        {(widget.items || []).map((item, index) => (
          <li key={`${item.title}-${index}`} className="flex gap-5">
            <span className="w-12 shrink-0 font-display text-lg text-white/50">{item.time}</span>
            <div>
              <p className="text-white">{item.title}</p>
              {item.detail ? <p className="text-sm text-white/35">{item.detail}</p> : null}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

function Quote({ widget }: { widget: Widget }) {
  return <p className="font-display text-3xl text-white/80">{widget.text}</p>;
}

export function WidgetCard({ widget }: { widget: Widget }) {
  switch (widget.type) {
    case "kpi":
      return <Kpi widget={widget} />;
    case "table":
      return <TableCard widget={widget} />;
    case "chart":
      return <ChartCard widget={widget} />;
    case "timeline":
      return <Timeline widget={widget} />;
    case "quote":
      return <Quote widget={widget} />;
    default:
      return <MarkdownCard widget={widget} />;
  }
}
