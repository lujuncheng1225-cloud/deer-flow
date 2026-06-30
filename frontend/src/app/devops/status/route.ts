export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const DEFAULT_API_PORT = "18010";
const DEFAULT_TIMEOUT_MS = 3000;
const PRODUCT_NAME = "美图商业化 aios";

function getMeituApiBaseURL(): string {
  const configured = process.env.MEITU_API_INTERNAL_BASE_URL?.trim();
  if (configured) {
    return configured.replace(/\/+$/, "");
  }
  const configuredPort = process.env.MEITU_API_PORT?.trim();
  const port =
    configuredPort === undefined || configuredPort.length === 0
      ? DEFAULT_API_PORT
      : configuredPort;
  return `http://127.0.0.1:${port}`;
}

function getTimeoutMs(): number {
  const configured = Number(process.env.MEITU_API_DEVOPS_TIMEOUT_MS);
  return Number.isFinite(configured) && configured > 0
    ? configured
    : DEFAULT_TIMEOUT_MS;
}

function degradedFallback(blocker: string) {
  return {
    status: "degraded",
    service: {
      name: "meitu-bi-agent-platform",
      product_name: PRODUCT_NAME,
      phase: "deerflow_native_runtime_p1",
    },
    product_entry: {
      route: "/deerflow",
      native_workspace_url: "/workspace/chats/new",
      lab_route: "/deerflow/lab",
      lab_is_product_entry: false,
    },
    model_gateway: {},
    deerflow_sidecar: {},
    mcp: {},
    blockers: [blocker],
  };
}

export async function GET() {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), getTimeoutMs());

  try {
    const response = await fetch(`${getMeituApiBaseURL()}/devops/status`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    const payload: unknown = await response.json();
    if (payload && typeof payload === "object" && !Array.isArray(payload)) {
      return Response.json(payload);
    }
    return Response.json(degradedFallback("meitu_api_devops_status_invalid"));
  } catch {
    return Response.json(
      degradedFallback("meitu_api_devops_status_unreachable"),
    );
  } finally {
    clearTimeout(timeout);
  }
}
