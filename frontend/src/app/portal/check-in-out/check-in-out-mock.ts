// Check-in/Check-out page -- real backend now (db/repositories/
// attendance.py + portal/routes/attendance.py). This file keeps only the
// small display-only helpers/types the page needs to render the real
// AttendanceRecord shape returned by /api/portal/attendance/today --
// ActivityEventKind/ActivityEvent/CheckInHistoryStatus/CheckInHistoryRow
// and their mock generator functions are gone, replaced by
// buildTodaysActivity()/toHistoryRow() in page.tsx which derive the same
// shapes from a real record instead of static mock data.

export type CheckInHistoryStatus = "in_progress" | "completed";

export const HISTORY_STATUS_LABELS: Record<CheckInHistoryStatus, string> = {
  in_progress: "In Progress",
  completed: "Completed",
};

export const HISTORY_STATUS_STYLES: Record<CheckInHistoryStatus, string> = {
  in_progress: "bg-brand-50 text-brand-600",
  completed: "bg-success-tint text-success",
};

// A plain 8-hour reference day -- just what the "Live work timer" ring
// fills toward when this hospital hasn't configured a shift window
// (Settings -> Attendance) yet.
export const DEFAULT_REFERENCE_DAY_MINUTES = 480;
