"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import { Plus, Send, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PortalSidebar } from "@/components/portal/PortalSidebar";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { cn } from "@/lib/cn";
import { portalFetch } from "@/lib/portalAuth";

const DEFAULT_CANCEL_MESSAGE = "Your appointment has been cancelled.";

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
  const [cancelPanelId, setCancelPanelId] = useState<number | null>(null);
  const [cancelMessage, setCancelMessage] = useState(DEFAULT_CANCEL_MESSAGE);

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

  function openCancelPanel(id: number) {
    setCancelPanelId(id);
    setCancelMessage(DEFAULT_CANCEL_MESSAGE);
  }

  function closeCancelPanel() {
    setCancelPanelId(null);
  }

  async function handleCancel(id: number) {
    setCancellingId(id);
    const result = await portalFetch(`/api/portal/bookings/${id}/cancel`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: cancelMessage.trim() }),
    });
    setCancellingId(null);
    setCancelPanelId(null);
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
                    <Fragment key={a.id}>
                      <tr className={cn("border-b border-line last:border-0", cancelPanelId === a.id && "border-b-0")}>
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
                          {a.status === "booked" && cancelPanelId !== a.id && (
                            <button
                              type="button"
                              onClick={() => openCancelPanel(a.id)}
                              className="text-[12.5px] font-semibold text-error hover:underline"
                            >
                              Cancel
                            </button>
                          )}
                        </td>
                      </tr>
                      {cancelPanelId === a.id && (
                        <tr className="border-b border-line last:border-0">
                          <td colSpan={7} className="pb-space-3">
                            <div className="rounded-lg border border-line bg-paper p-space-3">
                              <label htmlFor={`cancel-msg-${a.id}`} className="mb-space-2 block text-[12px] font-semibold text-ink-600">
                                Message to send {a.phone} on WhatsApp
                              </label>
                              <textarea
                                id={`cancel-msg-${a.id}`}
                                value={cancelMessage}
                                onChange={(e) => setCancelMessage(e.target.value)}
                                rows={2}
                                className="mb-space-2 h-16 w-full resize-none rounded-md border border-line bg-card px-space-3 py-space-2 text-[13px] text-ink-900 outline-none focus:border-brand-400"
                              />
                              <div className="flex gap-space-2">
                                <Button
                                  size="md"
                                  onClick={() => handleCancel(a.id)}
                                  disabled={cancellingId === a.id}
                                  className="bg-error hover:bg-error/90 active:bg-error/80"
                                >
                                  <Send size={13} /> {cancellingId === a.id ? "Cancelling…" : "Send & cancel"}
                                </Button>
                                <Button size="md" variant="secondary" onClick={closeCancelPanel} disabled={cancellingId === a.id}>
                                  <X size={13} /> Dismiss
                                </Button>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
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
