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

  function toggle(name: string) {
    if (currentCollections.includes(name)) {
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
        🗂️ Collections{currentCollections.length > 0 ? ` (${currentCollections.length})` : ''}
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
            {existingCollections.length > 0 && (
              <div className="space-y-1 max-h-32 overflow-y-auto scrollbar-thin">
                {existingCollections.map((name) => (
                  <label
                    key={name}
                    className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs cursor-pointer"
                    style={{ background: 'var(--tint-1)', color: 'var(--foreground)' }}
                  >
                    <input
                      type="checkbox"
                      checked={currentCollections.includes(name)}
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
