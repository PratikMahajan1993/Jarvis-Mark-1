"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fitToItems, screenToWorld, zoomAt, type Point } from "@/lib/canvas/camera";
import { cropCanvasRegion, cropSourceForItem } from "@/lib/canvas/crop";
import { exportItemsPng } from "@/lib/canvas/export";
import { kindForFile, readImageSize } from "@/lib/canvas/files";
import { nudgeItems } from "@/lib/canvas/geometry";
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
  cloneItem,
  createId,
  fitDroppedSize,
  DEFAULT_BOARD_ID,
  NOTE_SIZE,
  type CanvasItem,
  type CanvasTool,
  type ImageItem,
  type PdfItem,
  type StrokeColor,
} from "@/lib/canvas/types";
import { ContextMenu, ShortcutHelp, type MenuAction } from "./CanvasMenu";
import { CanvasToolbar } from "./CanvasToolbar";
import { CanvasViewport, type CanvasCrop } from "./CanvasViewport";
import { Inspector } from "./Inspector";
import { MiniMap } from "./MiniMap";
import { ToolRail } from "./ToolRail";

let clipboard: CanvasItem[] = [];

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
  const state = useCanvasState();
  const { board, selectedIds } = state;
  const { dispatch, transport } = useCanvasActions();
  const surface = useRef<HTMLDivElement>(null);
  const [viewport, setViewport] = useState({ width: 0, height: 0 });
  const [notice, setNotice] = useState("");
  const [tool, setTool] = useState<CanvasTool>("select");
  const [snap, setSnap] = useState(true);
  const [spacePan, setSpacePan] = useState(false);
  const [help, setHelp] = useState(false);
  const [strokeColor, setStrokeColor] = useState<StrokeColor>("cyan");
  const [crop, setCrop] = useState<CanvasCrop | null>(null);
  const [cropBusy, setCropBusy] = useState(false);
  const [menu, setMenu] = useState<{ x: number; y: number } | null>(null);
  const cameraRef = useRef(board.camera);
  const itemsRef = useRef(board.items);
  const selectedRef = useRef(selectedIds);
  const toolRef = useRef(tool);
  const cropRef = useRef(crop);
  const snapRef = useRef(snap);
  cameraRef.current = board.camera;
  itemsRef.current = board.items;
  selectedRef.current = selectedIds;
  toolRef.current = tool;
  cropRef.current = crop;
  snapRef.current = snap;

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
      setTool("select");
    },
    [dispatch],
  );

  const addText = useCallback(
    (world: Point) => {
      dispatch({
        type: "addItem",
        item: {
          id: createId(),
          kind: "text",
          x: Math.round(world.x),
          y: Math.round(world.y - 16),
          w: 280,
          h: 48,
          rotation: 0,
          z: 0,
          text: "",
          color: "white",
          size: 28,
        },
      });
      setTool("select");
    },
    [dispatch],
  );

  const addNoteAtCenter = useCallback(() => {
    const center = { x: viewport.width / 2, y: viewport.height / 2 };
    addNote(screenToWorld(center, cameraRef.current));
  }, [addNote, viewport.height, viewport.width]);

  const selectedItems = () =>
    itemsRef.current.filter((item) => selectedRef.current.includes(item.id));

  const copySelected = useCallback(() => {
    clipboard = selectedItems().map((item) => cloneItem(item, 0, 0));
  }, []);

  const pasteClipboard = useCallback(() => {
    if (!clipboard.length) return;
    const copies = clipboard.map((item) => cloneItem(item, 24, 24));
    clipboard = copies.map((item) => cloneItem(item, 0, 0));
    dispatch({ type: "addItems", items: copies });
  }, [dispatch]);

  const duplicateSelected = useCallback(() => {
    const copies = selectedItems().map((item) => cloneItem(item));
    if (copies.length) dispatch({ type: "addItems", items: copies });
  }, [dispatch]);

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

  const exportPng = useCallback(async () => {
    const items = selectedItems().length ? selectedItems() : itemsRef.current;
    if (!items.length) return;
    setNotice("");
    try {
      const blob = await exportItemsPng(items, transport);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "canvas.png";
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Export failed.");
    }
  }, [transport]);

  const toggleGroup = useCallback(() => {
    const selected = selectedItems();
    if (selected.length < 2) {
      dispatch({ type: "checkpoint" });
      for (const item of selected) {
        if (item.groupId) dispatch({ type: "updateItem", id: item.id, patch: { groupId: undefined } });
      }
      return;
    }
    const grouped = selected.every((item) => item.groupId && item.groupId === selected[0].groupId);
    dispatch({ type: "checkpoint" });
    const groupId = grouped ? undefined : createId();
    for (const item of selected) dispatch({ type: "updateItem", id: item.id, patch: { groupId } });
  }, [dispatch]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.code === "Space" && !event.repeat) {
        const target = event.target as HTMLElement | null;
        if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) return;
        event.preventDefault();
        setSpacePan(true);
      }
    };
    const onKeyUp = (event: KeyboardEvent) => {
      if (event.code === "Space") setSpacePan(false);
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, []);

  useEffect(() => {
    const onPaste = (event: ClipboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) return;
      const files = event.clipboardData ? Array.from(event.clipboardData.files) : [];
      if (files.length) {
        event.preventDefault();
        const center = screenToWorld(
          { x: viewport.width / 2, y: viewport.height / 2 },
          cameraRef.current,
        );
        void onDropFiles(files, center);
        return;
      }
      if (clipboard.length) {
        event.preventDefault();
        pasteClipboard();
      }
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [onDropFiles, pasteClipboard, viewport.height, viewport.width]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) return;
      const camera = cameraRef.current;
      const center = { x: viewport.width / 2, y: viewport.height / 2 };
      const cmd = event.metaKey || event.ctrlKey;
      const key = event.key.toLowerCase();

      if (event.key === "Escape") {
        if (cropRef.current) {
          setCrop(null);
          return;
        }
        if (help) {
          setHelp(false);
          return;
        }
        if (menu) {
          setMenu(null);
          return;
        }
        if (toolRef.current !== "select") {
          setTool("select");
          return;
        }
        dispatch({ type: "select", ids: [] });
        setNotice("");
        return;
      }
      if (event.key === "?" || (event.shiftKey && event.key === "/")) {
        setHelp((value) => !value);
        return;
      }
      if (cmd && key === "z") {
        event.preventDefault();
        dispatch({ type: event.shiftKey ? "redo" : "undo" });
        return;
      }
      if (cmd && key === "a") {
        event.preventDefault();
        dispatch({ type: "select", ids: itemsRef.current.map((item) => item.id) });
        return;
      }
      if (cmd && key === "c") {
        event.preventDefault();
        copySelected();
        return;
      }
      if (cmd && key === "d") {
        event.preventDefault();
        duplicateSelected();
        return;
      }
      if (cmd && key === "g") {
        event.preventDefault();
        toggleGroup();
        return;
      }
      if (cmd && key === "l") {
        event.preventDefault();
        dispatch({ type: "checkpoint" });
        const selected = selectedItems();
        const locked = selected.every((item) => item.locked);
        for (const item of selected) dispatch({ type: "updateItem", id: item.id, patch: { locked: !locked } });
        return;
      }
      if (cmd && key === "e") {
        event.preventDefault();
        void exportPng();
        return;
      }
      if (cmd && event.key === "]") {
        event.preventDefault();
        dispatch({ type: "bringToFront", ids: selectedRef.current });
        return;
      }
      if (cmd && event.key === "[") {
        event.preventDefault();
        dispatch({ type: "sendToBack", ids: selectedRef.current });
        return;
      }
      if ((event.key === "Delete" || event.key === "Backspace") && selectedRef.current.length) {
        event.preventDefault();
        if (cropRef.current && selectedRef.current.includes(cropRef.current.itemId)) setCrop(null);
        dispatch({ type: "deleteItems", ids: selectedRef.current });
        return;
      }
      if (event.key.startsWith("Arrow") && selectedRef.current.length) {
        event.preventDefault();
        const step = (event.shiftKey ? 10 : 1) * (snapRef.current && !event.shiftKey ? 1 : 1);
        const dx = event.key === "ArrowLeft" ? -step : event.key === "ArrowRight" ? step : 0;
        const dy = event.key === "ArrowUp" ? -step : event.key === "ArrowDown" ? step : 0;
        dispatch({ type: "checkpoint" });
        const moved = nudgeItems(selectedItems(), dx, dy);
        const byId = new Map(moved.map((item) => [item.id, item]));
        dispatch({
          type: "replaceItems",
          items: itemsRef.current.map((item) => byId.get(item.id) ?? item),
        });
        return;
      }
      if (!cmd) {
        if (key === "v") setTool("select");
        else if (key === "h") setTool("pan");
        else if (key === "r") setTool((current) => (current === "region" ? "select" : "region"));
        else if (key === "n") {
          setTool("note");
          addNoteAtCenter();
        } else if (key === "t") setTool("text");
        else if (key === "p") setTool("ink");
        else if (key === "o") setTool("ellipse");
        else if (key === "l") setTool("line");
        else if (key === "a") setTool("arrow");
        else if (key === "g") setSnap((value) => !value);
        else if (key === "0") dispatch({ type: "setCamera", camera: zoomAt(camera, center, 1) });
        else if (key === "1") {
          dispatch({
            type: "setCamera",
            camera: fitToItems(itemsRef.current, viewport.width, viewport.height),
          });
        } else if (key === "2") {
          const selected = selectedItems();
          dispatch({
            type: "setCamera",
            camera: fitToItems(selected.length ? selected : itemsRef.current, viewport.width, viewport.height),
          });
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [
    addNoteAtCenter,
    copySelected,
    dispatch,
    duplicateSelected,
    exportPng,
    help,
    menu,
    toggleGroup,
    viewport.height,
    viewport.width,
  ]);

  const menuActions = (): MenuAction[] => {
    const selected = selectedItems();
    return [
      { label: "Duplicate", shortcut: "⌘D", disabled: !selected.length, run: duplicateSelected },
      { label: "Copy", shortcut: "⌘C", disabled: !selected.length, run: copySelected },
      { label: "Paste", shortcut: "⌘V", disabled: !clipboard.length, run: pasteClipboard },
      {
        label: "Delete",
        shortcut: "⌫",
        disabled: !selected.length,
        run: () => dispatch({ type: "deleteItems", ids: selectedRef.current }),
      },
      {
        label: selected.every((item) => item.locked) ? "Unlock" : "Lock",
        shortcut: "⌘L",
        disabled: !selected.length,
        run: () => {
          dispatch({ type: "checkpoint" });
          const locked = selected.every((item) => item.locked);
          for (const item of selected) dispatch({ type: "updateItem", id: item.id, patch: { locked: !locked } });
        },
      },
      {
        label: "Bring to front",
        shortcut: "⌘]",
        disabled: !selected.length,
        run: () => dispatch({ type: "bringToFront", ids: selectedRef.current }),
      },
      {
        label: "Send to back",
        shortcut: "⌘[",
        disabled: !selected.length,
        run: () => dispatch({ type: "sendToBack", ids: selectedRef.current }),
      },
      {
        label: "Group / ungroup",
        shortcut: "⌘G",
        disabled: !selected.length,
        run: toggleGroup,
      },
      { label: "Export PNG", shortcut: "⌘E", run: () => void exportPng() },
    ];
  };

  return (
    <CanvasZoomProvider value={board.camera.z}>
      <div ref={surface} className="hud-bg relative h-screen w-screen overflow-hidden">
        <CanvasViewport
          tool={tool}
          snap={snap}
          spacePan={spacePan}
          strokeColor={strokeColor}
          crop={crop}
          cropBusy={cropBusy}
          onCropChange={setCrop}
          onPlaceCrop={() => void onPlaceCrop()}
          onDownloadCrop={() => void onDownloadCrop()}
          onDropFiles={onDropFiles}
          onCreateNote={addNote}
          onCreateText={addText}
          onContextMenu={(point) => setMenu(point)}
        />
        <div className="scanline pointer-events-none absolute inset-0" />

        <div className="pointer-events-none absolute inset-x-0 top-0 flex justify-center px-6 py-5">
          <CanvasToolbar
            viewport={viewport}
            snap={snap}
            onAddNote={addNoteAtCenter}
            onToggleSnap={() => setSnap((value) => !value)}
            onExport={() => void exportPng()}
          />
        </div>

        <div className="pointer-events-none absolute left-5 top-1/2 flex -translate-y-1/2 flex-col items-center gap-2">
          <ToolRail tool={tool} onTool={setTool} />
          <div className="glass pointer-events-auto flex flex-col gap-1.5 rounded-full px-1.5 py-2">
            {(["cyan", "amber", "rose", "slate", "white"] as StrokeColor[]).map((color) => (
              <button
                key={color}
                type="button"
                title={color}
                onClick={() => setStrokeColor(color)}
                className={`h-3.5 w-3.5 rounded-full border ${strokeColor === color ? "border-white" : "border-transparent"}`}
                style={{
                  background:
                    color === "cyan"
                      ? "#3ee0d4"
                      : color === "amber"
                        ? "#f5c16c"
                        : color === "rose"
                          ? "#f082a0"
                          : color === "white"
                            ? "#d7eef2"
                            : "#94b2c4",
                }}
              />
            ))}
          </div>
        </div>

        <div className="pointer-events-none absolute right-5 top-24 flex w-44 flex-col gap-3">
          <Inspector />
        </div>

        <div className="pointer-events-none absolute bottom-6 right-6">
          <MiniMap viewport={viewport} />
        </div>

        <div className="pointer-events-none absolute inset-x-0 bottom-0 flex flex-col items-center gap-2 px-6 pb-6 text-center">
          {notice ? <p className="text-sm text-amber/80">{notice}</p> : null}
          {!board.items.length ? (
            <p className="text-sm text-white/25">
              Drop a drawing. N note, P pen, O oval, R region. Space to pan. ? for keys.
            </p>
          ) : null}
        </div>

        {menu ? (
          <ContextMenu x={menu.x} y={menu.y} actions={menuActions()} onClose={() => setMenu(null)} />
        ) : null}
        {help ? <ShortcutHelp onClose={() => setHelp(false)} /> : null}
      </div>
    </CanvasZoomProvider>
  );
}

function cropName(item: { name: string; kind: string; page?: number }): string {
  const base = item.name.replace(/\.(pdf|png|jpe?g|gif|webp|bmp|svg)$/i, "");
  const page = item.kind === "pdf" && item.page ? `-p${item.page}` : "";
  return `${base}${page}-crop.png`;
}
