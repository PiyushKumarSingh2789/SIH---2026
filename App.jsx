import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import ProtectedRoute from './auth/ProtectedRoute'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import RiskQueuePage from './pages/RiskQueuePage'
import ProjectProfilePage from './pages/ProjectProfilePage'
import ProjectExplorerPage from './pages/ProjectExplorerPage'
import PortfolioAnalyticsPage from './pages/PortfolioAnalyticsPage'
import CompliancePage from './pages/CompliancePage'
import MapPage from './pages/MapPage'
import ImportPage from './pages/ImportPage'
import CasesListPage from './pages/CasesListPage'
import CaseDetailPage from './pages/CaseDetailPage'
import AuditTrailPage from './pages/AuditTrailPage'
import InvestigationBriefPage from './pages/InvestigationBriefPage'

function Shell({ children }) {
  return (
    <ProtectedRoute>
      <Layout>{children}</Layout>
    </ProtectedRoute>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/dashboard" element={<Shell><DashboardPage /></Shell>} />
          <Route path="/queue" element={<Shell><RiskQueuePage /></Shell>} />
          <Route path="/analytics" element={<Shell><PortfolioAnalyticsPage /></Shell>} />
          <Route path="/projects" element={<Shell><ProjectExplorerPage /></Shell>} />
          <Route path="/projects/:projectId" element={<Shell><ProjectProfilePage /></Shell>} />
          <Route path="/map" element={<Shell><MapPage /></Shell>} />
          <Route path="/import" element={<Shell><ImportPage /></Shell>} />
          <Route path="/cases" element={<Shell><CasesListPage /></Shell>} />
          <Route path="/cases/:caseId" element={<Shell><CaseDetailPage /></Shell>} />
          <Route path="/compliance" element={<Shell><CompliancePage /></Shell>} />
          <Route path="/audit" element={<Shell><AuditTrailPage /></Shell>} />
          {/* Standalone, no sidebar chrome -- this is a print/share-friendly document, not an app screen. */}
          <Route
            path="/cases/:caseId/brief"
            element={
              <ProtectedRoute>
                <InvestigationBriefPage />
              </ProtectedRoute>
            }
          />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
