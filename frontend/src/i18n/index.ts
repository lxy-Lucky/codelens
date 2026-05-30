import { createI18n } from 'vue-i18n'
import zh from './locales/zh'
import ja from './locales/ja'
import en from './locales/en'

export type Locale = 'zh' | 'ja' | 'en'

const LS_LOCALE_KEY = 'codelens.locale'

function detectInitial(): Locale {
  // 1) localStorage 显式选择 > 2) 浏览器语言推断 > 3) 默认 zh
  const saved = localStorage.getItem(LS_LOCALE_KEY)
  if (saved === 'zh' || saved === 'ja' || saved === 'en') return saved
  const nav = (navigator.language || '').toLowerCase()
  if (nav.startsWith('ja')) return 'ja'
  if (nav.startsWith('en')) return 'en'
  return 'zh'
}

export const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: detectInitial(),
  fallbackLocale: 'en',
  messages: { zh, ja, en },
})

export function setLocale(loc: Locale) {
  i18n.global.locale.value = loc
  localStorage.setItem(LS_LOCALE_KEY, loc)
  document.documentElement.lang = loc
}

export function getLocale(): Locale {
  return i18n.global.locale.value as Locale
}

// 初始化 html lang
document.documentElement.lang = i18n.global.locale.value as string
