import { Lightbulb, TrendingDown, TrendingUp } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";

/** Backend sends each insight as one plain string (see
 * usePortalReportAnalytics.ts's own comment on `insights`), formatted
 * "Title — description" (em dash). Split here rather than asking the
 * backend for structured {title, description} fields, since the reference
 * screenshot's copy ("Appointments Increased — Total appointments are up by
 * 12%...") already reads as one backend-owned sentence, not two fields a
 * frontend should assemble itself. A string with no em dash still renders,
 * just without a bolded title. */
function splitInsight(raw: string): { title: string | null; description: string } {
  const dashIndex = raw.indexOf("—");
  if (dashIndex === -1) return { title: null, description: raw };
  return {
    title: raw.slice(0, dashIndex).trim(),
    description: raw.slice(dashIndex + 1).trim(),
  };
}

// Icon chosen by a light keyword sniff on the insight text -- purely
// cosmetic (which lucide glyph a card gets), never anything the page's
// logic depends on, so a backend copy change can't break rendering.
function iconFor(raw: string) {
  const lower = raw.toLowerCase();
  if (/\b(up|increase|grew|growth|higher|more)\b/.test(lower)) return TrendingUp;
  if (/\b(down|decrease|declin|lower|fewer|drop)\b/.test(lower)) return TrendingDown;
  return Lightbulb;
}

type Props = { insights: string[]; className?: string };

export function KeyInsightsList({ insights, className }: Props) {
  return (
    <Card className={cn("p-space-4", className)}>
      <h3 className="text-label mb-space-4 text-ink-900 font-bold">Key Insights</h3>
      {insights.length === 0 ? (
        <p className="text-ink-400 text-[13px]">No insights for the selected date range.</p>
      ) : (
        <ul className="space-y-space-3">
          {insights.map((raw, i) => {
            const { title, description } = splitInsight(raw);
            const Icon = iconFor(raw);
            return (
              <li
                key={i}
                className="border-line bg-paper p-space-3 gap-space-3 flex rounded-md border"
              >
                <span className="bg-brand-50 text-brand-600 flex h-8 w-8 shrink-0 items-center justify-center rounded-full">
                  <Icon size={16} strokeWidth={2} />
                </span>
                <div className="min-w-0">
                  {title && <p className="text-ink-900 text-[13px] font-bold">{title}</p>}
                  <p className="text-ink-600 text-[12.5px] leading-relaxed">{description}</p>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
