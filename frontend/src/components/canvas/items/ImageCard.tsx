"use client";

import { useState } from "react";
import { useCanvasActions } from "@/lib/canvas/store";
import type { ImageItem } from "@/lib/canvas/types";

export function ImageCard({ item }: { item: ImageItem }) {
  const { transport } = useCanvasActions();
  const [failed, setFailed] = useState(false);
  const source = transport.fileUrl(item.fileId);

  if (failed || !source) {
    return (
      <div className="glass grid h-full w-full place-items-center rounded-sm px-4 text-center text-sm text-white/40">
        {item.name}
      </div>
    );
  }

  return (
    <img
      src={source}
      alt={item.name}
      draggable={false}
      onError={() => setFailed(true)}
      className="pointer-events-none h-full w-full select-none rounded-sm object-contain"
    />
  );
}
