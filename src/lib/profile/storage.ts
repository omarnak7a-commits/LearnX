import type { StudentProfile } from '../../types/profile'

/**
 * localStorage persistence for the Student Profile — same "swappable
 * behind an interface" posture as `src/lib/fileVault/storage.ts`
 * (`FileVaultStorage`), just backed by `localStorage` instead of
 * IndexedDB since a profile record is small JSON with no binary blobs.
 * A real backend integration only needs to replace this module's
 * `load`/`save` implementations — every consumer goes through
 * `useProfile()`, never `localStorage` directly.
 */

const STORAGE_KEY = 'learnx-student-profile-v1'

/**
 * Coerces every field that has been added to `StudentProfile` after a
 * profile may have already been persisted (e.g. `longestStreakDays`,
 * added when the Gamification rebuild shipped) to a safe default. Same
 * root-cause fix as `src/lib/fileVault/migrations.ts` — a profile record
 * created before a new field existed would otherwise load back with that
 * field `undefined`, and any direct (non-optional-chained) access to it
 * elsewhere would crash the whole page (see that file's comment for the
 * full "My Files black screen" incident this pattern was born from).
 */
function normalizeProfile(raw: StudentProfile): StudentProfile {
  return {
    ...raw,
    longestStreakDays:
      typeof raw.longestStreakDays === 'number' ? raw.longestStreakDays : (raw.streakDays ?? 0),
  }
}

export function loadProfile(): StudentProfile | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as StudentProfile
    return normalizeProfile(parsed)
  } catch {
    return null
  }
}

export function saveProfile(profile: StudentProfile): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(profile))
  } catch {
    // Storage unavailable (private browsing quota etc.) — profile just
    // won't persist across reloads this session; never throw and break
    // the UI over it.
  }
}

export function clearProfile(): void {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // ignore
  }
}
