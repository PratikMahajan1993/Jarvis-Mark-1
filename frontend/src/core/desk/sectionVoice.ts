/** Desk notices that must not appear on section voice lines (orb / Monitor caption). */

export function isDeskNoticeVoice(line: string): boolean {
  return /^drawing closed\.?$/i.test(line.trim());
}

/** Voice for a section caption. Desk notices fall back so they never sit on the orb. */
export function sectionVoiceLine(voice: string, fallback: string): string {
  const v = voice.trim();
  if (!v || isDeskNoticeVoice(v)) return fallback;
  return v;
}
