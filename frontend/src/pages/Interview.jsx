// src/pages/Interview.jsx
// ============================================
// The most complex page. Handles:
//   1. Start session (pick role + job desc)
//   2. Display question one by one
//   3. Text OR audio answer
//   4. Show evaluation feedback
//   5. Show stress score + persona shift
//   6. Advance to next question
// ============================================

import { useState, useRef } from 'react'
import {
  Mic, MicOff, Send, ChevronRight, RotateCcw,
  Loader2, CheckCircle, AlertCircle, TrendingUp,
} from 'lucide-react'
import { interviewApi, submitApi, audioApi } from '@/lib/api'
import toast from 'react-hot-toast'

// Persona badge colours
const PERSONA_STYLE = {
  challenger:  { label: 'Challenger 🔥',   cls: 'badge-red' },
  neutral:     { label: 'Neutral 🎯',       cls: 'badge-blue' },
  prober:      { label: 'Prober 🔍',        cls: 'badge-yellow' },
  supportive:  { label: 'Supportive 💙',    cls: 'badge-green' },
}

// Score colour
function scoreColor(s) {
  if (s >= 8) return 'text-emerald-400'
  if (s >= 6) return 'text-yellow-400'
  return 'text-red-400'
}

// ---- Setup Form ----
function SetupForm({ onStart, loading }) {
  const [role, setRole] = useState('')
  const [jobDesc, setJobDesc] = useState('')

  function handleSubmit(e) {
    e.preventDefault()
    if (!role.trim()) { toast.error('Please enter a target role'); return }
    onStart({ role, job_description: jobDesc || null })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5 max-w-lg">
      <div>
        <label className="label">Target Role *</label>
        <input
          className="input"
          placeholder="e.g. Software Engineer, Data Scientist"
          value={role}
          onChange={(e) => setRole(e.target.value)}
        />
      </div>
      <div>
        <label className="label">Job Description (optional — improves question relevance)</label>
        <textarea
          className="input h-32 resize-none text-sm"
          placeholder="Paste the job description here..."
          value={jobDesc}
          onChange={(e) => setJobDesc(e.target.value)}
        />
      </div>
      <button type="submit" disabled={loading} className="btn-primary flex items-center gap-2">
        {loading ? <><Loader2 size={16} className="animate-spin" /> Generating questions...</> : 'Start Interview'}
      </button>
    </form>
  )
}

