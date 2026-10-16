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
    else if (url.pathname.endsWith('/intents')) body = { ...wire.intents, items: [wire.approved.item] };
    else if (url.pathname.endsWith('/evaluations') && route.request().method() === 'POST') {
      expect(route.request().postDataJSON()).toEqual({ intentId: wire.approved.item.intentId, intentVersion: wire.approved.item.activeVersion ?? wire.approved.item.version });
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
  await expect(page.getByRole('button', { name: 'Run evaluation', exact: true })).toBeDisabled();
  await page.getByLabel('Approved intent to evaluate').selectOption(wire.approved.item.intentId);
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

test('evaluation requires explicit approved baseline selection across intent pages', async ({ page }) => {
  const older = { ...wire.approved.item, intentId: 'older-approved-serverless', name: 'Approved serverless scope', activeVersion: 2 };
  const newest = { ...wire.approved.item, intentId: 'newer-unrelated-sample', name: 'Unrelated sample', activeVersion: 1 };
  let submitted: unknown;
  await page.route('**/v1/**', async route => {
    const url = new URL(route.request().url());
    let body: unknown = {};
    if (url.pathname.endsWith('/system/status')) body = { ...wire.status, features: { evaluations: true } };
    else if (url.pathname.endsWith('/dashboard/summary')) body = wire.dashboard;
    else if (url.pathname.endsWith('/intents')) body = { items: url.searchParams.has('nextToken') ? [older] : [newest, { ...wire.created.item, name: 'Unapproved draft', activeVersion: null }], count: 1, limit: 25, nextToken: url.searchParams.has('nextToken') ? null : 'opaque-next-page' };
    else if (url.pathname.endsWith('/evaluations') && route.request().method() === 'POST') {
      submitted = route.request().postDataJSON();
      body = { evaluation: { evaluationId: 'selected-run', status: 'QUEUED', intentId: older.intentId, intentVersion: 2, createdAt: new Date().toISOString() }, statusUrl: '/v1/evaluations/selected-run' };
    } else if (url.pathname.endsWith('/evaluations')) body = { items: [], nextToken: null, count: 0, limit: 25 };
    else if (url.pathname.endsWith('/evaluations/selected-run')) body = { item: { evaluationId: 'selected-run', status: 'SUCCEEDED', intentId: older.intentId, intentVersion: 2 } };
    await route.fulfill({ json: body });
  });
  await page.goto('/overview');
  const button = page.getByRole('button', { name: 'Run evaluation', exact: true });
  await expect(button).toBeDisabled();
  await expect(page.getByLabel('Approved intent to evaluate').getByRole('option', { name: 'Unapproved draft' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Next intent page', exact: true }).click();
  await page.getByLabel('Approved intent to evaluate').selectOption(older.intentId);
  await expect(page.getByText('Evaluation will use Approved serverless scope, approved version 2.', { exact: false })).toBeVisible();
  await button.click();
  await expect.poll(() => submitted).toEqual({ intentId: older.intentId, intentVersion: 2 });
  await expect(page.getByRole('status').filter({ hasText: 'Evaluation succeeded. ID: selected-run' })).toBeVisible();
});
