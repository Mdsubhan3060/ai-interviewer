// src/App.jsx
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import Layout from '@/components/common/Layout'
import Landing from '@/pages/Landing'
import Login from '@/pages/Login'
import Resume from '@/pages/Resume'
import JobMatch from '@/pages/JobMatch'
import Interview from '@/pages/Interview'
import Dashboard from '@/pages/Dashboard'

// ProtectedRoute: redirects to /login if not authenticated
function ProtectedRoute({ children }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  return isAuthenticated ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />

      {/* Protected — all inside the shared Layout (sidebar) */}
      <Route
        path="/app"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/app/resume" replace />} />
        <Route path="resume" element={<Resume />} />
        <Route path="job" element={<JobMatch />} />
        <Route path="interview" element={<Interview />} />
        <Route path="dashboard" element={<Dashboard />} />
      </Route>

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
