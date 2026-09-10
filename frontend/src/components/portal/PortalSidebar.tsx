"use client";

import {
  BarChart3,
  CalendarCheck,
  CalendarClock,
  ChevronsUpDown,
  ClipboardCheck,
  FlaskConical,
  LayoutDashboard,
  LogOut,
  MessageCircle,
  Receipt,
  Settings,
  ShieldCheck,
  Stethoscope,
  UserCog,
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

const ROLE_LABEL: Record<string, string> = {
  admin: "Admin",
  receptionist: "Receptionist",
  doctor: "Doctor",
};

// Menu list/order matches the reference dashboard mockup (visual pass
// only, per the conversation -- deeper wiring for the items with no href
// below is deliberate follow-up work, not done here). Items with no href
// render as disabled "Coming soon" rows (see the .filter/.map below) --
// there's no backend yet for report review, billing, report analytics, or a
// leave-request queue. Doctor appointments and Diagnostic & lab test
// appointments share the "appointments" permission -- both are views over
// the same underlying appointment list, just scoped to a different
// appointment_type_id category (useAppointments' `category` param).
const NAV_ITEMS = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard, href: "/portal/dashboard", pageKey: "dashboard" },
  { key: "appointments", label: "Doctor appointments", icon: CalendarCheck, href: "/portal/appointments", pageKey: "appointments" },
  { key: "diagnostic", label: "Diagnostic & lab test appointments", icon: FlaskConical, href: "/portal/appointments/diagnostic", pageKey: "appointments" },
  { key: "report-review", label: "Report review", icon: ClipboardCheck, pageKey: "report-review" },
  { key: "patients", label: "Patients", icon: Users, href: "/portal/patients", pageKey: "patients" },
  { key: "doctors", label: "Doctors", icon: Stethoscope, href: "/portal/doctors", pageKey: "doctors" },
  { key: "staff", label: "Staff", icon: UserCog, href: "/portal/settings/staff", pageKey: "staff" },
  { key: "messages", label: "Messages", icon: MessageCircle, href: "/portal/messages", pageKey: "messages" },
  { key: "billing", label: "Billing", icon: Receipt, pageKey: "billing" },
  { key: "report-analytics", label: "Report analytics", icon: BarChart3, pageKey: "report-analytics" },
  { key: "roles", label: "Roles & permissions", icon: ShieldCheck, href: "/portal/settings/roles", pageKey: "roles" },
  { key: "settings", label: "Settings", icon: Settings, href: "/portal/settings", pageKey: "settings" },
  { key: "leave-requests", label: "Leave requests", icon: CalendarClock, pageKey: "leave-requests" },
];

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
          "fixed inset-y-0 left-0 z-50 flex h-screen w-72 max-w-[85vw] shrink-0 -translate-x-full flex-col bg-brand-700 px-space-3 py-space-4 text-white transition-transform duration-200 ease-out",
          "lg:static lg:z-auto lg:w-60 lg:max-w-none lg:translate-x-0",
          open && "translate-x-0",
        )}
      >
        <div className="mb-space-5 flex items-center gap-space-2 px-space-2">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-white/15 font-display text-[14px] font-extrabold">
            H
          </div>
          <span className="truncate text-[14px] font-bold">{hospital?.name || "Hospital"}</span>
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
            // once per item inside this loop). Fails OPEN the same way the
            // old hardcoded "doctors" capability check did -- this is only a
            // UI convenience, the backend's 403 is the real enforcement.
            // Hrefless rows are visual placeholders, not real gated
            // capabilities, so they skip the permission map entirely --
            // otherwise an unrecognized pageKey would hide them outright.
            (item) => !item.href || hasPermission(session, item.pageKey, "view"),
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
                <button key={key} type="button" disabled title="Coming soon" className={itemClasses}>
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
          <DropdownMenuTrigger
            className="flex w-full items-center gap-space-3 rounded-md px-space-3 py-space-2 text-left text-[13.5px] font-medium text-white/85 transition-colors duration-150 hover:bg-white/10 hover:text-white"
          >
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white/15 text-[12px] font-bold">
              {(session?.name || "?").charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-[13px] font-semibold">{session?.name || "Account"}</div>
              {session && <div className="truncate text-[11.5px] text-white/60">{ROLE_LABEL[session.role] || session.role}</div>}
            </div>
            <ChevronsUpDown size={14} strokeWidth={2} className="shrink-0 text-white/50" />
          </DropdownMenuTrigger>
          <DropdownMenuContent side="top" align="start" className="w-60">
            <DropdownMenuItem onClick={() => { router.push("/portal/settings/profile-settings"); onClose?.(); }}>
              <Settings size={14} /> Settings
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
