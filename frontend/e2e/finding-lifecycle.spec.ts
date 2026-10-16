import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
const wire = JSON.parse(readFileSync(new URL('../tests/fixtures/backend-contract.json', import.meta.url), 'utf8'));
test.use({ channel: process.env.CIG_E2E_BROWSER_CHANNEL });

test('suppression requires a reason, waits for the server, and can be reopened', async ({ page }) => {
  let item = { ...wire.finding.item, revision: 0 };
  const requests: unknown[] = [];
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/v1/**', async route => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith('/system/status')) return route.fulfill({ json: wire.status });
    if (url.pathname.includes('/findings/')) {
      if (route.request().method() === 'PATCH') {
        const body = route.request().postDataJSON(); requests.push(body);
        await new Promise(resolve => setTimeout(resolve, 350));
        expect(body.expectedRevision).toBe(item.revision);
        if (body.action === 'SUPPRESS') {
          expect(body.reason).toBe('Earlier baseline is outside the approved monitoring scope.');
          item = { ...item, status: 'SUPPRESSED', revision: item.revision + 1, suppressionReason: body.reason };
        } else item = { ...item, status: body.action === 'REOPEN' ? 'OPEN' : 'ACKNOWLEDGED', revision: item.revision + 1 };
      }
      return route.fulfill({ json: { item } });
    }
    return route.fulfill({ json: {} });
  });
  await page.goto(`/findings/${item.findingId}`);
  await page.getByRole('button', { name: 'Suppress', exact: true }).click();
  const submit = page.getByRole('button', { name: 'Confirm suppression', exact: true });
  await expect(submit).toBeDisabled();
  await page.getByLabel('Suppression reason').fill('   ');
  await expect(submit).toBeDisabled();
  await page.getByLabel('Suppression reason').fill('Earlier baseline is outside the approved monitoring scope.');
  await submit.click();
  await expect(submit).toBeDisabled();
  await expect(page.getByRole('status').filter({ hasText: 'Finding suppressed. Server status: SUPPRESSED.' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Suppression decision', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Reopen', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Finding reopened. Server status: OPEN.' })).toBeVisible();
  await page.getByRole('button', { name: 'Acknowledge', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Server status: ACKNOWLEDGED.' })).toBeVisible();
  await page.getByRole('button', { name: 'Reopen', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Finding reopened. Server status: OPEN.' })).toBeVisible();
  expect(requests).toHaveLength(4);
  expect(errors).toEqual([]);
  await page.screenshot({ path: '/private/tmp/cig-finding-lifecycle.png' });
});

for (const status of [403, 409]) {
  test(`finding lifecycle preserves status on ${status} and offers refresh`, async ({ page }) => {
    const item = { ...wire.finding.item, revision: 7 };
    let reads = 0;
    await page.route('**/v1/**', async route => {
      const url = new URL(route.request().url());
      if (url.pathname.endsWith('/system/status')) return route.fulfill({ json: wire.status });
      if (url.pathname.includes('/findings/')) {
        if (route.request().method() === 'PATCH') return route.fulfill({ status, json: { error: { code: status === 403 ? 'FORBIDDEN' : 'STATE_CONFLICT', message: status === 403 ? 'You do not have permission to do this.' : 'The finding changed; refresh it.' } } });
        reads++;
        return route.fulfill({ json: { item } });
      }
      return route.fulfill({ json: {} });
    });
    await page.goto(`/findings/${item.findingId}`);
    await page.getByRole('button', { name: 'Suppress', exact: true }).click();
    await page.getByLabel('Suppression reason').fill('Reviewed monitoring scope.');
    await page.getByRole('button', { name: 'Confirm suppression', exact: true }).click();
    await expect(page.getByRole('alert')).toContainText(status === 403 ? 'permission' : 'changed');
    await expect(page.getByRole('button', { name: 'Reopen', exact: true })).toHaveCount(0);
    await expect(page.getByRole('status').filter({ hasText: 'Finding suppressed.' })).toHaveCount(0);
    await page.getByRole('button', { name: 'Refresh finding', exact: true }).click();
    await expect.poll(() => reads).toBeGreaterThan(1);
  });
}
