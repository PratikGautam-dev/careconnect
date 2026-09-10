import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/cn";

type Variant = "filled" | "outline";

const VARIANT_CLASSES: Record<Variant, string> = {
  filled: "bg-brand-600 text-white shadow-[var(--shadow-sm)] hover:bg-brand-700 active:bg-brand-800",
  outline: "border-2 border-brand-300 text-brand-700 hover:bg-brand-50 active:bg-brand-100",
};

type Props = {
  label: string;
  icon: LucideIcon;
  variant?: Variant;
} & ({ href: string; disabled?: never } | { href?: never; disabled: true });

/** Shared pill button for dashboard/portal "quick action" lists -- one
 * filled (the primary action) plus any number outlined in the same brand
 * color, per the quick-actions reference design. */
export function QuickActionButton({ label, icon: Icon, variant = "outline", ...action }: Props) {
  const classes = cn(
    "flex w-full items-center gap-space-2 rounded-sm px-space-4 py-space-2 text-[14px] font-semibold",
    "transition-colors duration-150 ease-[var(--ease-standard)]",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-2",
    "disabled:pointer-events-none disabled:opacity-50",
    VARIANT_CLASSES[variant],
  );
  const content = (
    <>
      <Icon size={16} strokeWidth={2} className="shrink-0" />
      {label}
    </>
  );

  if (action.disabled) {
    return (
      <button type="button" disabled title="Coming soon" className={classes}>
        {content}
      </button>
    );
  }

  return (
    <Link href={action.href} className={classes}>
      {content}
    </Link>
  );
}
