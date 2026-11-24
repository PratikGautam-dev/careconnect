"use client";

import { useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  CalendarDays,
  CheckCircle2,
  ClipboardList,
  IndianRupee,
  Pill,
  Plus,
  Printer,
  Search,
  Stethoscope,
  Trash2,
} from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { PermissionGate } from "@/components/portal/PermissionGate";
import { NewBookingDialog } from "@/components/portal/NewBookingDialog";
import { StatTile } from "@/components/portal/StatTile";
import { StatTileGrid } from "@/components/portal/StatTileGrid";
import { useDeletePatient } from "@/hooks/usePatients";
import { usePharmacyPrescriptions } from "@/hooks/usePharmacyPrescriptions";
import { usePermission } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";
import { DataTable } from "@/components/ui/DataTable";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Input";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { cn } from "@/lib/cn";
import { formatDate, formatDateTime, formatShortDateTime } from "@/lib/formatDate";
import { formatINR } from "@/lib/formatCurrency";
import { TYPE_LABELS } from "@/hooks/useAppointments";
import {
  CATEGORY_TYPE_TABS,
  CONSENT_LABELS,
  CONSENT_TYPE_ORDER,
  VISIT_CATEGORY_LABELS,
  VISIT_CATEGORY_ORDER,
  usePatientDetail,
  type Consent,
  type Visit,
} from "@/hooks/usePatientDetail";
import { createVisitHistoryColumns, STATUS_LABELS } from "./_components/visit-history-columns";
import { PatientPrescriptionsPanel } from "../_components/PatientPrescriptionsPanel";
import { PatientBillingPanel, CreateBillButton } from "../_components/PatientBillingPanel";
import { PatientDocumentsPanel } from "../_components/PatientDocumentsPanel";
import { ClinicalNotesPanel } from "../_components/ClinicalNotesPanel";

const VISIT_STATUS_BADGE_TONE: Record<string, "success" | "clay" | "neutral"> = {
  booked: "success",
  attended: "success",
  cancelled: "neutral",
  rescheduled: "clay",
  no_show: "neutral",
};

type Tab = "overview" | "appointments" | "prescriptions" | "billing" | "transactions" | "documents" | "clinical_notes" | "settings";
type TabCounts = { visits: number; prescriptions: number; bills: number; clinicalNotes: number };
const TABS: { id: Tab; label: string; count?: (ctx: TabCounts) => number }[] = [
  { id: "overview", label: "Overview" },
  { id: "appointments", label: "Appointments", count: (c) => c.visits },
  { id: "prescriptions", label: "Prescriptions", count: (c) => c.prescriptions },
  { id: "billing", label: "Billing", count: (c) => c.bills },
  { id: "transactions", label: "Transactions" },
  { id: "documents", label: "Documents" },
  { id: "clinical_notes", label: "Clinical Notes", count: (c) => c.clinicalNotes },
  { id: "settings", label: "Settings" },
];

