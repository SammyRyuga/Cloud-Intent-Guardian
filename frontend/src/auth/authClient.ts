/**
 * Auth Client (INV-10: Tokens handled by Amplify Auth only)
 * The ONLY file importing aws-amplify
 */
import { Amplify } from 'aws-amplify';
import { getCurrentUser, fetchAuthSession, signInWithRedirect, signOut as amplifySignOut } from 'aws-amplify/auth';
import { env } from '@/config/env';

// Configure Amplify
if (!env.useMocks) {
  try {
    Amplify.configure({
      Auth: {
        Cognito: {
          userPoolId: env.cognitoUserPoolId,
          userPoolClientId: env.cognitoClientId,
          loginWith: {
            oauth: {
              domain: env.cognitoDomain,
              scopes: ['openid', 'email', 'phone', 'profile'],
              redirectSignIn: [window.location.origin + '/'],
              redirectSignOut: [window.location.origin + '/login'],
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

export const authClient = {
  async getAccessToken(): Promise<string | null> {
    if (env.useMocks) {
      return 'mock-access-token-cig';
    }
    try {
      const session = await fetchAuthSession();
      return session.tokens?.accessToken?.toString() || null;
    } catch {
      return null;
    }
  },

  async getCurrentUser(): Promise<UserProfile | null> {
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
    if (env.useMocks) {
      sessionStorage.setItem('cig_mock_user', 'true');
      return;
    }
    await signInWithRedirect();
  },

  async signOut(): Promise<void> {
    if (env.useMocks) {
      sessionStorage.setItem('cig_mock_user', 'false');
      return;
    }
    await amplifySignOut();
  },
};
