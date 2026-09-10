import { Minus, TrendingDown, TrendingUp, type LucideIcon } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";

type Tint = "brand" | "success" | "error" | "clay";

const TINT_CLASSES: Record<Tint, string> = {
  brand: "bg-brand-50 text-brand-600",
  success: "bg-success-tint text-success",
  error: "bg-error-tint text-error",
  clay: "bg-clay-100 text-clay-700",
};

type Props = {
  label: string;
  /** null renders "—" -- for tiles the backend has no real number for yet
   * (see `hint` in that case: it should say why, e.g. "No data source yet"). */
  value: number | null;
  deltaPct: number | null;
  /** No-shows: an increase is bad, so up/down colors invert relative to the
   * other tiles (dataviz skill: "delta color = direction × whether up is
   * good", not a flat green-up/red-down rule). */
  upIsGood?: boolean;
  /** "Upcoming appointments" is a live snapshot count, not a daily rate --
   * "vs last week" doesn't mean anything for it, so callers without a real
   * comparison can override the footer text (or hide it with ""). */
  hint?: string;
  icon?: LucideIcon;
  tint?: Tint;
};

export function StatTile({ label, value, deltaPct, upIsGood = true, hint = "vs last week", icon: Icon, tint = "brand" }: Props) {
  const isUp = deltaPct !== null && deltaPct > 0;
  const isDown = deltaPct !== null && deltaPct < 0;
  const isGoodDirection = (isUp && upIsGood) || (isDown && !upIsGood);
  const isBadDirection = (isUp && !upIsGood) || (isDown && upIsGood);

  return (
    <Card className="p-space-4">
      <div className="flex items-center gap-space-3">
        {Icon && (
          <span className={cn("flex h-14 w-14 shrink-0 items-center justify-center rounded-full", TINT_CLASSES[tint])}>
            <Icon size={26} strokeWidth={2} />
          </span>
        )}
        <div className="min-w-0 flex-1">
          <p className="text-label mb-space-1 truncate font-medium text-ink-600">{label}</p>
          <div className="flex items-baseline justify-between gap-space-2">
            <span className="text-[26px] leading-none font-semibold text-ink-900">
              {value === null ? "—" : value.toLocaleString()}
            </span>
            <span
              className={cn(
                "flex shrink-0 items-center gap-0.5 text-[12.5px] font-semibold",
                isGoodDirection && "text-success",
                isBadDirection && "text-error",
                deltaPct === null && "text-ink-400",
              )}
            >
              {isUp && <TrendingUp size={13} />}
              {isDown && <TrendingDown size={13} />}
              {deltaPct === null && <Minus size={13} />}
              {deltaPct === null ? "—" : `${Math.abs(deltaPct)}%`}
            </span>
          </div>
          {hint && <p className="text-hint mt-space-0.5 truncate">{hint}</p>}
        </div>
      </div>
    </Card>
  );
}
