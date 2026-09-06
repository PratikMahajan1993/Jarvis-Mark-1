"use client";

import { useCanvasActions } from "@/lib/canvas/store";
import type { PdfItem } from "@/lib/canvas/types";

const MM_PER_POINT = 25.4 / 72;

function pageSize(item: PdfItem): string {
  if (!item.naturalW || !item.naturalH) return "";
  const width = Math.round(item.naturalW * MM_PER_POINT);
  const height = Math.round(item.naturalH * MM_PER_POINT);
  return `${width} × ${height} mm`;
}

/**
 * Placeholder until pdfjs-dist lands: the item already carries the true page
 * geometry, so swapping this body for a rendered page changes nothing else.
 */
export function PdfCard({ item }: { item: PdfItem }) {
  const { transport } = useCanvasActions();
  const source = transport.fileUrl(item.fileId);
  const size = pageSize(item);

  return (
    <div className="glass flex h-full w-full flex-col justify-between rounded-sm p-5">
      <div className="min-h-0">
        <p className="text-[10px] uppercase tracking-[0.3em] text-cyan/60">PDF</p>
        <p className="mt-2 break-words text-sm leading-snug text-white/80">{item.name}</p>
      </div>
      <div className="shrink-0 text-[11px] text-white/35">
        <p>
          {item.pageCount > 0 ? `${item.pageCount} page${item.pageCount === 1 ? "" : "s"}` : "Document"}
          {size ? ` · ${size}` : ""}
        </p>
        {source ? (
          <a
            href={source}
            target="_blank"
            rel="noreferrer"
            data-canvas-interactive="true"
            className="mt-1 inline-block text-cyan/80 hover:text-cyan"
          >
            Open
          </a>
        ) : null}
      </div>
    </div>
  );
}
