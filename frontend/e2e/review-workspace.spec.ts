import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
const load = (name: string) => JSON.parse(readFileSync(new URL(`../tests/fixtures/${name}.json`, import.meta.url), 'utf8'));
const wire = load('backend-contract');
const topology = load('topology-contract');
const proposals = load('remediation-contract');
test.use({ channel: process.env.CIG_E2E_BROWSER_CHANNEL });
for (const width of [390, 768, 1440]) {
  test(`architecture review workspace is usable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 960 });
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/v1/**', async route => {
      const path = new URL(route.request().url()).pathname;
      let body: unknown = {};
      if (path.endsWith('/system/status')) body = { ...wire.status, features: { evaluations: true, topology: true, fixtureInventory: true, remediationProposals: true, driftEvents: true } };
      else if (path.endsWith('/dashboard/summary')) body = wire.dashboard;
      else if (path.endsWith('/architecture/graph')) body = topology.diffGraph;
      else if (path.endsWith('/findings')) body = wire.findings;
      else if (path.includes('/findings/')) body = wire.finding;
      else if (path.endsWith('/intents')) body = { ...wire.intents, items: [wire.approved.item] };
      else if (path.endsWith('/versions')) body = wire.versions;
      else if (path.includes('/versions/')) body = wire.versionDetail;
      else if (path.includes('/intents/')) body = wire.approved;
      else if (path.endsWith('/evaluations')) body = wire.evaluations;
      else if (path.includes('/evaluations/')) body = wire.evaluationDetail;
      else if (path.endsWith('/remediations')) body = proposals.list;
      else if (path.includes('/remediations/')) body = proposals.created;
      else if (path.endsWith('/audit')) body = wire.audit;
      await route.fulfill({ json: body });
    });
    for (const [route, title, name] of [
      ['/overview', 'Overview', 'overview'], ['/architecture?view=DIFF', 'Architecture Explorer', 'architecture'],
      ['/findings', 'Findings', 'findings'], ['/intents', 'Architecture intents', 'intents'],
      ['/remediation', 'Remediation proposals', 'remediation'], ['/audit-trail', 'Audit trail', 'audit'],
    ]) {
      await page.goto(route);
      await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
      await expect(page.getByText('Unable to load data', { exact: true })).toHaveCount(0);
      if (name === 'architecture') {
        if (width >= 1280 || width < 768) await expect(page.getByText('Snapshot resources', { exact: true })).toBeVisible();
        if (width < 768) await expect(page.getByRole('button', { name: 'Resource list', exact: true })).toHaveAttribute('aria-pressed', 'true');
      }
      await page.screenshot({ path: `/private/tmp/cig-review-${process.env.CIG_VISUAL_ROUND || 'round1'}-${name}-${width}.png`, fullPage: true });
      expect(await page.locator('main').evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
    }
    await page.goto('/architecture?view=DIFF');
    await page.getByRole('button', { name: 'Resource list', exact: true }).click();
    const resource = page.getByRole('button', { name: /^Inspect resource / }).first();
    await resource.focus(); await page.keyboard.press('Enter');
    const drawer = page.getByRole('dialog', { name: 'Resource details' });
    await expect(drawer).toBeVisible(); await expect(drawer).toBeFocused();
    await page.keyboard.press('Escape'); await expect(drawer).toHaveCount(0); await expect(resource).toBeFocused();
    if (width < 1024) await expect(page.getByRole('navigation', { name: 'Mobile navigation' }).getByRole('link')).toHaveCount(8);
    expect(errors).toEqual([]);
  });
}
