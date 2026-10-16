import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';
import * as B from '../src/api/backendSchemas.ts';
import { queryKeys } from '../src/api/queryKeys.ts';
// Produced by the real Python versions handler against Moto, with no live writes.
const wire = JSON.parse(readFileSync(new URL('./fixtures/version-decisions-contract.json', import.meta.url), 'utf8'));

function loadHooks(response) {
  const invalidated = [];
  const requests = [];
  const output = ts.transpileModule(readFileSync(new URL('../src/hooks/apiHooks.ts', import.meta.url), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const module = { exports: {} };
  const deps = {
    react: {}, '@/utils/evaluationPolling': {},
    '@tanstack/react-query': { useMutation: options => options, useQueryClient: () => ({ invalidateQueries: ({ queryKey }) => invalidated.push(queryKey) }) },
    '@/api/apiClient': { apiClient: (endpoint, schema, options) => { requests.push({ endpoint, ...options }); return schema.parse(response); } },
    '@/api/endpoints': { endpoints: { intentVersionApprove: (id, version) => `/v1/intents/${id}/versions/${version}/approve`, intentRollback: id => `/v1/intents/${id}/rollback` } },
    '@/api/queryKeys': { queryKeys }, '@/api/schemas': {}, '@/api/backendSchemas': B,
    '@/config/env': { env: {} }, '@/config/capabilities': {}, '@/api/errors': {},
  };
  runInNewContext(output, { exports: module.exports, require: name => deps[name] });
  return { hooks: module.exports, requests, invalidated };
}

test('version approval parses the actual activated intent facade and refreshes state', async () => {
  assert.equal('contentHash' in wire.approved.item, false);
  const { hooks, requests, invalidated } = loadHooks(wire.approved);
  const mutation = hooks.useApproveIntentVersion();
  const args = { id: wire.approved.item.intentId, version: 2, expectedRevision: wire.approved.item.revision - 1 };
  const result = await mutation.mutationFn(args);
  assert.equal(result.item.activeVersion, 2);
  assert.equal(result.item.revision, wire.approved.item.revision);
  mutation.onSuccess(result, args);
  assert.ok(invalidated.some(key => key[0] === 'intent' && key[1] === args.id));
  assert.ok(invalidated.some(key => key[0] === 'intent-versions'));
  assert.equal(requests[0].body.expectedRevision, args.expectedRevision);
});

test('rollback parses the actual activated facade without requiring snapshot fields', async () => {
  const { hooks, invalidated } = loadHooks(wire.rolledBack);
  const mutation = hooks.useRollbackIntent();
  const args = { id: wire.rolledBack.item.intentId, targetVersion: 1, expectedRevision: wire.approved.item.revision, reason: 'Local contract verification' };
  const result = await mutation.mutationFn(args);
  assert.equal(result.item.activeVersion, 1);
  assert.equal(result.item.revision, wire.rolledBack.item.revision);
  mutation.onSuccess(result, args);
  assert.ok(invalidated.some(key => key[0] === 'intent'));
  assert.ok(invalidated.some(key => key[0] === 'intent-versions'));
});
