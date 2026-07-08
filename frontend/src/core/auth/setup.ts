import { parseAuthError } from "./types";

export type SetupStatusResponse = {
  needs_setup?: boolean;
  needs_local_admin_setup?: boolean;
  admin_exists?: boolean;
  auth_mode?: "local" | "mixed" | "oauth_only" | string;
  local_auth_enabled?: boolean;
  oauth_login_available?: boolean;
  sso_login_available?: boolean;
};

export type SetupStatusCheck = {
  checked: boolean;
  status: SetupStatusResponse | null;
};

export const setupStatusFetchInit = {
  cache: "no-store",
  credentials: "include",
} satisfies RequestInit;

export async function fetchSetupStatus(): Promise<SetupStatusResponse> {
  const response = await fetch(
    "/api/v1/auth/setup-status",
    setupStatusFetchInit,
  );
  if (!response.ok) {
    throw new Error(`setup-status failed: ${response.status}`);
  }
  return (await response.json()) as SetupStatusResponse;
}

export function isSystemAlreadyInitializedError(data: unknown): boolean {
  return parseAuthError(data).code === "system_already_initialized";
}

export function canCreateRegularAccount(check: SetupStatusCheck): boolean {
  return (
    check.checked &&
    check.status?.local_auth_enabled !== false &&
    check.status?.needs_local_admin_setup !== true &&
    check.status?.needs_setup !== true
  );
}
