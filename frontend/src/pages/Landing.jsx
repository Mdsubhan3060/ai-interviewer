// src/pages/Landing.jsx
import { useNavigate } from 'react-router-dom'
import { Brain, Mic, BarChart2, Zap, ArrowRight } from 'lucide-react'

const FEATURES = [
  {
    icon: Brain,
    title: 'Resume Intelligence',
    desc: 'Upload your PDF. GPT extracts skills, experience, and education automatically.',
  },
  {
    icon: Zap,
    title: 'Job Match Score',
    desc: 'Paste any job description. Get a 0–100 match score with missing skills highlighted.',
  },
  {
    icon: Mic,
    title: 'Stress-Aware Interviewer',
    desc: 'Answer by text or audio. The interviewer adapts its tone based on your stress signals in real time.',
  },
  {
    icon: BarChart2,
    title: 'Adaptive Memory',
    desc: 'Every session is tracked. Weak areas are targeted in future interviews automatically.',
  },
]

export default function Landing() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-200 flex flex-col">

      {/* Nav */}
      <nav className="flex items-center justify-between px-8 py-5 border-b border-white/5">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
            <Brain size={16} className="text-white" />
          </div>
          <span className="font-semibold text-white" style={{ fontFamily: 'Syne, sans-serif' }}>
            AI Job Hunter
          </span>
        </div>
        <button
          onClick={() => navigate('/login')}
          className="btn-primary text-sm"
        >
          Get Started
        </button>
      </nav>

      {/* Hero */}
      <section className="flex-1 flex flex-col items-center justify-center text-center px-6 py-24">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 text-indigo-400 text-xs font-medium mb-8">
          <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 record-pulse" />
          The only mock interview that reads your stress
        </div>

        <h1
          className="text-5xl md:text-6xl font-bold text-white leading-tight mb-6 max-w-3xl"
          style={{ fontFamily: 'Syne, sans-serif' }}
        >
          Ace every interview with{' '}
          <span className="text-indigo-400">AI that adapts to you</span>
        </h1>

        <p className="text-slate-400 text-lg max-w-xl mb-10 leading-relaxed">
          Upload your resume, match it to any job, then practice with an interviewer
          that shifts its personality based on how confident you sound.
        </p>

        <button
          onClick={() => navigate('/login')}
          className="flex items-center gap-2 btn-primary text-base px-7 py-3"
        >
          Start Practicing Free
          <ArrowRight size={18} />
        </button>
      </section>

      {/* Features */}
      <section className="px-8 pb-24 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 max-w-6xl mx-auto w-full">
        {FEATURES.map(({ icon: Icon, title, desc }) => (
          <div key={title} className="card hover:border-indigo-500/30 transition-colors">
            <div className="w-9 h-9 rounded-xl bg-indigo-600/15 flex items-center justify-center mb-4">
              <Icon size={18} className="text-indigo-400" />
            </div>
            <h3 className="text-white font-semibold mb-2 text-sm" style={{ fontFamily: 'Syne, sans-serif' }}>
              {title}
            </h3>
            <p className="text-slate-500 text-xs leading-relaxed">{desc}</p>
          </div>
        ))}
      </section>
    </div>
  )
}
