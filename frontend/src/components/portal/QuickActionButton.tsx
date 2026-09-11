import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/cn";

type Size = "sm" | "md";

// h-* fixed heights (not py-space-N padding) -- "space-2.5" isn't a real
// token in this design system's scale (space-1..10 are whole numbers only),
// so padding-based sizing here was silently a no-op and squashed the button
// down to line-height-only. Matches Button.tsx's own h-10 "md" size.
const SIZE_CLASSES: Record<Size, string> = {
  md: "h-10 gap-space-2 px-space-4 text-[14px]",
  sm: "h-9 gap-space-2 px-space-3 text-[12.5px]",
};

const ICON_SIZE: Record<Size, number> = { md: 16, sm: 14 };

export type Props = {
  label: string;
  icon: LucideIcon;
  href?: string;
  onClick?: () => void;
  disabled?: boolean;
  /** Reflects real toggled-open state (e.g. a "view schedule" panel that's
   * currently expanded) -- not a decorative "primary action" look. */
  active?: boolean;
  size?: Size;
  title?: string;
  className?: string;
};

/** Shared button for every "quick actions" list/grid in the portal -- same
 * bordered outline at rest for every item (nothing reads as pre-selected),
 * with the solid brand fill appearing only on hover/focus (and permanently
 * for a genuinely `active`/toggled item, which is real state, not a look). */
export function QuickActionButton({ label, icon: Icon, href, onClick, disabled, active, size = "md", title, className }: Props) {
  const classes = cn(
    "flex w-full items-center rounded-sm border-2 font-extrabold",
    "transition-colors duration-150 ease-[var(--ease-standard)]",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-2",
    "disabled:pointer-events-none disabled:opacity-50",
    SIZE_CLASSES[size],
    active
      ? "border-brand-600 bg-brand-600 text-white"
      : cn(
          "border-brand-600 text-brand-600 ",
          "hover:border-brand-600 hover:bg-brand-600 hover:text-white",
          "focus-visible:border-brand-600 focus-visible:bg-brand-600 focus-visible:text-white",
          "active:border-brand-700 active:bg-brand-700",
        ),
    className,
  );
  const content = (
    <>
      <Icon size={ICON_SIZE[size]} strokeWidth={2} className="shrink-0" />
      {label}
    </>
  );

  if (href && !disabled) {
    return (
      <Link href={href} className={classes} title={title}>
        {content}
      </Link>
    );
  }

  return (
    <button type="button" onClick={onClick} disabled={disabled ?? (!href && !onClick)} title={title} className={classes}>
      {content}
    </button>
  );
}
