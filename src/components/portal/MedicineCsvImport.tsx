"use client";

import { useRef } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { Download, Upload } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { useMedicineCsvImport } from "@/hooks/useMedicineCsvImport";

type CsvRow = Record<string, string>;

// Mirrors the "Add Stock" form's required fields, plus the medicine
// catalog's own required field (medicine_name) -- everything else is
// optional and, for the catalog fields, only used the first time a given
// medicine_name is seen in the file.
const REQUIRED_FIELDS = ["medicine_name", "batch_number", "expiry_date", "quantity"];

function missingFields(row: CsvRow): string[] {
  return REQUIRED_FIELDS.filter((f) => !(row[f] || "").trim());
}

// One line per CSV column, in the order of the template.
const COLUMN_GUIDE: { column: string; required: boolean; help: string }[] = [
  {
    column: "medicine_name",
    required: true,
    help: "Created automatically if it doesn't exist yet; otherwise this batch is added to its existing stock.",
  },
  { column: "generic_name", required: false, help: "Used only when the medicine is new." },
  { column: "category", required: false, help: "Used only when the medicine is new." },
  { column: "manufacturer", required: false, help: "Used only when the medicine is new." },
  { column: "unit", required: false, help: "e.g. strip, bottle, vial. Used only when the medicine is new." },
  { column: "unit_price", required: false, help: "Number. Used only when the medicine is new." },
  { column: "reorder_level", required: false, help: "Whole number. Used only when the medicine is new. Blank means 10." },
  { column: "batch_number", required: true, help: "This batch's own identifier." },
  { column: "expiry_date", required: true, help: "YYYY-MM-DD." },
  { column: "quantity", required: true, help: "Whole number, greater than zero." },
  { column: "cost_price", required: false, help: "Number — this batch's purchase cost." },
  {
    column: "supplier_name",
    required: false,
    help: "Created automatically if it doesn't exist yet. Blank leaves the batch with no supplier.",
  },
];

const PREVIEW_COLUMNS: ColumnDef<CsvRow>[] = [
  {
    id: "status",
    header: "Check",
    cell: ({ row }) => {
      const missing = missingFields(row.original);
      return missing.length === 0 ? (
        <span className="text-success text-[12px] font-semibold">Ready</span>
      ) : (
        <span className="text-error text-[12px] font-semibold">Missing: {missing.join(", ")}</span>
      );
    },
  },
  {
    id: "medicine_name",
    header: "Medicine",
    cell: ({ row }) => <span className="text-ink-900">{row.original.medicine_name}</span>,
  },
  {
    id: "batch_number",
    header: "Batch",
    cell: ({ row }) => <span className="text-ink-600">{row.original.batch_number}</span>,
  },
  {
    id: "expiry_date",
    header: "Expiry",
    cell: ({ row }) => <span className="text-ink-600">{row.original.expiry_date}</span>,
  },
  {
    id: "quantity",
    header: "Qty",
    cell: ({ row }) => <span className="text-ink-600">{row.original.quantity}</span>,
  },
];

const ALL_CSV_COLUMNS = [
  "medicine_name",
  "generic_name",
  "category",
  "manufacturer",
  "unit",
  "unit_price",
  "reorder_level",
  "batch_number",
  "expiry_date",
  "quantity",
  "cost_price",
  "supplier_name",
];

const SAMPLE_ROW = [
  "Paracetamol 500mg",
  "Paracetamol",
  "Analgesic",
  "Cipla",
  "strip",
  "25",
  "50",
  "BATCH-2026-001",
  "2027-06-30",
  "200",
  "18.5",
  "MedSupply Co",
];

function buildSampleCsv(): string {
  return [ALL_CSV_COLUMNS.join(","), SAMPLE_ROW.join(",")].join("\n");
}

function downloadSample() {
  const blob = new Blob([buildSampleCsv()], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "medicine-stock-template.csv";
  a.click();
  URL.revokeObjectURL(url);
}

export function MedicineCsvImport({ onImported }: { onImported: () => void }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const { rows, importing, result, loadFile, handleImport } = useMedicineCsvImport(onImported);
  const rowsWithProblems = (rows ?? []).filter((r) => missingFields(r).length > 0).length;

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
        <h3 className="text-label text-ink-900 font-bold">Bulk import stock from CSV</h3>
        <button
          type="button"
          onClick={downloadSample}
          className="text-brand-600 flex items-center gap-1 text-[12.5px] font-semibold hover:underline"
        >
          <Download size={13} /> Download template
        </button>
      </div>
      <p className="text-hint mb-space-3">
        Each row adds one received batch — same fields as the Add Stock form. An unrecognized medicine
        or supplier name is created automatically. Every row is checked separately — a bad row
        doesn&apos;t stop the good ones.
      </p>
      <details className="mb-space-3 border-line rounded-md border text-[12.5px]">
        <summary className="px-space-3 py-space-2 text-ink-900 cursor-pointer font-semibold">
          Column guide (required fields are marked *)
        </summary>
        <ul className="px-space-3 pb-space-3 space-y-1">
          {COLUMN_GUIDE.map((c) => (
            <li key={c.column}>
              <span className="text-ink-900 font-mono font-semibold">
                {c.column}
                {c.required ? " *" : ""}
              </span>{" "}
              <span className="text-ink-600">— {c.help}</span>
            </li>
          ))}
        </ul>
      </details>

      <label className="mb-space-3 gap-space-2 border-line px-space-4 py-space-3 text-ink-600 hover:border-brand-300 flex cursor-pointer items-center rounded-md border border-dashed text-[13px]">
        <Upload size={16} />
        {rows ? `${rows.length} row(s) loaded — choose a different file` : "Choose a CSV file"}
        <input ref={fileRef} type="file" accept=".csv,text/csv" onChange={handleFile} className="hidden" />
      </label>

      {rows && rows.length > 0 && (
        <div className="mb-space-3 border-line rounded-md border">
          <DataTable
            columns={PREVIEW_COLUMNS}
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
          <p className="text-success font-semibold">{result.created_count} stock batch(es) created.</p>
          {result.row_errors.length > 0 && (
            <ul className="mt-space-2 pl-space-4 text-error list-disc space-y-0.5">
              {result.row_errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <Button type="button" onClick={handleImportClick} disabled={!rows || rows.length === 0 || importing}>
        {importing ? "Importing…" : "Import stock"}
      </Button>
    </Card>
  );
}
