"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, AlertTriangle, ClipboardList, Edit3, FileText, Plus, Printer, Share2, Stethoscope } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { FilterSelect } from "@/components/ui/FilterSelect";
import { Textarea } from "@/components/ui/Input";
import { StatTile } from "@/components/portal/StatTile";
import { StatTileGrid } from "@/components/portal/StatTileGrid";
import { formatShortDateTime } from "@/lib/formatDate";
import { portalFetch } from "@/lib/portalAuth";
import {
  NOTE_TYPE_LABELS, NOTE_TYPE_ORDER,
  type ClinicalFlag, type ClinicalNote, type FlagSeverity, type NoteType,
} from "@/hooks/usePatientDetail";

type Props = {
  notes: ClinicalNote[];
  flags: ClinicalFlag[];
  onAdd: (body: {
    note_type: NoteType; diagnosis?: string; advice?: string; follow_up_plan?: string;
    follow_up_date?: string; department_name?: string; doctor_id?: string;
  }) => Promise<boolean>;
  saving: boolean;
};

const FLAG_SEVERITY_STYLES: Record<FlagSeverity, string> = {
  critical: "bg-error-tint text-error border-error/20",
  warning: "bg-clay-100 text-clay-700 border-clay-300",
  info: "bg-brand-50 text-brand-700 border-brand-200",
};

type BookingContext = { departments: { id: string; name: string }[]; doctors_by_department: Record<string, { id: string; name: string }[]> };

/** Patient Details page's "Clinical Notes" tab -- a structured note
 * (note_type/diagnosis/advice/follow_up_plan), separate from the plain
 * free-text General Notes elsewhere on this page. Reuses the same
 * department/doctor context the New Booking dialog already fetches
 * (GET /api/portal/new-booking/context) for the Add form's dropdowns. */
