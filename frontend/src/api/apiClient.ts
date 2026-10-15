/**
 * ApiClient (INV-01: Only src/api/ may call fetch)
 * Validates responses using zod schemas and attaches bearer token
 */
import { z } from 'zod';
import { env } from '@/config/env';
import { authClient } from '@/auth/authClient';
import { ApiError } from './errors';

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  body?: unknown;
  headers?: Record<string, string>;
}

export async function apiClient<T>(
  endpoint: string,
  schema: z.ZodType<T, z.ZodTypeDef, unknown>,
  options: RequestOptions = {}
): Promise<T> {
  const token = await authClient.getAccessToken();
  const url = endpoint.startsWith('http') ? endpoint : `${env.apiBaseUrl}${endpoint}`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method: options.method || 'GET',
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
    if (response.status === 401 && !env.useMocks && !env.localApi) {
      const refreshed = await authClient.getAccessToken(true);
      if (refreshed) {
        headers.Authorization = `Bearer ${refreshed}`;
        response = await fetch(url, {method: options.method || 'GET', headers,
          body: options.body ? JSON.stringify(options.body) : undefined});
      }
    }
  } catch {
    throw new ApiError({
      message: 'Could not reach the API. Check connection.',
      kind: 'network',
      code: 'NETWORK_ERROR',
    });
  }

  const requestId = response.headers.get('x-amzn-requestid') || response.headers.get('x-request-id') || undefined;

  if (response.status === 401) {
    if (!env.useMocks && !env.localApi) await authClient.clearExpiredSession();
    throw new ApiError({
      message: 'Your session has expired. Sign in again to continue.',
      kind: 'auth',
      code: 'UNAUTHENTICATED',
      requestId,
      status: 401,
    });
  }

  if (response.status === 403) {
    throw new ApiError({
      message: 'You do not have permission to do this.',
      kind: 'forbidden',
      code: 'FORBIDDEN',
      requestId,
      status: 403,
    });
  }

  if (response.status === 404) {
    throw new ApiError({
      message: 'Requested resource was not found.',
      kind: 'not_found',
      code: 'NOT_FOUND',
      requestId,
      status: 404,
    });
  }

  if (response.status === 409) {
    let errorPayload: unknown;
    try {
      errorPayload = await response.json();
    } catch {
      // A malformed or empty conflict response uses the safe generic fallback below.
    }
    const envelope = isRecord(errorPayload) ? errorPayload.error : undefined;
    const payload = isRecord(envelope) ? envelope : isRecord(errorPayload) ? errorPayload : undefined;
    const backendCode = typeof payload?.code === 'string' && payload.code.trim() ? payload.code.trim() : undefined;
    const backendMessage = typeof payload?.message === 'string' && payload.message.trim() ? payload.message.trim() : undefined;
    throw new ApiError({
      message: backendMessage || 'The request conflicts with the current state. Refresh and try again.',
      kind: 'conflict',
      code: backendCode || 'STATE_CONFLICT',
      requestId,
      status: 409,
    });
  }

  if (response.status === 429) {
    throw new ApiError({
      message: 'Too many requests. Please try again shortly.',
      kind: 'rate_limited',
      code: 'RATE_LIMITED',
      requestId,
      status: 429,
    });
  }

  if (response.status >= 500) {
    throw new ApiError({
      message: 'The server could not complete the request.',
      kind: 'server',
      code: 'INTERNAL_ERROR',
      requestId,
      status: response.status,
    });
  }

  if (!response.ok) {
    let errMsg = 'The request failed.';
    try {
      const errJson = await response.json();
      if (errJson.error?.message) errMsg = errJson.error.message;
      else if (errJson.message) errMsg = errJson.message;
    } catch {
      // ignore
    }
    throw new ApiError({
      message: errMsg,
      kind: 'validation',
      code: 'VALIDATION_ERROR',
      requestId,
      status: response.status,
    });
  }

  let data: unknown;
  try {
    data = await response.json();
  } catch {
    data = {};
  }

  const parseResult = schema.safeParse(data);
  if (!parseResult.success) {
    if (import.meta.env.DEV) {
      console.warn('API Contract Mismatch on', endpoint, parseResult.error);
    }
    throw new ApiError({
      message: 'The server sent data this version of the app does not understand.',
      kind: 'contract',
      code: 'CONTRACT_MISMATCH',
      requestId,
      status: response.status,
    });
  }

  return parseResult.data;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
