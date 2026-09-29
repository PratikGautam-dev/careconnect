import { ChevronRight, type LucideIcon } from "lucide-react";
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
  value: number | null;
  icon?: LucideIcon;
  tint?: Tint;
  href?: string;
  prefix?: string;
  mock?: boolean;
  hint?: string;
};

export function StatTile({
  label,
  value,
  icon: Icon,
  tint = "brand",
  href,
  prefix,
  mock = false,
  hint,
}: Props) {
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
        <span className="text-ink-900 text-[26px] leading-none font-semibold">
          {value === null ? "—" : `${prefix ?? ""}${value.toLocaleString()}`}
        </span>
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
