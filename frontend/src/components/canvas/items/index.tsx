import type { ComponentType } from "react";
import type { CanvasItem, CanvasItemKind, ImageItem, NoteItem, PdfItem } from "@/lib/canvas/types";
import { ImageCard } from "./ImageCard";
import { NoteCard } from "./NoteCard";
import { PdfCard } from "./PdfCard";

export type ItemRendererProps<T extends CanvasItem> = { item: T };

type RendererMap = {
  note: ComponentType<ItemRendererProps<NoteItem>>;
  image: ComponentType<ItemRendererProps<ImageItem>>;
  pdf: ComponentType<ItemRendererProps<PdfItem>>;
};

/** Adding an item kind: add the type in lib/canvas/types.ts, then a line here. */
export const ITEM_RENDERERS: RendererMap = {
  note: NoteCard,
  image: ImageCard,
  pdf: PdfCard,
};

export const ITEM_KINDS = Object.keys(ITEM_RENDERERS) as CanvasItemKind[];

/**
 * The one place the registry lookup is narrowed. Keeping the cast here means
 * the viewport never has to know about individual item shapes.
 */
export function CanvasItemContent({ item }: { item: CanvasItem }) {
  const Renderer = ITEM_RENDERERS[item.kind] as ComponentType<ItemRendererProps<CanvasItem>>;
  return <Renderer item={item} />;
}
