// src/components/common/Layout.jsx
// ============================================
// Shared layout wrapping all protected pages.
// Sidebar on left, page content on right.
// Uses React Router's <Outlet /> to render child pages.
// ============================================

import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import {
  FileText, Briefcase, Mic, BarChart2, LogOut, Brain,
} from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import toast from 'react-hot-toast'

const NAV = [
  { to: '/app/resume',    icon: FileText,  label: 'Resume' },
  { to: '/app/job',       icon: Briefcase, label: 'Job Match' },
  { to: '/app/interview', icon: Mic,       label: 'Interview' },
  { to: '/app/dashboard', icon: BarChart2, label: 'Dashboard' },
]

export default function Layout() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    toast.success('Logged out')
    navigate('/')
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[#0f1117]">
      {/* ---- Sidebar ---- */}
      <aside className="w-60 flex-shrink-0 flex flex-col bg-[#13151f] border-r border-white/5">

        {/* Logo */}
        <div className="flex items-center gap-2.5 px-5 py-5 border-b border-white/5">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
            <Brain size={16} className="text-white" />
          </div>
          <span className="font-display font-700 text-white text-sm leading-tight">
            AI Job<br />Hunter
          </span>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 ${
                  isActive
                    ? 'bg-indigo-600/20 text-indigo-400'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                }`
              }
            >
              <Icon size={17} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* User + logout */}
        <div className="px-3 py-4 border-t border-white/5">
          <div className="flex items-center gap-3 px-3 py-2 mb-1">
            <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center text-xs font-bold text-white">
              {user?.email?.[0]?.toUpperCase() ?? 'U'}
            </div>
            <span className="text-xs text-slate-400 truncate flex-1">
              {user?.email ?? 'user@email.com'}
            </span>
          </div>
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-all"
          >
            <LogOut size={16} />
            Logout
          </button>
        </div>
      </aside>

      {/* ---- Main content ---- */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
