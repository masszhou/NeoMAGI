import { create } from "zustand"

const TOKEN_KEY = "neomagi_auth_token"
const API_BASE = ""  // same origin

interface AuthState {
  token: string | null
  principalId: string | null
  principalName: string | null
  authRequired: boolean | null  // null = not yet checked
  loading: boolean

  checkAuthStatus: () => Promise<void>
  login: (password: string) => Promise<{ ok: boolean; error?: string }>
  logout: () => void
  getToken: () => string | null
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: localStorage.getItem(TOKEN_KEY),
  principalId: null,
  principalName: null,
  authRequired: null,
  loading: false,

  checkAuthStatus: async () => {
    try {
      const resp = await fetch(`${API_BASE}/auth/status`)
      const data = await resp.json()
      set({ authRequired: data.auth_required ?? false })
    } catch {
      // If status check fails, assume no-auth
      set({ authRequired: false })
    }
  },

  login: async (password: string) => {
    set({ loading: true })
    try {
      const resp = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      })
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}))
        const code = data?.error?.code ?? data?.detail ?? "AUTH_FAILED"
        set({ loading: false })
        return { ok: false, error: code }
      }
      const data = await resp.json()
      localStorage.setItem(TOKEN_KEY, data.token)
      set({
        token: data.token,
        principalId: data.principal_id,
        principalName: data.name,
        loading: false,
      })
      return { ok: true }
    } catch {
      set({ loading: false })
      return { ok: false, error: "NETWORK_ERROR" }
    }
  },

  logout: () => {
    localStorage.removeItem(TOKEN_KEY)
    set({ token: null, principalId: null, principalName: null })
  },

  getToken: () => get().token,
}))
