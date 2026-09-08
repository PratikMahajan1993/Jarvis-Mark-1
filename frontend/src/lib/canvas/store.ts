"use client";

import { createContext, useContext, useEffect, useMemo, useReducer, useRef } from "react";
import type { Dispatch } from "react";
import type { CanvasBoard, CanvasCamera, CanvasItem, CanvasTransport } from "./types";
import { emptyBoard } from "./types";

export type CanvasState = {
  board: CanvasBoard;
  selectedId: string | null;
  status: "loading" | "ready" | "error";
  error: string;
  dirty: boolean;
};

export type CanvasItemPatch = { [K in keyof CanvasItem]?: CanvasItem[K] } & Record<string, unknown>;

export type CanvasAction =
  | { type: "loaded"; board: CanvasBoard }
  | { type: "loadFailed"; error: string }
  | { type: "setCamera"; camera: CanvasCamera }
  | { type: "addItem"; item: CanvasItem }
  | { type: "moveItem"; id: string; x: number; y: number }
  | { type: "resizeItem"; id: string; x: number; y: number; w: number; h: number }
  | { type: "updateItem"; id: string; patch: CanvasItemPatch }
  | { type: "deleteItem"; id: string }
  | { type: "select"; id: string | null }
  | { type: "bringToFront"; id: string }
  | { type: "saved" };

const INITIAL: CanvasState = {
  board: emptyBoard(),
  selectedId: null,
  status: "loading",
  error: "",
  dirty: false,
};

function topZ(items: CanvasItem[]): number {
  return items.reduce((max, item) => Math.max(max, item.z), 0);
}

function mapItem(
  state: CanvasState,
  id: string,
  change: (item: CanvasItem) => CanvasItem,
): CanvasState {
  return {
    ...state,
    dirty: true,
    board: {
      ...state.board,
      items: state.board.items.map((item) => (item.id === id ? change(item) : item)),
    },
  };
}

export function canvasReducer(state: CanvasState, action: CanvasAction): CanvasState {
  switch (action.type) {
    case "loaded":
      return { ...state, board: action.board, status: "ready", error: "", dirty: false };
    case "loadFailed":
      return { ...state, status: "error", error: action.error };
    case "setCamera":
      return { ...state, dirty: true, board: { ...state.board, camera: action.camera } };
    case "addItem":
      return {
        ...state,
        dirty: true,
        selectedId: action.item.id,
        board: {
          ...state.board,
          items: [...state.board.items, { ...action.item, z: topZ(state.board.items) + 1 }],
        },
      };
    case "moveItem":
      return mapItem(state, action.id, (item) => ({ ...item, x: action.x, y: action.y }));
    case "resizeItem":
      return mapItem(state, action.id, (item) => ({
        ...item,
        x: action.x,
        y: action.y,
        w: Math.max(40, action.w),
        h: Math.max(40, action.h),
      }));
    case "updateItem":
      return mapItem(state, action.id, (item) => ({ ...item, ...action.patch } as CanvasItem));
    case "deleteItem":
      return {
        ...state,
        dirty: true,
        selectedId: state.selectedId === action.id ? null : state.selectedId,
        board: {
          ...state.board,
          items: state.board.items.filter((item) => item.id !== action.id),
        },
      };
    case "select":
      return state.selectedId === action.id ? state : { ...state, selectedId: action.id };
    case "bringToFront": {
      const max = topZ(state.board.items);
      const target = state.board.items.find((item) => item.id === action.id);
      if (!target || target.z === max) return state;
      return mapItem(state, action.id, (item) => ({ ...item, z: max + 1 }));
    }
    case "saved":
      return { ...state, dirty: false };
    default:
      return state;
  }
}

export type CanvasActions = {
  dispatch: Dispatch<CanvasAction>;
  transport: CanvasTransport;
};

/**
 * State and actions are separate contexts on purpose: actions never change
 * identity, so item cards that only dispatch do not re-render on every pan.
 */
const CanvasStateContext = createContext<CanvasState | null>(null);
const CanvasActionsContext = createContext<CanvasActions | null>(null);
const CanvasZoomContext = createContext(1);

const SAVE_DEBOUNCE_MS = 600;

export function useCanvasStore(
  boardId: string,
  transport: CanvasTransport,
): { state: CanvasState; actions: CanvasActions } {
  const [state, dispatch] = useReducer(canvasReducer, INITIAL);
  const boardRef = useRef(state.board);
  const dirtyRef = useRef(false);
  boardRef.current = state.board;
  dirtyRef.current = state.dirty;

  useEffect(() => {
    let cancelled = false;
    transport
      .load(boardId)
      .then((board) => {
        if (!cancelled) dispatch({ type: "loaded", board });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        dispatch({
          type: "loadFailed",
          error: err instanceof Error ? err.message : "The board did not load.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [boardId, transport]);

  useEffect(() => {
    if (state.status !== "ready" || !state.dirty) return;
    const timer = window.setTimeout(() => {
      void transport
        .save(boardRef.current)
        .then(() => dispatch({ type: "saved" }))
        .catch(() => {
          /* keep the board dirty; the next edit retries */
        });
    }, SAVE_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [state.status, state.dirty, state.board, transport]);

  // A pending debounce would otherwise lose the last edit on navigation away.
  useEffect(
    () => () => {
      if (dirtyRef.current) void transport.save(boardRef.current).catch(() => {});
    },
    [transport],
  );

  const actions = useMemo(() => ({ dispatch, transport }), [transport]);
  return { state, actions };
}

export const CanvasStateProvider = CanvasStateContext.Provider;
export const CanvasActionsProvider = CanvasActionsContext.Provider;
export const CanvasZoomProvider = CanvasZoomContext.Provider;

export function useCanvasState(): CanvasState {
  const value = useContext(CanvasStateContext);
  if (!value) throw new Error("useCanvasState must be used inside a CanvasStateProvider");
  return value;
}

export function useCanvasActions(): CanvasActions {
  const value = useContext(CanvasActionsContext);
  if (!value) throw new Error("useCanvasActions must be used inside a CanvasActionsProvider");
  return value;
}

/**
 * Camera zoom only — pan does not change this value, so PDF cards can
 * re-rasterize on zoom without subscribing to every camera move.
 */
export function useCanvasZoom(): number {
  return useContext(CanvasZoomContext);
}
