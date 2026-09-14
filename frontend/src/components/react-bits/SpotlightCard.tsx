"use client";

import React, { useRef, useState } from "react";

interface SpotlightCardProps extends React.PropsWithChildren {
  className?: string;
  /** Scroll / padding live here so the spotlight covers the full visible card. */
  bodyClassName?: string;
  spotlightColor?: string;
}

/** React Bits — SpotlightCard (TS + Tailwind), adapted for Jarvis task / board panels. */
export default function SpotlightCard({
  children,
  className = "",
  bodyClassName = "",
  spotlightColor = "rgba(125, 255, 224, 0.18)",
}: SpotlightCardProps) {
  const divRef = useRef<HTMLDivElement>(null);
  const [isFocused, setIsFocused] = useState(false);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [opacity, setOpacity] = useState(0);

  const handleMouseMove: React.MouseEventHandler<HTMLDivElement> = (e) => {
    if (!divRef.current || isFocused) return;
    const rect = divRef.current.getBoundingClientRect();
    setPosition({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  };

  return (
    <div
      ref={divRef}
      onMouseMove={handleMouseMove}
      onFocus={() => {
        setIsFocused(true);
        setOpacity(0.7);
      }}
      onBlur={() => {
        setIsFocused(false);
        setOpacity(0);
      }}
      onMouseEnter={() => setOpacity(0.7)}
      onMouseLeave={() => setOpacity(0)}
      className={`relative overflow-hidden ${className}`.trim()}
    >
      {/* Viewport-locked glow — does not scroll away with inner content */}
      <div
        className="pointer-events-none absolute inset-0 z-[3] transition-opacity duration-500 ease-in-out"
        style={{
          opacity,
          background: `radial-gradient(circle at ${position.x}px ${position.y}px, ${spotlightColor}, transparent 72%)`,
        }}
      />
      <div className={["relative z-[2] min-h-0", bodyClassName].filter(Boolean).join(" ")}>{children}</div>
    </div>
  );
}
