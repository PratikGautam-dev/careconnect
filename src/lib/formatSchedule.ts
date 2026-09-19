// Doctor/Staff working-schedule display formatting -- shared by
// DoctorDetailPanel.tsx and StaffDetailPanel.tsx (Staff schedule feature),
// lifted out of DoctorDetailPanel.tsx where these lived before staff had
// its own real working_days/working_hours to display.

/** "9:00 AM" from "09:00". Falls back to the raw string if unparseable. */
export function formatClockTime(hhmm: string): string {
  const [hStr, mStr = "00"] = hhmm.split(":");
  const h = Number(hStr);
  if (Number.isNaN(h)) return hhmm;
  const period = h >= 12 ? "PM" : "AM";
  const h12 = h % 12 || 12;
  return `${h12}:${mStr} ${period}`;
}

/** "Mon - Sat" for a contiguous run starting Monday, else a comma list --
 * working_days is a fixed-order subset of Mon..Sun, not necessarily
 * contiguous or Monday-starting. */
export function formatWorkingDays(days: string[]): string {
  const order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const sorted = [...days].sort((a, b) => order.indexOf(a) - order.indexOf(b));
  const isContiguousFromMon = sorted.every((d, i) => d === order[i]);
  return isContiguousFromMon && sorted.length > 1
    ? `${sorted[0]} - ${sorted[sorted.length - 1]}`
    : sorted.join(", ");
}

/** "9:00 AM - 1:00 PM, 4:00 PM - 7:00 PM" from ["09:00-13:00", "16:00-19:00"];
 * null when there are no shifts at all (nothing to show). */
export function formatWorkingHours(hours: string[]): string | null {
  if (hours.length === 0) return null;
  return hours
    .map((r) => {
      const [start, end] = r.split("-");
      return start && end ? `${formatClockTime(start)} - ${formatClockTime(end)}` : r;
    })
    .join(", ");
}
