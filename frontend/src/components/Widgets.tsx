import type { MailAttachment, Widget } from "@/lib/types";
import { isSavedLocal } from "@/lib/viewerMatch";
import { splitMarkdownTables } from "@/lib/tables";
import { useMemo, useState } from "react";

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
  const blocks = splitMarkdownTables(widget.text || "");
  const hasTable = blocks.some((block) => block.kind === "table");
  if (!hasTable) {
    return (
      <div>
        {widget.title ? <h3 className="mb-2 text-sm text-white/40">{widget.title}</h3> : null}
        <div className="whitespace-pre-wrap leading-relaxed text-white/70">{widget.text}</div>
      </div>
    );
  }
  return (
    <div className="space-y-6">
      {widget.title ? <h3 className="text-sm text-white/40">{widget.title}</h3> : null}
      {blocks.map((block, index) =>
        block.kind === "table" ? (
          <TableCard
            key={`t-${index}`}
            widget={{ type: "table", columns: block.columns, rows: block.rows }}
          />
        ) : (
          <div key={`p-${index}`} className="whitespace-pre-wrap leading-relaxed text-white/70">
            {block.text}
          </div>
        ),
      )}
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
        {(widget.items || []).map((item, index) => {
          const title = String(item.title ?? "");
          const time = String(item.time ?? "");
          const detail = item.detail != null ? String(item.detail) : "";
          return (
          <li key={`${title}-${index}`} className="flex gap-5">
            <span className="w-12 shrink-0 font-display text-lg text-white/50">{time}</span>
            <div>
              <p className="text-white">{title}</p>
              {detail ? <p className="text-sm text-white/35">{detail}</p> : null}
            </div>
          </li>
          );
        })}
      </ol>
    </div>
  );
}

function statusText(item: MailAttachment): string {
  if (item.status === "both") return "Saved · Drive";
  if (item.status === "local") return item.local_name ? `Saved here (${item.local_name})` : "Saved here";
  if (item.status === "drive") return item.drive_link ? "On Drive" : "Drive";
  return "Gmail only";
}

function AttachmentList({
  widget,
  onSave,
  onReply,
  onView,
  busy,
}: {
  widget: Widget;
  onSave: (emailId: string, attachmentIds: string[], filenames: string[]) => void;
  onReply: (emailId: string, attachmentIds: string[], filenames: string[]) => void;
  onView?: (item: MailAttachment) => void;
  busy?: boolean;
}) {
  const emailId = widget.email_id || "";
  const items = (widget.items || []) as MailAttachment[];
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const toggle = (id: string) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectedIds = useMemo(() => Array.from(selected), [selected]);
  const selectedNames = useMemo(
    () => items.filter((item) => selected.has(item.attachment_id)).map((item) => item.filename),
    [items, selected],
  );

  return (
    <div>
      {widget.title ? <h3 className="mb-3 text-sm text-white/40">{widget.title}</h3> : null}
      <ul className="space-y-2">
        {items.map((item) => (
          <li key={item.attachment_id || item.filename} className="flex items-start gap-3 border-t border-white/5 py-2.5">
            <input
              type="checkbox"
              checked={selected.has(item.attachment_id)}
              onChange={() => toggle(item.attachment_id)}
              aria-label={item.filename}
              className="mt-1 h-4 w-4 accent-cyan"
            />
            <div className="min-w-0 flex-1">
              <p className="truncate text-white/85">{item.filename}</p>
              <p className="text-xs text-cyan/70">{statusText(item)}</p>
              {item.drive_link ? (
                <a href={item.drive_link} target="_blank" rel="noreferrer" className="text-xs text-white/35 underline">
                  Drive link
                </a>
              ) : null}
            </div>
            {onView ? (
              <button
                type="button"
                disabled={busy || !isSavedLocal(item)}
                title={isSavedLocal(item) ? "View saved drawing" : "Save locally first"}
                onClick={() => onView(item)}
                className="shrink-0 rounded border border-cyan/40 px-3 py-1 text-xs tracking-wide text-cyan transition hover:bg-cyan/10 disabled:cursor-not-allowed disabled:opacity-30"
              >
                View
              </button>
            ) : null}
          </li>
        ))}
      </ul>
      <div className="mt-4 flex flex-wrap gap-3">
        <button
          type="button"
          disabled={busy || !emailId || selectedIds.length === 0}
          onClick={() => onSave(emailId, selectedIds, selectedNames)}
          className="rounded border border-cyan/40 px-4 py-2 text-sm tracking-wide text-cyan transition hover:bg-cyan/10 disabled:opacity-30"
        >
          Save selected
        </button>
        <button
          type="button"
          disabled={busy || !emailId || selectedIds.length === 0}
          onClick={() => onReply(emailId, selectedIds, selectedNames)}
          className="rounded border border-white/15 px-4 py-2 text-sm tracking-wide text-white/70 transition hover:bg-white/5 disabled:opacity-30"
        >
          Attach selected to reply
        </button>
        {onView ? (
          <button
            type="button"
            disabled={
              busy ||
              !items.some((item) => selected.has(item.attachment_id) && isSavedLocal(item))
            }
            onClick={() => {
              const saved = items.find((item) => selected.has(item.attachment_id) && isSavedLocal(item));
              if (saved) onView(saved);
            }}
            className="rounded border border-cyan/25 px-4 py-2 text-sm tracking-wide text-cyan/80 transition hover:bg-cyan/10 disabled:opacity-30"
          >
            View selected
          </button>
        ) : null}
      </div>
    </div>
  );
}

function Quote({ widget }: { widget: Widget }) {
  return <p className="font-display text-3xl text-white/80">{widget.text}</p>;
}

export function WidgetCard({
  widget,
  onSaveAttachments,
  onReplyAttachments,
  onViewAttachment,
  busy,
}: {
  widget: Widget;
  onSaveAttachments?: (emailId: string, attachmentIds: string[], filenames: string[]) => void;
  onReplyAttachments?: (emailId: string, attachmentIds: string[], filenames: string[]) => void;
  onViewAttachment?: (item: MailAttachment) => void;
  busy?: boolean;
}) {
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
    case "attachments":
      return (
        <AttachmentList
          widget={widget}
          busy={busy}
          onSave={onSaveAttachments || (() => undefined)}
          onReply={onReplyAttachments || (() => undefined)}
          onView={onViewAttachment}
        />
      );
    default:
      return <MarkdownCard widget={widget} />;
  }
}
