import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';

function readEnv(testEnv) {
  const source = readFileSync(new URL('../src/config/env.ts', import.meta.url), 'utf8');
  const output = ts.transpileModule(source.replaceAll('import.meta.env', 'testEnv'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const context = { testEnv, exports: {}, window: {location: {origin: 'http://localhost:5173'}} };
  runInNewContext(output, context);
  return context.exports.env;
}

test('mock mode requires an explicit true flag in development', () => {
  assert.equal(readEnv({ DEV: true }).useMocks, false);
  assert.equal(readEnv({ DEV: true, VITE_USE_MOCKS: 'false' }).useMocks, false);
  assert.equal(readEnv({ DEV: true, VITE_USE_MOCKS: 'true' }).useMocks, true);
});

test('mock mode remains disabled in production', () => {
  assert.equal(readEnv({ DEV: false, VITE_USE_MOCKS: 'true' }).useMocks, false);
});

test('API origin is normalized without a repeated default version prefix', () => {
  assert.equal(readEnv({ DEV: true }).apiBaseUrl, '');
  const config = readEnv({ DEV: true, VITE_API_BASE_URL: 'http://127.0.0.1:3000/' });
  assert.equal(config.apiBaseUrl + '/v1/intents', 'http://127.0.0.1:3000/v1/intents');
});

test('local API mode is explicit and limited to a loopback origin', () => {
  assert.equal(readEnv({DEV: true, VITE_LOCAL_API: 'true', VITE_API_BASE_URL: 'http://127.0.0.1:3000'}).localApi, true);
  assert.throws(() => readEnv({DEV: true, VITE_LOCAL_API: 'true', VITE_API_BASE_URL: 'https://example.com'}));
  assert.throws(() => readEnv({DEV: false, VITE_LOCAL_API: 'true', VITE_API_BASE_URL: 'http://localhost:3000'}));
  assert.throws(() => readEnv({DEV: true, VITE_LOCAL_API: 'true', VITE_USE_MOCKS: 'true', VITE_API_BASE_URL: 'http://localhost:3000'}));
});
