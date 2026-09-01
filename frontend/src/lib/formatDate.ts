// Shared date/time formatting -- was reimplemented per-page/component with
// the same handful of shapes (plain date, date+time, time-only, weekday
// heading); consolidated here so every call site formats consistently and a
// future locale/format change is one edit, not a dozen.

function parseDate(iso: string): Date | null {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** "Aug 28, 2026". Returns "—" for a null/undefined/empty iso (a field that
 * may genuinely be unset, e.g. a patient's last_visit), or the raw string
 * back if it doesn't parse as a date at all. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = parseDate(iso);
  return d ? d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : iso;
}

/** "Aug 28, 2026, 3:45 PM". */
export function formatDateTime(iso: string): string {
  const d = parseDate(iso);
  return d
    ? d.toLocaleString(undefined, { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" })
    : iso;
}

/** "Aug 28, 3:45 PM" -- same as formatDateTime but without the year, for
 * lists scoped to the current/recent period where the year is implied. */
export function formatShortDateTime(iso: string): string {
  const d = parseDate(iso);
  return d ? d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : iso;
}

/** "3:45 PM". */
export function formatTimeOnly(iso: string): string {
  const d = parseDate(iso);
  return d ? d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) : iso;
}

/** "Fri, Aug 28" -- takes a plain YYYY-MM-DD date string (not a full ISO
 * datetime), parsed at local midnight. */
export function formatDateHeading(dateStr: string): string {
  const d = parseDate(`${dateStr}T00:00:00`);
  return d ? d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" }) : dateStr;
}
