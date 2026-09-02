"use client";

import { Fragment } from "react";
import { ArrowLeft, ChevronDown, ChevronUp, FileText, Search, Send, Upload } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Input";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { cn } from "@/lib/cn";
import { formatDate, formatDateTime, formatShortDateTime } from "@/lib/formatDate";
import { TYPE_LABELS } from "@/hooks/useAppointments";
import { usePatientDetail } from "@/hooks/usePatientDetail";

// Same status/source styling as /portal/appointments (STATUS_STYLES/LABELS,
// SOURCE_LABELS there) -- duplicated per-file rather than shared, matching
// this codebase's existing convention for these small per-page Record maps
// (e.g. DoctorTodayAppointments.tsx has its own copy too).
const STATUS_STYLES: Record<string, string> = {
  booked: "bg-success-tint text-success",
  cancelled: "bg-error-tint text-error",
  rescheduled: "bg-clay-100 text-clay-700",
  attended: "bg-success-tint text-success",
  no_show: "bg-error-tint text-error",
};
const STATUS_LABELS: Record<string, string> = {
  booked: "Confirmed", cancelled: "Cancelled", rescheduled: "Rescheduled",
  attended: "Attended", no_show: "No-show",
};
const SOURCE_LABELS: Record<string, string> = { whatsapp: "WhatsApp", staff: "Walk-in" };
const TYPE_TAB_ORDER = ["all", "new", "followup", "tele", "second_opinion", "diagnostic", "lab", "daycare", "other"];

// WhatsApp menu restructuring: Reports & Prescriptions' "View
// Prescriptions/Lab Reports/Diagnostic Reports" submenu rows filter on
// this -- kept in sync by hand with portal/routes/documents.py's
// _VALID_DOCUMENT_TYPES.
const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  prescription: "Prescription", lab_report: "Lab Report", diagnostic_report: "Diagnostic Report", other: "Other",
};
const DOCUMENT_TYPE_OPTIONS = [
  { value: "prescription", label: "Prescription" },
  { value: "lab_report", label: "Lab Report" },
  { value: "diagnostic_report", label: "Diagnostic Report" },
  { value: "other", label: "Other" },
];

