import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

const here = dirname(fileURLToPath(import.meta.url));

/**
 * Layer 2: drive the REAL frontend against the REAL gateway (replay model, no
 * API key) and assert the browser renders the backend's data correctly.
 *
 * The prompt is read from the same fixture the gateway replays, so the input
 * hash matches and the recorded model turns reproduce deterministically.
 */
// Register through the frontend origin (same-origin proxy) so the auth cookies
// are stored for and sent to the browser origin — the gateway is reached via the
// next.config rewrite, never cross-origin from the browser.
const APP =
  process.env.E2E_APP_URL ??
  `http://localhost:${process.env.E2E_FRONTEND_PORT ?? "3000"}`;
const fixture = JSON.parse(
  readFileSync(
    join(
      here,
      "../../../backend/tests/fixtures/replay/write_read_file.ultra.json",
    ),
    "utf-8",
  ),
) as {
  prompt: string;
  turns: Array<{ output: { data: { content?: unknown } } }>;
};

const PROMPT = fixture.prompt;

const textTurns = fixture.turns
  .map((t) => t.output?.data?.content)
  .filter((c): c is string => typeof c === "string" && c.trim().length > 0);
const EXPECTED_RESPONSE = textTurns.at(-2) ?? "";

test.describe("real backend render (replay, no API key)", () => {
  test.beforeEach(async ({ context }) => {
    // Throwaway test account: register sets access_token + csrf_token cookies in
    // the browser context (host-scoped to localhost, shared across ports), so
    // the frontend's SDK (credentials:include + X-CSRF-Token) authenticates.
    const email = `e2e-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
    const resp = await context.request.post(`${APP}/api/v1/auth/register`, {
      data: { email, password: "very-strong-password-123" },
    });
    expect(resp.status(), await resp.text()).toBe(201);
  });

  test("renders the submitted prompt + replayed response from a real backend", async ({
    page,
  }) => {
    // ultra mode so the context the frontend sends (is_plan_mode + subagent_enabled)
    // matches the recorded fixture; otherwise the replay input hash would miss.
    await page.addInitScript(() => {
      window.localStorage.setItem(
        "deerflow.local-settings",
        JSON.stringify({ context: { mode: "ultra" } }),
      );
    });

    await page.route("**/projects", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify([
          { project: { project_id: "whee", product_name: "WHEE" } },
        ]),
      });
    });
    await page.route("**/projects/whee/conversations", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ contentType: "application/json", body: "[]" });
        return;
      }
      const request = route.request().postDataJSON() as {
        sidecar_thread_id: string;
        title: string;
      };
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          conversation_id: "dfconv-replay",
          project_id: "whee",
          title: request.title,
          sidecar_thread_id: request.sidecar_thread_id,
          updated_at: new Date().toISOString(),
        }),
      });
    });

    await page.goto("/workspace/chats/new?project=whee");

    const textarea = page.getByPlaceholder(/how can i assist you/i);
    await expect(textarea).toBeVisible({ timeout: 30_000 });
    await textarea.fill(PROMPT);
    await textarea.press("Enter");

    // The submitted prompt and replayed response prove both sides of the real
    // frontend/gateway contract render through the project-scoped workspace.
    expect(
      EXPECTED_RESPONSE,
      "fixture should contain a replayed assistant response",
    ).not.toBe("");
    const chat = page.locator("#chat");
    await expect(chat.getByText(PROMPT)).toBeVisible({
      timeout: 60_000,
    });
    await expect(chat.getByText(EXPECTED_RESPONSE)).toBeVisible({
      timeout: 30_000,
    });

    // Visual regression is OS-sensitive (a macOS baseline won't match CI's
    // Linux render), so it's a local dev gate only; in CI we capture the render
    // as an artifact for human review instead of hard-asserting a cross-OS
    // baseline. The DOM assertions above are the CI gate.
    if (process.env.CI) {
      await page.screenshot({
        path: "test-results/real-backend-render.png",
        fullPage: true,
      });
    } else {
      await expect(page).toHaveScreenshot("real-backend-render.png", {
        maxDiffPixelRatio: 0.02,
        fullPage: true,
      });
    }
  });
});
