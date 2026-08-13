import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import {
  getAiLanguage,
  hasExplicitAiLanguage,
  normalizeAiLanguage,
  setAiLanguage as persistAiLanguage,
  type AiLanguage,
} from '../lib/ai/language'

export function useAiLanguage() {
  const { user } = useAuth()
  const [language, setLanguageState] = useState<AiLanguage>(() =>
    getAiLanguage(user?.preferredLanguage),
  )

  useEffect(() => {
    if (hasExplicitAiLanguage()) return
    const next = normalizeAiLanguage(user?.preferredLanguage)
    if (next) setLanguageState(next)
  }, [user?.preferredLanguage])

  const setLanguage = useCallback((next: AiLanguage) => {
    persistAiLanguage(next)
    setLanguageState(next)
  }, [])

  return {
    language,
    setLanguage,
    isArabic: language === 'ar',
  }
}
