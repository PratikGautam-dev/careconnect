import {
  BarChart3,
  Building2,
  CalendarCheck,
  CalendarClock,
  ClipboardCheck,
  ClipboardList,
  FileText,
  FlaskConical,
  MessageCircle,
  Receipt,
  Settings,
  ShieldCheck,
  Stethoscope,
  UserCog,
  Users,
  type LucideIcon,
} from "lucide-react";

/** Single source of truth for hospitals.admin_capabilities (backend:
 * portal/capabilities.py, ALL_CAPABILITIES) as far as the frontend is
 * concerned -- both the Access Control admin page (the checkbox list under
 * "Hospital Feature & Menu Access") and the staff portal's own sidebar
 * (PortalSidebar's hasCapability gate, via PAGE_CAPABILITY below) read from
 * this one array. Add/relabel/re-icon a capability here and both surfaces
 * update together; add a brand-new key here AND to portal/capabilities.py's
 * ALL_CAPABILITIES (the two must be kept in sync by hand -- no shared
 * codegen between the Python backend and this Next.js app).
 *
 * `pageKeys` is what actually drives nav gating: it's the PortalSidebar
 * NAV_ITEMS `pageKey`(s) this capability controls visibility for. Most
 * capabilities map to exactly one nav item; MANAGE_BOOKINGS covers all
 * three appointment-type nav items at once. A capability with no
 * `pageKeys` (the four MANAGE_* rows inherited from the old sub-tab-level
 * gates: departments/appointment types/diagnostic resources/procedures)
 * has no nav item of its own -- it's still real (enforced by backend
 * routes and gated inside the Settings sub-tabs it belongs to), it's just
 * not a top-level sidebar entry. */
export type HospitalCapability = {
  key: string;
  label: string;
  icon: LucideIcon;
  pageKeys?: string[];
};

export const HOSPITAL_CAPABILITIES: HospitalCapability[] = [
  { key: "manage_doctors", label: "Doctors", icon: Stethoscope, pageKeys: ["doctors"] },
  { key: "manage_departments", label: "Manage Departments", icon: Building2 },
  { key: "manage_appointment_types", label: "Manage Appointment Types", icon: CalendarClock },
  {
    key: "manage_bookings",
    label: "Appointments",
    icon: CalendarCheck,
    pageKeys: ["appointments", "daycare_appointments", "diagnostic_appointments"],
  },
  { key: "manage_settings", label: "Settings", icon: Settings, pageKeys: ["settings"] },
  { key: "manage_staff", label: "Staff", icon: UserCog, pageKeys: ["staff"] },
  { key: "manage_diagnostic_resources", label: "Manage Diagnostic Resources", icon: FlaskConical },
  { key: "manage_procedures", label: "Manage Procedures", icon: FileText },
  { key: "report_review", label: "Report Review", icon: ClipboardCheck, pageKeys: ["report-review"] },
  { key: "patients", label: "Patients", icon: Users, pageKeys: ["patients"] },
  { key: "leave_requests", label: "Leave Requests", icon: CalendarClock, pageKeys: ["leave_requests"] },
  {
    key: "attendance_overview",
    label: "Attendance Overview",
    icon: ClipboardList,
    pageKeys: ["attendance_overview"],
  },
  { key: "messages", label: "Messages", icon: MessageCircle, pageKeys: ["messages"] },
  { key: "billing", label: "Billing", icon: Receipt, pageKeys: ["billing"] },
  { key: "report_analytics", label: "Report Analytics", icon: BarChart3, pageKeys: ["report-analytics"] },
  { key: "roles", label: "Roles & Permissions", icon: ShieldCheck, pageKeys: ["roles"] },
];

/** capability key -> {label, icon}, for the Access Control page's
 * DataTable rows (one row per hospital.admin_capabilities entry). */
export const CAPABILITY_META: Record<string, { label: string; icon: LucideIcon }> =
  Object.fromEntries(HOSPITAL_CAPABILITIES.map(({ key, label, icon }) => [key, { label, icon }]));

/** PortalSidebar pageKey -> the capability key that must be present in
 * hospital.admin_capabilities for that nav item to show. A pageKey absent
 * from this map has no capability concept and is gated by hasPermission
 * (RBAC) alone. */
export const PAGE_CAPABILITY: Record<string, string> = Object.fromEntries(
  HOSPITAL_CAPABILITIES.flatMap(({ key, pageKeys }) => (pageKeys ?? []).map((pageKey) => [pageKey, key])),
);
