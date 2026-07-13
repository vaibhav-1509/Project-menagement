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

// Dark UI everywhere (see index.css) - no light variant is ever shown, so
// these no longer need to react to OS/browser preference.
export function useIsDarkMode() {
  return true
}

export function useChartTheme() {
  return {
    categorical: CATEGORICAL_DARK,
    accent: ACCENT.dark,
    muted: MUTED.dark,
    grid: GRID.dark,
  }
}
