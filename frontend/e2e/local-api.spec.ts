import { test, expect } from "@playwright/test";

test("real local API creates, retrieves and approves a manifest", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await page.goto("/intents");
  await expect(
    page.getByRole("heading", { name: "Architecture intents", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "Local API development - DynamoDB Local data; AWS discovery and Cognito are not verified.",
    ),
  ).toBeVisible();
  const name = `Browser integration ${Date.now()}`;
  await page
    .getByLabel("JSON manifest")
    .fill(
      JSON.stringify({
        name,
        description: "Browser integration test",
        constraints: [
          {
            id: "ssh",
            type: "SECURITY_GROUP_NO_OPEN_SSH",
            severity: "HIGH",
            description: "No internet SSH",
          },
        ],
      }),
    );
  const createdResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/v1/intents") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Create draft", exact: true }).click();
  const response = await createdResponse;
  expect(response.status()).toBe(201);
  const created = (await response.json()).item;
  await expect(
    page.getByText(`Draft saved. ID: ${created.intentId}`),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve reviewed draft" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Approve reviewed draft" }).click();
  await expect(
    page.getByText("Version 1 - APPROVED", { exact: true }),
  ).toBeVisible();
  const api = process.env.CIG_API_URL || "http://127.0.0.1:3000";
  const persisted = await request.get(`${api}/v1/intents/${created.intentId}`);
  expect(persisted.status()).toBe(200);
  expect((await persisted.json()).item).toMatchObject({
    intentId: created.intentId,
    name,
    status: "APPROVED",
  });
  await page.reload();
  await expect(
    page.getByText("Version 1 - APPROVED", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "/tmp/cig-local-intent-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("navigation", { name: "Mobile navigation" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "/tmp/cig-local-intent-mobile.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("local feature gates follow backend-advertised capabilities", async ({
  page,
}) => {
  const failures: string[] = [];
  let status: { features?: Record<string, boolean> } | undefined;
  page.on("response", (response) => {
    if (response.status() >= 400)
      failures.push(`${response.status()} ${response.url()}`);
  });
  page.on("response", async (response) => {
    if (response.url().endsWith("/v1/system/status") && response.ok()) {
      status = await response.json();
    }
  });
  await page.goto("/overview");
  await expect(page.getByRole("heading", { name: "Architecture Conformance Overview" })).toBeVisible();
  await expect.poll(() => status?.features).toBeTruthy();
  const features = status!.features!;
  const evaluationButton = page.getByRole("button", { name: /Run evaluation|AWS evaluation not enabled locally/ });
  if (features.evaluations) await expect(evaluationButton).toBeEnabled();
  else await expect(evaluationButton).toBeDisabled();
  await page.goto("/findings");
  await expect(page.getByRole("heading", { name: "Architecture Findings" })).toBeVisible();
  await page.goto("/architecture");
  if (features.topology) await expect(page.getByRole("heading", { name: "Architecture Explorer" })).toBeVisible();
  else await expect(page.getByRole("heading", { name: "Not enabled" })).toBeVisible();
  await page.goto("/remediation");
  if (features.remediationProposals) await expect(page.getByRole("heading", { name: "Remediation proposals" })).toBeVisible();
  else await expect(page.getByRole("heading", { name: "Not enabled" })).toBeVisible();
  await page.goto("/audit-trail");
  await expect(page.getByRole("heading", { name: "Immutable Audit Trail" })).toBeVisible();
  expect(failures).toEqual([]);
});
