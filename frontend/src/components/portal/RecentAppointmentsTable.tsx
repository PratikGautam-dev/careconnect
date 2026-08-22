import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";

type Appointment = {
  id: number;
  phone: string;
  patient_name: string | null;
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
      <div className="mb-space-3 flex items-center justify-between">
        <h3 className="text-label font-bold text-ink-900">Recent appointments</h3>
        <Link href="/portal/patients" className="text-[12.5px] font-semibold text-brand-600 hover:underline">
          View all patients →
        </Link>
      </div>
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
                  <td className="py-space-2 text-ink-900">
                    <span className="font-semibold">{a.patient_name || a.phone}</span>
                    {a.patient_name && <span className="ml-space-2 text-[12px] text-ink-400">{a.phone}</span>}
                  </td>
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
