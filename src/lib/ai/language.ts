/** Shared Arabic / English helpers for LearnX AI surfaces. */

export type AiLanguage = 'ar' | 'en'

export const AI_LANGUAGE_KEY = 'learnx_ai_language'

const AR_ALIASES = new Set(['ar', 'ara', 'arabic', 'العربية', 'عربي', 'عربية', 'عربيه'])
const EN_ALIASES = new Set(['en', 'eng', 'english', 'الإنجليزية', 'الانجليزية', 'انجليزي', 'إنجليزي'])
const ARABIC_RE = /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/g
const LATIN_RE = /[A-Za-z]/g

export function normalizeAiLanguage(value: string | null | undefined): AiLanguage | null {
  if (!value) return null
  const cleaned = value.trim().toLowerCase().replace('_', '-').split('-')[0] ?? ''
  if (AR_ALIASES.has(cleaned) || AR_ALIASES.has(value.trim())) return 'ar'
  if (EN_ALIASES.has(cleaned) || EN_ALIASES.has(value.trim().toLowerCase())) return 'en'
  return null
}

export function detectAiLanguage(text: string | null | undefined): AiLanguage | null {
  if (!text) return null
  const arabic = text.match(ARABIC_RE)?.length ?? 0
  const latin = text.match(LATIN_RE)?.length ?? 0
  if (arabic === 0 && latin === 0) return null
  if (arabic > 0 && arabic * 2 >= latin) return 'ar'
  if (latin > 0) return 'en'
  return null
}

export function isMostlyArabic(text: string): boolean {
  return detectAiLanguage(text) === 'ar'
}

export function hasExplicitAiLanguage(): boolean {
  try {
    return normalizeAiLanguage(localStorage.getItem(AI_LANGUAGE_KEY)) !== null
  } catch {
    return false
  }
}

export function getAiLanguage(preferred?: string | null): AiLanguage {
  try {
    const stored = normalizeAiLanguage(localStorage.getItem(AI_LANGUAGE_KEY))
    if (stored) return stored
  } catch {
    // storage unavailable
  }
  return normalizeAiLanguage(preferred) ?? 'ar'
}

export function setAiLanguage(language: AiLanguage): void {
  try {
    localStorage.setItem(AI_LANGUAGE_KEY, language)
  } catch {
    // storage unavailable
  }
}

export function aiWelcomeMessage(
  kind: 'student' | 'doctor' | 'file' | 'course',
  language: AiLanguage,
  title?: string,
): string {
  if (language === 'ar') {
    if (kind === 'doctor') {
      return 'مرحباً دكتور 👋 أنا مساعدك التدريسي. اطلب مني إنشاء اختبارات أو تلخيص محاضرات أو بناء مخطط مقرر.'
    }
    if (kind === 'file') {
      return `فهرستُ «${title ?? 'هذا الملف'}» — اسألني أي شيء عنه.`
    }
    if (kind === 'course') {
      return `مرحباً! أنا مدرّسك الذكي لمقرر ${title ?? 'هذه المادة'}. اسألني عن أي جزء من المحتوى.`
    }
    return 'مرحباً! 👋 أنا مدرّسك الذكي. جاهز لمساعدتك على تحقيق أهدافك اليوم. بماذا نبدأ؟'
  }

  if (kind === 'doctor') {
    return "Hi 👋 I'm your AI Teaching Assistant. Ask me to generate quizzes, summarize lectures, or outline a course."
  }
  if (kind === 'file') {
    return `I've indexed "${title ?? 'this file'}" — ask me anything about it.`
  }
  if (kind === 'course') {
    return `Hi! I'm your AI tutor for ${title ?? 'this course'}. Ask me anything about the material.`
  }
  return "Hi! 👋 I'm your AI Tutor. Ready to help you crush today's goals. What would you like to work on?"
}

export function aiUiCopy(language: AiLanguage) {
  if (language === 'ar') {
    return {
      online: '● متصل',
      placeholder: 'اسأل مساعدك أي شيء...',
      send: 'إرسال',
      tutor: 'المدرّس الذكي',
      teachingAssistant: 'المساعد التدريسي',
      askAnything: 'اسأل مدرّسك أي شيء...',
    }
  }
  return {
    online: '● Online',
    placeholder: 'Ask your tutor anything...',
    send: 'Send',
    tutor: 'AI Tutor',
    teachingAssistant: 'AI Teaching Assistant',
    askAnything: 'Ask your tutor anything...',
  }
}
