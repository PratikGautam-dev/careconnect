"use client";

import {
  BarChart3,
  BedDouble,
  CalendarCheck,
  CalendarClock,
  CalendarRange,
  ChevronsUpDown,
  ClipboardCheck,
  ClipboardList,
  FlaskConical,
  LayoutDashboard,
  LogIn,
  LogOut,
  MessageCircle,
  Plane,
  Receipt,
  Settings,
  ShieldCheck,
  Stethoscope,
  UserCheck,
  UserCog,
  UserRound,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/cn";
import { clearPortalSession, type PortalHospital } from "@/lib/portalAuth";
import { hasPermission, useStaffSession } from "@/lib/staffAuth";

// Items with no href render as disabled "Coming soon" rows (see the
// .filter/.map below) -- there's no backend yet for billing. Billing is
// additionally `hidden` (kept, not deleted, so re-enabling is a one-line
// flip). Report review and Report analytics share /portal/report-review
// as their href -- "Report analytics" is a second nav label, not a second
// page. All real nav items are gated by hasPermission below.
const NAV_ITEMS = [
  {
    key: "dashboard",
    label: "Dashboard",
    icon: LayoutDashboard,
    href: "/portal/dashboard",
    pageKey: "dashboard",
  },

  // Doctor/Daycare/Lab & Diagnostic Appointments each have their own
  // page_key, since a role may reasonably get one category without the others.
  {
    key: "appointments",
    label: "Doctor Appointments",
    icon: CalendarCheck,
    href: "/portal/appointments",
    pageKey: "appointments",
  },
  {
    key: "daycare",
    label: "Daycare Appointments",
    icon: BedDouble,
    href: "/portal/appointments/daycare",
    pageKey: "daycare_appointments",
  },
  {
    key: "diagnostic",
    label: "Lab & Diagnostic Appointments",
    icon: FlaskConical,
    href: "/portal/appointments/diagnostic",
    pageKey: "diagnostic_appointments",
  },

  {
    key: "report-review",
    label: "Report review",
    icon: ClipboardCheck,
    href: "/portal/report-review",
    pageKey: "report-review",
  },
  {
    key: "patients",
    label: "Patients",
    icon: Users,
    href: "/portal/patients",
    pageKey: "patients",
  },
  // Real page (/portal/schedule -> DoctorScheduleView), was missing from
  // this list entirely -- not disabled/hrefless, just never added, so no
  // role (doctor included) could reach it from the sidebar despite the
  // route and its own permission gate ("schedule"/"view") already existing.
  {
    key: "schedule",
    label: "Schedule",
    icon: CalendarRange,
    href: "/portal/schedule",
    pageKey: "schedule",
  },
  {
    key: "doctors",
    label: "Doctors",
    icon: Stethoscope,
    href: "/portal/doctors",
    pageKey: "doctors",
  },
  {
    key: "staff",
    label: "Staff",
    icon: UserCog,
    href: "/portal/settings/staff",
    pageKey: "staff",
  },
  {
    key: "leave-requests",
    label: "Leave requests",
    icon: CalendarClock,
    href: "/portal/leave-requests",
    pageKey: "leave_requests",
  },
  // Admin-facing hospital-wide roster (every staff member's check-in/out
  // for one selected day) -- a SEPARATE page_key from "attendance" below
  // (that one is a staff member's own personal history, deliberately off
  // for admin by default; migration 20260919190000).
  {
    key: "attendance-overview",
    label: "Attendance Overview",
    icon: ClipboardList,
    href: "/portal/attendance-overview",
    pageKey: "attendance_overview",
  },
  {
    key: "messages",
    label: "Messages",
    icon: MessageCircle,
    href: "/portal/messages",
    pageKey: "messages",
  },
  {
    key: "billing",
    label: "Billing",
    icon: Receipt,
    pageKey: "billing",
    hidden: true,
  },
  {
    key: "report-analytics",
    label: "Report analytics",
    icon: BarChart3,
    href: "/portal/report-review",
    pageKey: "report-analytics",
  },
  {
    key: "roles",
    label: "Roles & permissions",
    icon: ShieldCheck,
    href: "/portal/settings/roles",
    pageKey: "roles",
  },
  {
    key: "settings",
    label: "Settings",
    icon: Settings,
    href: "/portal/settings",
    pageKey: "settings",
  },
  // Both pages themselves are still frontend-only mock data (explicit
  // instruction) -- only the Leave slice of Attendance's own "Attendance
  // status" donut comes from anything real eventually (Leave requests),
  // Check-in/Check-out wiring is a deliberate later follow-up. The
  // page_keys ("attendance"/"check_in_out") ARE real now though (migration
  // 20260914130000, portal/permissions.py) -- gated by hasPermission below
  // like every other real nav item, not a NO_PERMISSION_GATE_KEYS bypass.
  // Default permissions: view+write for every role except the seeded Admin
  // role (confirmed with the user -- an admin doesn't check themselves in/
  // out day to day), same as that migration's own backfill.
  {
    key: "attendance",
    label: "Attendance",
    icon: UserCheck,
    href: "/portal/attendance",
    pageKey: "attendance",
  },
  {
    key: "check-in-out",
    label: "Check-in / Check-out",
    icon: LogIn,
    href: "/portal/check-in-out",
    pageKey: "check_in_out",
  },

  // Self-service leave submission, open to any role (not just doctor)
  // since any staff member can apply for their own leave.
  {
    key: "holiday-application",
    label: "Holiday Application",
    icon: Plane,
    href: "/portal/holiday-application",
    pageKey: "holiday_application",
  },
];

// Nav items whose href-having route has no real backend permission model
// yet -- gating these through hasPermission would hide them for every role
// (an unrecognized pageKey never matches any role_permissions row), so they
// skip that check entirely instead.
const NO_PERMISSION_GATE_KEYS = new Set<string>([]);

type Props = {
  hospital: PortalHospital | null;
  active: string;
  /** Mobile drawer state -- undefined/false renders the sidebar off-canvas
   * below the `lg` breakpoint (PortalShell owns the toggle); at `lg` and up
   * the sidebar is always statically visible regardless of this prop. */
  open?: boolean;
  onClose?: () => void;
};

export function PortalSidebar({ hospital, active, open = false, onClose }: Props) {
  const router = useRouter();
  // Resolved once, here, via the real hook -- hasPermission below is a
  // plain function taking this value, safe to call inside .filter() (a real
  // hook can't be called in a loop). null on the server and on the client's
  // own first render pass (same value both places -- no hydration mismatch),
  // then the real session an instant later.
  const session = useStaffSession();

  function handleLogout() {
    clearPortalSession();
    router.push("/");
  }

  return (
    <>
      {/* Backdrop, mobile drawer only */}
      <div
        aria-hidden="true"
        onClick={onClose}
        className={cn(
          "fixed inset-0 z-40 bg-black/40 transition-opacity duration-200 lg:hidden",
          open ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0",
        )}
      />

      <aside
        className={cn(
          "bg-brand-700 px-space-3 py-space-4 fixed inset-y-0 left-0 z-50 flex h-screen w-72 max-w-[85vw] shrink-0 -translate-x-full flex-col text-white transition-transform duration-200 ease-out",
          "lg:static lg:z-auto lg:w-60 lg:max-w-none lg:translate-x-0",
          open && "translate-x-0",
        )}
      >
        <div className="mb-space-5 gap-space-2 px-space-2 flex items-center">
          <div className="font-display flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-white/15 text-[14px] font-extrabold">
            H
          </div>
          <span className="text-[14px] font-bold">{hospital?.name || "Hospital"}</span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close menu"
            className="ml-auto flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-white/70 hover:bg-white/10 hover:text-white lg:hidden"
          >
            <X size={18} strokeWidth={2} />
          </button>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto">
          {NAV_ITEMS.filter(
            // Per-page-key permission check (hasPermission is a plain
            // function here, not the usePermission hook, since it's called
            // once per item inside this loop). Fails CLOSED while the
            // session is still loading (hasPermission's own docstring) --
            // this is only a UI convenience, the backend's 403 is the real
            // enforcement, but failing open here used to render the full,
            // unfiltered nav for every role for a moment on first paint
            // before narrowing down to the real per-role set.
            // Hrefless rows are visual placeholders, not real gated
            // capabilities, so they skip the permission map entirely --
            // otherwise an unrecognized pageKey would hide them outright.
            (item) =>
              !item.hidden &&
              (!item.href ||
                NO_PERMISSION_GATE_KEYS.has(item.key) ||
                hasPermission(session, item.pageKey, "view")),
          ).map(({ key, label, icon: Icon, href }) => {
            const isActive = key === active;
            const itemClasses = cn(
              "flex w-full items-center gap-space-3 rounded-md px-space-3 py-space-2 text-left text-[13.5px] font-medium transition-colors duration-150",
              isActive && "bg-white text-brand-700",
              !isActive && href && "text-white/85 hover:bg-white/10 hover:text-white",
              !href && "cursor-not-allowed text-white/40",
            );
            if (!href) {
              return (
                <button
                  key={key}
                  type="button"
                  disabled
                  title="Coming soon"
                  className={itemClasses}
                >
                  <Icon size={16} strokeWidth={2} className="shrink-0" />
                  {label}
                </button>
              );
            }
            return (
              <Link key={key} href={href} onClick={onClose} className={itemClasses}>
                <Icon size={16} strokeWidth={2} className="shrink-0" />
                {label}
              </Link>
            );
          })}
        </nav>

        <DropdownMenu>
          <DropdownMenuTrigger className="gap-space-3 px-space-3 py-space-2 flex w-full items-center rounded-md text-left text-[13.5px] font-medium text-white/85 transition-colors duration-150 hover:bg-white/10 hover:text-white">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white/15 text-[12px] font-bold">
              {(session?.name || "?").charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-[13px] font-semibold">{session?.name || "Account"}</div>
              {session && (
                <div className="truncate text-[11.5px] text-white/60">{session.role_name}</div>
              )}
            </div>
            <ChevronsUpDown size={14} strokeWidth={2} className="shrink-0 text-white/50" />
          </DropdownMenuTrigger>
          <DropdownMenuContent side="top" align="start" className="w-60">
            <DropdownMenuItem
              onClick={() => {
                router.push("/portal/settings/profile-settings");
                onClose?.();
              }}
            >
              <UserRound size={14} /> Profile
            </DropdownMenuItem>
            <DropdownMenuItem variant="destructive" onClick={handleLogout}>
              <LogOut size={14} /> Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </aside>
    </>
  );
}
