import { api } from "@/lib/api";
import type { CanvasBoard, CanvasTransport } from "./types";
import { emptyBoard } from "./types";

/** The transport the board runs on: SQLite through /api/canvas/*. */
export function createCanvasTransport(): CanvasTransport {
  return {
    load: async (boardId) => {
      const board = await api.canvas.board(boardId);
      const fallback = emptyBoard(boardId);
      const loaded: CanvasBoard = {
        id: board.id || boardId,
        name: board.name || fallback.name,
        camera: board.camera ?? fallback.camera,
        items: board.items ?? [],
      };
      return loaded;
    },
    save: async (board) => {
      await api.canvas.saveBoard(board.id, {
        name: board.name,
        camera: board.camera,
        items: board.items,
      });
    },
    upload: (file) => api.canvas.upload(file),
    fileUrl: (fileId) => api.canvas.fileUrl(fileId),
  };
}
