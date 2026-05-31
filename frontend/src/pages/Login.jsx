// src/pages/Login.jsx
// Supabase login. Supabase returns an access token, Zustand stores it,
// and api.js sends it as Authorization: Bearer <token> to FastAPI.

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Brain } from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { isSupabaseConfigured, supabase } from '@/lib/supabase'
import toast from 'react-hot-toast'

export default function Login() {
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading]   = useState(false)
  const [mode, setMode]         = useState('signin')
  const { setAuth }             = useAuthStore()
  const navigate                = useNavigate()

  async function handleLogin(e) {
    e.preventDefault()
    if (!email || !password) {
      toast.error('Please fill in all fields')
      return
    }

    if (!isSupabaseConfigured) {
      toast.error('Supabase frontend env is missing. Create s1/frontend/.env and restart npm run dev.')
      return
    }

    setLoading(true)
    try {
      const authCall = mode === 'signup'
        ? supabase.auth.signUp({ email, password })
        : supabase.auth.signInWithPassword({ email, password })

      const { data, error } = await authCall
      if (error) throw error

      if (!data.session?.access_token) {
        toast.success('Account created. Check your email to confirm before signing in.')
        return
      }

      setAuth(data.user, data.session.access_token)
      toast.success(mode === 'signup' ? 'Account created. Welcome!' : 'Welcome back!')
      navigate('/app/resume')
    } catch (err) {
      toast.error(err.message ?? 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#0f1117] flex items-center justify-center px-4">
      <div className="w-full max-w-sm">

        <div className="flex items-center justify-center gap-2 mb-8">
          <div className="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center">
            <Brain size={18} className="text-white" />
          </div>
          <span className="text-white font-bold text-lg" style={{ fontFamily: 'Syne, sans-serif' }}>
            AI Job Hunter
          </span>
        </div>

        <div className="card">
          <h2 className="text-white font-semibold text-xl mb-1" style={{ fontFamily: 'Syne, sans-serif' }}>
            {mode === 'signup' ? 'Create account' : 'Sign in'}
          </h2>
          <p className="text-slate-500 text-sm mb-6">
            Use your email and password to continue
          </p>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="label">Email</label>
              <input
                type="email"
                className="input"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            <div>
              <label className="label">Password</label>
              <input
                type="password"
                className="input"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full mt-2"
            >
              {loading ? 'Please wait...' : mode === 'signup' ? 'Create account' : 'Sign in'}
            </button>
          </form>

          <button
            type="button"
            onClick={() => setMode((current) => current === 'signin' ? 'signup' : 'signin')}
            className="w-full text-xs text-slate-500 hover:text-slate-300 mt-4 transition"
          >
            {mode === 'signup'
              ? 'Already have an account? Sign in'
              : 'New here? Create an account'}
          </button>
        </div>

        <p className="text-center text-xs text-slate-600 mt-6">
          Authentication is handled by Supabase.
        </p>
      </div>
    </div>
  )
}
