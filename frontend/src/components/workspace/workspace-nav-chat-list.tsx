"use client";

import { CalendarClock, MessagesSquare } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  SidebarGroup,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { useI18n } from "@/core/i18n/hooks";
import { useProjectScope } from "@/core/project-scope/context";

import { resetThreadChatForNewConversation } from "./chats/use-thread-chat";

export function WorkspaceNavChatList() {
  const { t } = useI18n();
  const pathname = usePathname();
  const { workspacePath } = useProjectScope();
  const newChatPath = workspacePath("/workspace/chats/new");
  return (
    <SidebarGroup className="pt-1">
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton
            isActive={pathname.startsWith("/workspace/chats")}
            asChild
          >
            <Link
              className="text-muted-foreground"
              href={newChatPath}
              onClick={() => resetThreadChatForNewConversation(newChatPath)}
            >
              <MessagesSquare />
              <span>{t.sidebar.chats}</span>
            </Link>
          </SidebarMenuButton>
        </SidebarMenuItem>
        <SidebarMenuItem>
          <SidebarMenuButton
            isActive={pathname.startsWith("/workspace/scheduled-tasks")}
            asChild
          >
            <Link
              className="text-muted-foreground"
              href="/workspace/scheduled-tasks"
            >
              <CalendarClock />
              <span>{t.sidebar.scheduledTasks}</span>
            </Link>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    </SidebarGroup>
  );
}
