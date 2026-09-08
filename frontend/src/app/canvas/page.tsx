"use client";

import dynamic from "next/dynamic";

const CanvasShell = dynamic(
  () => import("@/components/canvas/CanvasShell").then((mod) => ({ default: mod.CanvasShell })),
  {
    ssr: false,
    loading: () => <div className="h-screen bg-[#05070a]" />,
  },
);

export default function CanvasPage() {
  return <CanvasShell />;
}
