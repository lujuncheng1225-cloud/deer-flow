import { afterEach, describe, expect, test, rs } from "@rstest/core";

import { GET } from "@/app/devops/status/route";

const ORIGINAL_ENV = {
  MEITU_API_DEVOPS_TIMEOUT_MS: process.env.MEITU_API_DEVOPS_TIMEOUT_MS,
  MEITU_API_INTERNAL_BASE_URL: process.env.MEITU_API_INTERNAL_BASE_URL,
  MEITU_API_PORT: process.env.MEITU_API_PORT,
};

function restoreEnv() {
  for (const [key, value] of Object.entries(ORIGINAL_ENV)) {
    if (value === undefined) {
      delete process.env[key];
    } else {
      process.env[key] = value;
    }
  }
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}

afterEach(() => {
  rs.restoreAllMocks();
  restoreEnv();
});

describe("/devops/status route", () => {
  test("proxies the full Meitu runtime readiness contract", async () => {
    process.env.MEITU_API_PORT = "19010";
    const upstream = {
      status: "degraded",
      service: {
        name: "meitu-bi-agent-platform",
        product_name: "美图商业化 aios",
      },
      product_entry: {
        route: "/deerflow",
        native_workspace_url: "/workspace/chats/new",
      },
      blockers: ["model_router_not_ready"],
    };
    const fetchSpy = rs
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(upstream));

    const response = await GET();
    const body = await response.json();
    const [url, init] = fetchSpy.mock.calls[0] ?? [];

    expect(url).toBe("http://127.0.0.1:19010/devops/status");
    expect(init).toMatchObject({
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    expect(body).toEqual(upstream);
  });

  test("keeps the same contract shape when the internal Meitu API is unreachable", async () => {
    process.env.MEITU_API_INTERNAL_BASE_URL = "http://127.0.0.1:19011/";
    rs.spyOn(globalThis, "fetch").mockRejectedValueOnce(
      new TypeError("network unavailable"),
    );

    const response = await GET();
    const body = await response.json();

    expect(body).toMatchObject({
      status: "degraded",
      service: {
        name: "meitu-bi-agent-platform",
        product_name: "美图商业化 aios",
      },
      product_entry: {
        route: "/deerflow",
        native_workspace_url: "/workspace/chats/new",
        lab_is_product_entry: false,
      },
      blockers: ["meitu_api_devops_status_unreachable"],
    });
    expect(body.service).not.toBe("meitu-aios-deerflow-frontend");
  });
});
