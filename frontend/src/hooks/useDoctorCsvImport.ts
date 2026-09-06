import { useState } from "react";
import { csvRowsToObjects, parseCsv } from "@/lib/csv";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";

type CsvRow = Record<string, string>;
type ImportResult = { created_count: number; row_errors: string[] };

/** Parses a CSV file client-side into preview rows, then POSTs them to
 * /api/portal/doctors/csv-import. Returns true from handleImport when every
 * row imported cleanly (the caller clears its file input in that case). */
export function useDoctorCsvImport(onImported: () => void) {
  const [rows, setRows] = useState<CsvRow[] | null>(null);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);

  function loadFile(file: File) {
    const reader = new FileReader();
    reader.onload = () => {
      const text = String(reader.result || "");
      const parsed = csvRowsToObjects(parseCsv(text));
      setRows(parsed);
      setResult(null);
    };
    reader.readAsText(file);
  }

  async function handleImport(): Promise<boolean> {
    if (!rows) return false;
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
      const data = res.data as ImportResult;
      setResult(data);
      if (data.created_count > 0) {
        toast.success(`${data.created_count} doctor(s) imported`);
        onImported();
      }
      if (data.row_errors.length > 0) {
        toast.error("Some rows couldn't be imported", data.row_errors[0]);
        return false;
      }
      setRows(null);
      return true;
    }
    if (!res.unauthorized) toast.error("Couldn't import doctors", res.error);
    return false;
  }

  return { rows, importing, result, loadFile, handleImport };
}
