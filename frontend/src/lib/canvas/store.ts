"use client";

import { createContext, useContext, useEffect, useMemo, useReducer, useRef } from "react";
import type { Dispatch } from "react";
import type { CanvasBoard, CanvasCamera, CanvasItem, CanvasTransport } from "./types";
import { emptyBoard } from "./types";

const HISTORY_LIMIT = 80;

export type CanvasState = {
  board: CanvasBoard;
  selectedIds: string[];
  status: "loading" | "ready" | "error";
  error: string;
  dirty: boolean;
  past: CanvasItem[][];
  future: CanvasItem[][];
};

export type CanvasItemPatch = { [K in keyof CanvasItem]?: CanvasItem[K] } & Record<string, unknown>;

export type CanvasAction =
  | { type: "loaded"; board: CanvasBoard }
  | { type: "loadFailed"; error: string }
  | { type: "setCamera"; camera: CanvasCamera }
  | { type: "addItem"; item: CanvasItem }
  | { type: "addItems"; items: CanvasItem[] }
  | { type: "moveItem"; id: string; x: number; y: number }
  | { type: "moveItems"; moves: Array<{ id: string; x: number; y: number }> }
  | { type: "resizeItem"; id: string; x: number; y: number; w: number; h: number }
  | { type: "replaceItems"; items: CanvasItem[] }
  | { type: "updateItem"; id: string; patch: CanvasItemPatch }
  | { type: "deleteItems"; ids: string[] }
  | { type: "select"; ids: string[] }
  | { type: "bringToFront"; ids: string[] }
  | { type: "sendToBack"; ids: string[] }
  | { type: "checkpoint" }
  | { type: "undo" }
  | { type: "redo" }
  | { type: "saved" };

const INITIAL: CanvasState = {
  board: emptyBoard(),
  selectedIds: [],
  status: "loading",
  error: "",
  dirty: false,
  past: [],
  future: [],
};

function topZ(items: CanvasItem[]): number {
  return items.reduce((max, item) => Math.max(max, item.z), 0);
}

function bottomZ(items: CanvasItem[]): number {
  if (!items.length) return 0;
  return items.reduce((min, item) => Math.min(min, item.z), Infinity);
}

function pushPast(state: CanvasState): CanvasState {
  return {
    ...state,
    past: [...state.past.slice(-(HISTORY_LIMIT - 1)), state.board.items],
    future: [],
  };
}

function commit(state: CanvasState, items: CanvasItem[], selectedIds?: string[]): CanvasState {
  return {
    ...state,
    dirty: true,
    selectedIds: selectedIds ?? state.selectedIds,
    board: { ...state.board, items },
  };
}

function mapMany(
  items: CanvasItem[],
  ids: Set<string>,
  change: (item: CanvasItem) => CanvasItem,
): CanvasItem[] {
  return items.map((item) => (ids.has(item.id) ? change(item) : item));
}

export function canvasReducer(state: CanvasState, action: CanvasAction): CanvasState {
  switch (action.type) {
    case "loaded":
      return {
        ...state,
        board: action.board,
        status: "ready",
        error: "",
        dirty: false,
        selectedIds: [],
        past: [],
        future: [],
      };
    case "loadFailed":
      return { ...state, status: "error", error: action.error };
    case "setCamera":
      return { ...state, dirty: true, board: { ...state.board, camera: action.camera } };
    case "checkpoint":
      return pushPast(state);
    case "addItem":
      return canvasReducer(state, { type: "addItems", items: [action.item] });
    case "addItems": {
      const next = pushPast(state);
      let z = topZ(next.board.items);
      const added = action.items.map((item) => {
        z += 1;
        return { ...item, z };
      });
      return commit(next, [...next.board.items, ...added], added.map((item) => item.id));
    }
    case "moveItem":
      return commit(
        state,
        state.board.items.map((item) =>
          item.id === action.id && !item.locked ? { ...item, x: action.x, y: action.y } : item,
        ),
      );
    case "moveItems": {
      const byId = new Map(action.moves.map((move) => [move.id, move]));
      return commit(
        state,
        state.board.items.map((item) => {
          const move = byId.get(item.id);
          if (!move || item.locked) return item;
          return { ...item, x: move.x, y: move.y };
        }),
      );
    }
    case "resizeItem":
      return commit(
        state,
        state.board.items.map((item) =>
          item.id === action.id && !item.locked
            ? {
                ...item,
                x: action.x,
                y: action.y,
                w: Math.max(8, action.w),
                h: Math.max(8, action.h),
              }
            : item,
        ),
      );
    case "replaceItems":
      return commit(state, action.items);
    case "updateItem":
      return commit(
        state,
        state.board.items.map((item) =>
          item.id === action.id ? ({ ...item, ...action.patch } as CanvasItem) : item,
        ),
      );
    case "deleteItems": {
      const ids = new Set(action.ids);
      const next = pushPast(state);
      return {
        ...commit(
          next,
          next.board.items.filter((item) => !ids.has(item.id)),
          next.selectedIds.filter((id) => !ids.has(id)),
        ),
      };
    }
    case "select": {
      const same =
        action.ids.length === state.selectedIds.length &&
        action.ids.every((id, index) => id === state.selectedIds[index]);
      return same ? state : { ...state, selectedIds: action.ids };
    }
    case "bringToFront": {
      const ids = new Set(action.ids);
      let z = topZ(state.board.items);
      const next = pushPast(state);
      return commit(
        next,
        mapMany(next.board.items, ids, (item) => {
          z += 1;
          return { ...item, z };
        }),
      );
    }
    case "sendToBack": {
      const ids = new Set(action.ids);
      let z = bottomZ(state.board.items) - action.ids.length;
      const next = pushPast(state);
      return commit(
        next,
        mapMany(next.board.items, ids, (item) => {
          z += 1;
          return { ...item, z };
        }),
      );
    }
    case "undo": {
      if (!state.past.length) return state;
      const items = state.past[state.past.length - 1];
      return {
        ...state,
        dirty: true,
        past: state.past.slice(0, -1),
        future: [state.board.items, ...state.future].slice(0, HISTORY_LIMIT),
        selectedIds: state.selectedIds.filter((id) => items.some((item) => item.id === id)),
        board: { ...state.board, items },
      };
    }
    case "redo": {
      if (!state.future.length) return state;
      const [items, ...rest] = state.future;
      return {
        ...state,
        dirty: true,
        past: [...state.past, state.board.items].slice(-HISTORY_LIMIT),
        future: rest,
        selectedIds: state.selectedIds.filter((id) => items.some((item) => item.id === id)),
        board: { ...state.board, items },
      };
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

export function useCanvasZoom(): number {
  return useContext(CanvasZoomContext);
}

export function selectedOf(state: CanvasState): CanvasItem[] {
  const ids = new Set(state.selectedIds);
  return state.board.items.filter((item) => ids.has(item.id));
}
