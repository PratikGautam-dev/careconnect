import { Minus, TrendingDown, TrendingUp } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";

type Props = {
  label: string;
  value: number;
  deltaPct: number | null;
  /** No-shows: an increase is bad, so up/down colors invert relative to the
   * other tiles (dataviz skill: "delta color = direction × whether up is
   * good", not a flat green-up/red-down rule). */
  upIsGood?: boolean;
};

export function StatTile({ label, value, deltaPct, upIsGood = true }: Props) {
  const isUp = deltaPct !== null && deltaPct > 0;
  const isDown = deltaPct !== null && deltaPct < 0;
  const isGoodDirection = (isUp && upIsGood) || (isDown && !upIsGood);
  const isBadDirection = (isUp && !upIsGood) || (isDown && upIsGood);

  return (
    <Card className="p-space-4">
      <p className="text-label mb-space-2 font-medium text-ink-600">{label}</p>
      <div className="flex items-baseline gap-space-2">
        <span className="text-[28px] leading-none font-semibold text-ink-900">{value.toLocaleString()}</span>
        <span
          className={cn(
            "flex items-center gap-0.5 text-[12.5px] font-semibold",
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
      <p className="text-hint mt-space-1">vs last week</p>
    </Card>
  );
}
