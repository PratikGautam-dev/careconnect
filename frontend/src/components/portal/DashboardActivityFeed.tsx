import { Card } from "@/components/ui/Card";
import { formatTimeOnly } from "@/lib/formatDate";

type ActivityItem = {
  label: string;
  phone: string;
  doctor_name: string;
  department_name: string;
  at: string;
};

export function DashboardActivityFeed({ items }: { items: ActivityItem[] }) {
  return (
    <Card className="p-space-4">
      <h3 className="text-label mb-space-3 font-bold text-ink-900">Today&apos;s activity</h3>
      {items.length === 0 ? (
        <p className="py-space-4 text-center text-[13px] text-ink-400">No activity yet.</p>
      ) : (
        <ul className="space-y-space-3">
          {items.map((item, i) => (
            <li key={i} className="flex items-start gap-space-3 text-[12.5px]">
              <span className="mt-0.5 w-[52px] shrink-0 tabular-nums text-ink-400">{formatTimeOnly(item.at)}</span>
              <div className="min-w-0">
                <p className="truncate font-semibold text-ink-900">{item.label}</p>
                <p className="truncate text-ink-400">
                  {item.phone} · {item.doctor_name} · {item.department_name}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
