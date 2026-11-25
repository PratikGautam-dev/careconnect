import { useState } from "react";
import { csvRowsToObjects, parseCsv } from "@/lib/csv";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";

type CsvRow = Record<string, string>;
type ImportResult = { created_count: number; row_errors: string[] };

/** Parses a CSV file client-side into preview rows (one row = one received
 * stock batch), then POSTs them to /api/portal/pharmacy/inventory/csv-import
 * -- mirrors useDoctorCsvImport.ts's shape exactly. Returns true from
 * handleImport when every row imported cleanly (the caller clears its file
 * input in that case). */
export function useMedicineCsvImport(onImported: () => void) {
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
      medicine_name: r.medicine_name || "",
      generic_name: r.generic_name || "",
      category: r.category || "",
      manufacturer: r.manufacturer || "",
      unit: r.unit || "",
      unit_price: r.unit_price || "",
      reorder_level: r.reorder_level || "",
      batch_number: r.batch_number || "",
      expiry_date: r.expiry_date || "",
      quantity: r.quantity || "",
      cost_price: r.cost_price || "",
      supplier_name: r.supplier_name || "",
    }));
    const res = await portalFetch("/api/portal/pharmacy/inventory/csv-import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rows: payloadRows }),
    });
    setImporting(false);
    if (res.ok) {
      const data = res.data as ImportResult;
      setResult(data);
      if (data.created_count > 0) {
        toast.success(`${data.created_count} stock batch(es) imported`);
        onImported();
      }
      if (data.row_errors.length > 0) {
        toast.error("Some rows couldn't be imported", data.row_errors[0]);
        return false;
      }
      setRows(null);
      return true;
    }
    if (!res.unauthorized) toast.error("Couldn't import stock", res.error);
    return false;
  }

  return { rows, importing, result, loadFile, handleImport };
}
