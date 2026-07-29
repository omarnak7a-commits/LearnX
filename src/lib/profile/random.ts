/**
 * Tiny deterministic PRNG helpers shared by the profile/ranking module —
 * same mulberry32 pattern already used in
 * `src/lib/fileVault/textAnalysis.ts`, duplicated locally (rather than
 * imported cross-module) so the profile system has zero dependency on
 * the File Vault's internals.
 */

export function hashString(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) {
    h = (h * 31 + s.charCodeAt(i)) | 0
  }
  return h
}

export function seededRandom(seed: number): () => number {
  let a = seed >>> 0 || 1
  return function () {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export function pick<T>(rng: () => number, items: readonly T[]): T {
  return items[Math.floor(rng() * items.length) % items.length]
}

export function randomInt(rng: () => number, min: number, max: number): number {
  return Math.floor(rng() * (max - min + 1)) + min
}
