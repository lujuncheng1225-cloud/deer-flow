import { getBackendBaseURL } from "../config";
import { isStaticWebsiteOnly } from "../static-mode";
import type { AgentThreadState } from "../threads";

const EMPTY_ARTIFACT_PATHS: readonly string[] = [];

const USER_DATA_OUTPUTS_PREFIX = "/mnt/user-data/outputs/";

export function normalizeArtifactFilepath(filepath: string) {
  const trimmed = filepath.trim();
  if (!trimmed || trimmed.startsWith("write-file:")) {
    return trimmed;
  }
  if (trimmed.startsWith(USER_DATA_OUTPUTS_PREFIX)) {
    return trimmed;
  }
  if (trimmed.startsWith("mnt/user-data/outputs/")) {
    return `/${trimmed}`;
  }
  if (trimmed.startsWith("user-data/outputs/")) {
    return `/mnt/${trimmed}`;
  }
  if (trimmed.startsWith("outputs/")) {
    return `/mnt/user-data/${trimmed}`;
  }
  if (!trimmed.startsWith("/")) {
    return `${USER_DATA_OUTPUTS_PREFIX}${trimmed}`;
  }
  return trimmed;
}

export function urlOfArtifact({
  filepath,
  threadId,
  download = false,
  isMock = false,
}: {
  filepath: string;
  threadId: string;
  download?: boolean;
  isMock?: boolean;
}) {
  const artifactPath = normalizeArtifactFilepath(filepath);
  if (isStaticWebsiteOnly()) {
    return staticDemoArtifactURL({
      filepath: artifactPath,
      threadId,
      download,
    });
  }
  if (isMock) {
    return `${getBackendBaseURL()}/mock/api/threads/${threadId}/artifacts${artifactPath}${download ? "?download=true" : ""}`;
  }
  return `${getBackendBaseURL()}/api/threads/${threadId}/artifacts${artifactPath}${download ? "?download=true" : ""}`;
}

export function extractArtifactsFromThread(thread: {
  values: Pick<AgentThreadState, "artifacts">;
}) {
  return thread.values.artifacts ?? EMPTY_ARTIFACT_PATHS;
}

export function resolveArtifactURL(absolutePath: string, threadId: string) {
  const artifactPath = normalizeArtifactFilepath(absolutePath);
  if (isStaticWebsiteOnly()) {
    return staticDemoArtifactURL({ filepath: artifactPath, threadId });
  }
  return `${getBackendBaseURL()}/api/threads/${threadId}/artifacts${artifactPath}`;
}

export function resolveMessageImageURL(
  src: string,
  threadId: string,
  artifactPaths: readonly string[],
) {
  if (src.startsWith("/mnt/")) {
    return resolveArtifactURL(src, threadId);
  }

  const [relativePath = ""] = src.split(/[?#]/, 1);
  const normalizedPath = relativePath.replace(/^(?:\.\/)+/, "");
  if (
    !normalizedPath ||
    normalizedPath.startsWith("/") ||
    /^[a-z][a-z\d+.-]*:/i.test(normalizedPath) ||
    normalizedPath.startsWith("//") ||
    normalizedPath.split("/").includes("..")
  ) {
    return src;
  }

  const matches = artifactPaths.filter((path) =>
    path.endsWith(`/${normalizedPath}`),
  );
  if (matches.length !== 1) {
    return src;
  }

  return `${resolveArtifactURL(matches[0]!, threadId)}${src.slice(relativePath.length)}`;
}

function staticDemoArtifactURL({
  filepath,
  threadId,
  download = false,
}: {
  filepath: string;
  threadId: string;
  download?: boolean;
}) {
  const demoPath = filepath.replace(/^\/mnt\//, "/");
  return `${getBackendBaseURL()}/demo/threads/${threadId}${demoPath}${download ? "?download=true" : ""}`;
}
