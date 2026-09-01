"use client";

import { ArrowLeft, ChevronDown, ChevronUp, FileText, Send, Upload } from "lucide-react";
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
import { formatDate, formatDateTime } from "@/lib/formatDate";
import { usePatientDetail } from "@/hooks/usePatientDetail";

const STATUS_STYLES: Record<string, string> = {
  booked: "bg-success-tint text-success",
  cancelled: "bg-error-tint text-error",
  rescheduled: "bg-clay-100 text-clay-700",
};
const STATUS_LABELS: Record<string, string> = { booked: "Confirmed", cancelled: "Cancelled", rescheduled: "Rescheduled" };

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
    fileInputRef, uploading, handleUpload,
    sendingDocId, sendError, handleSendToWhatsapp,
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
          <div>
            <h1 className="text-display !text-[24px]">{patient.name || patient.phone}</h1>
            <div className="flex items-center gap-space-2 text-[13px] text-ink-600">
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
                <ul className="divide-y divide-line">
                  {visit_history.map((v) => {
                    const expanded = expandedVisit === v.id;
                    const visitNotes = notesByVisit(v.id);
                    return (
                      <li key={v.id} className="py-space-3">
                        <button
                          type="button"
                          onClick={() => setExpandedVisit(expanded ? null : v.id)}
                          className="flex w-full items-center justify-between gap-space-3 text-left"
                        >
                          <div>
                            <p className="text-[13.5px] font-semibold text-ink-900">
                              {formatDateTime(v.scheduled_at)} — {v.doctor_name}
                            </p>
                            <p className="text-[12px] text-ink-600">
                              {v.department_name}
                              {visitNotes.length > 0 ? ` · ${visitNotes.length} note${visitNotes.length > 1 ? "s" : ""}` : ""}
                            </p>
                          </div>
                          <div className="flex items-center gap-space-2">
                            <span className={cn("rounded-full px-space-2 py-0.5 text-[11px] font-semibold", STATUS_STYLES[v.status] || "bg-black/[0.04] text-ink-600")}>
                              {STATUS_LABELS[v.status] || v.status}
                            </span>
                            {expanded ? <ChevronUp size={16} className="text-ink-400" /> : <ChevronDown size={16} className="text-ink-400" />}
                          </div>
                        </button>

                        {expanded && (
                          <div className="mt-space-3 rounded-lg border border-line bg-paper p-space-3">
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
                        )}
                      </li>
                    );
                  })}
                </ul>
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
              <div className="mb-space-3 flex items-center justify-between">
                <h3 className="text-label font-bold text-ink-900">Documents</h3>
                <label className="flex cursor-pointer items-center gap-space-2 text-[12.5px] font-semibold text-brand-600 hover:underline">
                  <Upload size={14} /> {uploading ? "Uploading…" : "Upload document"}
                  <input ref={fileInputRef} type="file" className="hidden" onChange={handleUpload} disabled={uploading} />
                </label>
              </div>
              {documents.length === 0 ? (
                <p className="py-space-4 text-center text-[13px] text-ink-400">No documents yet.</p>
              ) : (
                <ul className="divide-y divide-line">
                  {documents.map((doc) => (
                    <li key={doc.id} className="py-space-3">
                      <div className="flex items-center justify-between gap-space-3">
                        <div className="flex items-center gap-space-2 overflow-hidden">
                          <FileText size={16} className="shrink-0 text-ink-400" />
                          <div className="overflow-hidden">
                            <p className="truncate text-[13px] font-semibold text-ink-900">{doc.file_name}</p>
                            <p className="text-hint">
                              Uploaded {formatDate(doc.uploaded_at)}
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
