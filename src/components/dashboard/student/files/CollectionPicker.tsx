import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useFileVault } from '../../../../context/FileVaultContext'

interface CollectionPickerProps {
  fileId: string
  currentCollections: string[]
  existingCollections: string[]
}

/**
 * "Create Collections" from the spec — lets a student add/remove this
 * file from any number of named, student-defined collections (e.g.
 * "Exam Prep", "Midterm Review"), persisted as a real field on the
 * VaultFile via FileVaultContext. New collection names are created
 * on the fly simply by typing one that doesn't exist yet.
 */
export default function CollectionPicker({
  fileId,
  currentCollections,
  existingCollections,
}: CollectionPickerProps) {
  const { addToCollection, removeFromCollection } = useFileVault()
  const [open, setOpen] = useState(false)
  const [newName, setNewName] = useState('')

  // Defensive fallback: `currentCollections` should always be a real
  // array (the storage layer normalizes every persisted VaultFile
  // record — see src/lib/fileVault/migrations.ts), but this component
  // must never crash the page even if it somehow receives `undefined`
  // from a caller, since an uncaught error here previously took down
  // the entire app (see MyFilesErrorBoundary.tsx for the last line of
  // defense against exactly this class of bug).
  const safeCurrentCollections = currentCollections ?? []
  const safeExistingCollections = existingCollections ?? []

  function toggle(name: string) {
    if (safeCurrentCollections.includes(name)) {
      removeFromCollection(fileId, name)
    } else {
      addToCollection(fileId, name)
    }
  }

  function createAndAdd() {
    const trimmed = newName.trim()
    if (!trimmed) return
    addToCollection(fileId, trimmed)
    setNewName('')
  }

  return (
    <div className="relative">
      <button
        onClick={(e) => {
          e.stopPropagation()
          setOpen((v) => !v)
        }}
        className="text-xs font-semibold px-2.5 py-1.5 rounded-lg transition-all"
        style={{ background: 'var(--tint-2)', color: 'var(--foreground)' }}
      >
        🗂️ Collections
        {safeCurrentCollections.length > 0 ? ` (${safeCurrentCollections.length})` : ''}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            className="absolute z-20 top-full left-0 mt-1.5 w-56 rounded-xl p-3 space-y-2"
            style={{
              background: 'var(--surface-2)',
              border: '1px solid var(--border)',
              boxShadow: 'var(--shadow-lg)',
            }}
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.15 }}
            onClick={(e) => e.stopPropagation()}
          >
            {safeExistingCollections.length > 0 && (
              <div className="space-y-1 max-h-32 overflow-y-auto scrollbar-thin">
                {safeExistingCollections.map((name) => (
                  <label
                    key={name}
                    className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs cursor-pointer"
                    style={{ background: 'var(--tint-1)', color: 'var(--foreground)' }}
                  >
                    <input
                      type="checkbox"
                      checked={safeCurrentCollections.includes(name)}
                      onChange={() => toggle(name)}
                      className="accent-current"
                    />
                    {name}
                  </label>
                ))}
              </div>
            )}
            <div className="flex items-center gap-1.5">
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && createAndAdd()}
                placeholder="New collection..."
                className="input-field flex-1 px-2 py-1.5 rounded-lg text-xs"
              />
              <button
                onClick={createAndAdd}
                className="text-xs font-semibold px-2 py-1.5 rounded-lg flex-shrink-0"
                style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
              >
                +
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
