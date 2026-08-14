/**
 * File Vault API client — real upload/download via Supabase Storage S3.
 */

import { apiFetch, apiFetchArrayBuffer } from '../apiClient'
import type { FileAiAnalysis, VaultFile } from '../../types/fileVault'

export interface ApiVaultFile {
  id: string
  name: string
  sizeBytes: number
  mimeType: string
  course: string | null
  doctorName: string | null
  favorite: boolean
  pinned: boolean
  collections: string[]
  examDate: string | null
  readingProgressPct: number
  learningStatus: string
  lastPage: number
  totalPages: number
  createdAt: string
  updatedAt: string
  downloadUrl: string | null
  analysis: Record<string, unknown> | null
}

export interface UploadInitResponse {
  fileId: string
  uploadUrl: string
  storageKey: string
}

/** Build a frontend VaultFile skeleton from an API record. */
export function apiVaultFileToFrontend(api: ApiVaultFile, local: Partial<VaultFile> = {}): VaultFile {
  const now = Date.now()
  const uploadedAt = api.createdAt ? new Date(api.createdAt).getTime() : now
  return {
    id: api.id,
    name: api.name,
    title: api.name.replace(/\.pdf$/i, ''),
    course: api.course ?? 'Uncategorized',
    doctorName: api.doctorName ?? 'Self-uploaded',
    weekKey: '',
    weekLabel: '',
    uploadedAt,
    sizeBytes: api.sizeBytes,
    pageCount: api.totalPages,
    wordCount: 0,
    estimatedReadingMinutes: 0,
    thumbnailDataUrl: null,
    color: '#2DD4BF',
    icon: '📄',
    status: (api.learningStatus as VaultFile['status']) ?? 'not-started',
    pagesRead: [],
    currentPage: api.lastPage ?? 1,
    progressPct: api.readingProgressPct ?? 0,
    studyTimeSeconds: 0,
    lastViewedAt: null,
    completedAt: null,
    examDate: api.examDate ? new Date(api.examDate).getTime() : null,
    favorite: api.favorite,
    pinned: api.pinned,
    bookmarks: [],
    notes: [],
    tags: [],
    collections: api.collections ?? [],
    analysis: (api.analysis as unknown as FileAiAnalysis | null) ?? null,
    analysisState: api.analysis ? 'ready' : 'pending',
    pagesText: [],
    quizAttempts: [],
    examAttempts: [],
    ...local,
  }
}

/** Build the PATCH payload that mirrors local VaultFile state to the API. */
export function vaultFileToPatch(file: VaultFile): Record<string, unknown> {
  return {
    favorite: file.favorite,
    pinned: file.pinned,
    collections: file.collections,
    examDate: file.examDate ? new Date(file.examDate).toISOString() : null,
    readingProgressPct: file.progressPct,
    learningStatus: file.status,
    lastPage: file.currentPage,
    totalPages: file.pageCount,
    analysis: file.analysis ?? undefined,
    course: file.course === 'Uncategorized' ? null : file.course,
    doctorName: file.doctorName === 'Self-uploaded' ? null : file.doctorName,
  }
}

export const vaultApi = {
  list: () => apiFetch<ApiVaultFile[]>('/api/v1/file-vault'),

  uploadInit: (filename: string, contentType: string, sizeBytes: number) =>
    apiFetch<UploadInitResponse>(
      `/api/v1/file-vault/upload-init?filename=${encodeURIComponent(filename)}&content_type=${encodeURIComponent(contentType)}&size_bytes=${sizeBytes}`,
      { method: 'POST' },
    ),

  complete: (fileId: string) => apiFetch<ApiVaultFile>(`/api/v1/file-vault/${fileId}/complete`, { method: 'POST' }),

  update: (fileId: string, patch: Record<string, unknown>) =>
    apiFetch<ApiVaultFile>(`/api/v1/file-vault/${fileId}`, { method: 'PATCH', body: patch }),

  remove: (fileId: string) => apiFetch<void>(`/api/v1/file-vault/${fileId}`, { method: 'DELETE' }),

  downloadUrl: (fileId: string) =>
    apiFetch<{ downloadUrl: string; name: string }>(`/api/v1/file-vault/${fileId}/download`),

  /**
   * Returns the authenticated streaming URL for the raw PDF bytes of an
   * owned file. Callers (the PDF Viewer) attach the bearer token as a
   * query param only when they cannot set request headers (e.g. an
   * `<embed>`/`<object>` tag); the in-app viewer uses `contentBuffer`
   * below, which goes through the centralized request layer with proper
   * Authorization / X-Access-Token headers.
   */
  contentUrl: (fileId: string) => `/api/v1/file-vault/${fileId}/content`,

  /**
   * Fetches the raw PDF bytes for an owned file via the authenticated
   * backend, going through the same centralized request layer (with
   * JWT, X-Access-Token, the auth bootstrap gate, the concurrency-safe
   * refresh-on-401 path, and the global error type) used by every
   * other authenticated call. Returns the bytes as a real `ArrayBuffer`
   * so the PDF Viewer can pass them directly to `pdfjsLib.getDocument`.
   */
  contentBuffer: (fileId: string) => apiFetchArrayBuffer(`/api/v1/file-vault/${fileId}/content`),

  createNote: (input: { fileId: string; page: number; content: string; color?: string }) =>
    apiFetch<Record<string, unknown>>('/api/v1/file-vault/notes', { method: 'POST', body: input }),

  deleteNote: (noteId: string) =>
    apiFetch<void>(`/api/v1/file-vault/notes/${noteId}`, { method: 'DELETE' }),

  createBookmark: (input: { fileId: string; page: number; label?: string }) =>
    apiFetch<Record<string, unknown>>('/api/v1/file-vault/bookmarks', { method: 'POST', body: input }),

  deleteBookmark: (bookmarkId: string) =>
    apiFetch<void>(`/api/v1/file-vault/bookmarks/${bookmarkId}`, { method: 'DELETE' }),
}
