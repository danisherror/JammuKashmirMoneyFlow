/**
 * Pure helpers for the grant breakdown (todo.md 2.2b): flatten the head tree, rank unspent items,
 * label note categories and link to a PDF page.
 */
import type { AccountabilityFlag, FigureSource, FlagKind, GrantBreakdown, HeadNode, HeadRowItem, NoteCategory } from './api'

export function flattenRows(nodes: HeadNode[]): HeadRowItem[] {
  return nodes.flatMap(node => [...node.rows, ...flattenRows(node.children)])
}

/**
 * Money left unspent under a head, in ₹ lakhs, as printed: the saving, or the whole provision when
 * the note says it remained un-utilised (those tables print only the grant). null when the row
 * isn't about unspent money (excess, spending without provision).
 */
export function unspentLakhs(row: HeadRowItem): number | null {
  if (row.saving_lakhs !== null && row.saving_lakhs > 0) return row.saving_lakhs
  if ((row.category === 'unutilised' || row.category === 'unutilised_supplementary') && row.final_grant_lakhs !== null) {
    return row.final_grant_lakhs
  }
  return null
}

/** The `limit` heads with the most money left unspent, largest first. */
export function biggestUnspent(breakdown: GrantBreakdown, limit = 10): { row: HeadRowItem; unspent: number }[] {
  return flattenRows(breakdown.tree)
    .map(row => ({ row, unspent: unspentLakhs(row) }))
    .filter((x): x is { row: HeadRowItem; unspent: number } => x.unspent !== null)
    .sort((a, b) => b.unspent - a.unspent)
    .slice(0, limit)
}

const CATEGORY_LABELS: Record<NoteCategory, string> = {
  saving: 'Saving',
  excess: 'Excess',
  unutilised: 'Entire provision unspent',
  unutilised_supplementary: 'Supplementary unspent',
  without_provision: 'Spent without provision',
  comment: 'Comment',
}

export function categoryLabel(category: NoteCategory): string {
  return CATEGORY_LABELS[category] ?? category
}

/**
 * Link to a page of the source PDF. `#page=N` is the PDF fragment identifier defined in RFC 8118
 * section 3 (https://www.rfc-editor.org/rfc/rfc8118#section-3); viewers that ignore it open page 1.
 */
export function pdfPageUrl(source: FigureSource | null | undefined): string | null {
  if (!source?.source_url) return null
  return source.page != null ? `${source.source_url}#page=${source.page}` : source.source_url
}

/** "2052 › 090 › 0099 › 0518" for a head path. */
export function headCodePath(row: HeadRowItem): string {
  return row.head_path.map(p => p.code).join(' › ')
}

/** Total of a node's own rows and all rows below it, for a field; null when nothing is printed. */
export function nodeTotal(node: HeadNode, field: 'final_grant_lakhs' | 'expenditure_lakhs'): number | null {
  const values = flattenRows([node]).map(r => r[field]).filter((v): v is number => v !== null)
  return values.length ? Math.round(values.reduce((a, b) => a + b, 0) * 100) / 100 : null
}

export const FLAG_KINDS: { kind: FlagKind; label: string; hint: string }[] = [
  { kind: 'excess_over_grant', label: 'Spent over the grant', hint: 'Needs regularisation by the legislature' },
  { kind: 'savings_not_surrendered', label: 'Savings not surrendered', hint: 'Unspent money kept instead of surrendered during the year' },
  { kind: 'supplementary_not_needed', label: 'Supplementary not needed', hint: 'Final saving at least as large as the supplementary grant' },
  { kind: 'fully_unutilised', label: 'Entire provision unspent', hint: 'Heads where none of the provision was used' },
  { kind: 'reasons_not_communicated', label: 'Reasons not communicated', hint: 'Share of large variations the department did not explain' },
]

export function flagLabel(kind: FlagKind): string {
  return FLAG_KINDS.find(k => k.kind === kind)?.label ?? kind
}

/** Count of flags per kind, in FLAG_KINDS order, including kinds with none. */
export function countFlags(flags: AccountabilityFlag[]): { kind: FlagKind; label: string; count: number }[] {
  return FLAG_KINDS.map(({ kind, label }) => ({ kind, label, count: flags.filter(f => f.kind === kind).length }))
}
