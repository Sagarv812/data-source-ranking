import type { ReactNode } from 'react'
import { useEffect, useMemo, useState } from 'react'

import { ThemeContext } from './theme-context'
import { themeColors, type ThemeColor, type ThemeMode } from './theme-options'

function readInitialColor(): ThemeColor {
  const storedColor = window.localStorage.getItem('source-signal-theme-color')
  if (themeColors.some((themeColor) => themeColor.id === storedColor)) {
    return storedColor as ThemeColor
  }

  const legacyTheme = window.localStorage.getItem('source-signal-theme')
  if (legacyTheme === 'sage') return 'sage'
  if (legacyTheme === 'violet' || legacyTheme === 'midnight') return 'violet'
  return 'cobalt'
}

function readInitialMode(): ThemeMode {
  const storedMode = window.localStorage.getItem('source-signal-theme-mode')
  if (storedMode === 'light' || storedMode === 'dark') return storedMode

  const legacyTheme = window.localStorage.getItem('source-signal-theme')
  return legacyTheme === 'midnight' ? 'dark' : 'light'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [color, setColor] = useState<ThemeColor>(readInitialColor)
  const [mode, setMode] = useState<ThemeMode>(readInitialMode)
  const themeKey = `${color}-${mode}` as const

  useEffect(() => {
    document.documentElement.dataset.theme = themeKey
    window.localStorage.setItem('source-signal-theme-color', color)
    window.localStorage.setItem('source-signal-theme-mode', mode)
  }, [color, mode, themeKey])

  const value = useMemo(
    () => ({
      color,
      mode,
      themeKey,
      setColor,
      setMode,
    }),
    [color, mode, themeKey],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}
