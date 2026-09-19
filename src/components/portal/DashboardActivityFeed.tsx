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
      <h3 className="text-label mb-space-3 text-ink-900 font-bold">Today&apos;s activity</h3>
      {items.length === 0 ? (
        <p className="py-space-4 text-ink-400 text-center text-[13px]">No activity yet.</p>
      ) : (
        <ul className="space-y-space-3">
          {items.map((item, i) => (
            <li key={i} className="gap-space-3 flex items-start text-[12.5px]">
              <span className="text-ink-400 mt-0.5 w-[52px] shrink-0 tabular-nums">
                {formatTimeOnly(item.at)}
              </span>
              <div className="min-w-0">
                <p className="text-ink-900 truncate font-semibold">{item.label}</p>
                <p className="text-ink-400 truncate">
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
