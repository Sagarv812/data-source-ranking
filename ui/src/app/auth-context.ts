import { createContext, useContext } from 'react'

import { authConfigured, type SignedInUser } from './auth-client'

export type AuthContextValue = {
  configured: boolean
  displayName: string
  signOut: () => Promise<void>
  user: SignedInUser | null
}

export const AuthContext = createContext<AuthContextValue>({
  configured: authConfigured,
  displayName: 'Local',
  signOut: async () => undefined,
  user: null,
})

export function useAuth() {
  return useContext(AuthContext)
}
