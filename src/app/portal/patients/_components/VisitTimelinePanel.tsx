"use client";

import { useMemo, useState } from "react";
import {
  Activity, CalendarCheck, CalendarClock, ChevronDown, ChevronUp, Download, FileEdit, Filter,
  Pill, Printer, Receipt, StickyNote, Video,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Textarea } from "@/components/ui/Input";
import { StatTile } from "@/components/portal/StatTile";
import { PatientStatTileRow } from "./PatientStatTileRow";
import { cn } from "@/lib/cn";
import { formatDate, formatShortDateTime } from "@/lib/formatDate";
import { TYPE_LABELS } from "@/hooks/useAppointments";
import type { BillingRow } from "@/hooks/useBillingOverview";
import type { Note, Visit } from "@/hooks/usePatientDetail";
import type { Prescription } from "@/hooks/usePharmacyPrescriptions";
import { STATUS_LABELS } from "../[id]/_components/visit-history-columns";

const VISIT_STATUS_BADGE_TONE: Record<string, "success" | "clay" | "neutral"> = {
  booked: "clay", attended: "success", cancelled: "neutral", rescheduled: "clay", no_show: "neutral",
};
const OUTCOME_LABELS: Record<string, string> = {
  attended: "Consulted", booked: "Scheduled", cancelled: "Cancelled", rescheduled: "Rescheduled", no_show: "No-show",
};
const OUTCOME_TONES: Record<string, "success" | "clay" | "neutral"> = {
  attended: "success", booked: "clay", cancelled: "neutral", rescheduled: "clay", no_show: "neutral",
};

type FilterKey = "all" | "appointments" | "prescriptions" | "billing" | "notes";
const FILTERS: { key: FilterKey; label: string; icon: typeof CalendarCheck }[] = [
  { key: "all", label: "All Events", icon: Filter },
  { key: "appointments", label: "Appointments", icon: CalendarCheck },
  { key: "prescriptions", label: "Prescriptions", icon: Pill },
  { key: "billing", label: "Billing", icon: Receipt },
  { key: "notes", label: "Notes", icon: StickyNote },
];

function visitTitle(v: Visit): string {
  if (v.appointment_type_id === "tele") return "Tele-consultation";
  if (v.appointment_type_id === "daycare") return "Daycare Visit";
  // No type recorded at all (a legacy booking) reads as "new" for display,
  // same as the appointments table's own TYPE_ICONS/TYPE_STYLES fallback.
  return `OPD Visit – ${TYPE_LABELS[v.appointment_type_id || "new"] ?? "New Consultation"}`;
}

type VisitItem = { kind: "visit"; date: Date; visit: Visit; prescription: Prescription | null; bill: BillingRow | null; note: Note | null };
type NoteItem = { kind: "note"; date: Date; note: Note };
type TimelineItem = VisitItem | NoteItem;

type Props = {
  patientId: number;
  patientName: string;
  visitHistory: Visit[];
  notes: Note[];
  prescriptions: Prescription[];
  bills: BillingRow[];
  generalNoteDraft: string;
  setGeneralNoteDraft: (v: string) => void;
  savingGeneralNote: boolean;
  onAddNote: () => void;
  onOpenFollowup: (v: Visit) => void;
};

/** Patient Details page's "Visit Timeline" tab -- a single chronological
 * feed merging appointments (visit_history), the prescription/bill each
 * one produced, its own per-visit note, and every standalone general note
 * (appointment_id null) into one scrollable history. Built entirely from
 * data the other tabs already fetch -- no new backend endpoint. */
