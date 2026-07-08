import { Amplify } from 'aws-amplify'
import { fetchAuthSession, getCurrentUser } from 'aws-amplify/auth'

const userPoolId = import.meta.env.VITE_AUTH_USER_POOL_ID
const userPoolClientId = import.meta.env.VITE_AUTH_USER_POOL_CLIENT_ID

export const authConfigured = Boolean(userPoolId && userPoolClientId)

if (authConfigured) {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId,
        userPoolClientId,
      },
    },
  })
}

export type SignedInUser = Awaited<ReturnType<typeof getCurrentUser>>

export async function getAuthToken() {
  if (!authConfigured) {
    return null
  }
  try {
    const session = await fetchAuthSession()
    return session.tokens?.idToken?.toString() ?? session.tokens?.accessToken?.toString() ?? null
  } catch {
    return null
  }
}
