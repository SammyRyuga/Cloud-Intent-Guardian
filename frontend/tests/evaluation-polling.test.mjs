import test from 'node:test';
import assert from 'node:assert/strict';
import { evaluationPollInterval } from '../src/utils/evaluationPolling.ts';
import { queryKeys } from '../src/api/queryKeys.ts';
import { QueryClient } from '@tanstack/react-query';

test('visible queued and running history rows poll, terminal/empty pages stop', () => {
  for (const status of ['QUEUED', 'RUNNING']) assert.equal(evaluationPollInterval([{ status }], 0, 1), 5000);
  for (const status of ['SUCCEEDED', 'PARTIAL', 'FAILED']) assert.equal(evaluationPollInterval([{ status }], 0, 1), false);
  assert.equal(evaluationPollInterval([], 0, 1), false);
  assert.equal(evaluationPollInterval([{ status: 'QUEUED' }], 0, 900000), false);
  assert.equal(evaluationPollInterval(undefined, 0, 900000), false);
});

test('terminal invalidation refreshes every cached history page and filter', async () => {
  const client = new QueryClient();
  const keys = [queryKeys.evaluations(), queryKeys.evaluations({ cursor: 'opaque-page-2' }), queryKeys.evaluations({ status: 'QUEUED' })];
  for (const key of keys) client.setQueryData(key, { items: [] });
  await client.invalidateQueries({ queryKey: queryKeys.evaluationLists() });
  for (const key of keys) assert.equal(client.getQueryState(key).isInvalidated, true);
  client.clear();
});
