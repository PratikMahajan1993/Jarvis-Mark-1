"use client";

import { useEffect, useRef, useState } from "react";
import { isPdfCancel, rasterBucket, renderPdfPage } from "@/lib/canvas/pdf";
import { useCanvasActions, useCanvasZoom } from "@/lib/canvas/store";
import type { PdfItem } from "@/lib/canvas/types";

const MM_PER_POINT = 25.4 / 72;

function pageSizeLabel(item: PdfItem): string {
  if (!item.naturalW || !item.naturalH) return "";
  const width = Math.round(item.naturalW * MM_PER_POINT);
  const height = Math.round(item.naturalH * MM_PER_POINT);
  return `${width} × ${height} mm`;
}

export function PdfFallback({ item }: { item: PdfItem }) {
  const { transport } = useCanvasActions();
  const source = transport.fileUrl(item.fileId);
  const size = pageSizeLabel(item);
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

export function PdfCard({ item }: { item: PdfItem }) {
  const { transport } = useCanvasActions();
  const zoom = useCanvasZoom();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const painted = useRef(false);
  const [failed, setFailed] = useState(false);
  const [ready, setReady] = useState(false);
  const bucket = rasterBucket(zoom, typeof window === "undefined" ? 1 : window.devicePixelRatio || 1);

  useEffect(() => {
    setFailed(false);
    setReady(false);
    painted.current = false;
  }, [item.fileId]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || failed) return;
    const url = transport.fileUrl(item.fileId);
    if (!url) {
      setFailed(true);
      return;
    }

    let settled = false;
    const delay = painted.current ? 180 : 0;
    let job: ReturnType<typeof renderPdfPage> | null = null;
    const timer = window.setTimeout(() => {
      job = renderPdfPage({
        fileId: item.fileId,
        url,
        page: item.page,
        canvas,
        width: item.w,
        height: item.h,
        outputScale: bucket,
      });
      void job.promise
        .then(() => {
          if (settled) return;
          painted.current = true;
          setReady(true);
        })
        .catch((err: unknown) => {
          if (settled || isPdfCancel(err)) return;
          setFailed(true);
        });
    }, delay);

    return () => {
      settled = true;
      window.clearTimeout(timer);
      job?.cancel();
    };
  }, [bucket, failed, item.fileId, item.h, item.page, item.w, transport]);

  if (failed) return <PdfFallback item={item} />;

  return (
    <div className="relative h-full w-full overflow-hidden rounded-sm bg-white ring-1 ring-white/10">
      <canvas ref={canvasRef} className="pointer-events-none h-full w-full select-none" />
      {!ready ? (
        <div className="pointer-events-none absolute inset-0 grid place-items-center bg-[#050b11]/80 text-[11px] text-white/35">
          {item.name}
        </div>
      ) : null}
    </div>
  );
}
