import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';
import { ApiError } from '../src/api/errors.ts';
import { getEvaluationErrorGuidance } from '../src/features/overview/evaluationErrorGuidance.ts';
import { getOptionalCountPresentation } from '../src/features/overview/optionalCountPresentation.ts';

function loadApiClient(fetchImpl) {
  const source = readFileSync(new URL('../src/api/apiClient.ts', import.meta.url), 'utf8')
    .replaceAll('import.meta.env', 'testEnv');
  const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const module = { exports: {} };
  const dependencies = {
    '@/config/env': { env: { apiBaseUrl: 'https://api.example.test' } },
    '@/auth/authClient': { authClient: { getAccessToken: async () => null } },
    './errors': { ApiError },
  };
  runInNewContext(output, {
    exports: module.exports,
    require: (name) => dependencies[name],
    fetch: fetchImpl,
    testEnv: { DEV: false },
    console,
  });
  return module.exports.apiClient;
}

function conflictResponse(body, requestId = 'req-conflict-01') {
  return {
    status: 409,
    ok: false,
    headers: { get: (name) => name === 'x-amzn-requestid' ? requestId : null },
    json: async () => body,
  };
}

test('apiClient preserves backend conflict code, message, and request ID', async () => {
  const apiClient = loadApiClient(async () => conflictResponse({
    error: {
      code: 'NO_APPROVED_INTENT',
      message: 'Create and approve an intent before running an evaluation.',
    },
  }));

  await assert.rejects(
    apiClient('/v1/evaluations', { safeParse: () => ({ success: true, data: {} }) }, { method: 'POST' }),
    (error) => {
      assert.ok(error instanceof ApiError);
      assert.equal(error.kind, 'conflict');
      assert.equal(error.code, 'NO_APPROVED_INTENT');
      assert.equal(error.message, 'Create and approve an intent before running an evaluation.');
      assert.equal(error.requestId, 'req-conflict-01');
      assert.equal(error.status, 409);
      return true;
    },
  );
});

test('apiClient uses the generic conflict message when the 409 body is unusable', async () => {
  const apiClient = loadApiClient(async () => ({
    ...conflictResponse(undefined),
    json: async () => { throw new SyntaxError('invalid json'); },
  }));

  await assert.rejects(
    apiClient('/v1/evaluations', { safeParse: () => ({ success: true, data: {} }) }, { method: 'POST' }),
    (error) => {
      assert.equal(error.code, 'STATE_CONFLICT');
      assert.equal(error.message, 'The request conflicts with the current state. Refresh and try again.');
      return true;
    },
  );
});

test('evaluation error guidance links only the missing-approved-intent conflict to Intents', () => {
  assert.deepEqual(
    getEvaluationErrorGuidance({ code: 'NO_APPROVED_INTENT' }),
    { to: '/intents', label: 'Create and approve an intent' },
  );
  assert.equal(getEvaluationErrorGuidance({ code: 'INTENT_NOT_APPROVED' }), null);
  assert.equal(getEvaluationErrorGuidance(new Error('network failure')), null);
});

test('dashboard count presentation distinguishes disabled from unavailable data', () => {
  assert.deepEqual(getOptionalCountPresentation(0, true), { label: '0', showLink: true });
  assert.deepEqual(getOptionalCountPresentation(null, true), { label: 'Unavailable', showLink: true });
  assert.deepEqual(getOptionalCountPresentation(null, false), { label: 'Not enabled', showLink: false });
});
