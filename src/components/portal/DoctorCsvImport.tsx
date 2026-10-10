"use client";

import { useRef } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { Download, Upload } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { useDoctorCsvImport } from "@/hooks/useDoctorCsvImport";

type CsvRow = Record<string, string>;

// Mirrors the single Add doctor form's required fields (and the backend's
// _validate_doctor_fields): everything else is optional. department_name is
// only required for a hospital -- a clinic has no departments, so its
// doctors are filed under a default one.
const REQUIRED_FIELDS = [
  "name",
  "specialization",
  "qualification",
  "working_days",
  "working_hours",
  "phone",
];

function missingFields(row: CsvRow, hideDepartment: boolean): string[] {
  const required = hideDepartment ? REQUIRED_FIELDS : ["department_name", ...REQUIRED_FIELDS];
  return required.filter((f) => !(row[f] || "").trim());
}

// One line per CSV column, in the order of the template -- the same fields,
// with the same rules, as the single Add doctor form.
const COLUMN_GUIDE: { column: string; required: boolean; help: string }[] = [
  {
    column: "department_name",
    required: true,
    help: "Hospitals only. Created automatically if it doesn't exist yet. Clinics don't use this column.",
  },
  { column: "name", required: true, help: "Doctor's full name." },
  { column: "specialization", required: true, help: "e.g. Cardiologist." },
  { column: "qualification", required: true, help: "e.g. MD, MBBS." },
  { column: "years_experience", required: false, help: "Whole number." },
  {
    column: "working_days",
    required: true,
    help: "Mon,Tue,Wed,Thu,Fri,Sat,Sun — comma-separated, in quotes.",
  },
  {
    column: "working_hours",
    required: true,
    help: 'HH:MM-HH:MM shifts, comma-separated, in quotes — e.g. "09:00-13:00,16:00-19:00".',
  },
  {
    column: "slot_duration_minutes",
    required: false,
    help: "Whole number. Blank uses your hospital's default appointment length.",
  },
  {
    column: "breaks",
    required: false,
    help: "HH:MM-HH:MM, inside a working shift, comma-separated, in quotes.",
  },
  {
    column: "max_bookings_per_slot",
    required: false,
    help: "Whole number, at least 1. Blank means 1.",
  },
  {
    column: "daily_booking_limit",
    required: false,
    help: "Whole number, 0 or more. Blank means no limit.",
  },
  {
    column: "online_quota",
    required: false,
    help: "WhatsApp bookings allowed per day. Whole number, 0 or more.",
  },
  {
    column: "walkin_quota",
    required: false,
    help: "Walk-in bookings allowed per day. Whole number, 0 or more.",
  },
  { column: "followup_duration_minutes", required: false, help: "Whole number above 0." },
  {
    column: "effective_from",
    required: false,
    help: "YYYY-MM-DD. Blank means the schedule applies immediately.",
  },
  { column: "phone", required: true, help: "Doctor's phone number." },
  { column: "location", required: false, help: "Address" },
];

function buildPreviewColumns(hideDepartment: boolean): ColumnDef<CsvRow>[] {
  const columns: ColumnDef<CsvRow>[] = [
    {
      id: "status",
      header: "Check",
      cell: ({ row }) => {
        const missing = missingFields(row.original, hideDepartment);
        return missing.length === 0 ? (
          <span className="text-success text-[12px] font-semibold">Ready</span>
        ) : (
          <span className="text-error text-[12px] font-semibold">
            Missing: {missing.join(", ")}
          </span>
        );
      },
    },
  ];
  if (!hideDepartment) {
    columns.push({
      id: "department_name",
      header: "Department",
      cell: ({ row }) => <span className="text-ink-900">{row.original.department_name}</span>,
    });
  }
  return [...columns, ...PREVIEW_BASE_COLUMNS];
}

const PREVIEW_BASE_COLUMNS: ColumnDef<CsvRow>[] = [
  {
    id: "name",
    header: "Name",
    cell: ({ row }) => <span className="text-ink-900">{row.original.name}</span>,
  },
  {
    id: "specialization",
    header: "Specialization",
    cell: ({ row }) => <span className="text-ink-600">{row.original.specialization}</span>,
  },
  {
    id: "phone",
    header: "Phone",
    cell: ({ row }) => <span className="text-ink-600">{row.original.phone}</span>,
  },
  {
    id: "working_days",
    header: "Days",
    cell: ({ row }) => <span className="text-ink-600">{row.original.working_days}</span>,
  },
];

// No employee_id column -- Employee ID auto-numbering feature: it's
// server-generated (EMP-DC-NNNNN) at create_doctor() time, never collected
// from a CSV row.
const ALL_CSV_COLUMNS = [
  "department_name",
  "name",
  "specialization",
  "qualification",
  "years_experience",
  "working_days",
  "working_hours",
  "slot_duration_minutes",
  "breaks",
  "max_bookings_per_slot",
  "daily_booking_limit",
  "online_quota",
  "walkin_quota",
  "followup_duration_minutes",
  "effective_from",
  "phone",
  "location",
];

