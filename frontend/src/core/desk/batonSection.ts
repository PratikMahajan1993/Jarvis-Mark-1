/**
 * On section change: flush the previous section's live compose, then adopt the
 * next section's stored text. Empty compose still flushes so a send clears the key.
 */
export function batonSectionChangePlan(
  previousSection: string,
  nextSection: string,
  liveCompose: string,
  storedNext: string,
): { save: { section: string; text: string }; nextCompose: string } | null {
  if (previousSection === nextSection) return null;
  return {
    save: { section: previousSection, text: liveCompose },
    nextCompose: storedNext,
  };
}
