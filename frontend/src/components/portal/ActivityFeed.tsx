import { CalendarCheck, CalendarX, RefreshCw } from "lucide-react";
import { Card } from "@/components/ui/Card";

type ActivityItem = {
  label: string;
  phone: string;
  doctor_name: string;
  department_name: string;
  at: string;
};

const ICONS: Record<string, typeof CalendarCheck> = {
  "Booked appointment": CalendarCheck,
  "Cancelled appointment": CalendarX,
  "Rescheduled appointment": RefreshCw,
};

function formatTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, { hour: "numeric", minute: "2-digit" });
}

export function ActivityFeed({ items }: { items: ActivityItem[] }) {
  return (
    <Card className="p-space-4">
      <h3 className="text-label mb-space-3 font-bold text-ink-900">Recent activity</h3>
      {items.length === 0 ? (
        <p className="py-space-4 text-center text-[13px] text-ink-400">Nothing has happened yet.</p>
      ) : (
        <ul className="space-y-space-3">
          {items.map((item, i) => {
            const Icon = ICONS[item.label] || CalendarCheck;
            return (
              <li key={i} className="flex items-start gap-space-3">
                <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600">
                  <Icon size={13} strokeWidth={2} />
                </div>
                <div className="min-w-0 flex-1 text-[12.5px]">
                  <p className="text-ink-900">
                    <span className="font-semibold">{item.phone}</span> — {item.label.toLowerCase()} with{" "}
                    {item.doctor_name} ({item.department_name})
                  </p>
                  <p className="text-hint">{formatTime(item.at)}</p>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
