// src/pages/Dashboard.jsx
// ============================================
// Shows:
//   - Overall avg score
//   - Score over time chart (recharts)
//   - Category breakdown (technical, confidence, etc.)
//   - Top weaknesses + strengths
//   - GPT-generated recommendations
// ============================================

import { useState, useEffect } from 'react'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts'
import { BarChart2, TrendingUp, AlertCircle, CheckCircle, Loader2 } from 'lucide-react'
import { dashboardApi } from '@/lib/api'

// ---- Score ring ----
function ScoreRing({ score, label }) {
  const r = 36
  const circ = 2 * Math.PI * r
  const pct = Math.min((score ?? 0) / 10, 1)
  const dash = pct * circ

  let color = '#ef4444'
  if (score >= 8) color = '#10b981'
  else if (score >= 6) color = '#f59e0b'

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width="88" height="88" viewBox="0 0 88 88">
        <circle cx="44" cy="44" r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="8" />
        <circle
          cx="44" cy="44" r={r} fill="none"
          stroke={color} strokeWidth="8"
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
          transform="rotate(-90 44 44)"
        />
        <text x="44" y="49" textAnchor="middle" fill="white" fontSize="16" fontWeight="700">
          {score != null ? score.toFixed(1) : '—'}
        </text>
      </svg>
      <span className="text-slate-500 text-xs">{label}</span>
    </div>
  )
}

export default function Dashboard() {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    dashboardApi.getSummary()
      .then(({ data }) => setSummary(data))
      .catch((err) => {
        const msg = err.response?.data?.detail ?? 'Failed to load dashboard'
        setError(msg)
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="p-8 flex items-center gap-3 text-slate-500">
        <Loader2 size={18} className="animate-spin" /> Loading dashboard...
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-8 max-w-lg">
        <div className="card border-red-500/20 text-red-400 text-sm flex items-start gap-3">
          <AlertCircle size={16} className="flex-shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      </div>
    )
  }

  if (!summary || summary.total_sessions === 0) {
    return (
      <div className="p-8 max-w-lg">
        <h1 className="text-2xl font-bold text-white mb-1" style={{ fontFamily: 'Syne, sans-serif' }}>
          Dashboard
        </h1>
        <p className="text-slate-500 text-sm mb-8">Your performance overview</p>
        <div className="card text-center py-12">
          <BarChart2 size={40} className="text-slate-600 mx-auto mb-4" />
          <p className="text-slate-400 text-sm">No sessions yet.</p>
          <p className="text-slate-600 text-xs mt-1">Complete your first mock interview to see stats here.</p>
          <a href="/app/interview" className="btn-primary inline-block mt-4 text-sm">
            Start Interview
          </a>
        </div>
      </div>
    )
  }

  // Build chart data from score_history
  const lineData = (summary.score_history ?? []).map((score, i) => ({
    session: `S${i + 1}`,
    score: Number((score ?? 0).toFixed(1)),
  }))

  // Radar data from category averages
  const radarData = [
    { subject: 'Technical',     A: summary.technical_avg ?? 0 },
    { subject: 'Confidence',    A: summary.confidence_avg ?? 0 },
    { subject: 'Communication', A: summary.communication_avg ?? 0 },
    { subject: 'Relevance',     A: summary.relevance_avg ?? 0 },
  ]

  return (
    <div className="p-8 max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white mb-1" style={{ fontFamily: 'Syne, sans-serif' }}>
          Dashboard
        </h1>
        <p className="text-slate-500 text-sm">
          {summary.total_sessions} session{summary.total_sessions !== 1 ? 's' : ''} ·{' '}
          {summary.total_questions_answered} questions answered
        </p>
      </div>

      {/* Score rings */}
      <div className="card">
        <h3 className="text-white font-semibold text-sm mb-5" style={{ fontFamily: 'Syne, sans-serif' }}>
          Category Averages
        </h3>
        <div className="flex justify-around flex-wrap gap-6">
          <ScoreRing score={summary.overall_avg}       label="Overall" />
          <ScoreRing score={summary.technical_avg}     label="Technical" />
          <ScoreRing score={summary.confidence_avg}    label="Confidence" />
          <ScoreRing score={summary.communication_avg} label="Communication" />
          <ScoreRing score={summary.relevance_avg}     label="Relevance" />
        </div>
      </div>

      {/* Score over time */}
      {lineData.length > 1 && (
        <div className="card">
          <h3 className="text-white font-semibold text-sm mb-4" style={{ fontFamily: 'Syne, sans-serif' }}>
            Score Over Time
          </h3>
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={lineData} margin={{ top: 5, right: 10, bottom: 5, left: -20 }}>
              <XAxis dataKey="session" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis domain={[0, 10]} tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: '#1a1d27', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 10, color: '#e2e8f0', fontSize: 12 }}
                cursor={{ stroke: 'rgba(255,255,255,0.08)' }}
              />
              <Line type="monotone" dataKey="score" stroke="#6366f1" strokeWidth={2} dot={{ fill: '#6366f1', r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Radar */}
      <div className="card">
        <h3 className="text-white font-semibold text-sm mb-4" style={{ fontFamily: 'Syne, sans-serif' }}>
          Skill Radar
        </h3>
        <ResponsiveContainer width="100%" height={200}>
          <RadarChart data={radarData}>
            <PolarGrid stroke="rgba(255,255,255,0.05)" />
            <PolarAngleAxis dataKey="subject" tick={{ fill: '#64748b', fontSize: 11 }} />
            <Radar dataKey="A" stroke="#6366f1" fill="#6366f1" fillOpacity={0.2} />
          </RadarChart>
        </ResponsiveContainer>
      </div>

      {/* Weaknesses + Strengths */}
      <div className="grid grid-cols-2 gap-4">
        <div className="card">
          <div className="flex items-center gap-2 mb-3">
            <AlertCircle size={14} className="text-red-400" />
            <h3 className="text-white font-semibold text-sm" style={{ fontFamily: 'Syne, sans-serif' }}>Weak Areas</h3>
          </div>
          {summary.top_weaknesses?.length > 0
            ? summary.top_weaknesses.map((w) => (
                <div key={w} className="badge-red mb-1.5 capitalize">{w.replace('_', ' ')}</div>
              ))
            : <p className="text-slate-600 text-xs">None identified yet</p>
          }
        </div>
        <div className="card">
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle size={14} className="text-emerald-400" />
            <h3 className="text-white font-semibold text-sm" style={{ fontFamily: 'Syne, sans-serif' }}>Strengths</h3>
          </div>
          {summary.top_strengths?.length > 0
            ? summary.top_strengths.map((s) => (
                <div key={s} className="badge-green mb-1.5 capitalize">{s.replace('_', ' ')}</div>
              ))
            : <p className="text-slate-600 text-xs">Keep practicing!</p>
          }
        </div>
      </div>

      {/* Recommendations */}
      {summary.recommendations?.length > 0 && (
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp size={15} className="text-indigo-400" />
            <h3 className="text-white font-semibold text-sm" style={{ fontFamily: 'Syne, sans-serif' }}>
              Recommendations
            </h3>
          </div>
          <ul className="space-y-2.5">
            {summary.recommendations.map((rec, i) => (
              <li key={i} className="text-slate-400 text-xs flex items-start gap-2 leading-relaxed">
                <span className="text-indigo-500 font-bold flex-shrink-0">{i + 1}.</span>
                {rec}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
