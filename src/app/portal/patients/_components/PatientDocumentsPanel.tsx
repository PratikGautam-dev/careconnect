"use client";

import { useState } from "react";
import { Download, Eye, FileText, Printer, Send, Upload } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { FilterSelect } from "@/components/ui/FilterSelect";
import { Textarea } from "@/components/ui/Input";
import { StatTile } from "@/components/portal/StatTile";
import { StatTileGrid } from "@/components/portal/StatTileGrid";
import { formatDate, formatShortDateTime } from "@/lib/formatDate";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";
import type { PatientDocument } from "@/hooks/usePatientDetail";

export const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  prescription: "Prescription",
  lab_report: "Lab Report",
  diagnostic_report: "Diagnostic Report",
  other: "Other",
};
export const DOCUMENT_TYPE_OPTIONS = [
  { value: "prescription", label: "Prescription" },
  { value: "lab_report", label: "Lab Report" },
  { value: "diagnostic_report", label: "Diagnostic Report" },
  { value: "other", label: "Other" },
];
const DOCUMENT_CATEGORY_TONES: Record<string, "brand" | "clay" | "success" | "neutral"> = {
  prescription: "brand",
  lab_report: "success",
  diagnostic_report: "clay",
  other: "neutral",
};

function fileExt(fileName: string): string {
  const parts = fileName.split(".");
  return parts.length > 1 ? parts[parts.length - 1].toUpperCase() : "FILE";
}

type Props = {
  patientId: number;
  documents: PatientDocument[];
  documentType: string;
  setDocumentType: (v: string) => void;
  uploading: boolean;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  handleUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
  sendingDocId: number | null;
  sendError: Record<number, string>;
  handleSendToWhatsapp: (docId: number) => void;
  onSaveRemarks: (documentId: number, remarks: string) => void;
  savingRemarks: boolean;
};

/** Documents tab -- stat tiles by category, a filterable table, a
 * View/Download action (resolves a short-lived signed URL on demand, see
 * portal_get_patient_document_url()), "Folders/Quick Filters" shortcuts
 * onto the same category filter the dropdown already uses, and a
 * per-document Remarks box. */
