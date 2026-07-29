import { openDB, type IDBPDatabase } from 'idb'
import type { VaultFile } from '../../types/fileVault'
import { normalizeVaultFile, normalizeVaultFiles } from './migrations'

/**
 * Persistence layer for the Smart AI File Vault, built behind a small
 * `FileVaultStorage` interface so it can be swapped for a real backend
 * (S3 + Postgres + FastAPI, per `backend/README.md`) later without
 * touching any UI or business-logic code — every call site only ever
 * talks to this interface, never to IndexedDB directly.
 *
 * Two object stores:
 *  - `files`     — VaultFile metadata (progress, favorites, bookmarks,
 *                  AI analysis results, quiz history). Small, JSON-safe.
 *  - `blobs`     — the actual uploaded PDF binary data, keyed by file id.
 *                  Kept separate so listing/searching the library never
 *                  has to touch multi-megabyte blobs.
 */
export interface FileVaultStorage {
  init(): Promise<void>
  listFiles(): Promise<VaultFile[]>
  getFile(id: string): Promise<VaultFile | undefined>
  putFile(file: VaultFile): Promise<void>
  deleteFile(id: string): Promise<void>
  putBlob(id: string, blob: Blob): Promise<void>
  getBlob(id: string): Promise<Blob | undefined>
  deleteBlob(id: string): Promise<void>
}

const DB_NAME = 'learnx-file-vault'
const DB_VERSION = 1
const FILES_STORE = 'files'
const BLOBS_STORE = 'blobs'

class IndexedDbFileVaultStorage implements FileVaultStorage {
  private dbPromise: Promise<IDBPDatabase> | null = null

  async init(): Promise<void> {
    if (this.dbPromise) {
      await this.dbPromise
      return
    }
    this.dbPromise = openDB(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains(FILES_STORE)) {
          db.createObjectStore(FILES_STORE, { keyPath: 'id' })
        }
        if (!db.objectStoreNames.contains(BLOBS_STORE)) {
          db.createObjectStore(BLOBS_STORE)
        }
      },
    })
    await this.dbPromise
  }

  private async db(): Promise<IDBPDatabase> {
    if (!this.dbPromise) await this.init()
    return this.dbPromise!
  }

  async listFiles(): Promise<VaultFile[]> {
    const db = await this.db()
    const raw = await db.getAll(FILES_STORE)
    return normalizeVaultFiles(raw)
  }

  async getFile(id: string): Promise<VaultFile | undefined> {
    const db = await this.db()
    const raw = await db.get(FILES_STORE, id)
    return raw ? normalizeVaultFile(raw) : undefined
  }

  async putFile(file: VaultFile): Promise<void> {
    const db = await this.db()
    await db.put(FILES_STORE, file)
  }

  async deleteFile(id: string): Promise<void> {
    const db = await this.db()
    await db.delete(FILES_STORE, id)
  }

  async putBlob(id: string, blob: Blob): Promise<void> {
    const db = await this.db()
    await db.put(BLOBS_STORE, blob, id)
  }

  async getBlob(id: string): Promise<Blob | undefined> {
    const db = await this.db()
    return db.get(BLOBS_STORE, id)
  }

  async deleteBlob(id: string): Promise<void> {
    const db = await this.db()
    await db.delete(BLOBS_STORE, id)
  }
}

/**
 * In-memory fallback used only if IndexedDB is unavailable (e.g. private
 * browsing modes that disable it in some browsers). Keeps the app
 * functional for the session even without persistence.
 */
class InMemoryFileVaultStorage implements FileVaultStorage {
  private files = new Map<string, VaultFile>()
  private blobs = new Map<string, Blob>()

  async init(): Promise<void> {}
  async listFiles(): Promise<VaultFile[]> {
    return normalizeVaultFiles([...this.files.values()])
  }
  async getFile(id: string): Promise<VaultFile | undefined> {
    const raw = this.files.get(id)
    return raw ? normalizeVaultFile(raw) : undefined
  }
  async putFile(file: VaultFile): Promise<void> {
    this.files.set(file.id, file)
  }
  async deleteFile(id: string): Promise<void> {
    this.files.delete(id)
  }
  async putBlob(id: string, blob: Blob): Promise<void> {
    this.blobs.set(id, blob)
  }
  async getBlob(id: string): Promise<Blob | undefined> {
    return this.blobs.get(id)
  }
  async deleteBlob(id: string): Promise<void> {
    this.blobs.delete(id)
  }
}

let storageInstance: FileVaultStorage | null = null

export function getFileVaultStorage(): FileVaultStorage {
  if (storageInstance) return storageInstance
  try {
    if (typeof indexedDB !== 'undefined') {
      storageInstance = new IndexedDbFileVaultStorage()
      return storageInstance
    }
  } catch {
    // fall through to in-memory
  }
  storageInstance = new InMemoryFileVaultStorage()
  return storageInstance
}
