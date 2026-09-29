/** Local Engineering-deck drop prompt: quote workflow vs view/discuss (not an external send). */

export type DropIntent = "quote" | "discuss";

/** Phrase that hits `is_quote_start` / shop-quote without queuing quote_send. */
export const QUOTE_START_FROM_DROP = "quote this drawing";

/**
 * Map an on-screen choice or spoken reply to a drop intent.
 * Returns null when the text is empty or ambiguous.
 */
export function dropIntentChoice(raw: string): DropIntent | null {
  const text = raw.trim().toLowerCase().replace(/\s+/g, " ");
  if (!text) return null;

  if (
    /^(quote|start quote|start a quote|quotation)$/.test(text) ||
    /\bstart\s+(a\s+)?quote(\s+workflow)?\b/.test(text) ||
    /\bquote\s+this\b/.test(text) ||
    /\bwant\s+(a\s+)?quote\b/.test(text)
  ) {
    return "quote";
  }

  if (
    /^(view|discuss|view and discuss|only view|talk)$/.test(text) ||
    /\bonly\s+view\b/.test(text) ||
    /\bview\s+and\s+discuss\b/.test(text) ||
    /\bjust\s+(view|discuss|talk)\b/.test(text) ||
    /\bdiscuss\s+(it|the\s+drawing)\b/.test(text)
  ) {
    return "discuss";
  }

  return null;
}
