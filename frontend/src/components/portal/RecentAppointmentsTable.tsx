import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";

type Appointment = {
  id: number;
  phone: string;
  department_name: string;
  doctor_name: string;
  scheduled_at: string;
  status: string;
  source: string;
};

const STATUS_STYLES: Record<string, string> = {
  booked: "bg-success-tint text-success",
  cancelled: "bg-error-tint text-error",
  rescheduled: "bg-clay-100 text-clay-700",
};

const STATUS_LABELS: Record<string, string> = {
  booked: "Confirmed",
  cancelled: "Cancelled",
  rescheduled: "Rescheduled",
};

function formatTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function RecentAppointmentsTable({ appointments }: { appointments: Appointment[] }) {
  return (
    <Card className="p-space-4">
      <h3 className="text-label mb-space-3 font-bold text-ink-900">Recent appointments</h3>
      {appointments.length === 0 ? (
        <p className="py-space-4 text-center text-[13px] text-ink-400">No appointments yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b border-line text-[11.5px] text-ink-400 uppercase">
                <th className="pb-space-2 font-semibold">Time</th>
                <th className="pb-space-2 font-semibold">Patient</th>
                <th className="pb-space-2 font-semibold">Doctor</th>
                <th className="pb-space-2 font-semibold">Department</th>
                <th className="pb-space-2 font-semibold">Status</th>
              </tr>
            </thead>
            <tbody>
              {appointments.map((a) => (
                <tr key={a.id} className="border-b border-line last:border-0">
                  <td className="py-space-2 whitespace-nowrap tabular-nums text-ink-600">
                    {formatTime(a.scheduled_at)}
                  </td>
                  <td className="py-space-2 text-ink-900">{a.phone}</td>
                  <td className="py-space-2 text-ink-600">{a.doctor_name}</td>
                  <td className="py-space-2 text-ink-600">{a.department_name}</td>
                  <td className="py-space-2">
                    <span
                      className={cn(
                        "rounded-full px-space-2 py-0.5 text-[11px] font-semibold",
                        STATUS_STYLES[a.status] || "bg-black/[0.04] text-ink-600",
                      )}
                    >
                      {STATUS_LABELS[a.status] || a.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
