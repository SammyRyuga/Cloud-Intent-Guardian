/**
 * Validated environment variables (INV-09: No secrets reach the client)
 * Only public VITE_ variables are read here.
 */

export interface AppEnv {
  apiBaseUrl: string;
  useMocks: boolean;
  cognitoRegion: string;
  cognitoUserPoolId: string;
  cognitoClientId: string;
  cognitoDomain: string;
  defaultRegion: string;
  features: string[];
}

const rawApiUrl = import.meta.env.VITE_API_BASE_URL || '/v1';
const rawUseMocks = import.meta.env.VITE_USE_MOCKS === 'true' || import.meta.env.DEV;
const rawCognitoRegion = import.meta.env.VITE_COGNITO_REGION || 'us-east-1';
const rawUserPoolId = import.meta.env.VITE_COGNITO_USER_POOL_ID || 'mock-user-pool';
const rawClientId = import.meta.env.VITE_COGNITO_CLIENT_ID || 'mock-client-id';
const rawDomain = import.meta.env.VITE_COGNITO_DOMAIN || 'auth.cig.example.com';
const rawDefaultRegion = import.meta.env.VITE_DEFAULT_REGION || 'us-east-1';
const rawFeatures = (import.meta.env.VITE_FEATURES || '').split(',').map((s: string) => s.trim()).filter(Boolean);

export const env: AppEnv = {
  apiBaseUrl: rawApiUrl,
  useMocks: rawUseMocks,
  cognitoRegion: rawCognitoRegion,
  cognitoUserPoolId: rawUserPoolId,
  cognitoClientId: rawClientId,
  cognitoDomain: rawDomain,
  defaultRegion: rawDefaultRegion,
  features: rawFeatures,
};
