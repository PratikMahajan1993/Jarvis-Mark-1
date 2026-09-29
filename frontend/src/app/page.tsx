"use client";

import dynamic from "next/dynamic";

const Desk = dynamic(() => import("@/core/desk/Desk").then((mod) => ({ default: mod.Desk })), {
  ssr: false,
  loading: () => <div className="h-[100dvh]" />,
});

export default function HomePage() {
  return <Desk />;
}
