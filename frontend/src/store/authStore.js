// src/store/authStore.js
// ============================================
// WHY ZUSTAND?
// Zustand = lightweight global state.
// Auth state (user, token) needs to be accessible
// from ANY component without prop drilling.
// Think of it like a mini Redux but 10x simpler.
// ============================================

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useAuthStore = create(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,

      // Called after Supabase login
      setAuth: (user, token) =>
        set({ user, token, isAuthenticated: true }),

      // Called on logout or 401
      logout: () =>
        set({ user: null, token: null, isAuthenticated: false }),
    }),
    {
      name: 'auth-storage', // localStorage key
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)
