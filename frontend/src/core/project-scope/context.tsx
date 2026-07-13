"use client";

import { useRouter, useSearchParams } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type PlatformProject = {
  project_id: string;
  product_name: string;
};

export type ProjectConversation = {
  conversation_id: string;
  project_id: string;
  title: string;
  sidecar_thread_id: string;
  updated_at: string;
};

type ProjectSummary = {
  project: PlatformProject;
};

type ProjectScopeValue = {
  activeProject: PlatformProject | null;
  activeProjectId: string | null;
  conversations: ProjectConversation[];
  conversationsLoading: boolean;
  projects: PlatformProject[];
  projectsLoading: boolean;
  projectsError: string | null;
  ensureConversation: (
    threadId: string,
    title: string,
  ) => Promise<ProjectConversation>;
  isThreadInActiveProject: (threadId: string) => boolean;
  selectProject: (projectId: string) => void;
  workspacePath: (path: string) => string;
};

const ProjectScopeContext = createContext<ProjectScopeValue | null>(null);

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? String(payload.detail)
        : `HTTP ${response.status}`;
    throw new Error(detail);
  }
  return payload as T;
}

function withProject(path: string, projectId: string | null): string {
  if (!projectId) return path;
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}project=${encodeURIComponent(projectId)}`;
}

export function ProjectScopeProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const selectedProjectParam = searchParams.get("project")?.trim() ?? null;
  const selectedProjectId = selectedProjectParam === "" ? null : selectedProjectParam;
  const [projects, setProjects] = useState<PlatformProject[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [projectsError, setProjectsError] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ProjectConversation[]>([]);
  const [conversationsLoading, setConversationsLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void requestJson<ProjectSummary[]>("/projects")
      .then((items) => {
        if (cancelled) return;
        setProjects(items.map((item) => item.project));
        setProjectsError(null);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setProjectsError(error instanceof Error ? error.message : "项目列表读取失败");
        }
      })
      .finally(() => {
        if (!cancelled) setProjectsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedProjectId) {
      setConversations([]);
      setConversationsLoading(false);
      return;
    }
    let cancelled = false;
    setConversationsLoading(true);
    void requestJson<ProjectConversation[]>(
      `/projects/${encodeURIComponent(selectedProjectId)}/conversations`,
    )
      .then((items) => {
        if (!cancelled) setConversations(items);
      })
      .catch(() => {
        if (!cancelled) setConversations([]);
      })
      .finally(() => {
        if (!cancelled) setConversationsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedProjectId]);

  const activeProject = useMemo(
    () =>
      projects.find((project) => project.project_id === selectedProjectId) ??
      null,
    [projects, selectedProjectId],
  );

  const workspacePath = useCallback(
    (path: string) => withProject(path, activeProject?.project_id ?? null),
    [activeProject?.project_id],
  );

  const selectProject = useCallback(
    (projectId: string) => {
      if (!projectId) {
        router.replace("/workspace/chats/new");
        return;
      }
      router.replace(withProject("/workspace/chats/new", projectId));
    },
    [router],
  );

  const ensureConversation = useCallback(
    async (threadId: string, title: string) => {
      if (!activeProject) {
        throw new Error("请先选择项目，再发起会话");
      }
      const existing = conversations.find(
        (conversation) => conversation.sidecar_thread_id === threadId,
      );
      if (existing) return existing;
      const conversation = await requestJson<ProjectConversation>(
        `/projects/${encodeURIComponent(activeProject.project_id)}/conversations`,
        {
          method: "POST",
          body: JSON.stringify({
            title: title.trim().slice(0, 120) || "新对话",
            sidecar_thread_id: threadId,
          }),
        },
      );
      setConversations((items) => [
        conversation,
        ...items.filter(
          (item) => item.conversation_id !== conversation.conversation_id,
        ),
      ]);
      return conversation;
    },
    [activeProject, conversations],
  );

  const isThreadInActiveProject = useCallback(
    (threadId: string) =>
      conversations.some(
        (conversation) => conversation.sidecar_thread_id === threadId,
      ),
    [conversations],
  );

  const value = useMemo<ProjectScopeValue>(
    () => ({
      activeProject,
      activeProjectId: activeProject?.project_id ?? null,
      conversations,
      conversationsLoading,
      ensureConversation,
      isThreadInActiveProject,
      projects,
      projectsError,
      projectsLoading,
      selectProject,
      workspacePath,
    }),
    [
      activeProject,
      conversations,
      conversationsLoading,
      ensureConversation,
      isThreadInActiveProject,
      projects,
      projectsError,
      projectsLoading,
      selectProject,
      workspacePath,
    ],
  );

  return (
    <ProjectScopeContext.Provider value={value}>
      {children}
    </ProjectScopeContext.Provider>
  );
}

export function useProjectScope(): ProjectScopeValue {
  const value = useContext(ProjectScopeContext);
  if (!value) {
    throw new Error("useProjectScope must be used inside ProjectScopeProvider");
  }
  return value;
}
