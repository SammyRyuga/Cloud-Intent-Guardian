import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';
import * as fixtures from '../src/api/mocks/fixtures.ts';
import * as backend from '../src/api/backendSchemas.ts';

test('mock lifecycle rejects missing reasons, stale revisions and invalid transitions', async () => {
  const routes = [];
  const http = Object.fromEntries(['get', 'post', 'patch'].map(method => [method, (path, resolver) => { routes.push({ method, path, resolver }); }]));
  const source = readFileSync(new URL('../src/api/mocks/handlers.ts', import.meta.url), 'utf8');
  const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const module = { exports: {} };
  const localFixtures = { ...fixtures, mockFindings: structuredClone(fixtures.mockFindings) };
  runInNewContext(output, { exports: module.exports, require: name => ({
    msw: { http, delay: async () => {}, HttpResponse: { json: (body, init = {}) => ({ body, status: init.status || 200 }) } },
    './fixtures': localFixtures, '@/api/backendSchemas': backend,
  })[name], URL, Date, console, structuredClone });
  const handler = routes.find(route => route.method === 'patch' && route.path === '/v1/findings/:id').resolver;
  const item = localFixtures.mockFindings.find(row => row.status === 'OPEN');
  const invoke = body => handler({ params: { id: item.id }, request: { json: async () => body } });
  const revision = item.revision;
  assert.equal((await invoke({ action: 'SUPPRESS', expectedRevision: revision, reason: ' ' })).status, 400);
  assert.equal((await invoke({ action: 'REOPEN', expectedRevision: revision })).status, 409);
  assert.equal(item.status, 'OPEN');
  const suppressed = await invoke({ action: 'SUPPRESS', expectedRevision: revision, reason: 'Reviewed scope.' });
  assert.equal(suppressed.status, 200);
  assert.equal(backend.FindingLifecycleResponseSchema.parse(suppressed.body).item.suppressionReason, 'Reviewed scope.');
  assert.equal((await invoke({ action: 'REOPEN', expectedRevision: revision })).status, 409);
  assert.equal(item.status, 'SUPPRESSED');
  assert.equal((await invoke({ action: 'REOPEN', expectedRevision: revision + 1 })).status, 200);
  assert.equal(item.status, 'OPEN');
  assert.equal(item.revision, revision + 2);
});
