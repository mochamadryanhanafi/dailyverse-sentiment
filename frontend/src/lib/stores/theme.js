import { writable } from 'svelte/store'

const STORAGE_KEY = 'dv-theme-mode'
const PALETTE_STORAGE_KEY = 'dv-theme-palette'

export const themePalettes = [
  { id: 'academic-blue', label: 'Academic Blue', swatch: '#2563eb' },
  { id: 'economic-green', label: 'Economic Green', swatch: '#059669' },
  { id: 'newsroom-red', label: 'Newsroom Red', swatch: '#dc2626' },
  { id: 'policy-navy', label: 'Policy Navy', swatch: '#1d4ed8' },
  { id: 'ml-cyan', label: 'ML Lab Cyan', swatch: '#0891b2' },
  { id: 'indonesia', label: 'Indonesia', swatch: '#e11d48' },
]

const DEFAULT_PALETTE = 'academic-blue'

function applyTheme({ isDark, palette }) {
  if (typeof document === 'undefined') return

  document.documentElement.classList.toggle('dark', isDark)
  document.documentElement.dataset.theme = palette || DEFAULT_PALETTE
}

function createThemeStore() {
  const storedMode = typeof localStorage !== 'undefined'
    ? localStorage.getItem(STORAGE_KEY)
    : null
  const storedPalette = typeof localStorage !== 'undefined'
    ? localStorage.getItem(PALETTE_STORAGE_KEY)
    : null
  const prefersDark = typeof window !== 'undefined'
    ? window.matchMedia('(prefers-color-scheme: dark)').matches
    : false

  const initial = {
    isDark: storedMode ? storedMode === 'dark' : prefersDark,
    palette: themePalettes.some(p => p.id === storedPalette) ? storedPalette : DEFAULT_PALETTE,
  }
  const { subscribe, set, update } = writable(initial)

  applyTheme(initial)

  return {
    subscribe,
    toggle() {
      update(current => {
        const next = { ...current, isDark: !current.isDark }
        applyTheme(next)
        localStorage.setItem(STORAGE_KEY, next.isDark ? 'dark' : 'light')
        return next
      })
    },
    setMode(isDark) {
      update(current => {
        const next = { ...current, isDark }
        applyTheme(next)
        localStorage.setItem(STORAGE_KEY, next.isDark ? 'dark' : 'light')
        return next
      })
    },
    setPalette(palette) {
      update(current => {
        const next = { ...current, palette }
        applyTheme(next)
        localStorage.setItem(PALETTE_STORAGE_KEY, palette)
        return next
      })
    },
    set(value) {
      const next = typeof value === 'boolean'
        ? { ...initial, isDark: value }
        : { ...initial, ...value }
      applyTheme(next)
      localStorage.setItem(STORAGE_KEY, next.isDark ? 'dark' : 'light')
      localStorage.setItem(PALETTE_STORAGE_KEY, next.palette)
      set(next)
    },
  }
}

export const theme = createThemeStore()
