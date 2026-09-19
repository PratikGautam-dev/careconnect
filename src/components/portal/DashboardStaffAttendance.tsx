import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";

// No real proxy exists -- staff_users.py tracks account-active, not daily
// check-in. Rendered as an explicit empty state (dashes, greyed ring)
// instead of an invented number.
export function DashboardStaffAttendance({ className }: { className?: string }) {
  const circumference = 2 * Math.PI * 40;

  return (
    <Card className={cn("p-space-4 flex flex-col", className)}>
      <h3 className="text-label mb-space-1 text-ink-900 shrink-0 font-bold">
        Staff attendance (today)
      </h3>
      <p className="text-hint mb-space-3 shrink-0">No check-in/attendance tracking exists yet.</p>
      <div className="scrollbar-hide gap-space-4 flex min-h-0 flex-1 items-center overflow-y-auto">
        <div className="relative h-24 w-24 shrink-0">
          <svg viewBox="0 0 100 100" className="h-24 w-24 -rotate-90">
            <circle cx="50" cy="50" r="40" fill="none" stroke="#e1e0d9" strokeWidth="10" />
            <circle
              cx="50"
              cy="50"
              r="40"
              fill="none"
              stroke="#c3c2b7"
              strokeWidth="10"
              strokeDasharray={circumference}
              strokeDashoffset={circumference}
              strokeLinecap="round"
            />
          </svg>
          <div className="text-ink-400 absolute inset-0 flex items-center justify-center text-[15px] font-bold">
            —
          </div>
        </div>
        <ul className="space-y-space-1 flex-1 text-[12.5px]">
          <li className="gap-space-2 text-ink-600 flex items-center">
            <span className="bg-success h-2.5 w-2.5 shrink-0 rounded-full" /> Present{" "}
            <span className="text-ink-400 ml-auto font-semibold">—</span>
          </li>
          <li className="gap-space-2 text-ink-600 flex items-center">
            <span className="bg-error h-2.5 w-2.5 shrink-0 rounded-full" /> Absent{" "}
            <span className="text-ink-400 ml-auto font-semibold">—</span>
          </li>
          <li className="gap-space-2 text-ink-600 flex items-center">
            <span className="bg-clay-500 h-2.5 w-2.5 shrink-0 rounded-full" /> On leave{" "}
            <span className="text-ink-400 ml-auto font-semibold">—</span>
          </li>
        </ul>
      </div>
    </Card>
  );
}
