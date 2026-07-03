export type ThemeColor = 'cobalt' | 'violet' | 'sage'
export type ThemeMode = 'light' | 'dark'

export const themeColors: Array<{ id: ThemeColor; label: string; detail: string }> = [
  { id: 'cobalt', label: 'Cobalt', detail: 'Clear blue command surface' },
  { id: 'violet', label: 'Violet', detail: 'Purple-blue glass surface' },
  { id: 'sage', label: 'Sage', detail: 'Quiet green review surface' },
]
