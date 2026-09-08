"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fitToItems, screenToWorld, zoomAt, type Point } from "@/lib/canvas/camera";
import { cropCanvasRegion, cropSourceForItem } from "@/lib/canvas/crop";
import { kindForFile, readImageSize } from "@/lib/canvas/files";
import {
  CanvasActionsProvider,
  CanvasStateProvider,
  CanvasZoomProvider,
  useCanvasActions,
  useCanvasState,
  useCanvasStore,
} from "@/lib/canvas/store";
import { createCanvasTransport } from "@/lib/canvas/transport";
import {
  createId,
  fitDroppedSize,
  DEFAULT_BOARD_ID,
  NOTE_SIZE,
  type CanvasItem,
  type CanvasTool,
  type ImageItem,
  type PdfItem,
} from "@/lib/canvas/types";
import { CanvasToolbar } from "./CanvasToolbar";
import { CanvasViewport, type CanvasCrop } from "./CanvasViewport";

export function CanvasShell() {
  const transport = useMemo(() => createCanvasTransport(), []);
  const { state, actions } = useCanvasStore(DEFAULT_BOARD_ID, transport);
  return (
    <CanvasActionsProvider value={actions}>
      <CanvasStateProvider value={state}>
        <BoardSurface />
      </CanvasStateProvider>
    </CanvasActionsProvider>
  );
}

