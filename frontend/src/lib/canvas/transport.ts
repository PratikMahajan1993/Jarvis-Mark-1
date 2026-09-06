import type { CanvasBoard, CanvasFile, CanvasTransport } from "./types";
import { createId, emptyBoard } from "./types";

/** The transport the board runs on. */
export function createCanvasTransport(): CanvasTransport {
  return createMemoryTransport();
}

/**
 * Board storage with no backend: survives navigation within the tab but not a
 * reload. Used as the fallback when the API is unreachable, so the canvas still
 * opens when the house systems are down.
 */
export function createMemoryTransport(): CanvasTransport {
  const boards = new Map<string, CanvasBoard>();
  const blobs = new Map<string, string>();
  return {
    load: async (boardId) => boards.get(boardId) ?? emptyBoard(boardId),
    save: async (board) => {
      boards.set(board.id, board);
    },
    upload: async (file) => {
      const fileId = createId();
      blobs.set(fileId, URL.createObjectURL(file));
      const uploaded: CanvasFile = {
        file_id: fileId,
        name: file.name,
        mime: file.type,
        width: 0,
        height: 0,
        page_count: 0,
      };
      return uploaded;
    },
    fileUrl: (fileId) => blobs.get(fileId) ?? "",
  };
}
