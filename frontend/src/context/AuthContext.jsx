import { createContext, useContext, useEffect, useState } from 'react'
import * as api from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(api.getToken())
  const [claims, setClaims] = useState(() => (token ? api.decodeJwt(token) : null))
  const [username, setUsername] = useState(api.getUsername())
  const [myRoleNames, setMyRoleNames] = useState([])
  const [rolesLoaded, setRolesLoaded] = useState(false)

  useEffect(() => {
    setClaims(token ? api.decodeJwt(token) : null)
    if (!token) {
      setMyRoleNames([])
      setRolesLoaded(true)
      return
    }
    setRolesLoaded(false)
    let cancelled = false
    api
      .getMe()
      .then((me) => !cancelled && setMyRoleNames(me.roleNames || []))
      .catch(() => !cancelled && setMyRoleNames([]))
      .finally(() => !cancelled && setRolesLoaded(true))
    return () => {
      cancelled = true
    }
  }, [token])

  async function login(user, password) {
    const data = await api.login(user, password)
    setToken(data.access_token)
    setUsername(user)
  }

  function logout() {
    api.logout()
    setToken(null)
    setUsername(null)
  }

  // client.js's request() clears storage and fires this the moment ANY API
  // call comes back 401 (expired/invalidated session) - clearing state here
  // in turn makes every ProtectedRoute re-render and redirect to /login,
  // from whatever page the user happens to be on.
  useEffect(() => {
    function handleUnauthorized() {
      setToken(null)
      setUsername(null)
    }
    window.addEventListener('pmt:unauthorized', handleUnauthorized)
    return () => window.removeEventListener('pmt:unauthorized', handleUnauthorized)
  }, [])

  // client.js's changePassword() writes a fresh token straight to
  // localStorage (to keep this session alive through a self-service password
  // change, since the backend rotates the account's session-invalidation
  // stamp as part of that call) - this re-syncs React state from it so
  // `claims`/`token` reflect the new one immediately.
  function refreshToken() {
    setToken(api.getToken())
  }

  const isAdmin = myRoleNames.includes('Admin')

  return (
    <AuthContext.Provider
      value={{ token, claims, username, myRoleNames, isAdmin, rolesLoaded, login, logout, refreshToken }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
