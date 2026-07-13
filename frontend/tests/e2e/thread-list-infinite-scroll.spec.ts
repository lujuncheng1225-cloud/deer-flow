import { expect, test } from "@playwright/test";

import { mockLangGraphAPI } from "./utils/mock-api";

const TOTAL_THREADS = 120;

const THREADS = Array.from({ length: TOTAL_THREADS }, (_, i) => {
  // Pad index so titles sort deterministically as strings. The thread-search
  // mock returns threads in the order provided, so paging boundaries are
  // stable across runs.
  const index = String(i + 1).padStart(3, "0");
  return {
    thread_id: `00000000-0000-0000-0000-0000000${index.padStart(5, "0")}`,
    title: `Conversation ${index}`,
    updated_at: `2025-06-${String((i % 28) + 1).padStart(2, "0")}T12:00:00Z`,
  };
});

const FIRST_CONVERSATION = "Conversation 001";
const LAST_CONVERSATION = `Conversation ${String(TOTAL_THREADS).padStart(3, "0")}`;

test.describe("Project conversation list", () => {
  test("chats list shows the active project's conversations", async ({
    page,
  }) => {
    mockLangGraphAPI(page, { threads: THREADS });

    await page.goto("/workspace/chats");

    const main = page.locator("main");
    await expect(main.getByText(FIRST_CONVERSATION)).toBeVisible({
      timeout: 15_000,
    });
    await expect(main.getByText(LAST_CONVERSATION)).toBeVisible();
    await expect(page.getByTestId("chats-page-sentinel")).toHaveCount(0);
  });

  test("sidebar shows the active project's conversations", async ({ page }) => {
    mockLangGraphAPI(page, { threads: THREADS });

    await page.goto("/workspace/chats/new");

    const sidebar = page.locator("[data-sidebar='sidebar']");
    await expect(sidebar.getByText(FIRST_CONVERSATION).first()).toBeVisible({
      timeout: 15_000,
    });
    await expect(sidebar.getByText(LAST_CONVERSATION).first()).toBeVisible();
    await expect(page.getByTestId("recent-chat-list-sentinel")).toHaveCount(0);
  });
});
