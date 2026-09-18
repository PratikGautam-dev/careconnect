// Attendance page -- real backend now for Present/Late/working-hours/
// overtime (db/repositories/attendance.py's attendance_records), fetched
// via GET /api/portal/attendance/summary. Absent/Leave are NOT yet real:
// this feature has no way to tell "no check-in row" apart from "not a
// working day" or "on approved leave" (that needs cross-referencing a
// staff member's working_days and the existing Leave Requests table, a
// separate follow-up) -- both always report 0 rather than a fabricated
// number. Kept in its own file, same "mock state lives next to the tab/
// page that owns it" convention as _components/general-settings-mock.ts,
// now holding only the display constants + the month/status filter presets
// (still genuinely mock -- a fixed recent-months list, not queried).

export type AttendanceStatus = "present" | "late" | "leave" | "absent";

export const STATUS_LABELS: Record<AttendanceStatus, string> = {
  present: "Present",
  late: "Late",
  leave: "Leave",
  absent: "Absent",
};

export const STATUS_STYLES: Record<AttendanceStatus, string> = {
  present: "bg-success-tint text-success",
  late: "bg-clay-100 text-clay-700",
  leave: "bg-brand-50 text-brand-600",
  absent: "bg-error-tint text-error",
};

// dataviz skill's documented categorical slots, reused here so this donut's
// colors read consistently with every other chart in the portal (see
// DepartmentDonut.tsx's own SLOT_COLORS).
export const STATUS_COLORS: Record<AttendanceStatus, string> = {
  present: "#1baf7a",
  late: "#2a78d6",
  leave: "#eda100",
  absent: "#e34948",
};

export const MONTH_OPTIONS = ["September 2026", "August 2026", "July 2026"];
export const STATUS_FILTER_OPTIONS: (AttendanceStatus | "all")[] = ["all", "present", "late", "leave", "absent"];
