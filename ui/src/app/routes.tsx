import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AuthGate } from './auth'
import { ThemeProvider } from './theme'
import { DecisionConsole } from '../pages/DecisionConsole'
import { ReviewPortal } from '../pages/ReviewPortal'
import { RunDetailPage } from '../pages/RunDetailPage'
import { RunReportPage } from '../pages/RunReportPage'
import { SettingsPage } from '../pages/SettingsPage'

export function AppRoutes() {
  return (
    <ThemeProvider>
      <AuthGate>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<DecisionConsole />} />
            <Route path="/runs/:runId" element={<RunDetailPage />} />
            <Route path="/runs/:runId/report" element={<RunReportPage />} />
            <Route path="/review/:runId" element={<ReviewPortal />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthGate>
    </ThemeProvider>
  )
}
