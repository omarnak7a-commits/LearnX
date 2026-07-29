import type { FileLearningStatus, VaultFile } from '../../../../types/fileVault'

export const statusMeta: Record<
  FileLearningStatus,
  { label: string; color: string; tone: 'neutral' | 'warning' | 'primary' | 'success' }
> = {
  'not-started': { label: 'Not Started', color: 'var(--muted-foreground)', tone: 'neutral' },
  'in-progress': { label: 'In Progress', color: '#f59e0b', tone: 'warning' },
  viewed: { label: 'Viewed', color: '#38bdf8', tone: 'primary' },
  completed: { label: 'Completed', color: 'var(--success)', tone: 'success' },
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function formatRelativeTime(timestamp: number | null): string {
  if (!timestamp) return 'Never'
  const diffMs = Date.now() - timestamp
  const minutes = Math.floor(diffMs / 60000)
  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  const weeks = Math.floor(days / 7)
  if (weeks < 5) return `${weeks}w ago`
  const months = Math.floor(days / 30)
  return `${months}mo ago`
}

export function formatStudyTime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  const remMinutes = minutes % 60
  return remMinutes > 0 ? `${hours}h ${remMinutes}m` : `${hours}h`
}

export function pagesRemaining(file: VaultFile): number {
  return Math.max(0, file.pageCount - new Set(file.pagesRead).size)
}

export function difficultyLabel(d: 'easy' | 'medium' | 'hard'): string {
  return d.charAt(0).toUpperCase() + d.slice(1)
}
