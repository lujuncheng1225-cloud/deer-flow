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
    schema_version: "1.0.0",
    observability_id: "meitu_deerflow_observability_p3",
    status: "degraded",
    run_replay_ready: false,
    sidecar_runtime_reachable: false,
    full_deerflow_capability_available: false,
    event_store_backends: [],
    required_run_fields: [],
    error_taxonomy: [],
    mcp_request_summary: {
      local_meitu_mcp_callable: false,
      local_tool_count: 0,
      remote_server_count: 0,
      required_remote_server_count: 0,
      callable_required_remote_server_count: 0,
      blocked_required_remote_servers: [],
    },
    features: [],
    values_redacted: true,
    canonical_write_allowed: false,
    blockers: [blocker],
    warnings: [
      `${PRODUCT_NAME} observability proxy could not reach the internal API.`,
    ],
    generated_at: new Date().toISOString(),
  };
}

export async function GET() {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), getTimeoutMs());

  try {
    const response = await fetch(
      `${getMeituApiBaseURL()}/deerflow/observability/status`,
      {
        cache: "no-store",
        headers: {
          Accept: "application/json",
          "Cache-Control": "no-cache",
          Pragma: "no-cache",
        },
        signal: controller.signal,
      },
    );
    const payload: unknown = await response.json();
    if (payload && typeof payload === "object" && !Array.isArray(payload)) {
      return Response.json(payload);
    }
    return Response.json(
      degradedFallback("meitu_api_observability_status_invalid"),
    );
  } catch {
    return Response.json(
      degradedFallback("meitu_api_observability_status_unreachable"),
    );
  } finally {
    clearTimeout(timeout);
  }
}
