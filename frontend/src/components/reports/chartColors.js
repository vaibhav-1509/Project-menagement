import { useEffect, useState } from 'react'

// Validated categorical palette (dataviz skill reference instance) - fixed hue
// order per slot, never cycled/reassigned per-render.
export const CATEGORICAL_LIGHT = [
  '#2a78d6', // blue
  '#1baf7a', // aqua
  '#eda100', // yellow
  '#008300', // green
  '#4a3aa7', // violet
  '#e34948', // red
  '#e87ba4', // magenta
  '#eb6834', // orange
]

export const CATEGORICAL_DARK = [
  '#3987e5',
  '#199e70',
  '#c98500',
  '#008300',
  '#9085e9',
  '#e66767',
  '#d55181',
  '#d95926',
]

const ACCENT = { light: '#5b3df0', dark: '#8a72ff' }
const MUTED = { light: '#898781', dark: '#898781' }
const GRID = { light: '#e1e0d9', dark: '#2c2c2a' }

export function useIsDarkMode() {
  const [isDark, setIsDark] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches
  )
  useEffect(() => {
    const mql = window.matchMedia('(prefers-color-scheme: dark)')
    const listener = (e) => setIsDark(e.matches)
    mql.addEventListener('change', listener)
    return () => mql.removeEventListener('change', listener)
  }, [])
  return isDark
}

export function useChartTheme() {
  const isDark = useIsDarkMode()
  return {
    categorical: isDark ? CATEGORICAL_DARK : CATEGORICAL_LIGHT,
    accent: isDark ? ACCENT.dark : ACCENT.light,
    muted: isDark ? MUTED.dark : MUTED.light,
    grid: isDark ? GRID.dark : GRID.light,
  }
}
