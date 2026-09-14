// Attendance page -- entirely frontend-mock for now (explicit instruction):
// only Check-in/Check-out (and, through it, real Present/Absent/Late
// numbers) is planned as a later follow-up. Kept in its own file, same
// "mock state lives next to the tab/page that owns it" convention as
// _components/general-settings-mock.ts.

export type AttendanceStatus = "present" | "late" | "leave" | "absent";

export type AttendanceStatRow = {
  presentDays: number;
  absentDays: number;
  lateCheckIns: number;
  overtimeHours: string;
};

export type WeeklyTrendPoint = { week: string; percent: number };

export type AttendanceStatusSlice = { status: AttendanceStatus; label: string; count: number };

export type AttendanceRecord = {
  date: string;
  checkIn: string | null;
  checkOut: string | null;
  breakTime: string | null;
  workingHours: string | null;
  status: AttendanceStatus;
};

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

export function initialAttendanceStats(): AttendanceStatRow {
  return { presentDays: 22, absentDays: 2, lateCheckIns: 3, overtimeHours: "08h 20m" };
}

export function initialWeeklyTrend(): WeeklyTrendPoint[] {
  return [
    { week: "Week 1", percent: 88 },
    { week: "Week 2", percent: 92 },
    { week: "Week 3", percent: 78 },
    { week: "Week 4", percent: 85 },
  ];
}

export function initialAttendanceStatusBreakdown(): AttendanceStatusSlice[] {
  return [
    { status: "present", label: "Present", count: 22 },
    { status: "leave", label: "Leave", count: 2 },
    { status: "absent", label: "Absent", count: 1 },
    { status: "late", label: "Late", count: 3 },
  ];
}

export function initialAttendanceRecords(): AttendanceRecord[] {
  return [
    { date: "09 Sep 2026", checkIn: "09:05 AM", checkOut: "06:25 PM", breakTime: "00h 30m", workingHours: "08h 20m", status: "present" },
    { date: "08 Sep 2026", checkIn: "09:20 AM", checkOut: "06:10 PM", breakTime: "00h 30m", workingHours: "07h 50m", status: "late" },
    { date: "07 Sep 2026", checkIn: "09:00 AM", checkOut: "06:00 PM", breakTime: "00h 30m", workingHours: "08h 00m", status: "present" },
    { date: "04 Sep 2026", checkIn: null, checkOut: null, breakTime: null, workingHours: null, status: "leave" },
    { date: "03 Sep 2026", checkIn: "09:10 AM", checkOut: "06:30 PM", breakTime: "00h 30m", workingHours: "08h 20m", status: "present" },
    { date: "02 Sep 2026", checkIn: null, checkOut: null, breakTime: null, workingHours: null, status: "absent" },
    { date: "01 Sep 2026", checkIn: "08:55 AM", checkOut: "06:05 PM", breakTime: "00h 10m", workingHours: "08h 10m", status: "present" },
  ];
}

export const MONTH_OPTIONS = ["September 2026", "August 2026", "July 2026"];
export const STATUS_FILTER_OPTIONS: (AttendanceStatus | "all")[] = ["all", "present", "late", "leave", "absent"];
