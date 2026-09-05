import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

type PageHeaderProps = {
  title: ReactNode;
  description?: ReactNode;
  /** Buttons/controls for this page, e.g. "Add doctor" -- rendered right-aligned. */
  actions?: ReactNode;
  className?: string;
};

export function PageHeader({ title, description, actions, className }: PageHeaderProps) {
  return (
    <div className={cn("mb-space-5 flex flex-wrap items-center justify-between gap-space-3", className)}>
      <div>
        <h1 className="text-display">{title}</h1>
        {description && <p className="mt-space-1 text-[13px] text-ink-400">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-space-2">{actions}</div>}
    </div>
  );
}
