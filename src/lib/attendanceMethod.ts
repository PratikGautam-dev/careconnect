/** How a check-in was verified -- attendance_records.check_in_verified_method.
 * One place for the wording so the check-in page, the dashboard, the
 * admin roster and the history dialog all say the same thing. */
export type CheckInMethod = "ip" | "gps" | "both" | "manual" | "none";

export const CHECK_IN_METHOD_LABELS: Record<CheckInMethod, string> = {
  ip: "Hospital WiFi",
  gps: "Location (GPS)",
  both: "WiFi + Location",
  manual: "Approved by admin",
  none: "Not verified",
};

export const CHECK_IN_METHOD_STYLES: Record<CheckInMethod, string> = {
  ip: "bg-success-tint text-success",
  gps: "bg-brand-50 text-brand-600",
  both: "bg-success-tint text-success",
  manual: "bg-clay-100 text-clay-700",
  none: "bg-black/4 text-ink-600",
};

export function checkInMethodLabel(method: string | null | undefined): string {
  return method && method in CHECK_IN_METHOD_LABELS
    ? CHECK_IN_METHOD_LABELS[method as CheckInMethod]
    : "-";
}

export function checkInMethodStyle(method: string | null | undefined): string {
  return method && method in CHECK_IN_METHOD_STYLES
    ? CHECK_IN_METHOD_STYLES[method as CheckInMethod]
    : "bg-black/4 text-ink-600";
}
