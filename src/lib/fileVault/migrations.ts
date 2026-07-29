import type { VaultFile } from '../../types/fileVault'

/**
 * Normalizes a VaultFile record loaded from persistent storage
 * (IndexedDB) so every field the app relies on is guaranteed to exist,
 * regardless of which schema version originally wrote that record.
 *
 * ROOT CAUSE this exists to fix: IndexedDB has no schema/migration
 * system — it stores exactly whatever JSON was written. When new
 * VaultFile fields (`collections`, `examDate`) were introduced, any
 * file record persisted by an earlier build of the app was loaded back
 * *without* those fields (`undefined`), because the object already
 * living in the browser's IndexedDB was never rewritten. Downstream
 * code that assumed those fields always exist (e.g.
 * `CollectionPicker.tsx` calling `currentCollections.includes(...)`)
 * threw an uncaught TypeError the moment such a file was rendered —
 * and because nothing in this app previously caught render errors,
 * that exception unmounted the entire React tree, leaving only the
 * bare `<body>` background visible (which looks exactly like a "black
 * screen" in dark mode). This normalizer is applied at the single
 * choke point every persisted file passes through
 * (`FileVaultStorage.listFiles()` / `getFile()`), so every component
 * downstream can keep trusting the `VaultFile` type without needing
 * defensive `?? []` checks scattered everywhere — and so the *next*
 * time a field is added to `VaultFile`, only this one function needs a
 * new line, not an audit of every consumer.
 */
export function normalizeVaultFile(raw: VaultFile): VaultFile {
  return {
    ...raw,
    pagesRead: Array.isArray(raw.pagesRead) ? raw.pagesRead : [],
    bookmarks: Array.isArray(raw.bookmarks) ? raw.bookmarks : [],
    notes: Array.isArray(raw.notes) ? raw.notes : [],
    tags: Array.isArray(raw.tags) ? raw.tags : [],
    collections: Array.isArray(raw.collections) ? raw.collections : [],
    pagesText: Array.isArray(raw.pagesText) ? raw.pagesText : [],
    quizAttempts: Array.isArray(raw.quizAttempts) ? raw.quizAttempts : [],
    examAttempts: Array.isArray(raw.examAttempts) ? raw.examAttempts : [],
    examDate: typeof raw.examDate === 'number' ? raw.examDate : null,
    favorite: Boolean(raw.favorite),
    pinned: Boolean(raw.pinned),
    analysisState: raw.analysisState ?? (raw.analysis ? 'ready' : 'pending'),
  }
}

export function normalizeVaultFiles(rawFiles: VaultFile[]): VaultFile[] {
  return rawFiles.map(normalizeVaultFile)
}
