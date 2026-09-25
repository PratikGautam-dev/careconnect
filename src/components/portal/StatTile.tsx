import { ChevronRight, Minus, TrendingDown, TrendingUp, type LucideIcon } from "lucide-react";
import Link from "next/link";
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
  /** Makes the whole tile a link (e.g. "Teleconsultations" -> the
   * appointments list) -- renders a trailing chevron so it reads as
   * navigable, same idea as the mockup's ">" on every tile. */
  href?: string;
  /** Prepended directly onto the formatted value, e.g. "₹" for a currency
   * tile (Billing's Total Collected/Today's Collection) -- omitted for a
   * plain count tile. */
  prefix?: string;
  /** Stamps a small "Mock" badge on the tile -- for cards whose data has no
   * real backend source yet (e.g. the super-admin dashboard's revenue/
   * subscription tiles, until a billing/plan model exists), so it's visually
   * obvious which numbers on a page are placeholders. Deliberately full
   * color, not greyed out (per explicit feedback) -- the badge alone is the
   * signal. Never paired with `href` -- a mock tile isn't a real navigable
   * destination. */
  mock?: boolean;
};

export function StatTile({
  label,
  value,
  deltaPct,
  upIsGood = true,
  hint = "vs last week",
  icon: Icon,
  tint = "brand",
  href,
  prefix,
  mock = false,
}: Props) {
  const isUp = deltaPct !== null && deltaPct > 0;
  const isDown = deltaPct !== null && deltaPct < 0;
  const isGoodDirection = (isUp && upIsGood) || (isDown && !upIsGood);
  const isBadDirection = (isUp && !upIsGood) || (isDown && upIsGood);

  const body = (
    <div className="gap-space-3 relative flex items-center">
      {mock && (
        <span className="bg-ink-900 absolute -top-2 -right-2 rounded-full px-2 py-0.5 text-[9.5px] font-bold tracking-wide text-white uppercase">
          Mock
        </span>
      )}
      {Icon && (
        <span
          className={cn(
            "flex h-14 w-14 shrink-0 items-center justify-center rounded-full",
            TINT_CLASSES[tint],
          )}
        >
          <Icon size={26} strokeWidth={2} />
        </span>
      )}
      <div className="min-w-0 flex-1">
        <p className="text-label mb-space-1 text-ink-600 truncate font-medium">{label}</p>
        <div className="gap-space-2 flex items-baseline justify-between">
          <span className="text-ink-900 text-[26px] leading-none font-semibold">
            {value === null ? "—" : `${prefix ?? ""}${value.toLocaleString()}`}
          </span>
          {deltaPct !== null && (
            <span
              className={cn(
                "flex shrink-0 items-center gap-0.5 text-[12.5px] font-semibold",
                isGoodDirection && "text-success",
                isBadDirection && "text-error",
                !isUp && !isDown && "text-ink-400",
              )}
            >
              {isUp && <TrendingUp size={13} />}
              {isDown && <TrendingDown size={13} />}
              {!isUp && !isDown && <Minus size={13} />}
              {`${Math.abs(deltaPct)}%`}
            </span>
          )}
        </div>
        {hint && <p className="text-hint mt-space-0.5 truncate">{hint}</p>}
      </div>
      {href && <ChevronRight size={18} className="text-ink-300 shrink-0" />}
    </div>
  );

  if (href) {
    return (
      <Link href={href} className="block">
        <Card className="p-space-4 hover:border-brand-300 transition-colors duration-150">
          {body}
        </Card>
      </Link>
    );
  }

  return <Card className="p-space-4">{body}</Card>;
}
