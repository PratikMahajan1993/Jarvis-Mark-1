import type { Conversation, MailAttachment, Widget } from "@/lib/types";
import { isSavedLocal } from "@/lib/viewerMatch";
import { splitMarkdownTables } from "@/lib/tables";
import { useMemo, useState } from "react";
import { ACCENT_SOLID_BG, ACCENT_TEXT, ACCENT_TEXT_SOFT, type Accent, Alert, HudButton, Panel, StatusDot } from "./hud/Hud";

const ACCENT_CYCLE: Accent[] = ["cyan", "violet", "magenta", "amber"];

function cycleAccent(index: number): Accent {
  return ACCENT_CYCLE[index % ACCENT_CYCLE.length];
}

function Kpi({ widget, accent = "cyan" }: { widget: Widget; accent?: Accent }) {
  return (
    <div>
      <p className={`font-mono text-[10px] uppercase tracking-[0.22em] ${ACCENT_TEXT_SOFT[accent]}`}>{widget.label}</p>
      <p className="mt-1.5 font-display text-4xl leading-none text-white">{widget.value ?? "—"}</p>
    </div>
  );
}

function TableCard({ widget }: { widget: Widget }) {
  return (
    <div className="overflow-auto">
      {widget.title ? <h3 className="mb-3 font-mono text-[11px] uppercase tracking-[0.18em] text-cyan/60">{widget.title}</h3> : null}
      <table className="w-full text-left text-sm">
        <thead className="text-[11px] uppercase tracking-widest text-white/30">
          <tr>
            {(widget.columns || []).map((col) => (
              <th key={col} className="border-b border-white/10 pb-2 pr-6 font-medium">{col}</th>
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
        {widget.title ? <h3 className="mb-2 font-mono text-[11px] uppercase tracking-[0.18em] text-cyan/60">{widget.title}</h3> : null}
        <div className="whitespace-pre-wrap leading-relaxed text-white/70">{widget.text}</div>
      </div>
    );
  }
  return (
    <div className="space-y-6">
      {widget.title ? <h3 className="font-mono text-[11px] uppercase tracking-[0.18em] text-cyan/60">{widget.title}</h3> : null}
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
      {widget.title ? <h3 className="mb-4 font-mono text-[11px] uppercase tracking-[0.18em] text-cyan/60">{widget.title}</h3> : null}
      <div className="flex h-32 items-end gap-3">
        {points.map((point, index) => (
          <div key={point.label} className="flex flex-1 flex-col items-center gap-2">
            <div
              className={`w-full rounded-t ${ACCENT_SOLID_BG[cycleAccent(index)]} opacity-80`}
              style={{ height: `${(Number(point.value) / max) * 100}%` }}
            />
            <span className="text-[11px] text-white/35">{point.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Timeline({ widget }: { widget: Widget }) {
  const items = widget.items || [];
  return (
    <div>
      {widget.title ? <h3 className="mb-4 font-mono text-[11px] uppercase tracking-[0.18em] text-cyan/60">{widget.title}</h3> : null}
      <ol className="relative space-y-5 border-l border-white/10 pl-5">
        {items.map((item, index) => {
          const title = String(item.title ?? "");
          const time = String(item.time ?? "");
          const detail = item.detail != null ? String(item.detail) : "";
          const accent = cycleAccent(index);
          return (
            <li key={`${title}-${index}`} className="relative">
              <span className={`absolute -left-[25px] top-1 h-2 w-2 rounded-full ${ACCENT_SOLID_BG[accent]}`} />
              <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-white/40">{time}</span>
              <p className="mt-0.5 text-white">{title}</p>
              {detail ? <p className="text-sm text-white/35">{detail}</p> : null}
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
      {widget.title ? <h3 className="mb-3 font-mono text-[11px] uppercase tracking-[0.18em] text-cyan/60">{widget.title}</h3> : null}
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
              <HudButton
                variant="primary"
                disabled={busy || !isSavedLocal(item)}
                title={isSavedLocal(item) ? "View saved drawing" : "Save locally first"}
                onClick={() => onView(item)}
                className="shrink-0 py-1"
              >
                View
              </HudButton>
            ) : null}
          </li>
        ))}
      </ul>
      <div className="mt-4 flex flex-wrap gap-3">
        <HudButton variant="primary" disabled={busy || !emailId || selectedIds.length === 0} onClick={() => onSave(emailId, selectedIds, selectedNames)}>
          Save selected
        </HudButton>
        <HudButton variant="ghost" disabled={busy || !emailId || selectedIds.length === 0} onClick={() => onReply(emailId, selectedIds, selectedNames)}>
          Attach to reply
        </HudButton>
        {onView ? (
          <HudButton
            variant="secondary"
            disabled={busy || !items.some((item) => selected.has(item.attachment_id) && isSavedLocal(item))}
            onClick={() => {
              const saved = items.find((item) => selected.has(item.attachment_id) && isSavedLocal(item));
              if (saved) onView(saved);
            }}
          >
            View selected
          </HudButton>
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
  accent,
  onSaveAttachments,
  onReplyAttachments,
  onViewAttachment,
  busy,
}: {
  widget: Widget;
  accent?: Accent;
  onSaveAttachments?: (emailId: string, attachmentIds: string[], filenames: string[]) => void;
  onReplyAttachments?: (emailId: string, attachmentIds: string[], filenames: string[]) => void;
  onViewAttachment?: (item: MailAttachment) => void;
  busy?: boolean;
}) {
  switch (widget.type) {
    case "kpi":
      return <Kpi widget={widget} accent={accent} />;
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

export type CriticalKind = "rfq" | "efficiency" | "shift";
export type CriticalTone = "cyan" | "amber" | "red";

export type CriticalItem = {
  kind: CriticalKind;
  title: string;
  detail?: string;
  tone?: CriticalTone;
  href?: string;
};

const CRITICAL_KINDS: readonly CriticalKind[] = ["rfq", "efficiency", "shift"];
const CRITICAL_TONES: readonly CriticalTone[] = ["cyan", "amber", "red"];
const CRITICAL_KIND_LABEL: Record<CriticalKind, string> = {
  rfq: "RFQ",
  efficiency: "Efficiency",
  shift: "Shift",
};

type ConversationLike = Partial<Pick<Conversation, "id" | "category" | "title" | "minimized">> | null | undefined;

function isCriticalKind(value: string): value is CriticalKind {
  return (CRITICAL_KINDS as readonly string[]).includes(value);
}

function isCriticalTone(value: string): value is CriticalTone {
  return (CRITICAL_TONES as readonly string[]).includes(value);
}

function expandedDrawing(conversations: ReadonlyArray<ConversationLike> | null | undefined): { id: string; title: string } | null {
  if (!Array.isArray(conversations)) return null;
  for (const row of conversations) {
    if (!row || typeof row !== "object") continue;
    const id = typeof row.id === "string" ? row.id.trim() : "";
    if (!id) continue;
    const category = typeof row.category === "string" ? row.category.trim().toLowerCase() : "";
    if (category !== "drawing") continue;
    if (row.minimized) continue;
    const title = typeof row.title === "string" ? row.title.trim() : "";
    return { id, title: title || "Drawing" };
  }
  return null;
}

/** Local Wave-1 critical: an expanded drawing conversation is an RFQ chip. Mail scenes do not qualify. */
export function deriveCritical(
  conversations: ReadonlyArray<ConversationLike> | null | undefined,
): (CriticalItem & { sourceId: string }) | null {
  const drawing = expandedDrawing(conversations);
  if (!drawing) return null;
  return {
    kind: "rfq",
    title: drawing.title,
    detail: "Drawing on the dock — waiting.",
    tone: "amber",
    sourceId: drawing.id,
  };
}

export function CriticalStrip({
  item,
  onDismiss,
}: {
  item: CriticalItem | null | undefined;
  onDismiss?: () => void;
}) {
  if (!item || typeof item !== "object") return null;
  const kind = typeof item.kind === "string" && isCriticalKind(item.kind) ? item.kind : null;
  if (!kind) return null;
  const tone = typeof item.tone === "string" && isCriticalTone(item.tone) ? item.tone : "cyan";
  const title = typeof item.title === "string" && item.title.trim() ? item.title.trim() : CRITICAL_KIND_LABEL[kind];
  const detail = typeof item.detail === "string" && item.detail.trim() ? item.detail.trim() : "";
  const href = typeof item.href === "string" && /^(https?:\/\/|\/|#)/.test(item.href) ? item.href : "";
  const titleNode = href ? (
    <a href={href} className={`${ACCENT_TEXT[tone]} underline-offset-2 hover:underline`}>
      {title}
    </a>
  ) : (
    title
  );
  return (
    <Panel
      accent={tone}
      className="critical-strip"
      eyebrow={
        <span className="inline-flex items-center gap-1.5">
          <StatusDot accent={tone} />
          {CRITICAL_KIND_LABEL[kind]}
        </span>
      }
      title={titleNode}
      right={
        onDismiss ? (
          <HudButton variant="ghost" className="py-1" onClick={onDismiss} aria-label="Dismiss critical alert">
            Dismiss
          </HudButton>
        ) : undefined
      }
      bodyClassName={detail ? "px-4 py-1.5" : "hidden"}
    >
      {detail ? (
        <Alert tone={tone === "red" ? "error" : tone === "amber" ? "warn" : "info"} className="whisper py-1">
          {detail}
        </Alert>
      ) : null}
    </Panel>
  );
}
