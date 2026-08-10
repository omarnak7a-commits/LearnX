import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import type { AuthUser } from '../types/auth'

interface AuthContextValue {
  user: AuthUser | null
  loading: boolean
  isAuthenticated: boolean
  register: (input: {
    fullName: string
    email: string
    password: string
    role: 'student' | 'doctor'
  }) => Promise<AuthUser>
  login: (input: { email: string; password: string; rememberMe: boolean }) => Promise<AuthUser>
  setUserFromAuthResponse: (user: AuthUser) => void
  logout: () => Promise<void>
  logoutAllDevices: () => Promise<void>
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => {
    try {
      const saved = localStorage.getItem('learnx_user')
      return saved ? JSON.parse(saved) : null
    } catch {
      return null
    }
  })
  const [loading, setLoading] = useState(true)
  const bootstrapped = useRef(false)

  const refreshUser = useCallback(async () => {
    try {
      const token = localStorage.getItem('learnx_access_token')
      if (!token) return
      const res = await fetch('/api/v1/auth/me', {
        headers: { Authorization: `Bearer ${token}` },
        credentials: 'include',
      })
      if (res.ok) {
        const me = await res.json()
        setUser(me)
        localStorage.setItem('learnx_user', JSON.stringify(me))
      } else if (res.status === 401 || res.status === 403) {
        localStorage.removeItem('learnx_user')
        localStorage.removeItem('learnx_access_token')
        setUser(null)
      }
    } catch {}
  }, [])

  useEffect(() => {
    if (bootstrapped.current) return
    bootstrapped.current = true
    ;(async () => {
      try {
        const token = localStorage.getItem('learnx_access_token')
        const refreshRes = await fetch('/api/v1/auth/refresh', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
          credentials: 'include',
        })
        if (refreshRes.ok) {
          const data = await refreshRes.json()
          const authUser = data.user || data
          setUser(authUser)
          localStorage.setItem('learnx_user', JSON.stringify(authUser))
          if (data.access_token) localStorage.setItem('learnx_access_token', data.access_token)
        } else {
          await refreshUser()
        }
      } catch {} finally {
        setLoading(false)
      }
    })()
  }, [refreshUser])

  const register = useCallback(
    async (input: {
      fullName: string
      email: string
      password: string
      role: 'student' | 'doctor'
    }) => {
      const res = await fetch('/api/v1/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          full_name: input.fullName,
          email: input.email,
          password: input.password,
          role: input.role,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || data.message || 'Registration failed')
      const authUser = data.user || data
      setUser(authUser)
      localStorage.setItem('learnx_user', JSON.stringify(authUser))
      if (data.access_token) localStorage.setItem('learnx_access_token', data.access_token)
      return authUser
    },
    []
  )

  const login = useCallback(
    async (input: { email: string; password: string; rememberMe: boolean }) => {
      const res = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          email: input.email,
          password: input.password,
          remember_me: input.rememberMe,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || data.message || 'Login failed')
      const authUser = data.user || data
      setUser(authUser)
      localStorage.setItem('learnx_user', JSON.stringify(authUser))
      if (data.access_token) localStorage.setItem('learnx_access_token', data.access_token)
      return authUser
    },
    []
  )

  const setUserFromAuthResponse = useCallback((nextUser: AuthUser) => {
    setUser(nextUser)
    try {
      localStorage.setItem('learnx_user', JSON.stringify(nextUser))
    } catch {}
  }, [])

  const logout = useCallback(async () => {
    try {
      await fetch('/api/v1/auth/logout', { method: 'POST', credentials: 'include' })
    } finally {
      localStorage.removeItem('learnx_user')
      localStorage.removeItem('learnx_access_token')
      setUser(null)
    }
  }, [])

  const logoutAllDevices = useCallback(async () => {
    try {
      const token = localStorage.getItem('learnx_access_token')
      await fetch('/api/v1/auth/logout-all', {
        method: 'POST',
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        credentials: 'include',
      })
    } finally {
      localStorage.removeItem('learnx_user')
      localStorage.removeItem('learnx_access_token')
      setUser(null)
    }
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      isAuthenticated: user !== null,
      register,
      login,
      setUserFromAuthResponse,
      logout,
      logoutAllDevices,
      refreshUser,
    }),
    [user, loading, register, login, setUserFromAuthResponse, logout, logoutAllDevices, refreshUser]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