export function ClinicalNotesPanel({ notes, flags, onAdd, saving }: Props) {
  const [departmentFilter, setDepartmentFilter] = useState("all");
  const [noteTypeFilter, setNoteTypeFilter] = useState("all");
  const [doctorFilter, setDoctorFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const [noteType, setNoteType] = useState<NoteType>("consultation");
  const [department, setDepartment] = useState("");
  const [doctorId, setDoctorId] = useState("");
  const [body, setBody] = useState("");

  const { data: ctx } = useQuery({
    queryKey: ["portal-new-booking-context"],
    queryFn: async () => {
      const result = await portalFetch("/api/portal/new-booking/context");
      return result.ok ? (result.data as BookingContext) : null;
    },
  });
  const doctorOptions = department && ctx ? ctx.doctors_by_department[department] || [] : [];

  const filtered = notes.filter((n) => {
    if (departmentFilter !== "all" && n.department_name !== departmentFilter) return false;
    if (noteTypeFilter !== "all" && n.note_type !== noteTypeFilter) return false;
    if (doctorFilter !== "all" && n.doctor_id !== doctorFilter) return false;
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      if (!(n.diagnosis || "").toLowerCase().includes(q) && !(n.doctor_name || "").toLowerCase().includes(q) && !(n.department_name || "").toLowerCase().includes(q)) return false;
    }
    return true;
  });
  const selected = notes.find((n) => n.id === selectedId) || filtered[0] || null;

  const doctorNotes = notes.filter((n) => n.doctor_id).length;
  const followUpNotes = notes.filter((n) => n.follow_up_plan).length;
  const criticalAlerts = flags.filter((f) => f.severity === "critical").length;

  async function handleSave() {
    // One combined free-text field backs both diagnosis/advice on the
    // backend (NOTE_TYPES schema has no separate fields for this single
    // textarea) -- stored as "advice" since that's the more general of
    // the two, "Selected Note Details" renders it back as-is either way.
    const ok = await onAdd({
      note_type: noteType,
      advice: body,
      department_name: department || undefined,
      doctor_id: doctorId || undefined,
    });
    if (ok) setBody("");
  }

  return (
    <>
      <StatTileGrid cols={4} className="mb-space-4">
        <StatTile label="Total Notes" value={notes.length} icon={FileText} />
        <StatTile label="Doctor Notes" value={doctorNotes} icon={Stethoscope} tint="clay" />
        <StatTile label="Follow-up Notes" value={followUpNotes} icon={ClipboardList} tint="success" />
        <StatTile label="Critical Alerts" value={criticalAlerts} icon={AlertTriangle} tint="error" />
      </StatTileGrid>

      <div className="gap-space-4 grid grid-cols-1 items-start lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-space-4">
          <Card className="p-space-4">
            <div className="mb-space-3 flex items-center justify-between">
              <h3 className="text-label text-ink-900 font-bold">Clinical Notes ({notes.length})</h3>
            </div>
            <div className="mb-space-3 gap-space-2 flex flex-wrap items-center">
              <input
                type="text" placeholder="Search notes by keywords (e.g., diagnosis, doctor, department)…"
                value={search} onChange={(e) => setSearch(e.target.value)}
                className="border-line bg-card px-space-3 text-ink-900 focus:border-brand-400 h-9 min-w-50 flex-1 rounded-md border text-[12.5px] outline-none"
              />
              <FilterSelect
                value={departmentFilter} onChange={setDepartmentFilter} allLabel="All Departments"
                options={Array.from(new Set(notes.map((n) => n.department_name).filter((d): d is string => !!d))).map((d) => ({ value: d, label: d }))}
              />
              <FilterSelect
                value={noteTypeFilter} onChange={setNoteTypeFilter} allLabel="All Note Types"
                options={NOTE_TYPE_ORDER.map((t) => ({ value: t, label: NOTE_TYPE_LABELS[t] }))}
              />
              <FilterSelect
                value={doctorFilter} onChange={setDoctorFilter} allLabel="All Doctors"
                options={Array.from(new Map(notes.filter((n) => n.doctor_id).map((n) => [n.doctor_id as string, n.doctor_name || n.doctor_id as string])).entries()).map(([value, label]) => ({ value, label }))}
              />
            </div>

            {filtered.length === 0 ? (
              <p className="py-space-4 text-ink-400 text-center text-[13px]">No clinical notes yet.</p>
            ) : (
              <DataTable
                columns={[
                  { id: "created_at", header: "Date & Time", cell: ({ row }: { row: { original: ClinicalNote } }) => (
                    <span className="text-ink-900 font-semibold">{formatShortDateTime(row.original.created_at)}</span>
                  ) },
                  { id: "doctor_name", header: "Doctor", cell: ({ row }: { row: { original: ClinicalNote } }) => (
                    <span className="text-ink-600">{row.original.doctor_name || "—"}</span>
                  ) },
                  { id: "department_name", header: "Department", cell: ({ row }: { row: { original: ClinicalNote } }) => (
                    <span className="text-ink-600">{row.original.department_name || "—"}</span>
                  ) },
                  { id: "note_type", header: "Note Type", cell: ({ row }: { row: { original: ClinicalNote } }) => (
                    <Badge tone="brand">{NOTE_TYPE_LABELS[row.original.note_type]}</Badge>
                  ) },
                  { id: "summary", header: "Summary", cell: ({ row }: { row: { original: ClinicalNote } }) => (
                    <span className="text-ink-600 line-clamp-1">{row.original.diagnosis || row.original.advice || "—"}</span>
                  ) },
                  { id: "follow_up_date", header: "Follow-up", cell: ({ row }: { row: { original: ClinicalNote } }) => (
                    <span className="text-ink-600">{row.original.follow_up_date || "—"}</span>
                  ) },
                ]}
                data={filtered}
                getRowId={(n: ClinicalNote) => String(n.id)}
                onRowClick={(n: ClinicalNote) => setSelectedId(n.id)}
                rowClassName={(n: ClinicalNote) => (selected?.id === n.id ? "bg-brand-50" : "")}
                pageSize={8}
              />
            )}
          </Card>

          <Card className="p-space-4">
            <h3 className="text-label mb-space-3 text-ink-900 font-bold">Add Clinical Note</h3>
            <div className="mb-space-3 gap-space-3 grid grid-cols-1 sm:grid-cols-2">
              <div>
                <label className="mb-space-1 text-ink-600 block text-[12px] font-semibold">Note Type *</label>
                <select value={noteType} onChange={(e) => setNoteType(e.target.value as NoteType)} className="border-line bg-card px-space-3 text-ink-900 h-10 w-full rounded-md border text-[13px]">
                  {NOTE_TYPE_ORDER.map((t) => <option key={t} value={t}>{NOTE_TYPE_LABELS[t]}</option>)}
                </select>
              </div>
              <div>
                <label className="mb-space-1 text-ink-600 block text-[12px] font-semibold">Department</label>
                <select value={department} onChange={(e) => { setDepartment(e.target.value); setDoctorId(""); }} className="border-line bg-card px-space-3 text-ink-900 h-10 w-full rounded-md border text-[13px]">
                  <option value="">Select department</option>
                  {ctx?.departments.map((d) => <option key={d.id} value={d.name}>{d.name}</option>)}
                </select>
              </div>
            </div>
            {department && doctorOptions.length > 0 && (
              <div className="mb-space-3">
                <label className="mb-space-1 text-ink-600 block text-[12px] font-semibold">Doctor</label>
                <select value={doctorId} onChange={(e) => setDoctorId(e.target.value)} className="border-line bg-card px-space-3 text-ink-900 h-10 w-full rounded-md border text-[13px]">
                  <option value="">Select doctor</option>
                  {doctorOptions.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                </select>
              </div>
            )}
            <Textarea
              id="clinical-note-body"
              value={body} onChange={(e) => setBody(e.target.value)} rows={5} maxLength={4000}
              placeholder="Enter clinical note details, including history, examination, diagnosis/assessment, advice, and follow-up plan…"
            />
            <p className="text-hint mt-space-1 text-right">{body.length} / 4000</p>
            <div className="mt-space-2 gap-space-2 flex justify-end">
              <Button variant="secondary" onClick={() => setBody("")}>Clear</Button>
              <Button disabled={saving || !body.trim()} onClick={handleSave}>
                {saving ? "Saving…" : "Save Clinical Note"}
              </Button>
            </div>
          </Card>
        </div>

        <div className="space-y-space-4">
          <Card className="p-space-4">
            <h3 className="text-label mb-space-3 text-ink-900 font-bold">Selected Note Details</h3>
            {!selected ? (
              <p className="text-hint text-[12.5px]">No notes yet.</p>
            ) : (
              <>
                <dl className="space-y-space-2 text-[12.5px]">
                  <div className="flex justify-between"><dt className="text-hint">Note ID</dt><dd className="text-ink-900 font-mono font-semibold">NOTE-{selected.id}</dd></div>
                  <div className="flex justify-between"><dt className="text-hint">Date & Time</dt><dd className="text-ink-900 font-semibold">{formatShortDateTime(selected.created_at)}</dd></div>
                  <div className="flex justify-between"><dt className="text-hint">Doctor</dt><dd className="text-ink-900 font-semibold">{selected.doctor_name || "—"}</dd></div>
                  <div className="flex justify-between"><dt className="text-hint">Department</dt><dd className="text-ink-900 font-semibold">{selected.department_name || "—"}</dd></div>
                  <div className="flex justify-between"><dt className="text-hint">Note Type</dt><dd><Badge tone="brand">{NOTE_TYPE_LABELS[selected.note_type]}</Badge></dd></div>
                </dl>
                {selected.diagnosis && (
                  <div className="mt-space-3">
                    <p className="text-ink-900 text-[12.5px] font-bold">Diagnosis / Assessment</p>
                    <p className="text-ink-700 text-[12.5px]">{selected.diagnosis}</p>
                  </div>
                )}
                {selected.advice && (
                  <div className="mt-space-3">
                    <p className="text-ink-900 text-[12.5px] font-bold">Advice</p>
                    <ul className="list-disc space-y-space-1 pl-space-4 text-[12.5px]">
                      {selected.advice.split("\n").filter(Boolean).map((line, i) => <li key={i} className="text-ink-700">{line}</li>)}
                    </ul>
                  </div>
                )}
                {selected.follow_up_plan && (
                  <div className="mt-space-3">
                    <p className="text-ink-900 text-[12.5px] font-bold">Follow-up Plan</p>
                    <p className="text-ink-700 text-[12.5px]">{selected.follow_up_plan}{selected.follow_up_date ? ` (${selected.follow_up_date})` : ""}</p>
                  </div>
                )}
              </>
            )}
          </Card>

          <Card className="p-space-4">
            <h3 className="text-label mb-space-3 text-ink-900 font-bold">Clinical Flags</h3>
            {flags.length === 0 ? (
              <p className="text-hint text-[12.5px]">No active clinical flags.</p>
            ) : (
              <div className="space-y-space-2">
                {flags.map((f) => (
                  <div key={f.id} className={`rounded-md border p-space-3 ${FLAG_SEVERITY_STYLES[f.severity]}`}>
                    <div className="gap-space-2 flex items-center text-[12.5px] font-bold"><AlertCircle size={14} /> {f.title}</div>
                    {f.description && <p className="mt-space-1 text-[11.5px]">{f.description}</p>}
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card className="p-space-4">
            <h3 className="text-label mb-space-3 text-ink-900 font-bold">Quick Actions</h3>
            <div className="gap-space-2 grid grid-cols-2">
              <Button size="md" variant="secondary" onClick={() => document.getElementById("clinical-note-body")?.focus()}>
                <Plus size={14} /> Add Note
              </Button>
              <Button size="md" variant="secondary" disabled={!selected}><Edit3 size={14} /> Edit Note</Button>
              <Button size="md" variant="secondary" onClick={() => window.print()} disabled={!selected}><Printer size={14} /> Print Note</Button>
              <Button size="md" variant="secondary" disabled={!selected}><Share2 size={14} /> Share with Patient</Button>
            </div>
          </Card>
        </div>
      </div>
    </>
  );
}
