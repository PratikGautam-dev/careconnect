"use client";

import { useRef, useState } from "react";
import { Download, Upload } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { csvRowsToObjects, parseCsv } from "@/lib/csv";
import { portalFetch } from "@/lib/portalAuth";

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
  const [rows, setRows] = useState<Record<string, string>[] | null>(null);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<{ created_count: number; row_errors: string[] } | null>(null);

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const text = String(reader.result || "");
      const parsed = csvRowsToObjects(parseCsv(text));
      setRows(parsed);
      setResult(null);
    };
    reader.readAsText(file);
  }

  async function handleImport() {
    if (!rows) return;
    setImporting(true);
    const payloadRows = rows.map((r) => ({
      department_name: r.department_name || "",
      name: r.name || "",
      specialization: r.specialization || "",
      qualification: r.qualification || "",
      years_experience: r.years_experience || "",
      working_days: r.working_days || "",
      working_hours: r.working_hours || "",
      slot_duration_minutes: r.slot_duration_minutes || "",
      breaks: r.breaks || "",
      max_bookings_per_slot: r.max_bookings_per_slot || "1",
      daily_booking_limit: r.daily_booking_limit || "",
      online_quota: r.online_quota || "",
      walkin_quota: r.walkin_quota || "",
      followup_duration_minutes: r.followup_duration_minutes || "",
      effective_from: r.effective_from || "",
    }));
    const res = await portalFetch("/api/portal/doctors/csv-import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rows: payloadRows }),
    });
    setImporting(false);
    if (res.ok) {
      const data = res.data as { created_count: number; row_errors: string[] };
      setResult(data);
      if (data.created_count > 0) onImported();
      if (data.row_errors.length === 0) {
        setRows(null);
        if (fileRef.current) fileRef.current.value = "";
      }
    }
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
        <div className="mb-space-3 max-h-52 overflow-auto rounded-md border border-line">
          <table className="w-full text-left text-[12px]">
            <thead className="sticky top-0 bg-paper">
              <tr>
                <th className="p-space-2 font-semibold text-ink-600">Department</th>
                <th className="p-space-2 font-semibold text-ink-600">Name</th>
                <th className="p-space-2 font-semibold text-ink-600">Specialization</th>
                <th className="p-space-2 font-semibold text-ink-600">Days</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-t border-line">
                  <td className="p-space-2 text-ink-900">{r.department_name}</td>
                  <td className="p-space-2 text-ink-900">{r.name}</td>
                  <td className="p-space-2 text-ink-600">{r.specialization}</td>
                  <td className="p-space-2 text-ink-600">{r.working_days}</td>
                </tr>
              ))}
            </tbody>
          </table>
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

      <Button type="button" onClick={handleImport} disabled={!rows || rows.length === 0 || importing}>
        {importing ? "Importing…" : "Import doctors"}
      </Button>
    </Card>
  );
}
