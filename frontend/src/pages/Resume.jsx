// src/pages/Resume.jsx
// ============================================
// What this page does:
//   1. Drag & drop PDF upload
//   2. Calls POST /api/v1/resume/upload
//   3. Shows parsed skills, experience, education
// ============================================

import { useState, useCallback, useEffect } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, CheckCircle, Loader2, X } from 'lucide-react'
import { resumeApi } from '@/lib/api'
import toast from 'react-hot-toast'

function normalizeResume(payload) {
  const resume = payload?.resume ?? payload

  if (!resume) return null

  return {
    ...resume,
    original_filename: resume.original_filename ?? resume.filename,
    skills_extracted: resume.skills_extracted ?? resume.skills ?? [],
    experience_extracted: resume.experience_extracted ?? resume.experience ?? [],
    education_extracted: resume.education_extracted ?? resume.education ?? [],
  }
}

export default function Resume() {
  const [resume, setResume] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let ignore = false

    async function loadActiveResume() {
      try {
        const { data } = await resumeApi.getActive()
        if (!ignore) setResume(normalizeResume(data))
      } catch (err) {
        if (err.response?.status !== 404) {
          toast.error(err.response?.data?.detail ?? 'Could not load resume')
        }
      }
    }

    loadActiveResume()

    return () => {
      ignore = true
    }
  }, [])

  const onDrop = useCallback(async (acceptedFiles) => {
    const file = acceptedFiles[0]
    if (!file) return
    if (file.type !== 'application/pdf') {
      toast.error('Please upload a PDF file')
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      toast.error('File too large. Max 10MB.')
      return
    }

    setLoading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const { data } = await resumeApi.upload(formData)
      setResume(normalizeResume(data))
      toast.success('Resume parsed successfully!')
    } catch (err) {
      toast.error(err.response?.data?.detail ?? 'Upload failed')
    } finally {
      setLoading(false)
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    disabled: loading,
  })

  return (
    <div className="p-8 max-w-3xl">
      <h1 className="text-2xl font-bold text-white mb-1" style={{ fontFamily: 'Syne, sans-serif' }}>
        Resume
      </h1>
      <p className="text-slate-500 text-sm mb-8">
        Upload your PDF resume. GPT will extract your skills, experience, and education.
      </p>

      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all ${
          isDragActive
            ? 'border-indigo-500 bg-indigo-500/5'
            : 'border-white/10 hover:border-indigo-500/50 hover:bg-white/2'
        } ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center gap-3">
          {loading ? (
            <Loader2 size={36} className="text-indigo-400 animate-spin" />
          ) : (
            <Upload size={36} className="text-slate-500" />
          )}
          <p className="text-slate-400 text-sm">
            {loading
              ? 'Parsing your resume...'
              : isDragActive
              ? 'Drop it here!'
              : 'Drag & drop your PDF, or click to browse'}
          </p>
          <p className="text-slate-600 text-xs">PDF only · Max 10MB</p>
        </div>
      </div>

      {/* Parsed result */}
      {resume && !loading && (
        <div className="mt-8 space-y-5">
          {/* Header */}
          <div className="flex items-center gap-2 text-emerald-400">
            <CheckCircle size={18} />
            <span className="text-sm font-medium">
              Parsed: {resume.original_filename}
            </span>
          </div>

          {/* Experience */}
          <div className="card">
            <h3 className="text-white font-semibold text-sm mb-3" style={{ fontFamily: 'Syne, sans-serif' }}>
              Experience
            </h3>
            <p className="text-slate-300 text-sm">
              {resume.experience_label || 'Not detected'}{' '}
              {resume.experience_months ? `(${resume.experience_months} months)` : ''}
            </p>
          </div>

          {/* Skills */}
          <div className="card">
            <h3 className="text-white font-semibold text-sm mb-3" style={{ fontFamily: 'Syne, sans-serif' }}>
              Skills Extracted ({resume.skills_extracted?.length ?? 0})
            </h3>
            <div className="flex flex-wrap gap-2">
              {(resume.skills_extracted ?? []).map((skill) => (
                <span key={skill} className="badge-blue">{skill}</span>
              ))}
              {!resume.skills_extracted?.length && (
                <span className="text-slate-500 text-xs">No skills detected</span>
              )}
            </div>
          </div>

          {/* Education */}
          {resume.education_extracted?.length > 0 && (
            <div className="card">
              <h3 className="text-white font-semibold text-sm mb-3" style={{ fontFamily: 'Syne, sans-serif' }}>
                Education
              </h3>
              <div className="space-y-2">
                {resume.education_extracted.map((edu, i) => (
                  <div key={i} className="text-sm">
                    <span className="text-slate-200">{edu.degree}</span>
                    <span className="text-slate-500"> · {edu.institution}</span>
                    {edu.year && <span className="text-slate-600"> · {edu.year}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Summary */}
          {resume.summary && (
            <div className="card">
              <h3 className="text-white font-semibold text-sm mb-3" style={{ fontFamily: 'Syne, sans-serif' }}>
                Summary
              </h3>
              <p className="text-slate-400 text-sm leading-relaxed">{resume.summary}</p>
            </div>
          )}

          {/* Re-upload */}
          <button
            onClick={() => setResume(null)}
            className="btn-secondary text-sm flex items-center gap-2"
          >
            <X size={15} />
            Upload a different resume
          </button>
        </div>
      )}
    </div>
  )
}
