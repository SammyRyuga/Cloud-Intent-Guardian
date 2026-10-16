import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
const wire = JSON.parse(readFileSync(new URL('../tests/fixtures/backend-contract.json', import.meta.url), 'utf8'));
const proposals = JSON.parse(readFileSync(new URL('../tests/fixtures/remediation-contract.json', import.meta.url), 'utf8'));
test.use({ channel: process.env.CIG_E2E_BROWSER_CHANNEL });
const impact = { coverage: 'PARTIAL', sourceCoverage: { ec2: 'COMPLETE', lambda: 'PARTIAL' }, knownAttachmentCount: 1, attachmentCount: null, attachments: [{ resourceId: 'eni-fixture', resourceType: 'AWS::EC2::NetworkInterface', source: 'DescribeNetworkInterfaces' }], requiresHumanApproval: true, interpretation: 'Attachment records are not a unique workload count.' };

test('finding and remediation show partial attachment records without claiming workload totals', async ({ page }) => {
  await page.route('**/v1/**', async route => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown = {};
    if (path.endsWith('/system/status')) body = { ...wire.status, features: { remediationProposals: true } };
    else if (path.endsWith('/findings')) body = wire.findings;
    else if (path.includes('/findings/')) body = { item: { ...wire.finding.item, observed: { ...wire.finding.item.observed, attachmentImpact: impact } } };
    else if (path.endsWith('/remediations')) body = proposals.list;
    else if (path.includes('/remediations/')) body = { item: { ...proposals.created.item, resourceType: 'AWS::EC2::SecurityGroup', plan: { ...proposals.created.item.plan, attachmentImpact: impact } } };
    await route.fulfill({ json: body });
  });
  await page.goto(`/findings/${wire.finding.item.findingId}`);
  await expect(page.getByRole('heading', { name: 'Security group attachment context' })).toBeVisible();
  await expect(page.getByText('At least 1', { exact: true })).toBeVisible();
  await expect(page.getByText('attachment records / partial coverage')).toBeVisible();
  await expect(page.getByText('Human approval is required before changing the security group.')).toBeVisible();
  await page.goto(`/remediation?proposalId=${proposals.created.item.proposalId}`);
  await expect(page.getByRole('heading', { name: 'Security group attachment context' })).toBeVisible();
  await expect(page.getByText('At least 1', { exact: true })).toBeVisible();
});

test('first Tier 2 observation is shown as a baseline with no historical-change claim', async ({ page }) => {
  const history = { status: 'FIRST_OBSERVATION', reason: 'The first complete snapshot establishes a baseline.', previousEvaluationId: null, driftEventIds: [], comparisonScope: 'SAME_INTENT_VERSION', isHistoricalChange: false };
  await page.route('**/v1/**', async route => {
    const path = new URL(route.request().url()).pathname;
    await route.fulfill({ json: path.endsWith('/system/status') ? wire.status : { item: { ...wire.finding.item, tier: 'TIER_2', history, observed: { history } } } });
  });
  await page.goto(`/findings/${wire.finding.item.findingId}`);
  await expect(page.getByRole('heading', { name: 'Historical context' })).toBeVisible();
  await expect(page.getByText('First observation', { exact: true })).toBeVisible();
  await expect(page.getByText('The first complete snapshot establishes a baseline.')).toBeVisible();
  await expect(page.getByText('Comparison is limited to the same intent and immutable version.')).toBeVisible();
  await expect(page.getByText('Correlated drift events', { exact: true })).toHaveCount(0);
});
