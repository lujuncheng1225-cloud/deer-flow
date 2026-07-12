import { afterEach, expect, test, rs } from "@rstest/core";

import { fetch as fetchWithAuth } from "@/core/api/fetcher";

afterEach(() => {
  rs.unstubAllGlobals();
});

test("restores a missing CSRF cookie before a state-changing request", async () => {
  const documentStub = { cookie: "" };
  const fetchFn = rs.fn(
    async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.href
            : input.url;
      if (url === "/api/v1/auth/me") {
        documentStub.cookie = "csrf_token=recovered-token";
        return new Response(JSON.stringify({ id: "user-1" }), { status: 200 });
      }
      return new Response(null, { status: 200 });
    },
  );
  rs.stubGlobal("document", documentStub);
  rs.stubGlobal("fetch", fetchFn);

  const response = await fetchWithAuth("/api/threads/search", {
    method: "POST",
  });

  expect(response.status).toBe(200);
  expect(fetchFn).toHaveBeenCalledTimes(2);
  expect(fetchFn.mock.calls[0]?.[0]).toBe("/api/v1/auth/me");
  const requestHeaders = new Headers(fetchFn.mock.calls[1]?.[1]?.headers);
  expect(requestHeaders.get("X-CSRF-Token")).toBe("recovered-token");
});

test("uses an existing CSRF cookie without a recovery request", async () => {
  const fetchFn = rs.fn(
    async (_input: RequestInfo | URL, _init?: RequestInit) =>
      new Response(null, { status: 200 }),
  );
  rs.stubGlobal("document", { cookie: "csrf_token=existing-token" });
  rs.stubGlobal("fetch", fetchFn);

  await fetchWithAuth("/api/threads/search", { method: "POST" });

  expect(fetchFn).toHaveBeenCalledTimes(1);
  const requestHeaders = new Headers(fetchFn.mock.calls[0]?.[1]?.headers);
  expect(requestHeaders.get("X-CSRF-Token")).toBe("existing-token");
});
