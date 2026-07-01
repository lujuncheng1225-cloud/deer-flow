import { afterEach, describe, expect, test, rs } from "@rstest/core";

import { GET } from "@/app/deerflow/observability/status/route";

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

describe("/deerflow/observability/status route", () => {
  test("proxies the full Meitu observability contract", async () => {
    process.env.MEITU_API_PORT = "19010";
    const upstream = {
      schema_version: "1.0.0",
      observability_id: "meitu_deerflow_observability_p3",
      status: "degraded",
      run_replay_ready: false,
      values_redacted: true,
      canonical_write_allowed: false,
      blockers: ["required_remote_mcp_not_callable"],
    };
    const fetchSpy = rs
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(upstream));

    const response = await GET();
    const body = await response.json();
    const [url, init] = fetchSpy.mock.calls[0] ?? [];

    expect(url).toBe(
      "http://127.0.0.1:19010/deerflow/observability/status",
    );
    expect(init).toMatchObject({
      cache: "no-store",
      headers: {
        Accept: "application/json",
        "Cache-Control": "no-cache",
        Pragma: "no-cache",
      },
    });
    expect(body).toEqual(upstream);
  });

  test("returns a degraded safe contract when the internal API is unreachable", async () => {
    process.env.MEITU_API_INTERNAL_BASE_URL = "http://127.0.0.1:19011/";
    rs.spyOn(globalThis, "fetch").mockRejectedValueOnce(
      new TypeError("network unavailable"),
    );

    const response = await GET();
    const body = await response.json();

    expect(body).toMatchObject({
      schema_version: "1.0.0",
      observability_id: "meitu_deerflow_observability_p3",
      status: "degraded",
      values_redacted: true,
      canonical_write_allowed: false,
      blockers: ["meitu_api_observability_status_unreachable"],
    });
    expect(JSON.stringify(body)).not.toContain("token");
  });
});
