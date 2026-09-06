import type { CanvasItemKind } from "./types";

const IMAGE_TYPES = /^image\/(png|jpeg|jpg|gif|webp|bmp|svg\+xml)$/i;
const IMAGE_EXT = /\.(png|jpe?g|gif|webp|bmp|svg)$/i;
const PDF_EXT = /\.pdf$/i;

/** Which item a dropped file becomes, or null when we cannot place it. */
export function kindForFile(file: File): Extract<CanvasItemKind, "image" | "pdf"> | null {
  if (file.type === "application/pdf" || PDF_EXT.test(file.name)) return "pdf";
  if (IMAGE_TYPES.test(file.type) || IMAGE_EXT.test(file.name)) return "image";
  return null;
}

/**
 * Image dimensions are read in the browser rather than server-side, so the
 * backend needs no imaging dependency. PDF page size comes from pypdf instead.
 */
export function readImageSize(file: File): Promise<{ w: number; h: number }> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      resolve({ w: image.naturalWidth || 0, h: image.naturalHeight || 0 });
      URL.revokeObjectURL(url);
    };
    image.onerror = () => {
      resolve({ w: 0, h: 0 });
      URL.revokeObjectURL(url);
    };
    image.src = url;
  });
}