export default function PatientDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const patientId = params.id;
  const { hospital, ready } = usePortalGuard();
  const deletePatient = useDeletePatient();
  const canWriteAppointments = usePermission("appointments", "write");
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [tab, setTab] = useState<Tab>("overview");
  const [newBookingOpen, setNewBookingOpen] = useState(false);

  const {
    data,
    error,
    refetchDetail,
    dob,
    setDob,
    gender,
    setGender,
    address,
    setAddress,
    savingDemographics,
    handleSaveDemographics,
    savingStatus,
    handleSetStatus,
    savingConsent,
    handleSetConsent,
    expandedVisit,
    setExpandedVisit,
    noteDraft,
    setNoteDraft,
    savingNote,
    generalNoteDraft,
    setGeneralNoteDraft,
    savingGeneralNote,
    handleAddNote,
    fileInputRef,
    uploading,
    handleUpload,
    documentType,
    setDocumentType,
    sendingDocId,
    sendError,
    handleSendToWhatsapp,
    handleSaveDocumentRemarks,
    savingDocumentRemarks,
    handleSaveBillingNotes,
    savingBillingNotes,
    handleAddClinicalNote,
    savingClinicalNote,
    visitSearch,
    setVisitSearch,
    visitTimeFilter,
    setVisitTimeFilter,
    visitStatusFilter,
    setVisitStatusFilter,
    visitTypeFilter,
    setVisitTypeFilter,
    visitCategory,
    setVisitCategory,
    visitTypeCounts,
    filteredVisits,
    followupPanelId,
    openFollowupPanel,
    closeFollowupPanel,
    followupError,
    extendDays,
    setExtendDays,
    extendingId,
    handleExtendFollowup,
    bookSlotsByDate,
    bookDate,
    setBookDate,
    bookSlotId,
    setBookSlotId,
    bookingId,
    handleBookFollowupNow,
  } = usePatientDetail(patientId, ready);

  // Shared cache with PatientPrescriptionsPanel's own call -- just for the
  // "Prescriptions" tab's count badge and the Overview tab's stat tile.
  const { prescriptions: allPrescriptions } = usePharmacyPrescriptions(ready);

  if (!data) {
    return (
      <PortalShell hospital={hospital} active="patients">
        {error ? (
          <p className="text-error text-[13px]">{error}</p>
        ) : (
          <p className="text-ink-400 text-[13px]">Loading…</p>
        )}
      </PortalShell>
    );
  }

  const { patient, visit_history, notes, documents, consent, billing, clinical_notes, clinical_flags } = data;
  const generalNotes = notes.filter((n) => n.appointment_id === null);
  const notesByVisit = (visitId: number) => notes.filter((n) => n.appointment_id === visitId);
  const patientPrescriptions = allPrescriptions.filter((p) => p.patient_id === patient.id);
  const currentVisit: Visit | null = visit_history[0] ?? null;
  const currentVisitPrescriptions = currentVisit
    ? patientPrescriptions.filter((p) => p.appointment_id === currentVisit.id)
    : [];

  const tabCounts: TabCounts = {
    visits: visit_history.length,
    prescriptions: patientPrescriptions.length,
    bills: billing ? billing.stats.appointment_bills_count + billing.stats.pharmacy_bills_count : 0,
    clinicalNotes: clinical_notes.length,
  };

  const columns = createVisitHistoryColumns({
    followupPanelId,
    onOpenFollowup: openFollowupPanel,
    onCloseFollowup: closeFollowupPanel,
    expandedVisit,
    setExpandedVisit,
    notesByVisit,
  });

  function renderVisitRowDetail(v: Visit) {
    const expanded = expandedVisit === v.id;
    const visitNotes = notesByVisit(v.id);
    return (
      <>
        {expanded && (
          <div className="mb-space-3 border-line bg-paper p-space-3 rounded-lg border">
            {visitNotes.length === 0 ? (
              <p className="text-hint mb-space-3">No notes for this visit yet.</p>
            ) : (
              <ul className="mb-space-3 space-y-space-2">
                {visitNotes.map((n) => (
                  <li key={n.id} className="bg-card p-space-3 rounded-md text-[13px]">
                    <p className="text-ink-900">{n.note_text}</p>
                    <p className="text-hint mt-space-1">
                      {n.doctor_name ? `${n.doctor_name} · ` : ""}
                      {formatDateTime(n.created_at)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
            <div className="gap-space-2 flex flex-col items-stretch sm:flex-row sm:items-end">
              <Textarea
                placeholder="Add a note for this visit…"
                value={noteDraft[v.id] || ""}
                onChange={(e) => setNoteDraft((d) => ({ ...d, [v.id]: e.target.value }))}
                rows={2}
                className="flex-1"
              />
              <Button
                size="md"
                onClick={() => handleAddNote(v.id)}
                disabled={savingNote === v.id || !(noteDraft[v.id] || "").trim()}
              >
                {savingNote === v.id ? "Saving…" : "Add note"}
              </Button>
            </div>
          </div>
        )}
        {followupPanelId === v.id && (
          <div className="border-line bg-paper p-space-3 rounded-lg border">
            <p className="text-hint mb-space-3">
              Follow-up validity for this visit{" "}
              {v.followup_valid_until && new Date(v.followup_valid_until) >= new Date()
                ? `is open until ${formatDate(v.followup_valid_until)}`
                : "has closed"}
              . Grant extra days so the patient can book it themselves on WhatsApp, or book it
              directly right now.
            </p>

            <div className="mb-space-3 gap-space-2 flex flex-wrap items-end">
              <div>
                <label className="mb-space-1 text-ink-600 block text-[12px] font-semibold">
                  Extend by (days)
                </label>
                <input
                  type="number"
                  min={1}
                  value={extendDays}
                  onChange={(e) => setExtendDays(e.target.value)}
                  className="border-line bg-card px-space-2 text-ink-900 h-9 w-24 rounded-md border text-[13px]"
                />
              </div>
              <Button
                size="md"
                variant="secondary"
                onClick={() => handleExtendFollowup(v.id)}
                disabled={extendingId === v.id}
              >
                {extendingId === v.id ? "Granting…" : "Grant extension"}
              </Button>
            </div>

            <div className="border-line pt-space-3 border-t">
              <p className="mb-space-2 text-ink-600 text-[12px] font-semibold">
                Or book this follow-up now (with {v.doctor_name}, {v.department_name})
              </p>
              {(() => {
                const dates = bookSlotsByDate ? Object.keys(bookSlotsByDate).sort() : [];
                const slots = bookSlotsByDate && bookDate ? bookSlotsByDate[bookDate] || [] : [];
                return (
                  <>
                    {bookSlotsByDate === null ? (
                      <p className="mb-space-2 text-ink-400 text-[12.5px]">
                        Loading available dates…
                      </p>
                    ) : dates.length === 0 ? (
                      <p className="mb-space-2 text-ink-400 text-[12.5px]">
                        No available dates for this doctor.
                      </p>
                    ) : (
                      <div className="mb-space-2 gap-space-2 flex flex-wrap">
                        {dates.map((d) => (
                          <button
                            type="button"
                            key={d}
                            onClick={() => {
                              setBookDate(d);
                              setBookSlotId("");
                            }}
                            className={cn(
                              "px-space-2 py-space-1 rounded-md border text-[12px] font-semibold",
                              bookDate === d
                                ? "border-brand-600 bg-brand-600 text-white"
                                : "border-line bg-card text-ink-600",
                            )}
                          >
                            {d}
                          </button>
                        ))}
                      </div>
                    )}
                    {bookDate &&
                      (slots.length === 0 ? (
                        <p className="mb-space-2 text-ink-400 text-[12.5px]">
                          No slots available on this date.
                        </p>
                      ) : (
                        <div className="mb-space-2 gap-space-2 flex flex-wrap">
                          {slots.map((s) => (
                            <button
                              type="button"
                              key={s.id}
                              onClick={() => setBookSlotId(s.id)}
                              className={cn(
                                "px-space-2 py-space-1 rounded-md border text-[12px] font-semibold",
                                bookSlotId === s.id
                                  ? "border-brand-600 bg-brand-600 text-white"
                                  : "border-line bg-card text-ink-600",
                              )}
                            >
                              {s.label}
                            </button>
                          ))}
                        </div>
                      ))}
                  </>
                );
              })()}
              <Button
                size="md"
                onClick={() => handleBookFollowupNow(v.id)}
                disabled={bookingId === v.id || !bookSlotId}
              >
                {bookingId === v.id ? "Booking…" : "Book follow-up now"}
              </Button>
            </div>

            {followupError && <p className="mt-space-3 text-error text-[12px]">{followupError}</p>}
            <div className="mt-space-3">
              <Button size="md" variant="secondary" onClick={closeFollowupPanel}>
                Close
              </Button>
            </div>
          </div>
        )}
      </>
    );
  }

  return (
    <PortalShell hospital={hospital} active="patients">
      <button
        type="button"
        onClick={() => router.push("/portal/patients")}
        className="mb-space-3 gap-space-1 text-brand-600 flex items-center text-[12.5px] font-semibold hover:underline"
      >
        <ArrowLeft size={14} /> All patients
      </button>

      <div className="mb-space-5 gap-space-3 flex flex-wrap items-center">
        <div className="bg-brand-100 text-brand-700 flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-[18px] font-bold">
          {(patient.name || patient.phone).trim().charAt(0).toUpperCase()}
        </div>
        <div className="min-w-0 flex-1 basis-48">
          <h1 className="text-display !text-[20px] break-words sm:!text-[24px]">
            {patient.name || patient.phone}
          </h1>
          <div className="gap-space-2 text-ink-600 flex flex-wrap items-center text-[13px]">
            <span>{patient.phone}</span>
            {patient.patient_display_id && (
              <span className="bg-brand-100 px-space-3 text-brand-800 border-brand-300 rounded-full border py-1 font-mono text-[13px] font-extrabold tracking-wide">
                {patient.patient_display_id}
              </span>
            )}
            {patient.mrn && (
              <span className="bg-paper px-space-3 text-ink-900 border-line rounded-full border py-1 font-mono text-[13px] font-extrabold tracking-wide">
                MRN: {patient.mrn}
              </span>
            )}
            {patient.status !== "active" && (
              <Badge tone={patient.status === "blocked" ? "clay" : "neutral"}>
                {patient.status === "blocked" ? "Blocked" : "Inactive"}
              </Badge>
            )}
          </div>
        </div>
        <div className="gap-space-2 flex shrink-0 items-center sm:ml-auto">
          <Button variant="secondary" size="md" onClick={() => window.print()}>
            <Printer size={14} /> Print Summary
          </Button>
          <PermissionGate page="patients" action="delete">
            <button
              type="button"
              onClick={() => setConfirmingDelete(true)}
              className="border-error text-error hover:bg-error gap-space-2 px-space-3 flex h-9 items-center justify-center rounded-sm border-2 text-[12.5px] font-extrabold transition-colors hover:text-white"
            >
              <Trash2 size={14} /> Delete permanently
            </button>
          </PermissionGate>
        </div>
      </div>

      <ConfirmDialog
        open={confirmingDelete}
        title="Delete patient permanently?"
        message={`This permanently deletes ${patient.name || patient.phone} — they will no longer appear anywhere, can't book or sign in on WhatsApp, and their upcoming appointments are cancelled (with a refund if already paid). Past appointments, billing and medical records are kept for your records. This can't be undone.`}
        confirmLabel="Delete permanently"
        destructive
        busy={deletePatient.isPending}
        onConfirm={async () => {
          try {
            await deletePatient.mutateAsync(patient.id);
            toast.success("Patient deleted");
            router.push("/portal/patients");
          } catch (err) {
            setConfirmingDelete(false);
            toast.error(
              "Couldn't delete patient",
              err instanceof Error ? err.message : "Something went wrong.",
            );
          }
        }}
        onCancel={() => setConfirmingDelete(false)}
      />

      <NewBookingDialog
        open={newBookingOpen}
        onOpenChange={setNewBookingOpen}
        onBooked={() => refetchDetail()}
        initialPatientName={patient.name || undefined}
        initialPatientPhone={patient.phone}
      />

      {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

      <div className="mb-space-4 gap-space-1 border-line bg-card p-space-1 flex w-fit flex-wrap rounded-lg border">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={cn(
              "px-space-3 py-space-2 rounded-md text-[13px] font-semibold transition-colors duration-150",
              tab === t.id
                ? "bg-brand-50 text-brand-700"
                : "text-ink-400 hover:text-ink-700 hover:bg-black/[0.04]",
            )}
          >
            {t.label}
            {t.count && <span className="ml-space-1 tabular-nums">({t.count(tabCounts)})</span>}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <OverviewTab
          patient={patient}
          visitHistory={visit_history}
          currentVisit={currentVisit}
          currentVisitPrescriptions={currentVisitPrescriptions}
          totalPrescriptions={patientPrescriptions.length}
          billing={billing}
          generalNotes={generalNotes}
          generalNoteDraft={generalNoteDraft}
          setGeneralNoteDraft={setGeneralNoteDraft}
          savingGeneralNote={savingGeneralNote}
          handleAddNote={handleAddNote}
          onNewAppointment={() => setNewBookingOpen(true)}
          canWriteAppointments={canWriteAppointments}
          onGoToTab={setTab}
        />
      )}

      {tab === "appointments" && (
        <>
          <StatTileGrid cols={5} className="mb-space-4">
            <StatTile label="Total Appointments" value={visit_history.length} icon={CalendarDays} />
            <StatTile label="Upcoming" value={visit_history.filter((v) => v.status === "booked" && new Date(v.scheduled_at) > new Date()).length} icon={CalendarDays} tint="clay" />
            <StatTile label="Completed" value={visit_history.filter((v) => v.status === "attended").length} icon={CheckCircle2} tint="success" />
            <StatTile label="Cancelled" value={visit_history.filter((v) => v.status === "cancelled").length} icon={AlertTriangle} tint="error" />
            <StatTile label="Tele-consultations" value={visit_history.filter((v) => v.appointment_type_id === "tele").length} icon={Stethoscope} />
          </StatTileGrid>

          <div className="gap-space-4 grid grid-cols-1 items-start lg:grid-cols-3">
          <div className="lg:col-span-2">
          <Card className="p-space-4">
          <h3 className="text-label mb-space-3 text-ink-900 font-bold">Visit history</h3>

          <div className="mb-space-3 gap-space-1 border-line bg-paper flex w-full overflow-x-auto rounded-md border p-0.5">
            {VISIT_CATEGORY_ORDER.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => setVisitCategory(c)}
                className={cn(
                  "px-space-3 flex-1 rounded py-1.5 text-center text-[12.5px] font-semibold whitespace-nowrap transition-colors duration-150",
                  visitCategory === c
                    ? "bg-card text-ink-900 shadow-[var(--shadow-sm)]"
                    : "text-ink-400 hover:text-ink-700",
                )}
              >
                {VISIT_CATEGORY_LABELS[c]}
              </button>
            ))}
          </div>

          {visit_history.length === 0 ? (
            <p className="py-space-4 text-ink-400 text-center text-[13px]">No visits yet.</p>
          ) : (
            <>
              <div className="mb-space-3 gap-space-2 flex flex-wrap">
                {CATEGORY_TYPE_TABS[visitCategory]
                  .filter(
                    (id) =>
                      id === "all" || (visitTypeCounts[id] || 0) > 0 || visitTypeFilter === id,
                  )
                  .map((id) => (
                    <button
                      key={id}
                      type="button"
                      onClick={() => setVisitTypeFilter(id)}
                      className={cn(
                        "px-space-3 py-space-1 rounded-full border text-[12.5px] font-semibold transition-colors duration-150",
                        visitTypeFilter === id
                          ? "border-brand-600 bg-brand-600 text-white"
                          : "border-line bg-card text-ink-600 hover:border-brand-300 hover:bg-brand-50",
                      )}
                    >
                      {id === "all" ? "All" : id === "other" ? "Other" : TYPE_LABELS[id]}
                      <span
                        className={cn(
                          "ml-space-1 tabular-nums",
                          visitTypeFilter === id ? "text-white/80" : "text-ink-400",
                        )}
                      >
                        {visitTypeCounts[id] || 0}
                      </span>
                    </button>
                  ))}
              </div>

              <div className="mb-space-3 gap-space-2 flex flex-wrap items-center">
                <div className="gap-space-1 border-line bg-paper flex w-full rounded-md border p-0.5 sm:w-auto">
                  {(["all", "upcoming", "past"] as const).map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setVisitTimeFilter(t)}
                      className={cn(
                        "px-space-2 flex-1 rounded py-1 text-[12px] font-semibold capitalize transition-colors duration-150 sm:flex-none",
                        visitTimeFilter === t
                          ? "bg-card text-ink-900 shadow-[var(--shadow-sm)]"
                          : "text-ink-400 hover:text-ink-700",
                      )}
                    >
                      {t}
                    </button>
                  ))}
                </div>
                <div className="relative min-w-0 basis-full sm:min-w-[180px] sm:flex-1 sm:basis-auto">
                  <Search
                    size={14}
                    className="left-space-3 text-ink-400 pointer-events-none absolute top-1/2 -translate-y-1/2"
                  />
                  <input
                    type="text"
                    placeholder="Search doctor, department, or reference…"
                    value={visitSearch}
                    onChange={(e) => setVisitSearch(e.target.value)}
                    className="border-line bg-card pl-space-8 pr-space-3 text-ink-900 focus:border-brand-400 h-9 w-full rounded-md border text-[12.5px] outline-none"
                  />
                </div>
                <select
                  value={visitStatusFilter}
                  onChange={(e) => setVisitStatusFilter(e.target.value)}
                  className="border-line bg-card px-space-2 text-ink-900 h-9 w-full rounded-md border text-[12.5px] sm:w-auto"
                >
                  <option value="all">All statuses</option>
                  {Object.entries(STATUS_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>

              {filteredVisits.length === 0 ? (
                <p className="py-space-4 text-ink-400 text-center text-[13px]">
                  No visits match this filter.
                </p>
              ) : (
                <DataTable
                  columns={columns}
                  data={filteredVisits}
                  getRowId={(v) => String(v.id)}
                  isRowExpanded={(v) => expandedVisit === v.id || followupPanelId === v.id}
                  renderRowDetail={renderVisitRowDetail}
                />
              )}
            </>
          )}
          </Card>
          </div>

          <div className="space-y-space-4">
            <Card className="p-space-4">
              <h3 className="text-label mb-space-3 text-ink-900 font-bold">Selected Appointment Details</h3>
              {!currentVisit ? (
                <p className="text-hint text-[12.5px]">No appointments yet.</p>
              ) : (
                <dl className="space-y-space-2 text-[12.5px]">
                  <div className="flex justify-between"><dt className="text-hint">Appointment ID</dt><dd className="text-ink-900 font-mono font-semibold">{currentVisit.reference_id || `APT-${currentVisit.id}`}</dd></div>
                  <div className="flex justify-between"><dt className="text-hint">Doctor</dt><dd className="text-ink-900 font-semibold">{currentVisit.doctor_name || "—"}</dd></div>
                  <div className="flex justify-between"><dt className="text-hint">Department</dt><dd className="text-ink-900 font-semibold">{currentVisit.department_name || "—"}</dd></div>
                  <div className="flex justify-between"><dt className="text-hint">Date & Time</dt><dd className="text-ink-900 font-semibold">{formatShortDateTime(currentVisit.scheduled_at)}</dd></div>
                  <div className="flex justify-between"><dt className="text-hint">Source</dt><dd className="text-ink-900 font-semibold capitalize">{currentVisit.source}</dd></div>
                  <div className="flex justify-between"><dt className="text-hint">Status</dt><dd><Badge tone={VISIT_STATUS_BADGE_TONE[currentVisit.status] ?? "neutral"}>{STATUS_LABELS[currentVisit.status] ?? currentVisit.status}</Badge></dd></div>
                </dl>
              )}
            </Card>

            <Card className="p-space-4">
              <h3 className="text-label mb-space-3 text-ink-900 font-bold">Quick Actions</h3>
              <div className="gap-space-2 grid grid-cols-2">
                {canWriteAppointments && (
                  <Button size="md" variant="secondary" onClick={() => setNewBookingOpen(true)}>
                    <CalendarDays size={14} /> Book Appointment
                  </Button>
                )}
                {currentVisit && (
                  <Button size="md" variant="secondary" href={`/portal/appointments/${currentVisit.id}`}>
                    View Appointment
                  </Button>
                )}
                <Button size="md" variant="secondary" onClick={() => window.print()} className="col-span-2">
                  <Printer size={14} /> Print Slip
                </Button>
              </div>
            </Card>

            {(() => {
              const now = new Date();
              const nextFollowUp = visit_history
                .filter((v) => v.followup_valid_until && new Date(v.followup_valid_until) >= now)
                .sort((a, b) => new Date(a.followup_valid_until!).getTime() - new Date(b.followup_valid_until!).getTime())[0];
              return (
                <Card className="p-space-4">
                  <h3 className="text-label mb-space-3 text-ink-900 font-bold">Upcoming / Follow-up Schedule</h3>
                  {!nextFollowUp ? (
                    <p className="text-hint text-[12.5px]">No open follow-up window.</p>
                  ) : (
                    <div className="border-line bg-paper rounded-md border p-space-3">
                      <p className="text-ink-900 text-[12.5px] font-bold">Follow-up open until {formatDate(nextFollowUp.followup_valid_until!)}</p>
                      <p className="text-hint mt-space-1">{nextFollowUp.department_name} · {nextFollowUp.doctor_name}</p>
                      <button
                        type="button"
                        onClick={() => openFollowupPanel(nextFollowUp)}
                        className="text-brand-700 mt-space-2 text-[12px] font-semibold hover:underline"
                      >
                        View Details →
                      </button>
                    </div>
                  )}
                </Card>
              );
            })()}
          </div>
          </div>

          <Card className="p-space-4 mt-space-4">
            <h3 className="text-label mb-space-3 text-ink-900 font-bold">Visit Notes (Appointments)</h3>
            <p className="text-hint mb-space-3">Notes about the patient&apos;s appointments, follow-ups, or scheduling preferences.</p>
            <div className="gap-space-2 flex flex-col items-stretch sm:flex-row sm:items-end">
              <Textarea
                placeholder="Add notes about the patient's appointments, follow-ups, or scheduling preferences…"
                value={generalNoteDraft}
                onChange={(e) => setGeneralNoteDraft(e.target.value)}
                rows={2}
                className="flex-1"
              />
              <Button size="md" onClick={() => handleAddNote(null)} disabled={savingGeneralNote || !generalNoteDraft.trim()}>
                {savingGeneralNote ? "Saving…" : "Add note"}
              </Button>
            </div>
          </Card>
        </>
      )}

      {tab === "prescriptions" && (
        <PatientPrescriptionsPanel
          patientId={patient.id}
          patientName={patient.name || patient.phone}
          onViewBilling={() => setTab("billing")}
        />
      )}

      {tab === "billing" && (
        <PatientBillingPanel
          patientId={patient.id}
          billing={billing}
          billingNotes={patient.billing_notes}
          onCollected={() => refetchDetail()}
          onSaveBillingNotes={handleSaveBillingNotes}
          savingBillingNotes={savingBillingNotes}
        />
      )}

      {tab === "transactions" && (
        <Card className="p-space-4">
          <h3 className="text-label mb-space-3 text-ink-900 font-bold">Transactions</h3>
          <p className="text-hint mb-space-3">Every payment attempt and collection event for this patient, newest first.</p>
          {!billing || billing.payment_events.length === 0 ? (
            <p className="py-space-4 text-ink-400 text-center text-[13px]">No transactions yet.</p>
          ) : (
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="text-hint text-left">
                  <th className="py-space-2 font-semibold">Transaction ID</th>
                  <th className="py-space-2 font-semibold">Date & Time</th>
                  <th className="py-space-2 font-semibold">Reference</th>
                  <th className="py-space-2 font-semibold">Bill No.</th>
                  <th className="py-space-2 font-semibold">Payment Mode</th>
                  <th className="py-space-2 text-right font-semibold">Amount</th>
                  <th className="py-space-2 text-right font-semibold">Status</th>
                </tr>
              </thead>
              <tbody className="divide-line divide-y">
                {billing.payment_events.map((e) => (
                  <tr key={e.transaction_id}>
                    <td className="py-space-2 text-brand-700 font-mono font-semibold">{e.transaction_id}</td>
                    <td className="py-space-2 text-ink-600">{formatShortDateTime(e.date)}</td>
                    <td className="py-space-2 text-ink-600 font-mono">{e.reference_id}</td>
                    <td className="py-space-2 text-ink-600 font-mono">{e.bill_no}</td>
                    <td className="py-space-2 text-ink-600">{e.method || "—"}</td>
                    <td className="py-space-2 text-ink-900 text-right font-semibold">{formatINR(e.amount)}</td>
                    <td className="py-space-2 text-right">
                      <Badge tone={e.status === "paid" ? "success" : e.status === "failed" || e.status === "expired" || e.status === "cancelled" ? "neutral" : "clay"}>{e.status}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}

      {tab === "clinical_notes" && (
        <ClinicalNotesPanel
          notes={clinical_notes}
          flags={clinical_flags}
          onAdd={handleAddClinicalNote}
          saving={savingClinicalNote}
        />
      )}

      {tab === "documents" && (
        <PatientDocumentsPanel
          patientId={patient.id}
          documents={documents}
          documentType={documentType}
          setDocumentType={setDocumentType}
          uploading={uploading}
          fileInputRef={fileInputRef}
          handleUpload={handleUpload}
          sendingDocId={sendingDocId}
          sendError={sendError}
          handleSendToWhatsapp={handleSendToWhatsapp}
          onSaveRemarks={handleSaveDocumentRemarks}
          savingRemarks={savingDocumentRemarks}
        />
      )}

      {tab === "settings" && (
        <div className="gap-space-4 grid grid-cols-1 lg:grid-cols-2">
          <Card className="p-space-4 h-fit">
            <h3 className="text-label mb-space-3 text-ink-900 font-bold">Demographics</h3>
            <div className="mb-space-3 gap-space-3 grid grid-cols-1 sm:grid-cols-2">
              <Field label="Date of birth" htmlFor="dob">
                <Input id="dob" type="date" value={dob} onChange={(e) => setDob(e.target.value)} />
              </Field>
              <Field label="Gender" htmlFor="gender">
                <Input
                  id="gender"
                  value={gender}
                  onChange={(e) => setGender(e.target.value)}
                  placeholder="Optional"
                />
              </Field>
            </div>
            <Field label="Address" htmlFor="address">
              <Textarea
                id="address"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                rows={3}
                placeholder="Optional"
              />
            </Field>
            <Button
              size="md"
              onClick={handleSaveDemographics}
              disabled={savingDemographics}
              className="mt-space-3 w-full"
            >
              {savingDemographics ? "Saving…" : "Save"}
            </Button>
          </Card>

          <Card className="p-space-4 h-fit">
            <h3 className="text-label mb-space-1 text-ink-900 font-bold">Record status</h3>
            <p className="text-hint mb-space-3">
              Blocking a patient stops them from being selected/booked against on WhatsApp -- their
              appointment history and Patient ID are untouched, and any phone still linked to them
              is unaffected.
            </p>
            {patient.status === "active" ? (
              <Button
                size="md"
                variant="secondary"
                onClick={() => handleSetStatus("blocked")}
                disabled={savingStatus}
                className="w-full"
              >
                {savingStatus ? "Saving…" : "Block this patient"}
              </Button>
            ) : (
              <Button
                size="md"
                onClick={() => handleSetStatus("active")}
                disabled={savingStatus}
                className="w-full"
              >
                {savingStatus ? "Saving…" : "Reactivate this patient"}
              </Button>
            )}
          </Card>

          <Card className="p-space-4 h-fit lg:col-span-2">
            <h3 className="text-label mb-space-1 text-ink-900 font-bold">Consent management</h3>
            <p className="text-hint mb-space-3">
              DPDP consent is collected from patients via WhatsApp. Privacy Policy mirrors DPDP
              (linked). Marketing consent is independent but currently has no collection mechanism
              (mock for now).
            </p>
            <ul className="gap-space-3 grid grid-cols-1 sm:grid-cols-3">
              {CONSENT_TYPE_ORDER.map((type) => {
                const key = `${type}_consent` as keyof Consent;
                const agreed = consent[key];
                const isPrivacyPolicy = type === "privacy_policy";
                const linkedAgreed = isPrivacyPolicy ? consent.dpdp_consent : agreed;
                const isLinked = isPrivacyPolicy;
                return (
                  <li key={type} className="border-line p-space-3 gap-space-2 flex items-center justify-between rounded-md border">
                    <span className="text-ink-900 text-[13px] font-semibold">
                      {CONSENT_LABELS[type]}
                    </span>
                    <div className="gap-space-3 flex items-center">
                      <label className="text-ink-600 flex items-center gap-1 text-[12px] font-semibold">
                        <input
                          type="checkbox"
                          checked={linkedAgreed}
                          onChange={() => !isLinked && handleSetConsent(type, true)}
                          disabled={savingConsent === type || isLinked}
                          className="accent-success h-4 w-4"
                        />
                        Agree
                      </label>
                      <label className="text-ink-600 flex items-center gap-1 text-[12px] font-semibold">
                        <input
                          type="checkbox"
                          checked={!linkedAgreed}
                          onChange={() => !isLinked && handleSetConsent(type, false)}
                          disabled={savingConsent === type || isLinked}
                          className="accent-error h-4 w-4"
                        />
                        Disagree
                      </label>
                    </div>
                  </li>
                );
              })}
            </ul>
          </Card>
        </div>
      )}
    </PortalShell>
  );
}

function OverviewTab({
  patient,
  visitHistory,
  currentVisit,
  currentVisitPrescriptions,
  totalPrescriptions,
  billing,
  generalNotes,
  generalNoteDraft,
  setGeneralNoteDraft,
  savingGeneralNote,
  handleAddNote,
  onNewAppointment,
  canWriteAppointments,
  onGoToTab,
}: {
  patient: import("@/hooks/usePatientDetail").Patient;
  visitHistory: Visit[];
  currentVisit: Visit | null;
  currentVisitPrescriptions: import("@/hooks/usePharmacyPrescriptions").Prescription[];
  totalPrescriptions: number;
  billing: import("@/hooks/usePatientDetail").PatientBilling | null;
  generalNotes: import("@/hooks/usePatientDetail").Note[];
  generalNoteDraft: string;
  setGeneralNoteDraft: (v: string) => void;
  savingGeneralNote: boolean;
  handleAddNote: (visitId: number | null) => void;
  onNewAppointment: () => void;
  canWriteAppointments: boolean;
  onGoToTab: (t: Tab) => void;
}) {
  const pendingDues = billing?.stats.pending_dues ?? 0;
  const recentBills = (billing?.transactions ?? []).slice(0, 5);

  return (
    <>
      <StatTileGrid cols={5} className="mb-space-4">
        <StatTile label="Total Appointments" value={visitHistory.length} icon={CalendarDays} />
        <StatTile label="Total Prescriptions" value={totalPrescriptions} icon={ClipboardList} tint="clay" />
        <StatTile label="Pharmacy Bills" value={billing ? billing.stats.pharmacy_bills_total : null} icon={Pill} prefix="₹" />
        <StatTile label="Appointment Bills" value={billing ? billing.stats.appointment_bills_total : null} icon={Stethoscope} prefix="₹" tint="clay" />
        <StatTile label="Total Amount" value={billing ? billing.stats.total_amount : null} icon={IndianRupee} prefix="₹" tint="success" />
      </StatTileGrid>

      <div className="gap-space-4 grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-space-4 min-w-0">
          <Card className="p-space-4">
            <h3 className="text-label mb-space-3 text-ink-900 font-bold">Visit History</h3>
            {visitHistory.length === 0 ? (
              <p className="py-space-4 text-ink-400 text-center text-[13px]">No visits yet.</p>
            ) : (
              <ol className="space-y-space-4 border-line relative ml-1.5 border-l pl-space-4">
                {visitHistory.slice(0, 6).map((v, i) => (
                  <li key={v.id} className="relative">
                    <span
                      className={cn(
                        "absolute top-1 h-2.5 w-2.5 rounded-full",
                        i === 0 ? "bg-brand-600" : "bg-line",
                      )}
                      style={{ left: "-1.3125rem" }}
                    />
                    <div className="gap-space-2 flex flex-wrap items-center">
                      <p className="text-ink-900 text-[13px] font-semibold">
                        {formatDateTime(v.scheduled_at)}
                      </p>
                      {i === 0 && <Badge tone="brand">Current</Badge>}
                      <Badge tone={VISIT_STATUS_BADGE_TONE[v.status] ?? "neutral"}>
                        {STATUS_LABELS[v.status] ?? v.status}
                      </Badge>
                    </div>
                    <p className="text-hint">
                      {v.department_name} · {v.doctor_name}
                      {v.appointment_type_id ? ` · ${TYPE_LABELS[v.appointment_type_id] ?? v.appointment_type_id}` : ""}
                    </p>
                  </li>
                ))}
              </ol>
            )}
          </Card>

          {currentVisit && (
            <Card className="p-space-4">
              <h3 className="text-label mb-space-3 text-ink-900 font-bold">Current Visit Details</h3>
              <div className="gap-space-3 grid grid-cols-2 sm:grid-cols-4">
                <div>
                  <p className="text-hint">Appointment ID</p>
                  <p className="text-ink-900 text-[13px] font-semibold">{currentVisit.reference_id || `APT-${currentVisit.id}`}</p>
                </div>
                <div>
                  <p className="text-hint">Date & Time</p>
                  <p className="text-ink-900 text-[13px] font-semibold">{formatShortDateTime(currentVisit.scheduled_at)}</p>
                </div>
                <div>
                  <p className="text-hint">Doctor</p>
                  <p className="text-ink-900 text-[13px] font-semibold">{currentVisit.doctor_name || "—"}</p>
                </div>
                <div>
                  <p className="text-hint">Department</p>
                  <p className="text-ink-900 text-[13px] font-semibold">{currentVisit.department_name || "—"}</p>
                </div>
              </div>
              <div className="mt-space-3">
                <Badge tone={VISIT_STATUS_BADGE_TONE[currentVisit.status] ?? "neutral"}>
                  {STATUS_LABELS[currentVisit.status] ?? currentVisit.status}
                </Badge>
              </div>
            </Card>
          )}

          <Card className="p-space-4">
            <div className="mb-space-3 flex items-center justify-between">
              <h3 className="text-label text-ink-900 font-bold">Prescriptions (This Visit)</h3>
              <Button size="md" variant="secondary" onClick={() => onGoToTab("prescriptions")}>
                View all
              </Button>
            </div>
            {currentVisitPrescriptions.length === 0 ? (
              <p className="py-space-3 text-ink-400 text-center text-[13px]">No prescriptions for this visit.</p>
            ) : (
              <ul className="divide-line divide-y">
                {currentVisitPrescriptions.map((p) => (
                  <li key={p.id} className="py-space-2 gap-space-2 flex items-center justify-between">
                    <div>
                      <p className="text-ink-900 text-[13px] font-semibold">RX{p.id}</p>
                      <p className="text-hint">{formatShortDateTime(p.created_at)} · {p.doctor_name || "—"}</p>
                    </div>
                    <Badge tone="clay">{p.status}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card className="p-space-4">
            <div className="mb-space-3 flex items-center justify-between">
              <h3 className="text-label text-ink-900 font-bold">Billing & Transactions (This Patient)</h3>
              <Button size="md" variant="secondary" onClick={() => onGoToTab("billing")}>
                View all
              </Button>
            </div>
            {recentBills.length === 0 ? (
              <p className="py-space-3 text-ink-400 text-center text-[13px]">No bills yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-[12.5px]">
                  <thead>
                    <tr className="text-hint text-left">
                      <th className="py-space-2 font-semibold">Bill No.</th>
                      <th className="py-space-2 font-semibold">Date</th>
                      <th className="py-space-2 font-semibold">Type</th>
                      <th className="py-space-2 text-right font-semibold">Amount</th>
                      <th className="py-space-2 text-right font-semibold">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-line divide-y">
                    {recentBills.map((b) => (
                      <tr key={`${b.bill_type}-${b.id}`}>
                        <td className="py-space-2 text-brand-700 font-mono font-semibold">{b.invoice_ref}</td>
                        <td className="py-space-2 text-ink-600">{formatShortDateTime(b.date)}</td>
                        <td className="py-space-2 text-ink-600 capitalize">{b.bill_type}</td>
                        <td className="py-space-2 text-ink-900 text-right font-semibold">{formatINR(b.amount)}</td>
                        <td className="py-space-2 text-right">
                          <Badge tone={b.payment_status === "paid" ? "success" : "clay"}>
                            {b.payment_status === "paid" ? "Paid" : "Unpaid"}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-line border-t">
                      <td colSpan={3} className="text-ink-700 py-space-2 font-bold">Total (This Patient)</td>
                      <td className="text-ink-900 py-space-2 text-right font-bold">
                        {formatINR(billing?.stats.total_amount ?? 0)}
                      </td>
                      <td />
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
          </Card>

          <Card className="p-space-4">
            <h3 className="text-label mb-space-3 text-ink-900 font-bold">General notes</h3>
            <p className="text-hint mb-space-3">
              Not tied to a specific visit — e.g. a walk-in or a phone conversation.
            </p>
            {generalNotes.length > 0 && (
              <ul className="mb-space-3 space-y-space-2">
                {generalNotes.map((n) => (
                  <li key={n.id} className="bg-paper p-space-3 rounded-md text-[13px]">
                    <p className="text-ink-900">{n.note_text}</p>
                    <p className="text-hint mt-space-1">{formatDateTime(n.created_at)}</p>
                  </li>
                ))}
              </ul>
            )}
            <div className="gap-space-2 flex flex-col items-stretch sm:flex-row sm:items-end">
              <Textarea
                placeholder="Add a general note…"
                value={generalNoteDraft}
                onChange={(e) => setGeneralNoteDraft(e.target.value)}
                rows={2}
                className="flex-1"
              />
              <Button
                size="md"
                onClick={() => handleAddNote(null)}
                disabled={savingGeneralNote || !generalNoteDraft.trim()}
              >
                {savingGeneralNote ? "Saving…" : "Add note"}
              </Button>
            </div>
          </Card>
        </div>

        <div className="space-y-space-4">
          <Card className="p-space-4 h-fit">
            <h3 className="text-label mb-space-3 text-ink-900 font-bold">Patient Summary</h3>
            <dl className="space-y-space-2 text-[12.5px]">
              <div className="flex justify-between">
                <dt className="text-hint">Patient ID</dt>
                <dd className="text-ink-900 font-mono font-semibold">{patient.patient_display_id || "—"}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-hint">MRN</dt>
                <dd className="text-ink-900 font-mono font-semibold">{patient.mrn || "—"}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-hint">Phone</dt>
                <dd className="text-ink-900 font-semibold">{patient.phone}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-hint">DOB</dt>
                <dd className="text-ink-900 font-semibold">{patient.date_of_birth ? formatDate(patient.date_of_birth) : "—"}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-hint">Gender</dt>
                <dd className="text-ink-900 font-semibold">{patient.gender || "—"}</dd>
              </div>
            </dl>
          </Card>

          <Card className="p-space-4 h-fit">
            <h3 className="text-label mb-space-3 text-ink-900 font-bold">Billing Summary</h3>
            {!billing ? (
              <p className="text-hint text-[12.5px]">Loading…</p>
            ) : (
              <>
                <dl className="space-y-space-2 text-[12.5px]">
                  <div className="flex justify-between">
                    <dt className="text-ink-600">Appointment Bills</dt>
                    <dd className="text-ink-900 font-semibold">{formatINR(billing.stats.appointment_bills_total)}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-ink-600">Pharmacy Bills</dt>
                    <dd className="text-ink-900 font-semibold">{formatINR(billing.stats.pharmacy_bills_total)}</dd>
                  </div>
                  <div className="border-line flex justify-between border-t pt-space-2 font-bold">
                    <dt className="text-ink-700">Total Amount</dt>
                    <dd className="text-ink-900">{formatINR(billing.stats.total_amount)}</dd>
                  </div>
                </dl>
                <div
                  className={cn(
                    "mt-space-3 p-space-3 gap-space-2 flex items-center rounded-md",
                    pendingDues > 0 ? "bg-clay-100" : "bg-success-tint",
                  )}
                >
                  {pendingDues > 0 ? (
                    <AlertTriangle size={16} className="text-clay-700 shrink-0" />
                  ) : (
                    <CheckCircle2 size={16} className="text-success shrink-0" />
                  )}
                  <div>
                    <p className={cn("text-[12.5px] font-bold", pendingDues > 0 ? "text-clay-700" : "text-success")}>
                      {pendingDues > 0 ? `${formatINR(pendingDues)} pending dues` : "All dues are cleared"}
                    </p>
                  </div>
                </div>
              </>
            )}
          </Card>

          <Card className="p-space-4 h-fit">
            <h3 className="text-label mb-space-3 text-ink-900 font-bold">Other Actions</h3>
            <div className="gap-space-2 grid grid-cols-2">
              {canWriteAppointments && (
                <Button size="md" variant="secondary" onClick={onNewAppointment} className="w-full">
                  <CalendarDays size={14} /> New Appointment
                </Button>
              )}
              <Button size="md" variant="secondary" onClick={() => onGoToTab("prescriptions")} className="w-full">
                <Plus size={14} /> Add Prescription
              </Button>
              <CreateBillButton />
              <Button size="md" variant="secondary" onClick={() => window.print()} className="w-full">
                <Printer size={14} /> Print Summary
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </>
  );
}
