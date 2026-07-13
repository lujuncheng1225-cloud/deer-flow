"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Input } from "@/components/ui/input";
import {
  WorkspaceBody,
  WorkspaceContainer,
  WorkspaceHeader,
} from "@/components/workspace/workspace-container";
import { useI18n } from "@/core/i18n/hooks";
import { useProjectScope } from "@/core/project-scope/context";
import { formatTimeAgo } from "@/core/utils/datetime";

export default function ChatsPage() {
  const { t } = useI18n();
  const { activeProject, conversations, conversationsLoading, workspacePath } =
    useProjectScope();
  const [search, setSearch] = useState("");

  useEffect(() => {
    document.title = `${t.pages.chats} - ${t.pages.appName}`;
  }, [t.pages.chats, t.pages.appName]);

  const filteredConversations = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    if (!normalizedSearch) return conversations;
    return conversations.filter((conversation) =>
      conversation.title.toLowerCase().includes(normalizedSearch),
    );
  }, [conversations, search]);

  return (
    <WorkspaceContainer>
      <WorkspaceHeader />
      <WorkspaceBody>
        <div className="flex size-full flex-col">
          <header className="flex shrink-0 items-center justify-center pt-8">
            <Input
              type="search"
              className="h-12 w-full max-w-(--container-width-md) text-xl"
              placeholder={t.chats.searchChats}
              autoFocus
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </header>
          <main className="min-h-0 flex-1">
            <div className="mx-auto flex size-full max-w-(--container-width-md) flex-col py-4">
              {!activeProject ? (
                <p className="text-muted-foreground p-4 text-sm">
                  请先选择项目，再查看项目会话。
                </p>
              ) : conversationsLoading ? (
                <p className="text-muted-foreground p-4 text-sm">
                  加载项目会话中…
                </p>
              ) : filteredConversations.length === 0 ? (
                <p className="text-muted-foreground p-4 text-sm">
                  当前项目没有匹配的会话。
                </p>
              ) : (
                filteredConversations.map((conversation) => (
                  <Link
                    key={conversation.conversation_id}
                    href={workspacePath(
                      `/workspace/chats/${conversation.sidecar_thread_id}`,
                    )}
                  >
                    <div className="flex flex-col gap-2 border-b p-4">
                      <div className="min-w-0 truncate">
                        {conversation.title}
                      </div>
                      <div className="text-muted-foreground text-sm">
                        {formatTimeAgo(conversation.updated_at)}
                      </div>
                    </div>
                  </Link>
                ))
              )}
            </div>
          </main>
        </div>
      </WorkspaceBody>
    </WorkspaceContainer>
  );
}
