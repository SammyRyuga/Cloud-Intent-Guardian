import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
const wire = JSON.parse(readFileSync(new URL('../tests/fixtures/backend-contract.json', import.meta.url), 'utf8'));

test.use({ channel: process.env.CIG_E2E_BROWSER_CHANNEL });

test('evaluation status, history and subsequent partial runs converge automatically', async ({ page }) => {
  let run = 0;
  let detailReads = 0;
  let historyReads = 0;
  const terminalStatus = () => run === 3 ? 'SUCCEEDED' : run === 4 ? 'FAILED' : 'PARTIAL';
  const evaluation = (id: string, status: string) => ({ evaluationId: id, status, error: status === 'FAILED' ? { code: 'EVALUATION_FAILED', message: 'Evaluation inventory failed.' } : null, intentId: null, intentVersion: null, createdAt: new Date().toISOString(), ruleResults: status === 'PARTIAL' ? [{ ruleId: 'component:database', outcome: 'UNKNOWN', explanation: 'Insufficient inventory evidence.' }] : [], warnings: status === 'PARTIAL' ? [{ source: 'aws_config', code: 'ACCESS_DENIED', message: 'Config inventory unavailable.' }] : [] });
  await page.route('**/v1/**', async route => {
    const url = new URL(route.request().url());
    let body: unknown = {};
    if (url.pathname.endsWith('/system/status')) body = { backendReachable: true, awsSourcesConnected: false, evaluatedRegion: 'ap-south-1', lastSyncAt: new Date().toISOString(), version: 'test', features: { evaluations: true } };
    else if (url.pathname.endsWith('/dashboard/summary')) body = wire.dashboard;
    else if (url.pathname.endsWith('/evaluations') && route.request().method() === 'POST') {
      run++; detailReads = 0;
      body = { evaluation: evaluation(`run-${run}`, 'QUEUED'), statusUrl: `/v1/evaluations/run-${run}` };
    } else if (url.pathname.endsWith('/evaluations')) {
      historyReads++;
      body = { items: run ? [evaluation(`run-${run}`, detailReads >= 2 ? terminalStatus() : 'QUEUED')] : [evaluation('existing', historyReads >= 2 ? 'PARTIAL' : 'QUEUED')], count: 1, limit: 25, nextToken: null };
    } else if (url.pathname.includes('/evaluations/')) {
      detailReads++;
      body = { item: evaluation(`run-${run}`, detailReads >= 2 ? terminalStatus() : 'RUNNING') };
    }
    await route.fulfill({ json: body });
  });
  await page.goto('/overview');
  const history = page.getByRole('list').filter({ has: page.getByRole('button', { name: 'Inspect evaluation existing' }) });
  await expect(history.getByText('QUEUED', { exact: true })).toBeVisible();
  await expect(history.getByText('PARTIAL', { exact: true })).toBeVisible({ timeout: 10000 });
  for (const id of ['run-1', 'run-2', 'run-3', 'run-4']) {
    await page.getByRole('button', { name: 'Run evaluation', exact: true }).click();
    await expect(page.getByRole('status').filter({ hasText: `Evaluation running. ID: ${id}` })).toBeVisible();
    await expect(page.getByRole('status').filter({ hasText: `Evaluation ${terminalStatus().toLowerCase()}. ID: ${id}` })).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Evaluation accepted as QUEUED', { exact: false })).toHaveCount(0);
    const row = page.getByRole('listitem').filter({ has: page.getByRole('button', { name: `Inspect evaluation ${id}` }) });
    await expect(row.getByText(terminalStatus(), { exact: true })).toBeVisible();
    if (terminalStatus() === 'PARTIAL') {
    await expect(page.getByText('component:database: Insufficient inventory evidence.')).toBeVisible();
    await expect(page.getByText('aws_config: Config inventory unavailable.')).toBeVisible();
    }
    if (terminalStatus() === 'FAILED') await expect(page.getByRole('alert').filter({ hasText: 'Evaluation inventory failed.' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Run evaluation', exact: true })).toBeEnabled();
  }
});