const SAMPLE_ROW = [
  "Cardiology",
  "Dr. Ananya Singh",
  "Cardiologist",
  "MD",
  "12",
  '"Mon,Tue,Wed,Thu,Fri"',
  '"09:00-13:00,16:00-19:00"',
  "20",
  '"11:20-11:40"',
  "1",
  "30",
  "20",
  "10",
  "15",
  "",
  "9876543210",
  "123, Street, City, State",
];

// A clinic has no departments, so its template drops that column entirely.
function buildSampleCsv(hideDepartment: boolean): string {
  const drop = hideDepartment ? 1 : 0;
  return [ALL_CSV_COLUMNS.slice(drop).join(","), SAMPLE_ROW.slice(drop).join(",")].join("\n");
}

function downloadSample(hideDepartment: boolean) {
  const blob = new Blob([buildSampleCsv(hideDepartment)], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "doctors-template.csv";
  a.click();
  URL.revokeObjectURL(url);
}

export function DoctorCsvImport({
  onImported,
  hideDepartment = false,
}: {
  onImported: () => void;
  /** Clinics have no departments -- drops the department_name column. */
  hideDepartment?: boolean;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const { rows, importing, result, loadFile, handleImport } = useDoctorCsvImport(onImported);
  const previewColumns = buildPreviewColumns(hideDepartment);
  const rowsWithProblems = (rows ?? []).filter(
    (r) => missingFields(r, hideDepartment).length > 0,
  ).length;

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
        <h3 className="text-label text-ink-900 font-bold">Bulk import from CSV</h3>
        <button
          type="button"
          onClick={() => downloadSample(hideDepartment)}
          className="text-brand-600 flex items-center gap-1 text-[12.5px] font-semibold hover:underline"
        >
          <Download size={13} /> Download template
        </button>
      </div>
      <p className="text-hint mb-space-3">
        Same fields as the Add doctor form. Columns with multiple values (working days, shifts,
        breaks) must be comma-joined and quoted, e.g. &quot;Mon,Tue,Wed&quot;. Every row is checked
        separately — a bad row doesn&apos;t stop the good ones.
      </p>
      <details className="mb-space-3 border-line rounded-md border text-[12.5px]">
        <summary className="px-space-3 py-space-2 text-ink-900 cursor-pointer font-semibold">
          Column guide (required fields are marked *)
        </summary>
        <p className="px-space-3 pb-space-2 text-ink-600">
          {hideDepartment
            ? "Clinics have no departments, so there is no department_name column — every doctor is filed under your clinic's default department."
            : "Hospitals must give each doctor a department_name. (Clinics have no departments, so their template has no such column and doctors go under a default department.)"}
        </p>
        <ul className="px-space-3 pb-space-3 space-y-1">
          {COLUMN_GUIDE.filter((c) => !(hideDepartment && c.column === "department_name")).map(
            (c) => (
              <li key={c.column}>
                <span className="text-ink-900 font-mono font-semibold">
                  {c.column}
                  {c.required ? " *" : ""}
                </span>{" "}
                <span className="text-ink-600">— {c.help}</span>
              </li>
            ),
          )}
        </ul>
      </details>

      <label className="mb-space-3 gap-space-2 border-line px-space-4 py-space-3 text-ink-600 hover:border-brand-300 flex cursor-pointer items-center rounded-md border border-dashed text-[13px]">
        <Upload size={16} />
        {rows ? `${rows.length} row(s) loaded — choose a different file` : "Choose a CSV file"}
        <input
          ref={fileRef}
          type="file"
          accept=".csv,text/csv"
          onChange={handleFile}
          className="hidden"
        />
      </label>

      {rows && rows.length > 0 && (
        <div className="mb-space-3 border-line rounded-md border">
          <DataTable
            columns={previewColumns}
            data={rows}
            getRowId={(_r, i) => String(i)}
            containerClassName="max-h-52"
            stickyHeader
          />
        </div>
      )}

      {rowsWithProblems > 0 && (
        <p className="mb-space-3 text-error text-[12.5px] font-semibold">
          {rowsWithProblems} row(s) are missing required fields and will be skipped with an error.
        </p>
      )}

      {result && (
        <div className="mb-space-3 border-line bg-paper p-space-3 rounded-md border text-[12.5px]">
          <p className="text-success font-semibold">{result.created_count} doctor(s) created.</p>
          {result.row_errors.length > 0 && (
            <ul className="mt-space-2 pl-space-4 text-error list-disc space-y-0.5">
              {result.row_errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <Button
        type="button"
        onClick={handleImportClick}
        disabled={!rows || rows.length === 0 || importing}
      >
        {importing ? "Importing…" : "Import doctors"}
      </Button>
    </Card>
  );
}
