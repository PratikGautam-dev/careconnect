import { Card } from "@/components/ui/Card";

const SAMPLE_APPROVALS = [
  { title: "Doctor leave request", detail: "Sample entry — leave approval isn't a real workflow yet" },
  { title: "Staff leave request", detail: "Sample entry — leave approval isn't a real workflow yet" },
  { title: "Schedule change", detail: "Sample entry — no schedule-change request type exists yet" },
];

// Doctor leave (db/repositories/leave.py) is direct and unmoderated -- no
// pending/approved status, and no staff-leave or schedule-change request
// types exist at all. Shown illustratively rather than dropped.
export function DashboardPendingApprovals() {
  return (
    <Card className="p-space-4">
      <h3 className="text-label mb-space-1 font-bold text-ink-900">Pending approvals</h3>
      <p className="text-hint mb-space-3">No approval workflow exists yet — sample layout only.</p>
      <ul className="space-y-space-3">
        {SAMPLE_APPROVALS.map((item) => (
          <li key={item.title} className="flex items-center justify-between gap-space-2">
            <div className="min-w-0">
              <p className="truncate text-[13px] font-semibold text-ink-900">{item.title}</p>
              <p className="truncate text-[11.5px] text-ink-400">{item.detail}</p>
            </div>
            <span className="shrink-0 rounded-full bg-clay-100 px-space-2 py-0.5 text-[11px] font-semibold text-clay-700">
              Pending
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
