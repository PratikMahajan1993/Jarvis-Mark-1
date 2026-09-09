"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { MailAttachment } from "@/lib/types";
import { api } from "@/lib/api";
import type { ViewerCommand } from "@/lib/viewerMatch";
import { HudButton } from "./hud/Hud";

type Mode = "pan" | "crop" | "mark";
type PenColor = "cyan" | "red";

type Point = { x: number; y: number };
type Stroke = { points: Point[]; color: PenColor };
type CropRect = { x: number; y: number; w: number; h: number };

const PEN: Record<PenColor, string> = { cyan: "#3ee0d4", red: "#ff5c5c" };
const RENDER_SCALE = 2;

function isPdf(att: MailAttachment): boolean {
  const name = (att.local_name || att.filename || "").toLowerCase();
  return name.endsWith(".pdf") || (att.mime || "").includes("pdf");
}

function fileUrl(att: MailAttachment): string {
  const name = att.local_name || att.filename;
  if (name) return api.drawingUrl(name);
  if (att.artifact_id) return api.downloadUrl(att.artifact_id);
  return "";
}

async function loadPdfJs() {
  const pdfjs = await import("pdfjs-dist");
  pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
  return pdfjs;
}

export function DrawingViewer({
  attachment,
  onClose,
  onWhisper,
  onSaved,
  voiceCommand,
  voiceSeq = 0,
}: {
  attachment: MailAttachment;
  onClose: () => void;
  onWhisper: (line: string) => void;
  onSaved?: (speak: string) => void;
  voiceCommand?: ViewerCommand | null;
  voiceSeq?: number;
}) {
  const [mode, setMode] = useState<Mode>("pan");
  const [pen, setPen] = useState<PenColor>("cyan");
  const [pageNum, setPageNum] = useState(1);
  const [numPages, setNumPages] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [pageSize, setPageSize] = useState({ w: 800, h: 600 });
  const [strokes, setStrokes] = useState<Stroke[]>([]);
  const [crop, setCrop] = useState<CropRect | null>(null);
  const [cropDraft, setCropDraft] = useState<CropRect | null>(null);

  const viewportRef = useRef<HTMLDivElement>(null);
  const pageCanvasRef = useRef<HTMLCanvasElement>(null);
  const markCanvasRef = useRef<HTMLCanvasElement>(null);
  const pdfRef = useRef<{ getPage: (n: number) => Promise<unknown> } | null>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const panRef = useRef(pan);
  const zoomRef = useRef(zoom);
  const dragging = useRef<
    | { kind: "pan"; startX: number; startY: number; originX: number; originY: number }
    | { kind: "crop"; start: Point }
    | { kind: "draw"; stroke: Stroke }
    | null
  >(null);

  panRef.current = pan;
  zoomRef.current = zoom;

  const renderPage = useCallback(async () => {
    const canvas = pageCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    if (pdfRef.current) {
      const pdfjs = await loadPdfJs();
      const page = await pdfRef.current.getPage(pageNum);
      const viewport = (page as { getViewport: (o: { scale: number }) => { width: number; height: number; transform: number[] } }).getViewport({
        scale: RENDER_SCALE,
      });
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      setPageSize({ w: viewport.width, h: viewport.height });
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      await (
        page as {
          render: (o: { canvasContext: CanvasRenderingContext2D; viewport: unknown; canvas: HTMLCanvasElement }) => {
            promise: Promise<void>;
          };
        }
      ).render({ canvasContext: ctx, viewport, canvas }).promise;
      return;
    }

    const img = imageRef.current;
    if (img?.complete) {
      canvas.width = img.naturalWidth || img.width;
      canvas.height = img.naturalHeight || img.height;
      setPageSize({ w: canvas.width, h: canvas.height });
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0);
    }
  }, [pageNum]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setStrokes([]);
    setCrop(null);
    setCropDraft(null);
    setPageNum(1);
    setPan({ x: 0, y: 0 });
    setZoom(1);

    const load = async () => {
      try {
        const url = fileUrl(attachment);
        if (!url) throw new Error("No local file");
        const response = await fetch(url);
        if (!response.ok) throw new Error("Drawing missing");
        const data = await response.arrayBuffer();
        if (isPdf(attachment)) {
          const pdfjs = await loadPdfJs();
          const doc = await pdfjs.getDocument({ data }).promise;
          if (cancelled) return;
          pdfRef.current = doc;
          imageRef.current = null;
          setNumPages(doc.numPages);
          await renderPage();
        } else {
          pdfRef.current = null;
          const blob = new Blob([data]);
          const objectUrl = URL.createObjectURL(blob);
          const img = new Image();
          await new Promise<void>((resolve, reject) => {
            img.onload = () => resolve();
            img.onerror = () => reject(new Error("Could not load image"));
            img.src = objectUrl;
          });
          if (cancelled) {
            URL.revokeObjectURL(objectUrl);
            return;
          }
          imageRef.current = img;
          setNumPages(1);
          await renderPage();
        }
      } catch {
        if (!cancelled) onWhisper("I could not open that drawing.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [attachment, onWhisper, renderPage]);

  useEffect(() => {
    void renderPage();
  }, [renderPage]);

  useEffect(() => {
    const mark = markCanvasRef.current;
    if (!mark) return;
    mark.width = pageSize.w;
    mark.height = pageSize.h;
    const ctx = mark.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, mark.width, mark.height);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.lineWidth = 4 * RENDER_SCALE;
    for (const stroke of strokes) {
      if (stroke.points.length < 2) continue;
      ctx.strokeStyle = PEN[stroke.color];
      ctx.beginPath();
      ctx.moveTo(stroke.points[0].x, stroke.points[0].y);
      for (let i = 1; i < stroke.points.length; i += 1) {
        ctx.lineTo(stroke.points[i].x, stroke.points[i].y);
      }
      ctx.stroke();
    }
    const box = cropDraft || crop;
    if (box && box.w > 0 && box.h > 0) {
      ctx.strokeStyle = "#3ee0d4";
      ctx.lineWidth = 2 * RENDER_SCALE;
      ctx.setLineDash([8 * RENDER_SCALE, 6 * RENDER_SCALE]);
      ctx.strokeRect(box.x, box.y, box.w, box.h);
      ctx.setLineDash([]);
      ctx.fillStyle = "rgba(2, 5, 8, 0.45)";
      ctx.fillRect(0, 0, mark.width, box.y);
      ctx.fillRect(0, box.y, box.x, box.h);
      ctx.fillRect(box.x + box.w, box.y, mark.width - box.x - box.w, box.h);
      ctx.fillRect(0, box.y + box.h, mark.width, mark.height - box.y - box.h);
    }
  }, [strokes, crop, cropDraft, pageSize]);

  useEffect(() => {
    if (!voiceCommand || !voiceSeq) return;
    if (voiceCommand === "close") {
      onClose();
      return;
    }
    if (voiceCommand === "zoom-in") setZoom((z) => Math.min(4, z * 1.25));
    if (voiceCommand === "zoom-out") setZoom((z) => Math.max(0.25, z / 1.25));
    if (voiceCommand === "next") setPageNum((p) => Math.min(numPages, p + 1));
    if (voiceCommand === "prev") setPageNum((p) => Math.max(1, p - 1));
  }, [voiceCommand, voiceSeq, numPages, onClose]);

  useEffect(() => {
    setStrokes([]);
    setCrop(null);
    setCropDraft(null);
  }, [pageNum]);

  const toLocal = (clientX: number, clientY: number): Point => {
    const canvas = pageCanvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    const x = ((clientX - rect.left) / rect.width) * canvas.width;
    const y = ((clientY - rect.top) / rect.height) * canvas.height;
    return {
      x: Math.max(0, Math.min(canvas.width, x)),
      y: Math.max(0, Math.min(canvas.height, y)),
    };
  };

  const onPointerDown = (event: React.PointerEvent) => {
    if (loading) return;
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    if (mode === "pan") {
      dragging.current = {
        kind: "pan",
        startX: event.clientX,
        startY: event.clientY,
        originX: panRef.current.x,
        originY: panRef.current.y,
      };
      return;
    }
    const pt = toLocal(event.clientX, event.clientY);
    if (mode === "crop") {
      dragging.current = { kind: "crop", start: pt };
      setCropDraft({ x: pt.x, y: pt.y, w: 0, h: 0 });
      return;
    }
    if (mode === "mark") {
      const stroke: Stroke = { points: [pt], color: pen };
      dragging.current = { kind: "draw", stroke };
      setStrokes((current) => [...current, stroke]);
    }
  };

  const onPointerMove = (event: React.PointerEvent) => {
    const drag = dragging.current;
    if (!drag) return;
    if (drag.kind === "pan") {
      setPan({
        x: drag.originX + (event.clientX - drag.startX),
        y: drag.originY + (event.clientY - drag.startY),
      });
      return;
    }
    const pt = toLocal(event.clientX, event.clientY);
    if (drag.kind === "crop") {
      const x = Math.min(drag.start.x, pt.x);
      const y = Math.min(drag.start.y, pt.y);
      const w = Math.abs(pt.x - drag.start.x);
      const h = Math.abs(pt.y - drag.start.y);
      setCropDraft({ x, y, w, h });
      return;
    }
    if (drag.kind === "draw") {
      drag.stroke.points.push(pt);
      setStrokes((current) => {
        const next = current.slice();
        next[next.length - 1] = { ...drag.stroke, points: [...drag.stroke.points] };
        return next;
      });
    }
  };

  const onPointerUp = () => {
    const drag = dragging.current;
    if (drag?.kind === "crop" && cropDraft && cropDraft.w > 8 && cropDraft.h > 8) {
      setCrop(cropDraft);
    }
    dragging.current = null;
  };

  const onWheel = (event: React.WheelEvent) => {
    event.preventDefault();
    const delta = event.deltaY > 0 ? 0.9 : 1.1;
    setZoom((z) => Math.max(0.25, Math.min(4, z * delta)));
  };

  const exportPng = async (): Promise<string> => {
    const page = pageCanvasRef.current;
    const mark = markCanvasRef.current;
    if (!page) throw new Error("Nothing to save");
    const box = crop || { x: 0, y: 0, w: page.width, h: page.height };
    const out = document.createElement("canvas");
    out.width = Math.max(1, Math.round(box.w));
    out.height = Math.max(1, Math.round(box.h));
    const ctx = out.getContext("2d");
    if (!ctx) throw new Error("Canvas unavailable");
    ctx.drawImage(page, box.x, box.y, box.w, box.h, 0, 0, out.width, out.height);
    if (mark) {
      ctx.drawImage(mark, box.x, box.y, box.w, box.h, 0, 0, out.width, out.height);
    }
    return out.toDataURL("image/png");
  };

  const saveMarked = async () => {
    setSaving(true);
    try {
      const dataUrl = await exportPng();
      const result = await api.saveMarkedDrawing(attachment.local_name || attachment.filename, dataUrl);
      onWhisper(result.speak);
      onSaved?.(result.speak);
    } catch {
      onWhisper("Could not save the marked drawing.");
    } finally {
      setSaving(false);
    }
  };

  const title = attachment.local_name || attachment.filename;

  return (
    <div className="absolute inset-0 z-30 flex flex-col bg-black/70 backdrop-blur-sm">
      <header className="hud-panel hud-accent-cyan flex shrink-0 items-center justify-between rounded-none border-x-0 border-t-0 px-6 py-3">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-cyan/50">Drawing viewer</p>
          <p className="font-display text-xl text-white">{title}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {numPages > 1 ? (
            <div className="flex items-center gap-2 text-sm text-white/60">
              <HudButton variant="ghost" disabled={pageNum <= 1} onClick={() => setPageNum((p) => Math.max(1, p - 1))}>
                Prev
              </HudButton>
              <span className="font-mono text-xs">
                {pageNum} / {numPages}
              </span>
              <HudButton variant="ghost" disabled={pageNum >= numPages} onClick={() => setPageNum((p) => Math.min(numPages, p + 1))}>
                Next
              </HudButton>
            </div>
          ) : null}
          <HudButton variant="ghost" onClick={() => setZoom((z) => Math.min(4, z * 1.25))}>
            Zoom +
          </HudButton>
          <HudButton variant="ghost" onClick={() => setZoom((z) => Math.max(0.25, z / 1.25))}>
            Zoom −
          </HudButton>
          {(["pan", "crop", "mark"] as Mode[]).map((m) => (
            <HudButton key={m} variant={mode === m ? "primary" : "ghost"} className="capitalize" onClick={() => setMode(m)}>
              {m}
            </HudButton>
          ))}
          {mode === "mark" ? (
            <>
              <button
                type="button"
                onClick={() => setPen("cyan")}
                className={`h-6 w-6 rounded-full border-2 ${pen === "cyan" ? "border-white" : "border-transparent"}`}
                style={{ background: PEN.cyan }}
                aria-label="Cyan pen"
              />
              <button
                type="button"
                onClick={() => setPen("red")}
                className={`h-6 w-6 rounded-full border-2 ${pen === "red" ? "border-white" : "border-transparent"}`}
                style={{ background: PEN.red }}
                aria-label="Red pen"
              />
            </>
          ) : null}
          <HudButton variant="primary" disabled={saving || loading} onClick={() => void saveMarked()}>
            {saving ? "Saving…" : "Save marked"}
          </HudButton>
          <HudButton variant="ghost" onClick={onClose}>
            Close
          </HudButton>
        </div>
      </header>

      <div
        ref={viewportRef}
        className={`relative min-h-0 flex-1 overflow-hidden ${mode === "pan" ? "cursor-grab active:cursor-grabbing" : mode === "crop" ? "cursor-crosshair" : "cursor-crosshair"}`}
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
      >
        {loading ? (
          <div className="pointer-events-none absolute inset-0 z-10 grid place-items-center text-white/40">Loading drawing…</div>
        ) : null}
        <div
          className={`absolute left-1/2 top-1/2 origin-center ${loading ? "invisible" : ""}`}
          style={{
            transform: `translate(calc(-50% + ${pan.x}px), calc(-50% + ${pan.y}px)) scale(${zoom})`,
          }}
        >
          <div className="relative inline-block">
            <canvas ref={pageCanvasRef} className="block max-h-[75vh] w-auto bg-[#0a1218]" />
            <canvas
              ref={markCanvasRef}
              className="pointer-events-none absolute left-0 top-0 h-full w-full"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
