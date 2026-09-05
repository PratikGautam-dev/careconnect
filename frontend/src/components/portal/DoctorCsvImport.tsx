"use client";

import { useRef } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { Download, Upload } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { useDoctorCsvImport } from "@/hooks/useDoctorCsvImport";

type CsvRow = Record<string, string>;

const PREVIEW_COLUMNS: ColumnDef<CsvRow>[] = [
  { id: "department_name", header: "Department", cell: ({ row }) => <span className="text-ink-900">{row.original.department_name}</span> },
  { id: "name", header: "Name", cell: ({ row }) => <span className="text-ink-900">{row.original.name}</span> },
  { id: "specialization", header: "Specialization", cell: ({ row }) => <span className="text-ink-600">{row.original.specialization}</span> },
  { id: "working_days", header: "Days", cell: ({ row }) => <span className="text-ink-600">{row.original.working_days}</span> },
];

const CSV_COLUMNS = [
  "department_name", "name", "specialization", "qualification", "years_experience",
  "working_days", "working_hours", "slot_duration_minutes", "breaks",
  "max_bookings_per_slot", "daily_booking_limit", "online_quota", "walkin_quota",
  "followup_duration_minutes", "effective_from",
];

const SAMPLE_CSV = [
  CSV_COLUMNS.join(","),
  [
    "Cardiology", "Dr. Ananya Singh", "Cardiologist", "MD", "12",
    '"Mon,Tue,Wed,Thu,Fri"', '"09:00-13:00,16:00-19:00"', "20", '"11:20-11:40"',
    "1", "30", "20", "10", "15", "",
  ].join(","),
].join("\n");

function downloadSample() {
  const blob = new Blob([SAMPLE_CSV], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "doctors-template.csv";
  a.click();
  URL.revokeObjectURL(url);
}

export function DoctorCsvImport({ onImported }: { onImported: () => void }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const { rows, importing, result, loadFile, handleImport } = useDoctorCsvImport(onImported);

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    loadFile(file);
  }

  async function handleImportClick() {
    const cleared = await handleImport();
    if (cleared && fileRef.current) fileRef.current.value = "";
  }

  return (
    <Card className="p-space-4">
      <div className="mb-space-3 flex items-center justify-between">
        <h3 className="text-label font-bold text-ink-900">Bulk import from CSV</h3>
        <button type="button" onClick={downloadSample} className="flex items-center gap-1 text-[12.5px] font-semibold text-brand-600 hover:underline">
          <Download size={13} /> Download template
        </button>
      </div>
      <p className="text-hint mb-space-3">
        Columns with multiple values (working days, shifts, breaks) must be comma-joined and quoted, e.g. &quot;Mon,Tue,Wed&quot;.
      </p>

      <label className="mb-space-3 flex cursor-pointer items-center gap-space-2 rounded-md border border-dashed border-line px-space-4 py-space-3 text-[13px] text-ink-600 hover:border-brand-300">
        <Upload size={16} />
        {rows ? `${rows.length} row(s) loaded — choose a different file` : "Choose a CSV file"}
        <input ref={fileRef} type="file" accept=".csv,text/csv" onChange={handleFile} className="hidden" />
      </label>

      {rows && rows.length > 0 && (
        <div className="mb-space-3 rounded-md border border-line">
          <DataTable
            columns={PREVIEW_COLUMNS}
            data={rows}
            getRowId={(_r, i) => String(i)}
            containerClassName="max-h-52"
            stickyHeader
          />
        </div>
      )}

      {result && (
        <div className="mb-space-3 rounded-md border border-line bg-paper p-space-3 text-[12.5px]">
          <p className="font-semibold text-success">{result.created_count} doctor(s) created.</p>
          {result.row_errors.length > 0 && (
            <ul className="mt-space-2 list-disc space-y-0.5 pl-space-4 text-error">
              {result.row_errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <Button type="button" onClick={handleImportClick} disabled={!rows || rows.length === 0 || importing}>
        {importing ? "Importing…" : "Import doctors"}
      </Button>
    </Card>
  );
}
