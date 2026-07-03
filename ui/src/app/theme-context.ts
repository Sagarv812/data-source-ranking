import { createContext, useContext } from 'react'

import type { ThemeColor, ThemeMode } from './theme-options'

export type ThemeContextValue = {
  color: ThemeColor
  mode: ThemeMode
  themeKey: `${ThemeColor}-${ThemeMode}`
  setColor: (color: ThemeColor) => void
  setMode: (mode: ThemeMode) => void
}

export const ThemeContext = createContext<ThemeContextValue | null>(null)

export function useTheme() {
  const value = useContext(ThemeContext)
  if (!value) {
    throw new Error('useTheme must be used inside ThemeProvider')
  }
  return value
}
