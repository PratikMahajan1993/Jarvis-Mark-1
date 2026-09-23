/** DOM/GSAP highlight bus — no React commits on pointer move. */

import gsap from "gsap";

let current: number | null = null;
const pinScaleTo = new Map<number, ReturnType<typeof gsap.quickTo>>();

export function registerPinScale(index: number, el: HTMLElement): () => void {
  gsap.set(el, { transformOrigin: "50% 50%", scale: 1 });
  pinScaleTo.set(
    index,
    gsap.quickTo(el, "scale", { duration: 0.22, ease: "power3.out" }),
  );
  return () => {
    pinScaleTo.delete(index);
  };
}

export function setBenchHighlight(index: number | null): void {
  if (current === index) return;
  current = index;

  document.querySelectorAll<HTMLElement>("[data-bench-row]").forEach((el) => {
    const i = Number(el.dataset.benchRow);
    const on = Number.isFinite(i) && i === index;
    el.classList.toggle("bench-row-hl", on);
    el.style.transform = on ? "translateY(-2px)" : "";
  });

  document.querySelectorAll<HTMLElement>("[data-bench-pin]").forEach((el) => {
    const i = Number(el.dataset.benchPin);
    const on = Number.isFinite(i) && i === index;
    el.classList.toggle("bench-pin-hl", on);
    const to = pinScaleTo.get(i);
    to?.(on ? 1.25 : 1);
  });
}

export function clearBenchHighlight(): void {
  setBenchHighlight(null);
}
