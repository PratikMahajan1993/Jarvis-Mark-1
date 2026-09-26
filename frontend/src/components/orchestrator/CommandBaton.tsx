"use client";

import { FormEvent, KeyboardEvent, useEffect, useRef } from "react";
import GlareHover from "@/components/react-bits/GlareHover";
import { primeVoicePlayback } from "@/lib/voice";

export function CommandBaton({
  value,
  onChange,
  onSubmit,
  onMic,
  listening = false,
  disabled = false,
  hidden = false,
  absolute = true,
  placeholder = "Speak or type to Jarvis...",
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (value: string) => void;
  onMic?: () => void;
  listening?: boolean;
  disabled?: boolean;
  hidden?: boolean;
  absolute?: boolean;
  placeholder?: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!hidden && !disabled) inputRef.current?.focus();
  }, [hidden, disabled]);

  function handleSubmit(event: FormEvent | KeyboardEvent) {
    event.preventDefault();
    primeVoicePlayback();
    const next = value.trim();
    if (!next || disabled) return;
    onSubmit(next);
  }

  return (
    <GlareHover
      className={[
        "orch-baton flex h-12 w-[480px] max-w-[calc(100vw-2rem)] items-center rounded-full border border-[color:var(--border)] bg-[color:var(--surface)] px-6 shadow-[0_10px_30px_rgba(0,0,0,0.5)] transition-all duration-[600ms]",
        absolute ? "absolute bottom-12 left-1/2 z-10 -translate-x-1/2" : "relative z-10",
        listening ? "listening" : "",
        hidden ? "pointer-events-none translate-y-5 opacity-0" : "",
        disabled ? "opacity-50" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      glareColor="#7dffe0"
      glareOpacity={0.28}
      glareSize={240}
    >
      <form onSubmit={handleSubmit} className="relative z-[2] flex h-full w-full items-center">
        <button
          type="button"
          className="orch-mic relative mr-4 flex h-6 w-6 items-center justify-center"
          onClick={onMic}
          disabled={disabled}
          aria-label={listening ? "Listening" : "Listen"}
        >
          <span className="orch-mic-ring absolute inset-[-4px] z-[1] rounded-full bg-[color:var(--accent)] opacity-0" />
          <svg className="orch-mic-icon relative z-[2] h-4 w-4 fill-[color:var(--muted)]" viewBox="0 0 24 24">
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5-3c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
          </svg>
        </button>
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key !== "Enter" || event.shiftKey) return;
            event.preventDefault();
            primeVoicePlayback();
            handleSubmit(event);
          }}
          placeholder={placeholder}
          autoComplete="off"
          disabled={disabled}
          className="w-full bg-transparent font-body text-[0.95rem] text-[color:var(--fg)] outline-none placeholder:text-[color:var(--muted)]"
        />
      </form>
    </GlareHover>
  );
}
