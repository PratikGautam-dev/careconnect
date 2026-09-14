// Check-in/Check-out page -- entirely frontend-mock for now (explicit
// instruction, same as the Attendance page's own attendance-mock.ts):
// there's no real check-in/check-out backend yet, so every value here is
// static/local, not read from or written to anything real.

export type ActivityEventKind = "check_in" | "break_start" | "break_end" | "current_session";

export type ActivityEvent = {
  time: string;
  kind: ActivityEventKind;
  title: string;
  subtitle: string;
};

export type CheckInHistoryStatus = "in_progress" | "completed";

export type CheckInHistoryRow = {
  date: string;
  checkIn: string;
  checkOut: string | null;
  totalHours: string;
  status: CheckInHistoryStatus;
};

export const HISTORY_STATUS_LABELS: Record<CheckInHistoryStatus, string> = {
  in_progress: "In Progress",
  completed: "Completed",
};

export const HISTORY_STATUS_STYLES: Record<CheckInHistoryStatus, string> = {
  in_progress: "bg-brand-50 text-brand-600",
  completed: "bg-success-tint text-success",
};

export function initialTodaysActivity(): ActivityEvent[] {
  return [
    { time: "09:05 AM", kind: "check_in", title: "Check in", subtitle: "You checked in to the hospital" },
    { time: "12:30 PM", kind: "break_start", title: "Break start", subtitle: "Started lunch break" },
    { time: "01:00 PM", kind: "break_end", title: "Break end", subtitle: "Returned from break" },
    { time: "01:00 PM", kind: "current_session", title: "Current session", subtitle: "Working since 01:00 PM" },
  ];
}

export function initialCheckInHistory(): CheckInHistoryRow[] {
  return [
    { date: "09 Sep 2026", checkIn: "09:05 AM", checkOut: null, totalHours: "06h 25m", status: "in_progress" },
    { date: "08 Sep 2026", checkIn: "09:10 AM", checkOut: "05:35 PM", totalHours: "08h 25m", status: "completed" },
    { date: "07 Sep 2026", checkIn: "09:00 AM", checkOut: "05:20 PM", totalHours: "08h 20m", status: "completed" },
    { date: "04 Sep 2026", checkIn: "09:15 AM", checkOut: "05:45 PM", totalHours: "08h 30m", status: "completed" },
    { date: "03 Sep 2026", checkIn: "09:00 AM", checkOut: "05:30 PM", totalHours: "08h 30m", status: "completed" },
  ];
}

export const MOCK_TODAY_SUMMARY = {
  currentStatus: "Checked in",
  checkedInSince: "09:05 AM",
  checkInTime: "09:05 AM",
  breakTaken: "00h 30m",
  workingHours: "06h 25m",
  workingMinutes: 385,
  // A plain 8-hour reference day -- just what the "Live work timer" ring
  // fills toward, not a real configured shift length (Section 0: no such
  // per-staff setting exists yet).
  referenceDayMinutes: 480,
  activeSince: "01:00 PM",
};
