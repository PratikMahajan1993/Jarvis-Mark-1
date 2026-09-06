import { FormEvent, useEffect, useRef } from "react";

type Props = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  busy: boolean;
  open: boolean;
};

export function Composer({ value, onChange, onSubmit, busy, open }: Props) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (open) ref.current?.focus();
  }, [open]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit();
  };

  if (!open) return null;

  return (
    <form onSubmit={submit} className="w-full max-w-2xl">
      <input
        ref={ref}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder=""
        disabled={busy}
        className="w-full bg-transparent text-center font-display text-2xl text-white outline-none placeholder:text-white/20"
      />
    </form>
  );
}
