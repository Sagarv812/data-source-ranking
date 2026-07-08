import {
  confirmSignIn as amplifyConfirmSignIn,
  getCurrentUser,
  signIn as amplifySignIn,
  signOut as amplifySignOut,
} from 'aws-amplify/auth'
import { LogIn, ShieldCheck } from 'lucide-react'
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type ReactNode,
} from 'react'

import { authConfigured, type SignedInUser } from './auth-client'
import { AuthContext, type AuthContextValue } from './auth-context'
import { queryClient } from './queryClient'

type AuthPhase = 'checking' | 'signedIn' | 'signedOut'
type SignInMode = 'password' | 'newPassword'

export function AuthGate({ children }: { children: ReactNode }) {
  const [phase, setPhase] = useState<AuthPhase>(authConfigured ? 'checking' : 'signedIn')
  const [user, setUser] = useState<SignedInUser | null>(null)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [mode, setMode] = useState<SignInMode>('password')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const refreshUser = useCallback(async () => {
    const currentUser = await getCurrentUser()
    setUser(currentUser)
    setPhase('signedIn')
    setError(null)
  }, [])

  useEffect(() => {
    if (!authConfigured) {
      return
    }

    let mounted = true
    getCurrentUser()
      .then((currentUser) => {
        if (mounted) {
          setUser(currentUser)
          setPhase('signedIn')
        }
      })
      .catch(() => {
        if (mounted) {
          setPhase('signedOut')
        }
      })

    return () => {
      mounted = false
    }
  }, [])

  const handleSignIn = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      if (mode === 'newPassword') {
        const result = await amplifyConfirmSignIn({ challengeResponse: newPassword })
        if (result.nextStep.signInStep === 'DONE') {
          await refreshUser()
        } else {
          setError(`Additional sign-in step required: ${result.nextStep.signInStep}`)
        }
        return
      }

      const result = await amplifySignIn({ username: email.trim(), password })
      if (result.nextStep.signInStep === 'DONE') {
        await refreshUser()
      } else if (result.nextStep.signInStep === 'CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED') {
        setMode('newPassword')
      } else {
        setError(`Additional sign-in step required: ${result.nextStep.signInStep}`)
      }
    } catch (caught) {
      setError(errorMessage(caught))
    } finally {
      setSubmitting(false)
    }
  }

  const handleSignOut = useCallback(async () => {
    await amplifySignOut()
    queryClient.clear()
    setUser(null)
    setPhase('signedOut')
    setPassword('')
    setNewPassword('')
    setMode('password')
  }, [])

  const contextValue = useMemo<AuthContextValue>(
    () => ({
      configured: authConfigured,
      displayName: user ? displayName(user) : 'Local',
      signOut: handleSignOut,
      user,
    }),
    [handleSignOut, user],
  )

  if (!authConfigured) {
    return <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>
  }

  if (phase === 'checking') {
    return <AuthFrame title="Source Signal" label="Checking session" />
  }

  if (phase === 'signedOut') {
    return (
      <AuthFrame title="Source Signal" label={mode === 'newPassword' ? 'Set new password' : 'Sign in'}>
        <form className="mt-6 space-y-4" onSubmit={(event) => void handleSignIn(event)}>
          {mode === 'password' ? (
            <>
              <label className="block">
                <span className="field-label">Email</span>
                <input
                  autoComplete="email"
                  className="field mt-2"
                  onChange={(event) => setEmail(event.target.value)}
                  required
                  type="email"
                  value={email}
                />
              </label>
              <label className="block">
                <span className="field-label">Password</span>
                <input
                  autoComplete="current-password"
                  className="field mt-2"
                  onChange={(event) => setPassword(event.target.value)}
                  required
                  type="password"
                  value={password}
                />
              </label>
            </>
          ) : (
            <label className="block">
              <span className="field-label">New password</span>
              <input
                autoComplete="new-password"
                className="field mt-2"
                minLength={8}
                onChange={(event) => setNewPassword(event.target.value)}
                required
                type="password"
                value={newPassword}
              />
            </label>
          )}
          {error ? (
            <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-700">
              {error}
            </p>
          ) : null}
          <button className="button-primary w-full" disabled={submitting} type="submit">
            <LogIn size={17} />
            {submitting ? 'Working' : mode === 'newPassword' ? 'Save password' : 'Sign in'}
          </button>
        </form>
      </AuthFrame>
    )
  }

  return <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>
}

function AuthFrame({
  children,
  label,
  title,
}: {
  children?: ReactNode
  label: string
  title: string
}) {
  return (
    <div className="grid min-h-dvh place-items-center bg-[var(--app-background)] px-4 py-8 text-ink">
      <section className="workspace-surface w-full max-w-sm p-6">
        <div className="flex items-center gap-3">
          <span className="grid size-12 place-items-center rounded-lg bg-primary text-white shadow-soft">
            <ShieldCheck size={24} strokeWidth={2.2} />
          </span>
          <div>
            <p className="text-xl font-bold leading-tight">{title}</p>
            <p className="mt-1 text-sm font-semibold text-ink-muted">{label}</p>
          </div>
        </div>
        {children}
      </section>
    </div>
  )
}

function displayName(user: SignedInUser) {
  return user.signInDetails?.loginId ?? user.username ?? 'Signed in'
}

function errorMessage(caught: unknown) {
  if (caught instanceof Error && caught.message) {
    return caught.message
  }
  return 'Sign-in failed.'
}