export function VisitTimelinePanel({
  patientId, patientName, visitHistory, notes, prescriptions, bills,
  generalNoteDraft, setGeneralNoteDraft, savingGeneralNote, onAddNote, onOpenFollowup,
}: Props) {
  const [filter, setFilter] = useState<FilterKey>("all");
  const [sortAsc, setSortAsc] = useState(false);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [noteComposerOpen, setNoteComposerOpen] = useState(false);

  const items: TimelineItem[] = useMemo(() => {
    const visitItems: VisitItem[] = visitHistory.map((v) => ({
      kind: "visit",
      date: new Date(v.scheduled_at),
      visit: v,
      prescription: prescriptions.find((p) => p.appointment_id === v.id) || null,
      bill: bills.find((b) => b.bill_type === "appointment" && b.appointment_id === v.id) || null,
      note: notes.find((n) => n.appointment_id === v.id) || null,
    }));
    const noteItems: NoteItem[] = notes
      .filter((n) => n.appointment_id === null)
      .map((n) => ({ kind: "note", date: new Date(n.created_at), note: n }));
    return [...visitItems, ...noteItems];
  }, [visitHistory, prescriptions, bills, notes]);

  const filtered = items.filter((item) => {
    if (filter === "all") return true;
    if (filter === "notes") return item.kind === "note";
    if (item.kind === "note") return false;
    if (filter === "appointments") return true;
    if (filter === "prescriptions") return !!item.prescription;
    if (filter === "billing") return !!item.bill;
    return true;
  });
  const sorted = [...filtered].sort((a, b) => (sortAsc ? a.date.getTime() - b.date.getTime() : b.date.getTime() - a.date.getTime()));

  const procedureCount = visitHistory.filter((v) => v.appointment_type_id === "daycare").length;
  const nextFollowUp = visitHistory
    .filter((v) => v.followup_valid_until && new Date(v.followup_valid_until) >= new Date())
    .sort((a, b) => new Date(a.followup_valid_until!).getTime() - new Date(b.followup_valid_until!).getTime())[0];
  const lastVisit = visitHistory[0] ?? null;

  function toggleCollapsed(id: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function handleExportSummary() {
    const lines = [
      `Visit Timeline -- ${patientName}`,
      `Generated ${formatDate(new Date().toISOString())}`,
      "",
      ...sorted.map((item) => {
        if (item.kind === "note") return `${formatShortDateTime(item.note.created_at)} -- Note: ${item.note.note_text}`;
        const v = item.visit;
        const parts = [`${formatShortDateTime(v.scheduled_at)} -- ${visitTitle(v)} [${STATUS_LABELS[v.status] ?? v.status}]`, `  Doctor: ${v.doctor_name || "—"} | Department: ${v.department_name || "—"}`];
        if (item.prescription) parts.push(`  Prescription: RX${item.prescription.id}`);
        if (item.bill) parts.push(`  Bill: ${item.bill.invoice_ref} (${item.bill.payment_status})`);
        if (item.note) parts.push(`  Note: ${item.note.note_text}`);
        return parts.join("\n");
      }),
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `visit-timeline-${patientId}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <>
      <PatientStatTileRow>
        <StatTile label="Total Visits" value={visitHistory.length} icon={CalendarCheck} />
        <StatTile label="Prescriptions" value={prescriptions.length} icon={Pill} tint="clay" />
        <StatTile label="Bills" value={bills.filter((b) => b.bill_type === "appointment").length} icon={Receipt} tint="success" />
        <StatTile label="Procedures" value={procedureCount} icon={Activity} />
        <StatTile label="Upcoming Follow-up" value={nextFollowUp ? 1 : 0} icon={CalendarClock} tint="clay" />
      </PatientStatTileRow>

      <div className="gap-space-4 grid grid-cols-1 items-start lg:grid-cols-3">
        <div className="lg:col-span-2 min-w-0">
          <Card className="p-space-4">
            <div className="mb-space-4 gap-space-2 flex flex-wrap items-center justify-between">
              <div>
                <h3 className="text-label text-ink-900 font-bold">Patient Visit Timeline</h3>
                <p className="text-hint mt-space-1">A chronological view of all visits, prescriptions, billing and key patient events.</p>
              </div>
              <select
                value={sortAsc ? "oldest" : "latest"}
                onChange={(e) => setSortAsc(e.target.value === "oldest")}
                className="border-line bg-card px-space-3 text-ink-900 h-9 rounded-md border text-[12.5px]"
              >
                <option value="latest">Sort: Latest First</option>
                <option value="oldest">Sort: Oldest First</option>
              </select>
            </div>

            {sorted.length === 0 ? (
              <p className="py-space-4 text-ink-400 text-center text-[13px]">No events match this filter.</p>
            ) : (
              <ol className="space-y-space-4 border-line relative ml-1.5 border-l pl-space-4">
                {sorted.map((item) => {
                  if (item.kind === "note") {
                    return (
                      <li key={`note-${item.note.id}`} className="relative">
                        <span className="bg-line absolute top-1.5 h-2.5 w-2.5 rounded-full" style={{ left: "-1.3125rem" }} />
                        <div className="text-hint mb-space-1 text-[11.5px]">{formatShortDateTime(item.note.created_at)}</div>
                        <div className="bg-brand-50 border-brand-100 rounded-lg border p-3">
                          <div className="gap-space-2 flex items-center text-[13px] font-bold text-ink-900">
                            <StickyNote size={14} className="text-brand-600" /> Visit Note – Care Update
                          </div>
                          <p className="text-ink-700 mt-space-1 text-[12.5px]">{item.note.note_text}</p>
                        </div>
                      </li>
                    );
                  }
                  const v = item.visit;
                  const id = `visit-${v.id}`;
                  const isCollapsed = collapsed.has(id);
                  return (
                    <li key={id} className="relative">
                      <span className={cn("absolute top-1.5 h-2.5 w-2.5 rounded-full", v.status === "attended" ? "bg-success" : v.status === "cancelled" ? "bg-line" : "bg-brand-600")} style={{ left: "-1.3125rem" }} />
                      <div className="text-hint mb-space-1 text-[11.5px]">{formatShortDateTime(v.scheduled_at)}</div>
                      <div className="border-line rounded-lg border p-3">
                        <button type="button" onClick={() => toggleCollapsed(id)} className="flex w-full items-center justify-between text-left">
                          <div className="gap-space-2 flex items-center">
                            {v.appointment_type_id === "tele" ? <Video size={15} className="text-brand-600" /> : <CalendarCheck size={15} className="text-brand-600" />}
                            <span className="text-ink-900 text-[13.5px] font-bold">{visitTitle(v)}</span>
                            <Badge tone={VISIT_STATUS_BADGE_TONE[v.status] ?? "neutral"}>{STATUS_LABELS[v.status] ?? v.status}</Badge>
                          </div>
                          {isCollapsed ? <ChevronDown size={16} className="text-ink-400" /> : <ChevronUp size={16} className="text-ink-400" />}
                        </button>

                        {!isCollapsed && (
                          <>
                            <div className="gap-space-3 mt-space-2 flex flex-wrap text-[12px]">
                              <span className="text-ink-600">{v.doctor_name || "—"}</span>
                              <span className="text-ink-600">{v.department_name || "—"}</span>
                              <span className="text-ink-600">{v.appointment_type_id ? (TYPE_LABELS[v.appointment_type_id] ?? v.appointment_type_id) : "—"}</span>
                              <span className="gap-space-1 flex items-center text-ink-600">
                                Outcome: <Badge tone={OUTCOME_TONES[v.status] ?? "neutral"}>{OUTCOME_LABELS[v.status] ?? v.status}</Badge>
                              </span>
                            </div>
                            <div className="gap-space-4 mt-space-2 flex flex-wrap text-[12px]">
                              <span className="text-ink-600">
                                Prescription: {item.prescription ? <a href="#" onClick={(e) => e.preventDefault()} className="text-brand-700 font-mono font-semibold hover:underline">RX{item.prescription.id}</a> : "—"}
                              </span>
                              <span className="text-ink-600">
                                Billing: {item.bill ? <><span className="text-brand-700 font-mono font-semibold">{item.bill.invoice_ref}</span> <Badge tone={item.bill.payment_status === "paid" ? "success" : "clay"}>{item.bill.payment_status === "paid" ? "Paid" : "Unpaid"}</Badge></> : "—"}
                              </span>
                              <span className="text-ink-600">
                                Follow-up: {v.followup_valid_until && new Date(v.followup_valid_until) >= new Date() ? formatDate(v.followup_valid_until) : "—"}
                              </span>
                            </div>
                            {item.note && (
                              <div className="mt-space-2 border-t border-line pt-space-2 text-[12px]">
                                <span className="text-ink-600 font-semibold">Note:</span> <span className="text-ink-700">{item.note.note_text}</span>
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ol>
            )}
          </Card>

          {noteComposerOpen && (
            <Card className="p-space-4 mt-space-4">
              <h3 className="text-label mb-space-3 text-ink-900 font-bold">Add Event Note</h3>
              <Textarea placeholder="Add a note…" value={generalNoteDraft} onChange={(e) => setGeneralNoteDraft(e.target.value)} rows={2} />
              <div className="mt-space-2 flex justify-end gap-2">
                <Button variant="secondary" onClick={() => setNoteComposerOpen(false)}>Cancel</Button>
                <Button disabled={savingGeneralNote || !generalNoteDraft.trim()} onClick={() => { onAddNote(); setNoteComposerOpen(false); }}>
                  {savingGeneralNote ? "Saving…" : "Save Note"}
                </Button>
              </div>
            </Card>
          )}
        </div>

        <div className="space-y-space-4">
          <Card className="p-space-4">
            <h3 className="text-label mb-space-3 text-ink-900 font-bold">Timeline Filters</h3>
            <div className="gap-space-2 grid grid-cols-2">
              {FILTERS.map(({ key, label, icon: Icon }) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setFilter(key)}
                  className={cn(
                    "gap-space-2 flex h-10 items-center justify-center rounded-md border text-[12px] font-semibold",
                    filter === key ? "border-brand-600 bg-brand-600 text-white" : "border-line bg-card text-ink-700",
                  )}
                >
                  <Icon size={14} /> {label}
                </button>
              ))}
            </div>
          </Card>

          <Card className="p-space-4">
            <h3 className="text-label mb-space-3 text-ink-900 font-bold">Next Follow-up</h3>
            {!nextFollowUp ? (
              <p className="text-hint text-[12.5px]">No open follow-up window.</p>
            ) : (
              <div className="bg-success-tint rounded-md p-3">
                <p className="text-success text-[13px] font-bold">{formatDate(nextFollowUp.followup_valid_until!)}</p>
                <p className="text-hint mt-space-1">Department: {nextFollowUp.department_name} | Doctor: {nextFollowUp.doctor_name}</p>
                <button type="button" onClick={() => onOpenFollowup(nextFollowUp)} className="text-brand-700 mt-space-2 text-[12px] font-semibold hover:underline">
                  View Details →
                </button>
              </div>
            )}
          </Card>

          <Card className="p-space-4">
            <h3 className="text-label mb-space-3 text-ink-900 font-bold">Actions</h3>
            <div className="gap-space-2 grid grid-cols-2">
              <Button size="md" variant="secondary" onClick={() => window.print()}><Printer size={14} /> Print Timeline</Button>
              <Button size="md" variant="secondary" onClick={handleExportSummary}><Download size={14} /> Export Summary</Button>
              <Button size="md" variant="secondary" className="col-span-2" onClick={() => setNoteComposerOpen(true)}><FileEdit size={14} /> Add Event Note</Button>
            </div>
          </Card>

          <Card className="p-space-4">
            <h3 className="text-label mb-space-3 text-ink-900 font-bold">Visit Summary</h3>
            <dl className="space-y-space-2 text-[12.5px]">
              <div className="flex justify-between"><dt className="text-ink-600">Total Visits</dt><dd className="text-ink-900 font-semibold">{visitHistory.length}</dd></div>
              <div className="flex justify-between"><dt className="text-ink-600">Last Visit</dt><dd className="text-ink-900 font-semibold">{lastVisit ? formatShortDateTime(lastVisit.scheduled_at) : "—"}</dd></div>
              <div className="flex justify-between"><dt className="text-ink-600">Last Doctor</dt><dd className="text-ink-900 font-semibold">{lastVisit?.doctor_name || "—"}</dd></div>
              <div className="flex justify-between"><dt className="text-ink-600">Current Status</dt><dd><Badge tone={lastVisit ? (VISIT_STATUS_BADGE_TONE[lastVisit.status] ?? "neutral") : "neutral"}>{lastVisit ? (STATUS_LABELS[lastVisit.status] ?? lastVisit.status) : "—"}</Badge></dd></div>
            </dl>
          </Card>
        </div>
      </div>
    </>
  );
}
