import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { ThemeProvider } from './theme'
import { DecisionConsole } from '../pages/DecisionConsole'
import { ReviewPortal } from '../pages/ReviewPortal'
import { RunDetailPage } from '../pages/RunDetailPage'
import { SettingsPage } from '../pages/SettingsPage'

export function AppRoutes() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<DecisionConsole />} />
          <Route path="/runs/:runId" element={<RunDetailPage />} />
          <Route path="/review/:runId" element={<ReviewPortal />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  )
}
