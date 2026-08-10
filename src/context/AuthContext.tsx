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
import {
  apiGetMe,
  apiLogin,
  apiLogout,
  apiLogoutAllDevices,
  apiRefreshSession,
  apiRegister,
  getAccessToken,
  setAccessToken,
} from '../lib/auth/apiClient'
import { ApiError } from '../lib/auth/apiClient'

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

  useEffect(() => {
    if (bootstrapped.current) return
    bootstrapped.current = true
    ;(async () => {
      try {
        const savedToken = localStorage.getItem('learnx_access_token')
        if (savedToken) setAccessToken(savedToken)

        const restored = await apiRefreshSession()
        if (restored) {
          setUser(restored.user)
          try {
            localStorage.setItem('learnx_user', JSON.stringify(restored.user))
            if (restored.accessToken) localStorage.setItem('learnx_access_token', restored.accessToken)
          } catch {}
        } else if (getAccessToken()) {
          try {
            const me = await apiGetMe()
            setUser(me)
            localStorage.setItem('learnx_user', JSON.stringify(me))
          } catch {}
        }
      } catch {} finally {
        setLoading(false)
      }
    })()
  }, [])

  const refreshUser = useCallback(async () => {
    try {
      const me = await apiGetMe()
      setUser(me)
      try { localStorage.setItem('learnx_user', JSON.stringify(me)) } catch {}
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        try {
          localStorage.removeItem('learnx_user')
          localStorage.removeItem('learnx_access_token')
        } catch {}
        setUser(null)
      }
    }
  }, [])

  useEffect(() => {
    if (!user) return
    const intervalId = window.setInterval(() => { void refreshUser() }, 5 * 60 * 1000)
    return () => window.clearInterval(intervalId)
  }, [user, refreshUser])

  const register = useCallback(
    async (input: {
      fullName: string
      email: string
      password: string
      role: 'student' | 'doctor'
    }) => {
      const result = await apiRegister(input)
      setUser(result.user)
      try {
        localStorage.setItem('learnx_user', JSON.stringify(result.user))
        if (result.accessToken) localStorage.setItem('learnx_access_token', result.accessToken)
      } catch {}
      return result.user
    },
    []
  )

  const login = useCallback(
    async (input: { email: string; password: string; rememberMe: boolean }) => {
      const result = await apiLogin(input)
      setUser(result.user)
      try {
        localStorage.setItem('learnx_user', JSON.stringify(result.user))
        if (result.accessToken) localStorage.setItem('learnx_access_token', result.accessToken)
      } catch {}
      return result.user
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
      await apiLogout()
    } finally {
      try {
        localStorage.removeItem('learnx_user')
        localStorage.removeItem('learnx_access_token')
      } catch {}
      setUser(null)
    }
  }, [])

  const logoutAllDevices = useCallback(async () => {
    try {
      await apiLogoutAllDevices()
    } finally {
      try {
        localStorage.removeItem('learnx_user')
        localStorage.removeItem('learnx_access_token')
      } catch {}
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
