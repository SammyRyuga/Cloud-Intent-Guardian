import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  outputDir: process.env.CIG_E2E_OUTPUT || "/tmp/cig-e2e-results",
  reporter: "list",
  fullyParallel: false,
  use: { baseURL: "http://127.0.0.1:15173", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 15173 --strictPort",
    url: "http://127.0.0.1:15173",
    reuseExistingServer: false,
    env: {
      VITE_API_BASE_URL: process.env.CIG_API_URL || "http://127.0.0.1:3000",
      VITE_USE_MOCKS: "false",
      VITE_LOCAL_API: "true",
      VITE_DEFAULT_REGION: "ap-south-1",
    },
  },
});
