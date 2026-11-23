/** Percentage of `part` in `whole`, or null when either is missing or `whole` isn't positive. */
export function pct(part: number | null | undefined, whole: number | null | undefined): number | null {
  if (part == null || whole == null || whole <= 0) return null
  return Math.round((part / whole) * 10000) / 100
}
