import { cn } from "@/lib/cn";

type BadgeTone = "brand" | "clay" | "success" | "neutral";

const tones: Record<BadgeTone, string> = {
  brand: "bg-brand-50 text-brand-700",
  clay: "bg-clay-100 text-clay-700",
  success: "bg-success-tint text-success",
  neutral: "bg-black/[0.04] text-ink-600",
};

export function Badge({
  tone = "clay",
  className,
  children,
}: {
  tone?: BadgeTone;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "gap-space-1 px-space-3 inline-flex items-center rounded-full py-1 text-[11px] font-bold tracking-wide uppercase",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
