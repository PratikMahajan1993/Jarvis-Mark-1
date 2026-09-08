import { FormEvent, useRef } from "react";

type Props = {
  onSubmit: (value: string) => void;
  onFocusChange?: (focused: boolean) => void;
  busy: boolean;
};

export function Composer({ onSubmit, onFocusChange, busy }: Props) {
  const ref = useRef<HTMLInputElement>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = (ref.current?.value || "").trim();
    if (!value || busy) return;
    onSubmit(value);
    if (ref.current) ref.current.value = "";
  };

  return (
    <form onSubmit={submit} className="w-full max-w-2xl">
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
        onFocus={() => onFocusChange?.(true)}
        onBlur={() => onFocusChange?.(false)}
        className="w-full bg-transparent text-center font-display text-2xl text-white outline-none placeholder:text-white/20"
      />
    </form>
  );
}
