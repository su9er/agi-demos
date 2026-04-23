/**
 * extractMentionQuery — helper for host input components.
 *
 * Given the raw text up to the caret, returns the mention trigger query
 * (characters after the last ``@`` that is either at start or preceded
 * by whitespace) or ``null`` if no active mention.
 *
 * Pure structural tokenizer — no NL interpretation. The *selection* of
 * which agent the user means is driven by their explicit click/enter
 * from the picker; this helper merely detects that a mention is being
 * typed.
 */
export function extractMentionQuery(textBeforeCaret: string): string | null {
  if (!textBeforeCaret) return null;
  const atIdx = textBeforeCaret.lastIndexOf('@');
  if (atIdx < 0) return null;
  const isAtBoundary = atIdx === 0 || /\s/.test(textBeforeCaret[atIdx - 1] ?? '');
  if (!isAtBoundary) return null;
  const query = textBeforeCaret.slice(atIdx + 1);
  if (/\s/.test(query)) return null;
  return query;
}
