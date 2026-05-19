import { writable } from 'svelte/store'

const STORAGE_KEY = 'dv-theme'

function createThemeStore() {
  const stored = typeof localStorage !== 'undefined'
    ? localStorage.getItem(STORAGE_KEY)
    : null
  const prefersDark = typeof window !== 'undefined'
    ? window.matchMedia('(prefers-color-scheme: dark)').matches
    : false

  const initial = stored ? stored === 'dark' : prefersDark
  const { subscribe, set, update } = writable(initial)

  if (initial) {
    document.documentElement.classList.add('dark')
  }

  return {
    subscribe,
    toggle() {
      update(isDark => {
        const next = !isDark
        if (next) {
          document.documentElement.classList.add('dark')
          localStorage.setItem(STORAGE_KEY, 'dark')
        } else {
          document.documentElement.classList.remove('dark')
          localStorage.setItem(STORAGE_KEY, 'light')
        }
        return next
      })
    },
    set(value) {
      set(value)
      if (value) {
        document.documentElement.classList.add('dark')
        localStorage.setItem(STORAGE_KEY, 'dark')
      } else {
        document.documentElement.classList.remove('dark')
        localStorage.setItem(STORAGE_KEY, 'light')
      }
    },
  }
}

export const theme = createThemeStore()
