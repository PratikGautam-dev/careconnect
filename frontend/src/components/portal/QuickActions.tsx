import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import { QuickActionButton } from "./QuickActionButton";

export type QuickAction = {
  label: string;
  icon: LucideIcon;
  href?: string;
  onClick?: () => void;
  disabled?: boolean;
  active?: boolean;
  title?: string;
  /** Grid layouts only -- lets one item span the full row (e.g. a wide
   * "Manage leave" tile below a 2-column grid of shorter actions). */
  fullWidth?: boolean;
};

type ListProps = {
  actions: QuickAction[];
  columns?: 1 | 2;
  size?: "sm" | "md";
  className?: string;
  /** Escape hatch for a non-button item that still belongs in the same
   * grid/list (e.g. a "More" dropdown trigger) -- rendered after the array. */
  children?: ReactNode;
};

/** Renders just the row/grid of buttons, with no Card or heading -- for
 * embedding inside a panel that already owns its own heading/wrapper. */
export function QuickActionList({ actions, columns = 1, size, className, children }: ListProps) {
  return (
    <div className={cn(columns === 2 ? "grid grid-cols-2 gap-space-2" : "space-y-space-2", className)}>
      {actions.map((action) => (
        <QuickActionButton key={action.label} {...action} size={size} className={action.fullWidth ? "col-span-2" : undefined} />
      ))}
      {children}
    </div>
  );
}

type Props = ListProps & {
  title?: string;
  /** Applied to the outer Card, not the button list (that's `className`) --
   * e.g. a fixed height so this card matches its siblings in a dashboard
   * row of otherwise differently-sized widgets. */
  cardClassName?: string;
};

/** Standalone "Quick actions" card -- title + Card wrapper + QuickActionList.
 * Use this for a page's own sidebar card; use QuickActionList directly when
 * embedding inside an existing panel (e.g. a detail-view sidebar). */
export function QuickActions({ title = "Quick actions", actions, columns, size, className, cardClassName }: Props) {
  return (
    <Card className={cn("p-space-4", cardClassName)}>
      <h3 className="text-label mb-space-3 font-bold text-ink-900">{title}</h3>
      <QuickActionList actions={actions} columns={columns} size={size} className={className} />
    </Card>
  );
}
