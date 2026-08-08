/** Minimal RFC-4180-ish CSV parser -- handles quoted fields (with embedded
 * commas and escaped "" quotes) since this app's own CSV columns
 * (working_days, working_hours, breaks) are themselves comma-joined lists
 * and MUST be quoted in the source file, e.g. "Mon,Tue,Wed". Not a full
 * spec implementation (no embedded newlines inside quoted fields), but
 * covers every case this app's own export/import round-trip needs. */
export function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let inQuotes = false;
  const lines = text.replace(/\r\n/g, "\n").split("\n");

  for (const line of lines) {
    if (!inQuotes && line.trim() === "" && row.length === 0 && field === "") continue;
    let i = 0;
    while (i < line.length) {
      const ch = line[i];
      if (inQuotes) {
        if (ch === '"') {
          if (line[i + 1] === '"') {
            field += '"';
            i += 2;
            continue;
          }
          inQuotes = false;
          i++;
          continue;
        }
        field += ch;
        i++;
        continue;
      }
      if (ch === '"') {
        inQuotes = true;
        i++;
        continue;
      }
      if (ch === ",") {
        row.push(field);
        field = "";
        i++;
        continue;
      }
      field += ch;
      i++;
    }
    if (inQuotes) {
      field += "\n";
      continue;
    }
    row.push(field);
    rows.push(row);
    row = [];
    field = "";
  }
  return rows.filter((r) => r.length > 1 || (r.length === 1 && r[0].trim() !== ""));
}

export function csvRowsToObjects(rows: string[][]): Record<string, string>[] {
  if (rows.length === 0) return [];
  const headers = rows[0].map((h) => h.trim());
  return rows.slice(1).map((row) => {
    const obj: Record<string, string> = {};
    headers.forEach((h, i) => {
      obj[h] = (row[i] ?? "").trim();
    });
    return obj;
  });
}
