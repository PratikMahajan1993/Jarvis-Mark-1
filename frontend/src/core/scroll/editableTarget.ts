/**
 * Section keys (PageUp/PageDown, Alt+1–9) treat single-line text as non-editable
 * so the always-focused baton does not swallow navigation.
 */
export function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable || target.getAttribute("contenteditable") === "true") return true;
  const tag = target.tagName;
  if (tag === "TEXTAREA" || tag === "SELECT") return true;
  if (tag !== "INPUT") return false;
  const type = (target as HTMLInputElement).type;
  return !(type === "text" || type === "search" || type === "");
}

/**
 * Any form field or contenteditable. Space must type here, not preventDefault.
 * Includes `input[type=text]` (the baton) which `isEditableTarget` deliberately excludes.
 */
export function isFieldTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable || target.getAttribute("contenteditable") === "true") return true;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
}
