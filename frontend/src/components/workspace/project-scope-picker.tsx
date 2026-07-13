"use client";

import { useProjectScope } from "@/core/project-scope/context";
import { cn } from "@/lib/utils";

export function ProjectScopePicker({ className }: { className?: string }) {
  const {
    activeProjectId,
    projects,
    projectsError,
    projectsLoading,
    selectProject,
  } = useProjectScope();

  return (
    <label
      className={cn(
        "border-sidebar-border bg-sidebar-accent/35 flex min-w-0 items-center gap-2 rounded-md border px-2 py-1.5 text-xs",
        className,
      )}
    >
      <span className="text-muted-foreground shrink-0">当前项目</span>
      <select
        aria-label="切换项目"
        className="text-foreground min-w-0 flex-1 bg-transparent outline-none"
        disabled={projectsLoading}
        onChange={(event) => selectProject(event.target.value)}
        value={activeProjectId ?? ""}
      >
        <option value="">
          {projectsLoading ? "加载项目中…" : "请选择项目"}
        </option>
        {projects.map((project) => (
          <option key={project.project_id} value={project.project_id}>
            {project.product_name}（{project.project_id}）
          </option>
        ))}
      </select>
      {projectsError && <span className="sr-only">{projectsError}</span>}
    </label>
  );
}
