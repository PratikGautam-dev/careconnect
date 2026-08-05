"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PortalSidebar } from "@/components/portal/PortalSidebar";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { cn } from "@/lib/cn";
import { portalFetch } from "@/lib/portalAuth";

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
const STATUS_LABELS: Record<string, string> = { booked: "Confirmed", cancelled: "Cancelled", rescheduled: "Rescheduled" };
const SOURCE_LABELS: Record<string, string> = { whatsapp: "WhatsApp", staff: "Walk-in" };

function formatTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export default function PortalAppointmentsPage() {
  const router = useRouter();
  const { hospital, ready } = usePortalGuard();
  const [appointments, setAppointments] = useState<Appointment[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cancellingId, setCancellingId] = useState<number | null>(null);

  const load = useCallback(async () => {
    const result = await portalFetch("/api/portal/bookings");
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    setAppointments((result.data as { appointments: Appointment[] }).appointments);
  }, [router]);

  useEffect(() => {
    if (ready) load();
  }, [ready, load]);

  async function handleCancel(id: number) {
    setCancellingId(id);
    const result = await portalFetch(`/api/portal/bookings/${id}/cancel`, { method: "POST" });
    setCancellingId(null);
    if (result.ok) load();
  }

  return (
    <div className="flex min-h-screen bg-paper">
      <PortalSidebar hospital={hospital} active="appointments" />
      <main className="flex-1 overflow-y-auto p-space-6">
        <div className="mb-space-5 flex items-center justify-between">
          <h1 className="text-display">Appointments</h1>
          <Button href="/portal/new-booking">
            <Plus size={15} /> New booking
          </Button>
        </div>

        {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

        <Card className="p-space-4">
          {!appointments ? (
            <p className="py-space-4 text-center text-[13px] text-ink-400">Loading…</p>
          ) : appointments.length === 0 ? (
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
                    <th className="pb-space-2 font-semibold">Source</th>
                    <th className="pb-space-2 font-semibold">Status</th>
                    <th className="pb-space-2 font-semibold"></th>
                  </tr>
                </thead>
                <tbody>
                  {appointments.map((a) => (
                    <tr key={a.id} className="border-b border-line last:border-0">
                      <td className="py-space-2 whitespace-nowrap tabular-nums text-ink-600">{formatTime(a.scheduled_at)}</td>
                      <td className="py-space-2 text-ink-900">{a.phone}</td>
                      <td className="py-space-2 text-ink-600">{a.doctor_name}</td>
                      <td className="py-space-2 text-ink-600">{a.department_name}</td>
                      <td className="py-space-2 text-ink-600">{SOURCE_LABELS[a.source] || a.source}</td>
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
                      <td className="py-space-2 text-right">
                        {a.status === "booked" && (
                          <button
                            type="button"
                            disabled={cancellingId === a.id}
                            onClick={() => handleCancel(a.id)}
                            className="text-[12.5px] font-semibold text-error hover:underline disabled:opacity-50"
                          >
                            {cancellingId === a.id ? "Cancelling…" : "Cancel"}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </main>
    </div>
  );
}