// ---- Evaluation Card ----
function EvalCard({ evaluation, onNext, isLast }) {
  if (!evaluation) return null
  const scores = evaluation.scores ?? {}
  const overall_score = evaluation.overall_score
  const relevance_score = evaluation.relevance_score ?? scores.relevance
  const clarity_score = evaluation.clarity_score ?? scores.clarity
  const confidence_score = evaluation.confidence_score ?? scores.confidence
  const technical_score = evaluation.technical_score ?? scores.technical
  const {
    strengths,
    weaknesses,
    ideal_answer,
    stress_score,
  } = evaluation
  const persona = evaluation.persona ?? evaluation.interviewer_persona

  const personaInfo = PERSONA_STYLE[persona] ?? PERSONA_STYLE.neutral

  return (
    <div className="space-y-4 mt-6">
      {/* Scores */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-white font-semibold text-sm" style={{ fontFamily: 'Syne, sans-serif' }}>
            Evaluation
          </h3>
          <span className={`text-2xl font-bold ${scoreColor(overall_score)}`}>
            {overall_score}/10
          </span>
        </div>
        <div className="grid grid-cols-2 gap-3 text-xs">
          {[
            ['Relevance',   relevance_score],
            ['Clarity',     clarity_score],
            ['Confidence',  confidence_score],
            ['Technical',   technical_score],
          ].map(([label, val]) => (
            <div key={label} className="flex justify-between">
              <span className="text-slate-500">{label}</span>
              <span className={scoreColor(val)}>{val}/10</span>
            </div>
          ))}
        </div>
      </div>

      {/* Stress + Persona */}
      {stress_score !== undefined && (
        <div className="card flex items-center justify-between">
          <div>
            <p className="text-slate-500 text-xs mb-1">Stress Signal</p>
            <p className="text-slate-200 text-sm font-medium">{stress_score}/10</p>
          </div>
          <div className="text-right">
            <p className="text-slate-500 text-xs mb-1">Interviewer Mode</p>
            <span className={personaInfo.cls}>{personaInfo.label}</span>
          </div>
        </div>
      )}

      {/* Strengths */}
      {strengths?.length > 0 && (
        <div className="card">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle size={14} className="text-emerald-400" />
            <span className="text-white text-sm font-semibold" style={{ fontFamily: 'Syne, sans-serif' }}>Strengths</span>
          </div>
          <ul className="space-y-1">
            {strengths.map((s, i) => <li key={i} className="text-slate-400 text-xs">• {s}</li>)}
          </ul>
        </div>
      )}

      {/* Weaknesses */}
      {weaknesses?.length > 0 && (
        <div className="card">
          <div className="flex items-center gap-2 mb-2">
            <AlertCircle size={14} className="text-red-400" />
            <span className="text-white text-sm font-semibold" style={{ fontFamily: 'Syne, sans-serif' }}>Areas to Improve</span>
          </div>
          <ul className="space-y-1">
            {weaknesses.map((w, i) => <li key={i} className="text-slate-400 text-xs">• {w}</li>)}
          </ul>
        </div>
      )}

      {/* Ideal answer */}
      {ideal_answer && (
        <div className="card border-indigo-500/20">
          <p className="text-indigo-400 text-xs font-semibold mb-2">Ideal Answer</p>
          <p className="text-slate-400 text-xs leading-relaxed">{ideal_answer}</p>
        </div>
      )}

      {/* Next */}
      <button onClick={onNext} className="btn-primary flex items-center gap-2 w-full justify-center">
        {isLast ? (
          <><CheckCircle size={16} /> Finish Interview</>
        ) : (
          <>Next Question <ChevronRight size={16} /></>
        )}
      </button>
    </div>
  )
}

// ---- Main Page ----
export default function Interview() {
  const [phase, setPhase]       = useState('setup')   // setup | interview | done
  const [session, setSession]   = useState(null)
  const [question, setQuestion] = useState(null)
  const [answer, setAnswer]     = useState('')
  const [evaluation, setEval]   = useState(null)
  const [loading, setLoading]   = useState(false)
  const [recording, setRecording] = useState(false)
  const [inputMode, setInputMode] = useState('text')   // text | audio
  const [latencyStart, setLatencyStart] = useState(null)

  const mediaRef  = useRef(null)
  const chunksRef = useRef([])

  // ---- Start Session ----
  async function handleStart(formData) {
    setLoading(true)
    try {
      const { data } = await interviewApi.start(formData)
      setSession(data.session)
      setQuestion(data.first_question)
      setLatencyStart(Date.now())
      setPhase('interview')
    } catch (err) {
      toast.error(err.response?.data?.detail ?? 'Could not start interview')
    } finally {
      setLoading(false)
    }
  }

  // ---- Submit Text Answer ----
  async function handleTextSubmit() {
    if (!answer.trim()) { toast.error('Please type an answer'); return }
    const latency = latencyStart ? Date.now() - latencyStart : 0
    setLoading(true)
    try {
      const { data } = await submitApi.submit({
        session_id: session.id,
        question_number: question.number,
        answer_text: answer,
        latency_ms: latency,
      })
      setEval(data)
      setSession((prev) => prev ? {
        ...prev,
        questions_answered: data.questions_answered,
        status: data.session_complete ? 'completed' : prev.status,
        overall_score: data.session_overall_score ?? prev.overall_score,
      } : prev)
    } catch (err) {
      toast.error(err.response?.data?.detail ?? 'Submission failed')
    } finally {
      setLoading(false)
    }
  }

  // ---- Audio Recording ----
  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr = new MediaRecorder(stream)
      mediaRef.current = mr
      chunksRef.current = []
      mr.ondataavailable = (e) => chunksRef.current.push(e.data)
      mr.start()
      setRecording(true)
      setLatencyStart(Date.now())
    } catch {
      toast.error('Microphone access denied')
    }
  }

  async function stopRecording() {
    return new Promise((resolve) => {
      const mr = mediaRef.current
      if (!mr) return resolve(null)
      mr.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        const formData = new FormData()
        formData.append('audio', blob, 'answer.webm')
        formData.append('question_category', question?.category ?? 'technical')
        try {
          const { data } = await audioApi.transcribe(formData)
          resolve(data)
        } catch {
          toast.error('Transcription failed')
          resolve(null)
        }
        mr.stream.getTracks().forEach((t) => t.stop())
      }
      mr.stop()
      setRecording(false)
    })
  }

  async function handleAudioSubmit() {
    setLoading(true)
    try {
      const transcribed = await stopRecording()
      if (!transcribed) return

      const { data } = await submitApi.submit({
        session_id: session.id,
        question_number: question.number,
        answer_text: transcribed.transcription,
        is_audio: true,
        stress_score: transcribed.stress_score,
        stress_signals: transcribed.stress_signals,
        persona: transcribed.persona,
        latency_ms: latencyStart ? Date.now() - latencyStart : 0,
      })
      setAnswer(transcribed.transcription)
      setEval(data)
      setSession((prev) => prev ? {
        ...prev,
        questions_answered: data.questions_answered,
        status: data.session_complete ? 'completed' : prev.status,
        overall_score: data.session_overall_score ?? prev.overall_score,
      } : prev)
    } catch (err) {
      toast.error('Submission failed')
    } finally {
      setLoading(false)
    }
  }

  // ---- Next Question ----
  async function handleNext() {
    setLoading(true)
    setEval(null)
    setAnswer('')
    try {
      const { data } = await interviewApi.getNext(session.id)
      if (data.status === 'completed') {
        setSession((prev) => prev ? { ...prev, status: 'completed' } : prev)
        setPhase('done')
      } else {
        setQuestion(data)
        setSession((prev) => prev ? {
          ...prev,
          current_question_index: data.current_question_index ?? Math.max((data.number ?? 1) - 1, 0),
          status: data.status ?? prev.status,
        } : prev)
        setLatencyStart(Date.now())
      }
    } catch {
      toast.error('Could not load next question')
    } finally {
      setLoading(false)
    }
  }

  // ---- Render ----
  return (
    <div className="p-8 max-w-2xl">
      <h1 className="text-2xl font-bold text-white mb-1" style={{ fontFamily: 'Syne, sans-serif' }}>
        Mock Interview
      </h1>
      <p className="text-slate-500 text-sm mb-8">
        Answer questions by text or audio. The interviewer adapts to your stress signals.
      </p>

      {/* Setup */}
      {phase === 'setup' && (
        <SetupForm onStart={handleStart} loading={loading} />
      )}

      {/* Interview */}
      {phase === 'interview' && question && (
        <div>
          {/* Progress */}
          <div className="flex items-center justify-between mb-5 text-xs text-slate-500">
            <span>Question {question.number ?? ((session?.current_question_index ?? 0) + 1)} of {session?.total_questions ?? 10}</span>
            <span className="badge-blue capitalize">{question.category}</span>
          </div>

          {/* Question */}
          <div className="card mb-5 border-indigo-500/20">
            <p className="text-white text-base leading-relaxed">{question.question_text}</p>
          </div>

          {/* Input mode toggle */}
          {!evaluation && (
            <div className="flex gap-2 mb-4">
              <button
                onClick={() => setInputMode('text')}
                className={`text-xs px-3 py-1.5 rounded-lg transition ${inputMode === 'text' ? 'bg-indigo-600 text-white' : 'btn-secondary'}`}
              >
                Text
              </button>
              <button
                onClick={() => setInputMode('audio')}
                className={`text-xs px-3 py-1.5 rounded-lg transition ${inputMode === 'audio' ? 'bg-indigo-600 text-white' : 'btn-secondary'}`}
              >
                Audio
              </button>
            </div>
          )}

          {/* Text answer */}
          {!evaluation && inputMode === 'text' && (
            <div className="space-y-3">
              <textarea
                className="input h-36 resize-none text-sm"
                placeholder="Type your answer here..."
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                disabled={loading}
              />
              <button
                onClick={handleTextSubmit}
                disabled={loading}
                className="btn-primary flex items-center gap-2"
              >
                {loading ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
                {loading ? 'Evaluating...' : 'Submit Answer'}
              </button>
            </div>
          )}

          {/* Audio answer */}
          {!evaluation && inputMode === 'audio' && (
            <div className="space-y-3">
              {answer && (
                <div className="card text-xs text-slate-400 italic">
                  <span className="text-slate-500 not-italic font-medium">Transcribed: </span>
                  {answer}
                </div>
              )}
              <div className="flex gap-3">
                {!recording ? (
                  <button
                    onClick={startRecording}
                    disabled={loading}
                    className="btn-primary flex items-center gap-2"
                  >
                    <Mic size={15} /> Start Recording
                  </button>
                ) : (
                  <button
                    onClick={handleAudioSubmit}
                    disabled={loading}
                    className="bg-red-600 hover:bg-red-500 text-white font-semibold px-5 py-2.5 rounded-xl flex items-center gap-2 transition"
                  >
                    <MicOff size={15} className="record-pulse" />
                    {loading ? 'Processing...' : 'Stop & Submit'}
                  </button>
                )}
              </div>
              {recording && (
                <p className="text-xs text-red-400 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-red-400 record-pulse" />
                  Recording... speak clearly
                </p>
              )}
            </div>
          )}

          {/* Evaluation */}
          <EvalCard
            evaluation={evaluation}
            onNext={handleNext}
            isLast={(question?.number ?? 1) >= (session?.total_questions ?? 10)}
          />
        </div>
      )}

      {/* Done */}
      {phase === 'done' && (
        <div className="card text-center space-y-4">
          <TrendingUp size={40} className="text-emerald-400 mx-auto" />
          <h2 className="text-white font-bold text-xl" style={{ fontFamily: 'Syne, sans-serif' }}>
            Interview Complete!
          </h2>
          <p className="text-slate-400 text-sm">
            Your scores have been saved. Check the Dashboard to see your performance and weak areas.
          </p>
          <div className="flex gap-3 justify-center">
            <button
              onClick={() => { setPhase('setup'); setSession(null); setQuestion(null); setEval(null); setAnswer('') }}
              className="btn-secondary flex items-center gap-2 text-sm"
            >
              <RotateCcw size={15} /> Practice Again
            </button>
            <a href="/app/dashboard" className="btn-primary text-sm">
              View Dashboard
            </a>
          </div>
        </div>
      )}
    </div>
  )
}
