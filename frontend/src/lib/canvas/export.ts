import { renderPdfPage } from "./pdf";
import { STROKE_COLORS, type CanvasItem, type CanvasTransport } from "./types";

function noteFill(color: string): string {
  if (color === "cyan") return "rgba(62, 224, 212, 0.35)";
  if (color === "rose") return "rgba(240, 130, 160, 0.35)";
  if (color === "slate") return "rgba(148, 178, 196, 0.3)";
  return "rgba(245, 193, 108, 0.4)";
}

async function loadImage(url: string): Promise<HTMLImageElement> {
  const image = new Image();
  image.crossOrigin = "anonymous";
  await new Promise<void>((resolve, reject) => {
    image.onload = () => resolve();
    image.onerror = () => reject(new Error("Image missing"));
    image.src = url;
  });
  return image;
}

/**
 * Rasterize the current items to a PNG. Used by Export; later vision work can
 * call the same function with a subset of items.
 */
export async function exportItemsPng(
  items: CanvasItem[],
  transport: CanvasTransport,
): Promise<Blob> {
  if (!items.length) throw new Error("Nothing to export");
  const pad = 24;
  const minX = Math.min(...items.map((item) => item.x));
  const minY = Math.min(...items.map((item) => item.y));
  const maxX = Math.max(...items.map((item) => item.x + item.w));
  const maxY = Math.max(...items.map((item) => item.y + item.h));
  const width = Math.max(1, Math.ceil(maxX - minX + pad * 2));
  const height = Math.max(1, Math.ceil(maxY - minY + pad * 2));
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas unavailable");
  ctx.fillStyle = "#050b11";
  ctx.fillRect(0, 0, width, height);
  const ordered = [...items].sort((a, b) => a.z - b.z);

  for (const item of ordered) {
    const x = item.x - minX + pad;
    const y = item.y - minY + pad;
    ctx.save();
    ctx.translate(x + item.w / 2, y + item.h / 2);
    ctx.rotate(((item.rotation || 0) * Math.PI) / 180);
    ctx.translate(-item.w / 2, -item.h / 2);
    await drawItem(ctx, item, transport);
    ctx.restore();
  }

  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("PNG encode failed"))), "image/png");
  });
}

async function drawItem(
  ctx: CanvasRenderingContext2D,
  item: CanvasItem,
  transport: CanvasTransport,
): Promise<void> {
  if (item.kind === "note") {
    ctx.fillStyle = noteFill(item.color);
    ctx.strokeStyle = STROKE_COLORS[item.color];
    ctx.lineWidth = 1;
    ctx.fillRect(0, 0, item.w, item.h);
    ctx.strokeRect(0, 0, item.w, item.h);
    ctx.fillStyle = STROKE_COLORS[item.color === "amber" ? "amber" : item.color];
    ctx.font = "15px sans-serif";
    wrapText(ctx, item.text, 12, 24, item.w - 24, 20);
    return;
  }
  if (item.kind === "text") {
    ctx.fillStyle = STROKE_COLORS[item.color];
    ctx.font = `${item.size || 28}px Rajdhani, sans-serif`;
    wrapText(ctx, item.text, 0, item.size || 28, item.w, (item.size || 28) * 1.15);
    return;
  }
  if (item.kind === "shape") {
    const stroke = STROKE_COLORS[item.stroke];
    ctx.strokeStyle = stroke;
    ctx.lineWidth = item.weight || 2;
    ctx.fillStyle = item.fill === "none" ? "rgba(0,0,0,0)" : `${STROKE_COLORS[item.fill]}33`;
    ctx.beginPath();
    if (item.shape === "ellipse") {
      ctx.ellipse(item.w / 2, item.h / 2, item.w / 2, item.h / 2, 0, 0, Math.PI * 2);
    } else if (item.shape === "diamond") {
      ctx.moveTo(item.w / 2, 0);
      ctx.lineTo(item.w, item.h / 2);
      ctx.lineTo(item.w / 2, item.h);
      ctx.lineTo(0, item.h / 2);
      ctx.closePath();
    } else {
      ctx.rect(0, 0, item.w, item.h);
    }
    ctx.fill();
    ctx.stroke();
    return;
  }
  if (item.kind === "stroke") {
    ctx.strokeStyle = STROKE_COLORS[item.color];
    ctx.lineWidth = item.weight || 2;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.beginPath();
    item.points.forEach((point, index) => {
      if (index === 0) ctx.moveTo(point.x, point.y);
      else ctx.lineTo(point.x, point.y);
    });
    ctx.stroke();
    return;
  }
  if (item.kind === "image") {
    try {
      const image = await loadImage(transport.fileUrl(item.fileId));
      ctx.drawImage(image, 0, 0, item.w, item.h);
    } catch {
      ctx.fillStyle = "rgba(255,255,255,0.08)";
      ctx.fillRect(0, 0, item.w, item.h);
    }
    return;
  }
  if (item.kind === "pdf") {
    const page = document.createElement("canvas");
    const job = renderPdfPage({
      fileId: item.fileId,
      url: transport.fileUrl(item.fileId),
      page: item.page,
      canvas: page,
      width: item.w,
      height: item.h,
      outputScale: 2,
    });
    try {
      await job.promise;
      ctx.drawImage(page, 0, 0, item.w, item.h);
    } catch {
      ctx.fillStyle = "rgba(255,255,255,0.08)";
      ctx.fillRect(0, 0, item.w, item.h);
    }
  }
}

function wrapText(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  maxWidth: number,
  lineHeight: number,
): void {
  const lines = (text || "").split("\n");
  let cursor = y;
  for (const line of lines) {
    const words = line.split(" ");
    let current = "";
    for (const word of words) {
      const next = current ? `${current} ${word}` : word;
      if (ctx.measureText(next).width > maxWidth && current) {
        ctx.fillText(current, x, cursor);
        current = word;
        cursor += lineHeight;
      } else {
        current = next;
      }
    }
    ctx.fillText(current, x, cursor);
    cursor += lineHeight;
  }
}