function BoardSurface() {
  const { board, selectedId } = useCanvasState();
  const { dispatch, transport } = useCanvasActions();
  const surface = useRef<HTMLDivElement>(null);
  const [viewport, setViewport] = useState({ width: 0, height: 0 });
  const [notice, setNotice] = useState("");
  const [tool, setTool] = useState<CanvasTool>("select");
  const [crop, setCrop] = useState<CanvasCrop | null>(null);
  const [cropBusy, setCropBusy] = useState(false);
  const cameraRef = useRef(board.camera);
  const itemsRef = useRef(board.items);
  const selectedRef = useRef(selectedId);
  const toolRef = useRef(tool);
  const cropRef = useRef(crop);
  cameraRef.current = board.camera;
  itemsRef.current = board.items;
  selectedRef.current = selectedId;
  toolRef.current = tool;
  cropRef.current = crop;

  useEffect(() => {
    const element = surface.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => {
      setViewport({ width: entry.contentRect.width, height: entry.contentRect.height });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const addNote = useCallback(
    (world: Point) => {
      dispatch({
        type: "addItem",
        item: {
          id: createId(),
          kind: "note",
          x: Math.round(world.x - NOTE_SIZE.w / 2),
          y: Math.round(world.y - NOTE_SIZE.h / 2),
          w: NOTE_SIZE.w,
          h: NOTE_SIZE.h,
          rotation: 0,
          z: 0,
          text: "",
          color: "amber",
        },
      });
    },
    [dispatch],
  );

  const addNoteAtCenter = useCallback(() => {
    const center = { x: viewport.width / 2, y: viewport.height / 2 };
    addNote(screenToWorld(center, cameraRef.current));
  }, [addNote, viewport.height, viewport.width]);

  const runCrop = useCallback(async (): Promise<{
    item: ImageItem | PdfItem;
    result: Awaited<ReturnType<typeof cropCanvasRegion>>;
  } | null> => {
    const current = cropRef.current;
    if (!current) return null;
    const item = itemsRef.current.find((candidate) => candidate.id === current.itemId);
    if (!item || (item.kind !== "pdf" && item.kind !== "image")) return null;
    const source =
      item.kind === "pdf"
        ? {
            ...cropSourceForItem(item, transport.fileUrl(item.fileId)),
            page: current.page ?? item.page,
            itemSize: { w: item.w, h: item.h },
          }
        : cropSourceForItem(item, transport.fileUrl(item.fileId));
    const result = await cropCanvasRegion(source, current.rect);
    return { item, result };
  }, [transport]);

  const onPlaceCrop = useCallback(async () => {
    setCropBusy(true);
    setNotice("");
    try {
      const cropped = await runCrop();
      if (!cropped) return;
      const file = new File([cropped.result.blob], cropName(cropped.item), { type: "image/png" });
      const uploaded = await transport.upload(file);
      const size = fitDroppedSize(cropped.result.width, cropped.result.height);
      dispatch({
        type: "addItem",
        item: {
          id: createId(),
          kind: "image",
          x: Math.round(cropped.item.x + cropped.item.w + 24),
          y: Math.round(cropped.item.y),
          w: size.w,
          h: size.h,
          rotation: 0,
          z: 0,
          fileId: uploaded.file_id,
          name: uploaded.name || file.name,
          naturalW: cropped.result.width,
          naturalH: cropped.result.height,
        },
      });
      setCrop(null);
      setTool("select");
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "I could not crop that region.");
    } finally {
      setCropBusy(false);
    }
  }, [dispatch, runCrop, transport]);

  const onDownloadCrop = useCallback(async () => {
    setCropBusy(true);
    setNotice("");
    try {
      const cropped = await runCrop();
      if (!cropped) return;
      const url = URL.createObjectURL(cropped.result.blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = cropName(cropped.item);
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "I could not crop that region.");
    } finally {
      setCropBusy(false);
    }
  }, [runCrop]);

  const onDropFiles = useCallback(
    async (files: File[], world: Point) => {
      setNotice("");
      let cascade = 0;
      for (const file of files) {
        const kind = kindForFile(file);
        if (!kind) {
          setNotice(`I cannot place ${file.name} on the board.`);
          continue;
        }
        try {
          // Images are measured in the browser; PDFs get page size from the API.
          const measured = kind === "image" ? await readImageSize(file) : { w: 0, h: 0 };
          const uploaded = await transport.upload(file);
          const naturalW = measured.w || uploaded.width;
          const naturalH = measured.h || uploaded.height;
          const size = fitDroppedSize(naturalW, naturalH);
          const base = {
            id: createId(),
            x: Math.round(world.x - size.w / 2 + cascade),
            y: Math.round(world.y - size.h / 2 + cascade),
            w: size.w,
            h: size.h,
            rotation: 0,
            z: 0,
            fileId: uploaded.file_id,
            name: uploaded.name || file.name,
            naturalW,
            naturalH,
          };
          const item: CanvasItem =
            kind === "image"
              ? { ...base, kind: "image" }
              : { ...base, kind: "pdf", page: 1, pageCount: uploaded.page_count };
          dispatch({ type: "addItem", item });
          cascade += 28;
        } catch (err) {
          setNotice(err instanceof Error ? err.message : `I could not take ${file.name}.`);
        }
      }
    },
    [dispatch, transport],
  );

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) return;
      const camera = cameraRef.current;
      const center = { x: viewport.width / 2, y: viewport.height / 2 };

      if (event.key === "Escape") {
        if (cropRef.current) {
          setCrop(null);
          return;
        }
        if (toolRef.current === "region") {
          setTool("select");
          return;
        }
        dispatch({ type: "select", id: null });
        setNotice("");
        return;
      }
      if (event.key === "r" || event.key === "R") {
        setTool((current) => (current === "region" ? "select" : "region"));
        return;
      }
      if ((event.key === "Delete" || event.key === "Backspace") && selectedRef.current) {
        event.preventDefault();
        if (cropRef.current?.itemId === selectedRef.current) setCrop(null);
        dispatch({ type: "deleteItem", id: selectedRef.current });
        return;
      }
      if (event.key === "0") {
        dispatch({ type: "setCamera", camera: zoomAt(camera, center, 1) });
        return;
      }
      if (event.key === "1") {
        dispatch({
          type: "setCamera",
          camera: fitToItems(itemsRef.current, viewport.width, viewport.height),
        });
        return;
      }
      if (event.key === "n" || event.key === "N") {
        addNoteAtCenter();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [addNoteAtCenter, dispatch, viewport.height, viewport.width]);

  return (
    <CanvasZoomProvider value={board.camera.z}>
      <div ref={surface} className="hud-bg relative h-screen w-screen overflow-hidden">
        <CanvasViewport
          tool={tool}
          crop={crop}
          cropBusy={cropBusy}
          onCropChange={setCrop}
          onPlaceCrop={() => void onPlaceCrop()}
          onDownloadCrop={() => void onDownloadCrop()}
          onDropFiles={onDropFiles}
          onCreateNote={addNote}
        />
        <div className="scanline pointer-events-none absolute inset-0" />

        <div className="pointer-events-none absolute inset-x-0 top-0 flex justify-center px-6 py-5">
          <CanvasToolbar viewport={viewport} tool={tool} onAddNote={addNoteAtCenter} onTool={setTool} />
        </div>

        <div className="pointer-events-none absolute inset-x-0 bottom-0 flex flex-col items-center gap-2 px-6 pb-6 text-center">
          {notice ? <p className="text-sm text-amber/80">{notice}</p> : null}
          {!board.items.length ? (
            <p className="text-sm text-white/25">
              Drop a drawing or a PDF. Double-click for a note. Scroll to zoom, drag to pan.
            </p>
          ) : null}
        </div>
      </div>
    </CanvasZoomProvider>
  );
}

function cropName(item: { name: string; kind: string; page?: number }): string {
  const base = item.name.replace(/\.(pdf|png|jpe?g|gif|webp|bmp|svg)$/i, "");
  const page = item.kind === "pdf" && item.page ? `-p${item.page}` : "";
  return `${base}${page}-crop.png`;
}
