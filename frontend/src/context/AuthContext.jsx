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

  const isAdmin = myRoleNames.includes('Admin')

  return (
    <AuthContext.Provider value={{ token, claims, username, myRoleNames, isAdmin, rolesLoaded, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
