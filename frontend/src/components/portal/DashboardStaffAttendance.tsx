import { Card } from "@/components/ui/Card";

// No real proxy exists -- staff_users.py tracks account-active, not daily
// check-in. Rendered as an explicit empty state (dashes, greyed ring)
// instead of an invented number.
export function DashboardStaffAttendance() {
  const circumference = 2 * Math.PI * 40;

  return (
    <Card className="p-space-4">
      <h3 className="text-label mb-space-1 font-bold text-ink-900">Staff attendance (today)</h3>
      <p className="text-hint mb-space-3">No check-in/attendance tracking exists yet.</p>
      <div className="flex items-center gap-space-4">
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
          <div className="absolute inset-0 flex items-center justify-center text-[15px] font-bold text-ink-400">—</div>
        </div>
        <ul className="flex-1 space-y-space-1 text-[12.5px]">
          <li className="flex items-center gap-space-2 text-ink-600">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-success" /> Present <span className="ml-auto font-semibold text-ink-400">—</span>
          </li>
          <li className="flex items-center gap-space-2 text-ink-600">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-error" /> Absent <span className="ml-auto font-semibold text-ink-400">—</span>
          </li>
          <li className="flex items-center gap-space-2 text-ink-600">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-clay-500" /> On leave <span className="ml-auto font-semibold text-ink-400">—</span>
          </li>
        </ul>
      </div>
    </Card>
  );
}
