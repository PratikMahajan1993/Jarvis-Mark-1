import type { ComponentType } from "react";
import type {
  CanvasItem,
  CanvasItemKind,
  ImageItem,
  NoteItem,
  PdfItem,
  ShapeItem,
  StrokeItem,
  TextItem,
} from "@/lib/canvas/types";
import { ImageCard } from "./ImageCard";
import { NoteCard } from "./NoteCard";
import { PdfCard } from "./PdfCard";
import { ShapeCard } from "./ShapeCard";
import { StrokeCard } from "./StrokeCard";
import { TextCard } from "./TextCard";

export type ItemRendererProps<T extends CanvasItem> = { item: T };

type RendererMap = {
  note: ComponentType<ItemRendererProps<NoteItem>>;
  image: ComponentType<ItemRendererProps<ImageItem>>;
  pdf: ComponentType<ItemRendererProps<PdfItem>>;
  shape: ComponentType<ItemRendererProps<ShapeItem>>;
  stroke: ComponentType<ItemRendererProps<StrokeItem>>;
  text: ComponentType<ItemRendererProps<TextItem>>;
};

/** Adding an item kind: add the type in lib/canvas/types.ts, then a line here. */
export const ITEM_RENDERERS: RendererMap = {
  note: NoteCard,
  image: ImageCard,
  pdf: PdfCard,
  shape: ShapeCard,
  stroke: StrokeCard,
  text: TextCard,
};

export const ITEM_KINDS = Object.keys(ITEM_RENDERERS) as CanvasItemKind[];

export function CanvasItemContent({ item }: { item: CanvasItem }) {
  const Renderer = ITEM_RENDERERS[item.kind] as ComponentType<ItemRendererProps<CanvasItem>> | undefined;
  if (!Renderer) return null;
  return <Renderer item={item} />;
}
