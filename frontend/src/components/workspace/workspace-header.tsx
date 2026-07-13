"use client";

import { MessageSquarePlus } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";
import { PRODUCT_DISPLAY_NAME, PRODUCT_SHORT_MARK } from "@/core/branding";
import { useI18n } from "@/core/i18n/hooks";
import { useProjectScope } from "@/core/project-scope/context";
import { env } from "@/env";
import { cn } from "@/lib/utils";

import { ProjectScopePicker } from "./project-scope-picker";

export function WorkspaceHeader({ className }: { className?: string }) {
  const { t } = useI18n();
  const { state } = useSidebar();
  const pathname = usePathname();
  const { workspacePath } = useProjectScope();
  return (
    <>
      <div
        className={cn(
          "group/workspace-header flex min-h-12 flex-col justify-center",
          className,
        )}
      >
        {state === "collapsed" ? (
          <div className="group-has-data-[collapsible=icon]/sidebar-wrapper:-translate-y flex w-full cursor-pointer items-center justify-center">
            <div className="text-primary block pt-1 font-serif group-hover/workspace-header:hidden">
              {PRODUCT_SHORT_MARK}
            </div>
            <SidebarTrigger className="hidden pl-2 group-hover/workspace-header:block" />
          </div>
        ) : (
          <div className="flex flex-col gap-2 py-2">
            <div className="flex items-center justify-between gap-2">
              {env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true" ? (
                <Link href="/" className="text-primary ml-2 font-serif">
                  {PRODUCT_DISPLAY_NAME}
                </Link>
              ) : (
                <div className="text-primary ml-2 cursor-default font-serif">
                  {PRODUCT_DISPLAY_NAME}
                </div>
              )}
              <SidebarTrigger />
            </div>
            <ProjectScopePicker className="mx-2" />
          </div>
        )}
      </div>
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton
            isActive={pathname === "/workspace/chats/new"}
            asChild
          >
            <Link
              className="text-muted-foreground"
              href={workspacePath("/workspace/chats/new")}
            >
              <MessageSquarePlus size={16} />
              <span>{t.sidebar.newChat}</span>
            </Link>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    </>
  );
}
