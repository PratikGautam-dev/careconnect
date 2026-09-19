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
    <div
      className={cn(
        "mb-space-5 gap-space-3 flex flex-wrap items-center justify-between",
        className,
      )}
    >
      <div>
        <h1 className="text-display">{title}</h1>
        {description && <p className="mt-space-1 text-ink-400 text-[13px]">{description}</p>}
      </div>
      {actions && <div className="gap-space-2 flex flex-wrap items-center">{actions}</div>}
    </div>
  );
}
