// src/lib/api.js
// ============================================
// WHY THIS FILE EXISTS:
// All axios calls live here. No component ever
// calls fetch/axios directly.
// Benefits:
//   1. One place to change base URL
//   2. Auth token injected automatically
//   3. Error handling in one place
// ============================================

import axios from 'axios'
import { useAuthStore } from '@/store/authStore'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

// Inject JWT token into every request automatically
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Handle 401 (token expired) globally
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      useAuthStore.getState().logout()
    }
    return Promise.reject(err)
  }
)

// ---- Resume ----
export const resumeApi = {
  upload: (formData) =>
    api.post('/resume/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  getActive: () => api.get('/resume/active'),
  getAll: () => api.get('/resume/all'),
}

// ---- Job Matching ----
export const jobApi = {
  match: (data) => api.post('/job/match', data),
  getHistory: () => api.get('/job/history'),
}

// ---- Interview ----
export const interviewApi = {
  start: (data) => api.post('/interview/start', data),
  getNext: (sessionId) => api.get(`/interview/${sessionId}/next`),
  getSession: (sessionId) => api.get(`/interview/${sessionId}`),
}

// ---- Submit Answer ----
export const submitApi = {
  submit: (data) => api.post('/interview/submit', data),
}

// ---- Audio ----
export const audioApi = {
  transcribe: (formData) =>
    api.post('/audio/transcribe', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
}

// ---- Dashboard ----
export const dashboardApi = {
  getSummary: () => api.get('/dashboard/summary'),
  getHistory: () => api.get('/dashboard/history'),
}

export default api
