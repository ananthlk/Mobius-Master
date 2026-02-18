/**
 * Static suggestions for sub-tags by parent code (domain).
 * Used by "Add from suggestions" in the lexicon tree context menu.
 */
export const SUGGESTIONS_BY_PARENT: Record<string, { code: string; label?: string }[]> = {
  benefits: [
    { code: 'transportation', label: 'Transportation' },
    { code: 'housing', label: 'Housing' },
    { code: 'food_assistance', label: 'Food assistance' },
    { code: 'childcare', label: 'Childcare' },
    { code: 'utilities', label: 'Utilities' },
    { code: 'medical', label: 'Medical' },
  ],
  claims: [
    { code: 'filing', label: 'Filing' },
    { code: 'status', label: 'Status' },
    { code: 'appeals', label: 'Appeals' },
    { code: 'documents', label: 'Documents' },
  ],
}
