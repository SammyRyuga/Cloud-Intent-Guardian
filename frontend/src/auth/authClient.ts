/**
 * Auth Client (INV-10: Tokens handled by Amplify Auth only)
 * The ONLY file importing aws-amplify
 */
import { Amplify } from 'aws-amplify';
import { getCurrentUser, fetchAuthSession, signInWithRedirect, signOut as amplifySignOut } from 'aws-amplify/auth';
import { env } from '@/config/env';
import 'aws-amplify/auth/enable-oauth-listener';

// Configure Amplify
if (!env.useMocks && !env.localApi) {
  try {
    Amplify.configure({
      Auth: {
        Cognito: {
          userPoolId: env.cognitoUserPoolId,
          userPoolClientId: env.cognitoClientId,
          loginWith: {
            oauth: {
              domain: env.cognitoDomain,
              scopes: ['openid', 'email', 'profile'],
              redirectSignIn: [env.redirectSignIn],
              redirectSignOut: [env.redirectSignOut],
              responseType: 'code',
            },
          },
        },
      },
    });
  } catch (e) {
    console.error('Amplify configure error:', e);
  }
}

export interface UserProfile {
  username: string;
  email?: string;
  name?: string;
}
let sessionExpired: (() => void) | undefined;

export const authClient = {
  async getAccessToken(forceRefresh = false): Promise<string | null> {
    if (env.localApi) return null;
    if (env.useMocks) {
      return 'mock-access-token-cig';
    }
    try {
      const session = await fetchAuthSession({forceRefresh});
      return session.tokens?.accessToken?.toString() || null;
    } catch {
      return null;
    }
  },

  onSessionExpired(listener: () => void): () => void {
    sessionExpired = listener;
    return () => { if (sessionExpired === listener) sessionExpired = undefined; };
  },

  async clearExpiredSession(): Promise<void> {
    try { await amplifySignOut(); } catch { /* The expired session is still cleared from UI state. */ }
    sessionExpired?.();
  },

  async getCurrentUser(): Promise<UserProfile | null> {
    if (env.localApi) return sessionStorage.getItem('cig_local_signed_out') === 'true' ? null : { username: 'Local developer' };
    if (env.useMocks) {
      const stored = sessionStorage.getItem('cig_mock_user');
      if (stored === 'false') return null;
      return {
        username: 'aritra',
        email: 'aritra@example.com',
        name: 'Aritra Ghosh',
      };
    }
    try {
      const user = await getCurrentUser();
      const session = await fetchAuthSession();
      const idPayload = session.tokens?.idToken?.payload;
      return {
        username: user.username,
        email: idPayload?.email as string | undefined,
        name: (idPayload?.name as string | undefined) || user.username,
      };
    } catch {
      return null;
    }
  },

  async signIn(): Promise<void> {
    if (env.localApi) { sessionStorage.removeItem('cig_local_signed_out'); return; }
    if (env.useMocks) {
      sessionStorage.setItem('cig_mock_user', 'true');
      return;
    }
    await signInWithRedirect();
  },

  async signOut(): Promise<void> {
    if (env.localApi) { sessionStorage.setItem('cig_local_signed_out', 'true'); return; }
    if (env.useMocks) {
      sessionStorage.setItem('cig_mock_user', 'false');
      return;
    }
    await amplifySignOut();
  },
};