export default function PatientDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const patientId = params.id;
  const { hospital, ready } = usePortalGuard();

  const {
    data, error,
    dob, setDob, gender, setGender, address, setAddress, savingDemographics, handleSaveDemographics,
    savingStatus, handleSetStatus,
    expandedVisit, setExpandedVisit, noteDraft, setNoteDraft, savingNote,
    generalNoteDraft, setGeneralNoteDraft, savingGeneralNote,
    handleAddNote,
    fileInputRef, uploading, handleUpload, documentType, setDocumentType,
    sendingDocId, sendError, handleSendToWhatsapp,
    visitSearch, setVisitSearch, visitTimeFilter, setVisitTimeFilter,
    visitStatusFilter, setVisitStatusFilter, visitTypeFilter, setVisitTypeFilter,
    visitTypeCounts, filteredVisits,
  } = usePatientDetail(patientId, ready);

  if (!data) {
    return (
      <PortalShell hospital={hospital} active="patients">
          {error ? <p className="text-[13px] text-error">{error}</p> : <p className="text-[13px] text-ink-400">Loading…</p>}
      </PortalShell>
    );
  }

  const { patient, visit_history, notes, documents } = data;
  const generalNotes = notes.filter((n) => n.appointment_id === null);
  const notesByVisit = (visitId: number) => notes.filter((n) => n.appointment_id === visitId);

  return (
    <PortalShell hospital={hospital} active="patients">
        <button
          type="button"
          onClick={() => router.push("/portal/patients")}
          className="mb-space-3 flex items-center gap-space-1 text-[12.5px] font-semibold text-brand-600 hover:underline"
        >
          <ArrowLeft size={14} /> All patients
        </button>

        <div className="mb-space-5 flex items-center gap-space-3">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-brand-100 text-[18px] font-bold text-brand-700">
            {(patient.name || patient.phone).trim().charAt(0).toUpperCase()}
          </div>
          <div className="min-w-0">
            <h1 className="text-display !text-[24px]">{patient.name || patient.phone}</h1>
            <div className="flex flex-wrap items-center gap-space-2 text-[13px] text-ink-600">
              <span>{patient.phone}</span>
              {patient.patient_display_id && (
                <span className="rounded-full bg-brand-50 px-space-2 py-0.5 font-mono text-[11.5px] font-semibold text-brand-700">
                  {patient.patient_display_id}
                </span>
              )}
              {patient.mrn && (
                <span className="rounded-full bg-ink-50 px-space-2 py-0.5 font-mono text-[11.5px] font-semibold text-ink-600">
                  MRN {patient.mrn}
                </span>
              )}
              {patient.status !== "active" && (
                <Badge tone={patient.status === "blocked" ? "clay" : "neutral"}>
                  {patient.status === "blocked" ? "Blocked" : "Inactive"}
                </Badge>
              )}
            </div>
          </div>
        </div>

        {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

        <div className="grid grid-cols-1 gap-space-4 lg:grid-cols-[1fr_320px]">
          <div className="space-y-space-4">
            <Card className="p-space-4">
              <h3 className="text-label mb-space-3 font-bold text-ink-900">Visit history</h3>

              {visit_history.length === 0 ? (
                <p className="py-space-4 text-center text-[13px] text-ink-400">No visits yet.</p>
              ) : (
                <>
                  {/* Same filter shape as /portal/appointments: type tabs,
                      search, status dropdown -- plus an upcoming/past time
                      filter this single-patient view adds on top. */}
                  <div className="mb-space-3 flex flex-wrap gap-space-2">
                    {TYPE_TAB_ORDER.filter((id) => id === "all" || (visitTypeCounts[id] || 0) > 0 || visitTypeFilter === id).map((id) => (
                      <button
                        key={id}
                        type="button"
                        onClick={() => setVisitTypeFilter(id)}
                        className={cn(
                          "rounded-full border px-space-3 py-space-1 text-[12.5px] font-semibold transition-colors duration-150",
                          visitTypeFilter === id
                            ? "border-brand-600 bg-brand-600 text-white"
                            : "border-line bg-card text-ink-600 hover:border-brand-300 hover:bg-brand-50",
                        )}
                      >
                        {id === "all" ? "All" : id === "other" ? "Other" : TYPE_LABELS[id]}
                        <span className={cn("ml-space-1 tabular-nums", visitTypeFilter === id ? "text-white/80" : "text-ink-400")}>
                          {visitTypeCounts[id] || 0}
                        </span>
                      </button>
                    ))}
                  </div>

                  <div className="mb-space-3 flex flex-wrap items-center gap-space-2">
                    <div className="flex gap-space-1 rounded-md border border-line bg-paper p-0.5">
                      {(["all", "upcoming", "past"] as const).map((t) => (
                        <button
                          key={t}
                          type="button"
                          onClick={() => setVisitTimeFilter(t)}
                          className={cn(
                            "rounded px-space-2 py-1 text-[12px] font-semibold capitalize transition-colors duration-150",
                            visitTimeFilter === t ? "bg-card text-ink-900 shadow-[var(--shadow-sm)]" : "text-ink-400 hover:text-ink-700",
                          )}
                        >
                          {t}
                        </button>
                      ))}
                    </div>
                    <div className="relative min-w-[180px] flex-1">
                      <Search size={14} className="pointer-events-none absolute top-1/2 left-space-3 -translate-y-1/2 text-ink-400" />
                      <input
                        type="text"
                        placeholder="Search doctor, department, or reference…"
                        value={visitSearch}
                        onChange={(e) => setVisitSearch(e.target.value)}
                        className="h-9 w-full rounded-md border border-line bg-card pl-space-8 pr-space-3 text-[12.5px] text-ink-900 outline-none focus:border-brand-400"
                      />
                    </div>
                    <select
                      value={visitStatusFilter}
                      onChange={(e) => setVisitStatusFilter(e.target.value)}
                      className="h-9 rounded-md border border-line bg-card px-space-2 text-[12.5px] text-ink-900"
                    >
                      <option value="all">All statuses</option>
                      {Object.entries(STATUS_LABELS).map(([value, label]) => (
                        <option key={value} value={value}>{label}</option>
                      ))}
                    </select>
                  </div>

                  {filteredVisits.length === 0 ? (
                    <p className="py-space-4 text-center text-[13px] text-ink-400">No visits match this filter.</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-[13px]">
                        <thead>
                          <tr className="border-b border-line text-[11.5px] text-ink-400 uppercase">
                            <th className="pb-space-2 font-semibold">Appointment time</th>
                            <th className="pb-space-2 font-semibold">Booked</th>
                            <th className="pb-space-2 font-semibold">Reference</th>
                            <th className="pb-space-2 font-semibold">Doctor</th>
                            <th className="pb-space-2 font-semibold">Department</th>
                            <th className="pb-space-2 font-semibold">Type</th>
                            <th className="pb-space-2 font-semibold">Source</th>
                            <th className="pb-space-2 font-semibold">Status</th>
                            <th className="pb-space-2 font-semibold"></th>
                          </tr>
                        </thead>
                        <tbody>
                          {filteredVisits.map((v) => {
                            const expanded = expandedVisit === v.id;
                            const visitNotes = notesByVisit(v.id);
                            return (
                              <Fragment key={v.id}>
                                <tr className={cn("border-b border-line last:border-0 hover:bg-black/[0.02]", expanded && "border-b-0")}>
                                  <td className="py-space-2 whitespace-nowrap tabular-nums text-ink-600">{formatShortDateTime(v.scheduled_at)}</td>
                                  <td className="py-space-2 whitespace-nowrap tabular-nums text-ink-400">
                                    {v.created_at ? formatShortDateTime(v.created_at) : "—"}
                                  </td>
                                  <td className="py-space-2 whitespace-nowrap font-mono text-[12px] text-ink-400">{v.reference_id || "—"}</td>
                                  <td className="py-space-2 text-ink-600">{v.doctor_name}</td>
                                  <td className="py-space-2 text-ink-600">{v.department_name}</td>
                                  <td className="py-space-2 text-ink-600">
                                    <div>{v.appointment_type_id ? TYPE_LABELS[v.appointment_type_id] || v.appointment_type_id : "—"}</div>
                                    {v.appointment_type_id === "tele" && v.video_link && (
                                      <a
                                        href={v.video_link}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-[11.5px] font-semibold text-brand-600 hover:underline"
                                      >
                                        🎥 Join
                                      </a>
                                    )}
                                  </td>
                                  <td className="py-space-2 text-ink-600">{SOURCE_LABELS[v.source] || v.source}</td>
                                  <td className="py-space-2">
                                    <span className={cn("rounded-full px-space-2 py-0.5 text-[11px] font-semibold", STATUS_STYLES[v.status] || "bg-black/[0.04] text-ink-600")}>
                                      {STATUS_LABELS[v.status] || v.status}
                                    </span>
                                  </td>
                                  <td className="py-space-2 text-right whitespace-nowrap">
                                    <button
                                      type="button"
                                      onClick={() => setExpandedVisit(expanded ? null : v.id)}
                                      className="inline-flex items-center gap-1 text-[12px] font-semibold text-brand-600 hover:underline"
                                    >
                                      {visitNotes.length > 0 ? `${visitNotes.length} note${visitNotes.length > 1 ? "s" : ""}` : "Notes"}
                                      {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                    </button>
                                  </td>
                                </tr>
                                {expanded && (
                                  <tr className="border-b border-line last:border-0">
                                    <td colSpan={9} className="pb-space-3">
                                      <div className="rounded-lg border border-line bg-paper p-space-3">
                                        {visitNotes.length === 0 ? (
                                          <p className="text-hint mb-space-3">No notes for this visit yet.</p>
                                        ) : (
                                          <ul className="mb-space-3 space-y-space-2">
                                            {visitNotes.map((n) => (
                                              <li key={n.id} className="rounded-md bg-card p-space-3 text-[13px]">
                                                <p className="text-ink-900">{n.note_text}</p>
                                                <p className="text-hint mt-space-1">
                                                  {n.doctor_name ? `${n.doctor_name} · ` : ""}
                                                  {formatDateTime(n.created_at)}
                                                </p>
                                              </li>
                                            ))}
                                          </ul>
                                        )}
                                        <div className="flex items-end gap-space-2">
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
                                    </td>
                                  </tr>
                                )}
                              </Fragment>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </>
              )}
            </Card>

            <Card className="p-space-4">
              <h3 className="text-label mb-space-3 font-bold text-ink-900">General notes</h3>
              <p className="text-hint mb-space-3">Not tied to a specific visit — e.g. a walk-in or a phone conversation.</p>
              {generalNotes.length > 0 && (
                <ul className="mb-space-3 space-y-space-2">
                  {generalNotes.map((n) => (
                    <li key={n.id} className="rounded-md bg-paper p-space-3 text-[13px]">
                      <p className="text-ink-900">{n.note_text}</p>
                      <p className="text-hint mt-space-1">{formatDateTime(n.created_at)}</p>
                    </li>
                  ))}
                </ul>
              )}
              <div className="flex items-end gap-space-2">
                <Textarea
                  placeholder="Add a general note…"
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

            <Card className="p-space-4">
              <div className="mb-space-3 flex items-center justify-between gap-space-2">
                <h3 className="text-label font-bold text-ink-900">Documents</h3>
                <div className="flex items-center gap-space-2">
                  <select
                    value={documentType}
                    onChange={(e) => setDocumentType(e.target.value)}
                    disabled={uploading}
                    aria-label="Document type"
                    className="h-8 rounded-md border border-line bg-card px-space-2 text-[12.5px] text-ink-900"
                  >
                    {DOCUMENT_TYPE_OPTIONS.map(({ value, label }) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                  <label className="flex cursor-pointer items-center gap-space-2 text-[12.5px] font-semibold text-brand-600 hover:underline">
                    <Upload size={14} /> {uploading ? "Uploading…" : "Upload document"}
                    <input ref={fileInputRef} type="file" className="hidden" onChange={handleUpload} disabled={uploading} />
                  </label>
                </div>
              </div>
              {documents.length === 0 ? (
                <p className="py-space-4 text-center text-[13px] text-ink-400">No documents yet.</p>
              ) : (
                <ul className="divide-y divide-line">
                  {documents.map((doc) => (
                    <li key={doc.id} className="py-space-3">
                      <div className="flex flex-col gap-space-2 sm:flex-row sm:items-center sm:justify-between">
                        <div className="flex items-center gap-space-2 overflow-hidden">
                          <FileText size={16} className="shrink-0 text-ink-400" />
                          <div className="overflow-hidden">
                            <p className="truncate text-[13px] font-semibold text-ink-900">{doc.file_name}</p>
                            <p className="text-hint">
                              {DOCUMENT_TYPE_LABELS[doc.document_type] ?? doc.document_type} · Uploaded {formatDate(doc.uploaded_at)}
                              {doc.sent_to_whatsapp_at ? ` · Sent ${formatDate(doc.sent_to_whatsapp_at)}` : ""}
                            </p>
                          </div>
                        </div>
                        <div className="flex shrink-0 items-center gap-space-2">
                          {doc.sent_to_whatsapp_at && <Badge tone="success">Sent</Badge>}
                          <Button
                            size="md"
                            variant="secondary"
                            onClick={() => handleSendToWhatsapp(doc.id)}
                            disabled={sendingDocId === doc.id}
                          >
                            <Send size={13} /> {sendingDocId === doc.id ? "Sending…" : "Send to WhatsApp"}
                          </Button>
                        </div>
                      </div>
                      {sendError[doc.id] && <p className="mt-space-2 text-[12px] text-error">{sendError[doc.id]}</p>}
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          <Card className="h-fit p-space-4">
            <h3 className="text-label mb-space-1 font-bold text-ink-900">Record status</h3>
            <p className="text-hint mb-space-3">
              Blocking a patient stops them from being selected/booked against on WhatsApp -- their appointment
              history and Patient ID are untouched, and any phone still linked to them is unaffected.
            </p>
            {patient.status === "active" ? (
              <Button size="md" variant="secondary" onClick={() => handleSetStatus("blocked")} disabled={savingStatus} className="w-full">
                {savingStatus ? "Saving…" : "Block this patient"}
              </Button>
            ) : (
              <Button size="md" onClick={() => handleSetStatus("active")} disabled={savingStatus} className="w-full">
                {savingStatus ? "Saving…" : "Reactivate this patient"}
              </Button>
            )}
          </Card>

          <Card className="h-fit p-space-4">
            <h3 className="text-label mb-space-3 font-bold text-ink-900">Demographics</h3>
            <Field label="Date of birth" htmlFor="dob">
              <Input id="dob" type="date" value={dob} onChange={(e) => setDob(e.target.value)} />
            </Field>
            <Field label="Gender" htmlFor="gender">
              <Input id="gender" value={gender} onChange={(e) => setGender(e.target.value)} placeholder="Optional" />
            </Field>
            <Field label="Address" htmlFor="address">
              <Textarea id="address" value={address} onChange={(e) => setAddress(e.target.value)} rows={3} placeholder="Optional" />
            </Field>
            <Button size="md" onClick={handleSaveDemographics} disabled={savingDemographics} className="w-full">
              {savingDemographics ? "Saving…" : "Save"}
            </Button>
          </Card>
        </div>
    </PortalShell>
  );
}
