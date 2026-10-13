/**
 * Validated environment variables (INV-09: No secrets reach the client)
 * Only public VITE_ variables are read here.
 */

export interface AppEnv {
  apiBaseUrl: string;
  useMocks: boolean;
  localApi: boolean;
  cognitoRegion: string;
  cognitoUserPoolId: string;
  cognitoClientId: string;
  cognitoDomain: string;
  defaultRegion: string;
  features: string[];
  redirectSignIn: string;
  redirectSignOut: string;
}

// Endpoint paths already contain /v1; the base must be an origin, not /v1.
const rawApiUrl = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');
const rawUseMocks = import.meta.env.DEV && import.meta.env.VITE_USE_MOCKS === 'true';
const localApiRequested = import.meta.env.VITE_LOCAL_API === 'true';
const rawLocalApi = import.meta.env.DEV && localApiRequested;
if (localApiRequested) {
  if (!import.meta.env.DEV || rawUseMocks || !/^http:\/\/(localhost|127\.0\.0\.1|\[::1\])(?::\d+)?$/.test(rawApiUrl)) {
    throw new Error('VITE_LOCAL_API requires development, VITE_USE_MOCKS=false and a loopback HTTP API origin.');
  }
}
const rawCognitoRegion = import.meta.env.VITE_COGNITO_REGION || 'us-east-1';
const rawUserPoolId = import.meta.env.VITE_COGNITO_USER_POOL_ID || 'mock-user-pool';
const rawClientId = import.meta.env.VITE_COGNITO_CLIENT_ID || 'mock-client-id';
const rawDomain = import.meta.env.VITE_COGNITO_DOMAIN || 'auth.cig.example.com';
const rawDefaultRegion = import.meta.env.VITE_DEFAULT_REGION || 'us-east-1';
const rawFeatures = (import.meta.env.VITE_FEATURES || '').split(',').map((s: string) => s.trim()).filter(Boolean);

export const env: AppEnv = {
  apiBaseUrl: rawApiUrl,
  useMocks: rawUseMocks,
  localApi: rawLocalApi,
  cognitoRegion: rawCognitoRegion,
  cognitoUserPoolId: rawUserPoolId,
  cognitoClientId: rawClientId,
  cognitoDomain: rawDomain,
  defaultRegion: rawDefaultRegion,
  features: rawFeatures,
  redirectSignIn: import.meta.env.VITE_COGNITO_REDIRECT_SIGN_IN || window.location.origin + '/',
  redirectSignOut: import.meta.env.VITE_COGNITO_REDIRECT_SIGN_OUT || window.location.origin + '/login',
};
