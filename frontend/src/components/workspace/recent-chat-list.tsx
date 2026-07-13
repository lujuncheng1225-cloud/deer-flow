"use client";

import { MessageSquare } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { useProjectScope } from "@/core/project-scope/context";

export function RecentChatList() {
  const pathname = usePathname();
  const { activeProject, conversations, conversationsLoading, workspacePath } =
    useProjectScope();

  return (
    <SidebarGroup>
      <SidebarGroupLabel>最近的对话</SidebarGroupLabel>
      <SidebarGroupContent className="group-data-[collapsible=icon]:pointer-events-none group-data-[collapsible=icon]:-mt-8 group-data-[collapsible=icon]:opacity-0">
        {!activeProject ? (
          <p className="text-muted-foreground px-2 py-1 text-xs">
            请先在顶部选择项目
          </p>
        ) : conversationsLoading ? (
          <p className="text-muted-foreground px-2 py-1 text-xs">
            加载项目会话中…
          </p>
        ) : conversations.length === 0 ? (
          <p className="text-muted-foreground px-2 py-1 text-xs">
            当前项目还没有会话
          </p>
        ) : (
          <SidebarMenu>
            {conversations.map((conversation) => {
              const path = `/workspace/chats/${conversation.sidecar_thread_id}`;
              return (
                <SidebarMenuItem key={conversation.conversation_id}>
                  <SidebarMenuButton isActive={pathname === path} asChild>
                    <Link
                      className="text-muted-foreground min-w-0"
                      href={workspacePath(path)}
                    >
                      <MessageSquare />
                      <span className="truncate">{conversation.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              );
            })}
          </SidebarMenu>
        )}
      </SidebarGroupContent>
    </SidebarGroup>
  );
}
