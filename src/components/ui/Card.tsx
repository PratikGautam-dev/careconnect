import { cn } from "@/lib/cn";

type CardProps = React.HTMLAttributes<HTMLDivElement> & {
  /** resting = default card elevation. interactive = adds a hover lift for
   * clickable cards (tier cards, list rows). active = the current/selected
   * state's stronger elevation (e.g. the wizard's current-step card). */
  elevation?: "resting" | "interactive" | "active";
};

export function Card({ elevation = "resting", className, children, ...props }: CardProps) {
  return (
    <div
      className={cn(
        "rounded-lg border border-line bg-card shadow-[var(--shadow-sm)] transition-[box-shadow,transform,border-color] duration-150 ease-[var(--ease-standard)]",
        elevation === "interactive" &&
          "cursor-pointer hover:-translate-y-0.5 hover:border-brand-200 hover:shadow-[var(--shadow-md)] active:translate-y-0",
        elevation === "active" && "border-brand-300 shadow-[var(--shadow-lg)]",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
