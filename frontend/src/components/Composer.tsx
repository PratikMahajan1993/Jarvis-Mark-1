import { FormEvent, useRef, useState } from "react";

type Props = {
  onSubmit: (value: string) => void;
  onFocusChange?: (focused: boolean) => void;
  busy: boolean;
};

export function Composer({ onSubmit, onFocusChange, busy }: Props) {
  const ref = useRef<HTMLInputElement>(null);
  const [focused, setFocused] = useState(false);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = (ref.current?.value || "").trim();
    if (!value || busy) return;
    onSubmit(value);
    if (ref.current) ref.current.value = "";
  };

  return (
    <form onSubmit={submit} className="hud-panel hud-accent-cyan w-full max-w-2xl px-5 py-2.5">
      <div className="flex items-center gap-3">
        <span className={`font-mono text-sm ${focused ? "text-cyan" : "text-cyan/40"}`}>&gt;</span>
        <input
          ref={ref}
          name="command"
          placeholder="Type a command"
          disabled={busy}
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
          data-lpignore="true"
          data-1p-ignore="true"
          data-form-type="other"
          onFocus={() => {
            setFocused(true);
            onFocusChange?.(true);
          }}
          onBlur={() => {
            setFocused(false);
            onFocusChange?.(false);
          }}
          className="w-full bg-transparent text-center font-display text-2xl text-white outline-none placeholder:text-white/20"
        />
      </div>
    </form>
  );
}
