// src/pages/JobMatch.jsx
// ============================================
// What this page does:
//   1. User pastes a job description
//   2. Calls POST /api/v1/job/match
//   3. Shows match score + matched/missing skills
// ============================================

import { useState } from 'react'
import { Briefcase, Loader2, CheckCircle, XCircle, AlertCircle } from 'lucide-react'
import { jobApi } from '@/lib/api'
import toast from 'react-hot-toast'

function ScoreBadge({ score }) {
  const displayScore = Number.isFinite(score) ? score.toFixed(1) : '—'
  if (score >= 80) return <span className="badge-green text-lg font-bold">{displayScore}%</span>
  if (score >= 65) return <span className="badge-yellow text-lg font-bold">{displayScore}%</span>
  if (score >= 50) return <span className="badge-yellow text-lg font-bold">{displayScore}%</span>
  return <span className="badge-red text-lg font-bold">{displayScore}%</span>
}

function ScoreLabel({ score, label }) {
  if (label) return <span className="text-emerald-400 font-semibold">{label}</span>
  if (score >= 80) return <span className="text-emerald-400 font-semibold">Excellent Match 🎯</span>
  if (score >= 65) return <span className="text-yellow-400 font-semibold">Good Match ✅</span>
  if (score >= 50) return <span className="text-orange-400 font-semibold">Moderate Match 🟡</span>
  return <span className="text-red-400 font-semibold">Weak Match ❌</span>
}

function normalizeMatchResult(data) {
  const score = Number(data.score ?? data.match_score ?? 0)

  return {
    ...data,
    score,
    label: data.label,
    matched_skills: data.matched_skills ?? [],
    missing_skills: data.missing_skills ?? [],
    bonus_skills: data.bonus_skills ?? [],
  }
}

export default function JobMatch() {
  const [jobDescription, setJobDescription] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  async function handleMatch() {
    if (!jobDescription.trim()) {
      toast.error('Please paste a job description')
      return
    }
    setLoading(true)
    setResult(null)
    try {
      const { data } = await jobApi.match({ job_description: jobDescription })
      setResult(normalizeMatchResult(data))
    } catch (err) {
      const msg = err.response?.data?.detail ?? 'Match failed'
      if (msg.includes('resume')) toast.error('Upload your resume first!')
      else toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-8 max-w-3xl">
      <h1 className="text-2xl font-bold text-white mb-1" style={{ fontFamily: 'Syne, sans-serif' }}>
        Job Match
      </h1>
      <p className="text-slate-500 text-sm mb-8">
        Paste a job description to see how well your resume matches it.
      </p>

      {/* Input */}
      <div className="card mb-5">
        <label className="label">Job Description</label>
        <textarea
          className="input h-48 resize-none text-sm"
          placeholder="Paste the full job description here..."
          value={jobDescription}
          onChange={(e) => setJobDescription(e.target.value)}
        />
        <button
          onClick={handleMatch}
          disabled={loading}
          className="btn-primary mt-4 flex items-center gap-2"
        >
          {loading ? (
            <><Loader2 size={16} className="animate-spin" /> Analysing...</>
          ) : (
            <><Briefcase size={16} /> Match Resume</>
          )}
        </button>
      </div>

      {/* Results */}
      {result && (
        <div className="space-y-5">

          {/* Score */}
          <div className="card flex items-center justify-between">
            <div>
              <p className="text-slate-500 text-xs mb-1">Match Score</p>
              <ScoreLabel score={result.score} label={result.label} />
            </div>
            <ScoreBadge score={result.score} />
          </div>

          {/* Score breakdown */}
          {result.score_breakdown && (
            <div className="card">
              <h3 className="text-white font-semibold text-sm mb-4" style={{ fontFamily: 'Syne, sans-serif' }}>
                Score Breakdown
              </h3>
              <div className="space-y-3">
                {Object.entries(result.score_breakdown).map(([key, val]) => (
                  <div key={key}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-400 capitalize">{key.replace('_', ' ')}</span>
                      <span className="text-slate-300">{Math.round(val)}%</span>
                    </div>
                    <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-indigo-500 rounded-full transition-all duration-700"
                        style={{ width: `${val}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Matched skills */}
          {result.matched_skills?.length > 0 && (
            <div className="card">
              <div className="flex items-center gap-2 mb-3">
                <CheckCircle size={15} className="text-emerald-400" />
                <h3 className="text-white font-semibold text-sm" style={{ fontFamily: 'Syne, sans-serif' }}>
                  Matched Skills ({result.matched_skills.length})
                </h3>
              </div>
              <div className="flex flex-wrap gap-2">
                {result.matched_skills.map((s) => (
                  <span key={s} className="badge-green">{s}</span>
                ))}
              </div>
            </div>
          )}

          {/* Missing skills */}
          {result.missing_skills?.length > 0 && (
            <div className="card">
              <div className="flex items-center gap-2 mb-3">
                <XCircle size={15} className="text-red-400" />
                <h3 className="text-white font-semibold text-sm" style={{ fontFamily: 'Syne, sans-serif' }}>
                  Missing Skills ({result.missing_skills.length})
                </h3>
              </div>
              <div className="flex flex-wrap gap-2">
                {result.missing_skills.map((s) => (
                  <span key={s} className="badge-red">{s}</span>
                ))}
              </div>
            </div>
          )}

          {/* Recommendation */}
          {result.recommendation && (
            <div className="card border-indigo-500/20">
              <div className="flex items-start gap-3">
                <AlertCircle size={15} className="text-indigo-400 mt-0.5 flex-shrink-0" />
                <p className="text-slate-400 text-sm leading-relaxed">{result.recommendation}</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
