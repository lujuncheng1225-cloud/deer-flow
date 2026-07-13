import { expect, test } from "@playwright/test";

import { mockLangGraphAPI } from "./utils/mock-api";

test.describe("Landing page", () => {
  test("renders the header and hero section", async ({ page }) => {
    mockLangGraphAPI(page);
    await page.goto("/");

    await expect(
      page.getByText("美图商业化 aios", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText(/Find clarity in complexity|从复杂里，找到答案/i).first(),
    ).toBeVisible();
  });

  for (const width of [320, 375, 390]) {
    test(`does not overflow at ${width}px width`, async ({ page }) => {
      await page.setViewportSize({ width, height: 812 });
      mockLangGraphAPI(page);
      await page.goto("/");

      await expect
        .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
        .toBeLessThanOrEqual(width);
      await expect(page.locator("main").first()).toBeInViewport();
    });
  }

  test("root navigates to workspace", async ({ page }) => {
    mockLangGraphAPI(page);

    await page.goto("/");
    await expect(page).toHaveURL(/\/workspace\/chats\/new(?:\?.*)?$/);
  });
});
