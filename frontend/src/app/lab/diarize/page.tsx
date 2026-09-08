"use client";

import dynamic from "next/dynamic";

const DiarizeLab = dynamic(() => import("./DiarizeLab"), {
  ssr: false,
  loading: () => <div className="hud-bg min-h-screen" />,
});

export default function DiarizeLabPage() {
  return <DiarizeLab />;
}
