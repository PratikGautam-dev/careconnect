import Link from "next/link";
import { cn } from "@/lib/cn";

type ButtonVariant = "primary" | "secondary" | "ghost";
type ButtonSize = "md" | "lg";

const base =
  "inline-flex items-center justify-center gap-space-2 rounded-md font-semibold " +
  "transition-[background-color,border-color,color,box-shadow,transform] duration-150 ease-[var(--ease-standard)] " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-2 " +
  "disabled:pointer-events-none disabled:opacity-50 active:translate-y-px";

// Primary/secondary/ghost are visually unambiguous on purpose: primary is
// the only one with a filled, colored surface -- secondary and ghost both
// read as lower-emphasis, with secondary (outlined) one step above ghost
// (text-only) so a screen with all three never leaves you guessing which
// action is "the" action.
const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-brand-600 text-white shadow-[var(--shadow-sm)] " +
    "hover:bg-brand-700 hover:shadow-[var(--shadow-md)] " +
    "active:bg-brand-800",
  secondary:
    "bg-card text-ink-900 border border-line shadow-[var(--shadow-sm)] " +
    "hover:border-brand-300 hover:bg-brand-50 " +
    "active:bg-brand-100",
  ghost:
    "bg-transparent text-ink-600 " +
    "hover:bg-black/[0.04] hover:text-ink-900 " +
    "active:bg-black/[0.06]",
};

const sizes: Record<ButtonSize, string> = {
  md: "h-10 px-space-4 text-[14px]",
  lg: "h-14 px-space-5 text-[16px]",
};

type CommonProps = {
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
  children: React.ReactNode;
};

type ButtonAsButton = CommonProps &
  React.ButtonHTMLAttributes<HTMLButtonElement> & { href?: undefined };

type ButtonAsLink = CommonProps &
  Omit<React.AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & { href: string };

export function Button({
  variant = "primary",
  size = "md",
  className,
  children,
  ...props
}: ButtonAsButton | ButtonAsLink) {
  const classes = cn(base, variants[variant], sizes[size], className);

  if ("href" in props && props.href) {
    const { href, ...rest } = props as ButtonAsLink;
    return (
      <Link href={href} className={classes} {...rest}>
        {children}
      </Link>
    );
  }

  return (
    <button className={classes} {...(props as React.ButtonHTMLAttributes<HTMLButtonElement>)}>
      {children}
    </button>
  );
}