export function PatientDocumentsPanel({
  patientId, documents, documentType, setDocumentType, uploading, fileInputRef, handleUpload,
  sendingDocId, sendError, handleSendToWhatsapp, onSaveRemarks, savingRemarks,
}: Props) {
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [fileTypeFilter, setFileTypeFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [remarksDraft, setRemarksDraft] = useState<string | null>(null);

  const fileTypeOptions = Array.from(new Set(documents.map((d) => fileExt(d.file_name)))).map((ext) => ({
    value: ext, label: ext,
  }));

  const filtered = documents.filter((d) => {
    if (categoryFilter !== "all" && d.document_type !== categoryFilter) return false;
    if (fileTypeFilter !== "all" && fileExt(d.file_name) !== fileTypeFilter) return false;
    if (search.trim() && !d.file_name.toLowerCase().includes(search.trim().toLowerCase())) return false;
    return true;
  });

  const selected = documents.find((d) => d.id === selectedId) || filtered[0] || null;
  const remarksValue = remarksDraft !== null ? remarksDraft : selected?.remarks || "";

  const countByType = (type: string) => documents.filter((d) => d.document_type === type).length;

  async function openDocument(doc: PatientDocument, download: boolean) {
    // Opens the tab synchronously, inside the click's own user-gesture
    // chain, THEN points it at the real URL once the signed-URL fetch
    // resolves -- a window.open() called only after an awaited fetch is
    // no longer inside that gesture chain and gets silently blocked as a
    // popup by Chrome/Firefox (download doesn't need this -- an <a
    // download> click isn't subject to the same popup-blocker rule).
    const newTab = download ? null : window.open("", "_blank", "noopener,noreferrer");
    const result = await portalFetch(`/api/portal/patients/${patientId}/documents/${doc.id}/view-url`);
    if (!result.ok) {
      newTab?.close();
      toast.error("Couldn't open document", result.unauthorized ? "Session expired." : result.error);
      return;
    }
    const { url } = result.data as { url: string };
    if (download) {
      const a = document.createElement("a");
      a.href = url;
      a.download = doc.file_name;
      a.click();
    } else if (newTab) {
      newTab.location.href = url;
    }
  }

  return (
    <>
      <StatTileGrid cols={5} className="mb-space-4">
        <StatTile label="Total Documents" value={documents.length} icon={FileText} />
        <StatTile label="Prescriptions" value={countByType("prescription")} icon={FileText} tint="clay" />
        <StatTile label="Lab Reports" value={countByType("lab_report")} icon={FileText} tint="success" />
        <StatTile label="Diagnostic Reports" value={countByType("diagnostic_report")} icon={FileText} />
        <StatTile label="Other" value={countByType("other")} icon={FileText} tint="clay" />
      </StatTileGrid>

      <div className="gap-space-4 grid grid-cols-1 lg:grid-cols-3">
      <div className="lg:col-span-2 space-y-space-4">
        <Card className="p-space-4">
          <div className="mb-space-3 gap-space-2 flex flex-wrap items-center justify-between">
            <div>
              <h3 className="text-label text-ink-900 font-bold">All Documents ({documents.length})</h3>
            </div>
            <div className="gap-space-2 flex flex-wrap items-center">
              <select
                value={documentType}
                onChange={(e) => setDocumentType(e.target.value)}
                disabled={uploading}
                aria-label="Document type"
                className="border-line bg-card px-space-2 text-ink-900 h-8 rounded-md border text-[12.5px]"
              >
                {DOCUMENT_TYPE_OPTIONS.map(({ value, label }) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
              <label className="gap-space-2 text-brand-600 flex cursor-pointer items-center text-[12.5px] font-semibold hover:underline">
                <Upload size={14} /> {uploading ? "Uploading…" : "Upload document"}
                <input ref={fileInputRef} type="file" className="hidden" onChange={handleUpload} disabled={uploading} />
              </label>
            </div>
          </div>

          <div className="mb-space-3 gap-space-2 flex flex-wrap items-center">
            <input
              type="text"
              placeholder="Search by document name…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="border-line bg-card px-space-3 text-ink-900 focus:border-brand-400 h-9 min-w-50 flex-1 rounded-md border text-[12.5px] outline-none"
            />
            <FilterSelect
              value={categoryFilter} onChange={setCategoryFilter} allLabel="All Categories"
              options={Object.entries(DOCUMENT_TYPE_LABELS).map(([value, label]) => ({ value, label }))}
            />
            <FilterSelect value={fileTypeFilter} onChange={setFileTypeFilter} allLabel="All File Types" options={fileTypeOptions} />
          </div>

          {filtered.length === 0 ? (
            <p className="py-space-4 text-ink-400 text-center text-[13px]">No documents match.</p>
          ) : (
            <DataTable
              columns={[
                { id: "file_name", header: "Document Name", cell: ({ row }: { row: { original: PatientDocument } }) => (
                  <button type="button" onClick={() => { setSelectedId(row.original.id); setRemarksDraft(null); }} className="gap-space-2 flex items-center text-left">
                    <FileText size={14} className="text-ink-400 shrink-0" />
                    <span className="text-ink-900 text-[12.5px] font-semibold">{row.original.file_name}</span>
                  </button>
                ) },
                { id: "document_type", header: "Category", cell: ({ row }: { row: { original: PatientDocument } }) => (
                  <Badge tone={DOCUMENT_CATEGORY_TONES[row.original.document_type] ?? "neutral"}>
                    {DOCUMENT_TYPE_LABELS[row.original.document_type] ?? row.original.document_type}
                  </Badge>
                ) },
                { id: "appointment_id", header: "Related Visit", cell: ({ row }: { row: { original: PatientDocument } }) => (
                  <span className="text-ink-600">{row.original.appointment_id ? `APT-${row.original.appointment_id}` : "—"}</span>
                ) },
                { id: "uploaded_at", header: "Date", cell: ({ row }: { row: { original: PatientDocument } }) => (
                  <span className="text-ink-600">{formatShortDateTime(row.original.uploaded_at)}</span>
                ) },
                { id: "file_type", header: "File Type", cell: ({ row }: { row: { original: PatientDocument } }) => (
                  <Badge tone="neutral">{fileExt(row.original.file_name)}</Badge>
                ) },
                { id: "actions", header: "Actions", enableHiding: false, cell: ({ row }: { row: { original: PatientDocument } }) => (
                  <div className="gap-space-1 flex items-center">
                    <Button size="md" variant="secondary" onClick={() => openDocument(row.original, false)}><Eye size={13} /> View</Button>
                    <Button size="md" variant="secondary" onClick={() => openDocument(row.original, true)}><Download size={13} /></Button>
                  </div>
                ) },
              ]}
              data={filtered}
              getRowId={(d: PatientDocument) => String(d.id)}
              onRowClick={(d: PatientDocument) => { setSelectedId(d.id); setRemarksDraft(null); }}
              rowClassName={(d: PatientDocument) => (selected?.id === d.id ? "bg-brand-50" : "")}
              pageSize={10}
            />
          )}
        </Card>

        <Card className="p-space-4">
          <h3 className="text-label mb-space-3 text-ink-900 font-bold">Document Remarks / Notes</h3>
          {!selected ? (
            <p className="text-hint text-[12.5px]">Select a document to add remarks.</p>
          ) : (
            <>
              <Textarea
                value={remarksValue}
                onChange={(e) => setRemarksDraft(e.target.value)}
                rows={3}
                placeholder="Add notes or remarks about this document, e.g., document validity, follow-up, or any important details…"
              />
              <div className="mt-space-2 flex justify-end">
                <Button
                  size="md"
                  disabled={savingRemarks || remarksDraft === null}
                  onClick={() => { onSaveRemarks(selected.id, remarksDraft ?? ""); setRemarksDraft(null); }}
                >
                  {savingRemarks ? "Saving…" : "Save Remarks"}
                </Button>
              </div>
            </>
          )}
        </Card>
      </div>

      <div className="space-y-space-4">
        <Card className="p-space-4">
          <h3 className="text-label mb-space-3 text-ink-900 font-bold">Selected Document Details</h3>
          {!selected ? (
            <p className="text-hint text-[12.5px]">No document selected.</p>
          ) : (
            <dl className="space-y-space-2 text-[12.5px]">
              <div className="flex justify-between"><dt className="text-hint">Document Title</dt><dd className="text-ink-900 font-semibold">{selected.file_name}</dd></div>
              <div className="flex justify-between"><dt className="text-hint">Category</dt><dd className="text-ink-900 font-semibold">{DOCUMENT_TYPE_LABELS[selected.document_type] ?? selected.document_type}</dd></div>
              <div className="flex justify-between"><dt className="text-hint">Linked Reference</dt><dd className="text-ink-900 font-semibold">{selected.appointment_id ? `APT-${selected.appointment_id}` : "—"}</dd></div>
              <div className="flex justify-between"><dt className="text-hint">Uploaded On</dt><dd className="text-ink-900 font-semibold">{formatDate(selected.uploaded_at)}</dd></div>
              <div className="flex justify-between"><dt className="text-hint">Sent to WhatsApp</dt><dd className="text-ink-900 font-semibold">{selected.sent_to_whatsapp_at ? formatDate(selected.sent_to_whatsapp_at) : "Not sent"}</dd></div>
            </dl>
          )}
        </Card>

        <Card className="p-space-4">
          <h3 className="text-label mb-space-3 text-ink-900 font-bold">Folders / Quick Filters</h3>
          <div className="gap-space-2 grid grid-cols-2">
            {Object.entries(DOCUMENT_TYPE_LABELS).map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setCategoryFilter(categoryFilter === value ? "all" : value)}
                className={`rounded-md border p-space-3 text-[12px] font-semibold ${categoryFilter === value ? "border-brand-600 bg-brand-50 text-brand-700" : "border-line bg-card text-ink-600"}`}
              >
                {label}
              </button>
            ))}
          </div>
        </Card>

        <Card className="p-space-4">
          <h3 className="text-label mb-space-3 text-ink-900 font-bold">Quick Actions</h3>
          <div className="gap-space-2 grid grid-cols-2">
            <label className="border-line bg-card text-ink-700 gap-space-1 flex h-16 cursor-pointer flex-col items-center justify-center rounded-md border text-[11.5px] font-semibold hover:bg-black/4">
              <Upload size={16} /> Upload
              <input ref={fileInputRef} type="file" className="hidden" onChange={handleUpload} disabled={uploading} />
            </label>
            <button
              type="button"
              disabled={!selected}
              onClick={() => selected && handleSendToWhatsapp(selected.id)}
              className="border-line bg-card text-ink-700 gap-space-1 disabled:opacity-40 flex h-16 flex-col items-center justify-center rounded-md border text-[11.5px] font-semibold hover:bg-black/4"
            >
              <Send size={16} /> {sendingDocId === selected?.id ? "Sending…" : "Send to WhatsApp"}
            </button>
            <button
              type="button"
              disabled={!selected}
              onClick={() => selected && openDocument(selected, true)}
              className="border-line bg-card text-ink-700 gap-space-1 disabled:opacity-40 flex h-16 flex-col items-center justify-center rounded-md border text-[11.5px] font-semibold hover:bg-black/4"
            >
              <Download size={16} /> Download
            </button>
            <button
              type="button"
              disabled={!selected}
              onClick={() => selected && openDocument(selected, false).then(() => window.print())}
              className="border-line bg-card text-ink-700 gap-space-1 disabled:opacity-40 flex h-16 flex-col items-center justify-center rounded-md border text-[11.5px] font-semibold hover:bg-black/4"
            >
              <Printer size={16} /> Print
            </button>
          </div>
          {selected && sendError[selected.id] && <p className="mt-space-2 text-error text-[12px]">{sendError[selected.id]}</p>}
        </Card>
      </div>
      </div>
    </>
  );
}
