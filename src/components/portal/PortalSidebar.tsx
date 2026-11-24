"use client";

import {
  BarChart3,
  BedDouble,
  CalendarCheck,
  CalendarClock,
  CalendarRange,
  ClipboardCheck,
  ClipboardList,
  FlaskConical,
  Globe,
  HeadphonesIcon,
  LayoutDashboard,
  LogIn,
  MessageCircle,
  Pill,
  Plane,
  Receipt,
  RotateCcw,
  Settings,
  ShieldCheck,
  Stethoscope,
  Boxes,
  Truck,
  UserCheck,
  UserCog,
  UserPlus,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { SidebarUserMenu } from "@/components/account/SidebarUserMenu";
import { cn } from "@/lib/cn";
import { clearPortalSession, type PortalHospital } from "@/lib/portalAuth";
import { hasCapability, hasPermission, useStaffSession } from "@/lib/staffAuth";

// Grouped the same way dine-connect's PortalSidebar groups its own nav (see
// that file's NAV_ITEMS/GROUP_ORDER) -- a labeled section per area of the
// product, item order inside a group is array order (the sort below is
// stable), and the "Settings" group is pinned at the bottom instead of
// scrolling with the rest.
//
// Items with no href render as disabled "Coming soon" rows (see the
// .filter/.map below). Report review (/portal/report-review) and Report analytics
// (/portal/report-analytics) are two separate real pages with their own
// independent page_keys -- they used to incorrectly share the same href
// (report-analytics pointed at report-review's route) until
// /portal/report-analytics/page.tsx was built. All real nav items are
// gated by hasPermission below.
// Only "Settings" is pinned (Raise a Ticket + Settings itself) -- matching
// dine-connect's own pinned footer, which is also just two items (Support +
// Settings). Pinning the whole admin-tools group here squeezed the
// scrollable area down to nearly nothing on short/mobile viewports, since
// the pinned footer's height comes out of the same fixed-height sidebar.
type NavGroup = "Main" | "Booking Channels" | "Workforce" | "Pharmacy" | "Admin" | "Settings";
const GROUP_ORDER: NavGroup[] = [
  "Main", "Booking Channels", "Workforce", "Pharmacy", "Admin", "Settings",
];

const NAV_ITEMS: {
  key: string;
  label: string;
  icon: typeof LayoutDashboard;
  href: string;
  pageKey: string;
  group: NavGroup;
}[] = [
  // Main: everything appointment/patient related lives here now, one flat
  // group -- no separate "Appointments" section/header.
  {
    key: "dashboard",
    label: "Dashboard",
    icon: LayoutDashboard,
    href: "/portal/dashboard",
    pageKey: "dashboard",
    group: "Main",
  },
  // Doctor/Daycare/Lab & Diagnostic Appointments each have their own
  // page_key, since a role may reasonably get one category without the others.
  {
    key: "appointments",
    label: "Doctor Appointments",
    icon: CalendarCheck,
    href: "/portal/appointments",
    pageKey: "appointments",
    group: "Main",
  },
  {
    key: "daycare",
    label: "Daycare Appointments",
    icon: BedDouble,
    href: "/portal/appointments/daycare",
    pageKey: "daycare_appointments",
    group: "Main",
  },
  {
    key: "diagnostic",
    label: "Lab & Diagnostic Appointments",
    icon: FlaskConical,
    href: "/portal/appointments/diagnostic",
    pageKey: "diagnostic_appointments",
    group: "Main",
  },
  {
    key: "report-review",
    label: "Report review",
    icon: ClipboardCheck,
    href: "/portal/report-review",
    pageKey: "report-review",
    group: "Main",
  },
  {
    key: "messages",
    label: "Messages",
    icon: MessageCircle,
    href: "/portal/messages",
    pageKey: "messages",
    group: "Main",
  },

  {
    key: "patients",
    label: "Patients",
    icon: Users,
    href: "/portal/patients",
    pageKey: "patients",
    group: "Main",
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
    group: "Main",
  },
  // Booking Channels: where a hospital's appointments come from (WhatsApp/
  // Website/Walk-in) -- config/status pages, not booking forms (bookings
  // from each channel show up in Doctor Appointments above, filtered by
  // its own Channel column/filter).
  {
    key: "channels-whatsapp",
    label: "WhatsApp",
    icon: MessageCircle,
    href: "/portal/channels/whatsapp",
    pageKey: "channels_whatsapp",
    group: "Booking Channels",
  },
  {
    key: "channels-website",
    label: "Website",
    icon: Globe,
    href: "/portal/channels/website",
    pageKey: "channels_website",
    group: "Booking Channels",
  },
  {
    key: "channels-walkin",
    label: "Walk-in",
    icon: UserPlus,
    href: "/portal/channels/walk-in",
    pageKey: "channels_walkin",
    group: "Booking Channels",
  },
  {
    key: "doctors",
    label: "Doctors",
    icon: Stethoscope,
    href: "/portal/doctors",
    pageKey: "doctors",
    group: "Main",
  },

  {
    key: "staff",
    label: "Staff",
    icon: UserCog,
    href: "/portal/settings/staff",
    pageKey: "staff",
    group: "Workforce",
  },
  {
    key: "leave-requests",
    label: "Leave requests",
    icon: CalendarClock,
    href: "/portal/leave-requests",
    pageKey: "leave_requests",
    group: "Workforce",
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
    group: "Workforce",
  },
  {
    key: "attendance",
    label: "Attendance",
    icon: UserCheck,
    href: "/portal/attendance",
    pageKey: "attendance",
    group: "Workforce",
  },
  {
    key: "check-in-out",
    label: "Check-in / Check-out",
    icon: LogIn,
    href: "/portal/check-in-out",
    pageKey: "check_in_out",
    group: "Workforce",
  },
  // Self-service leave submission, open to any role (not just doctor)
  // since any staff member can apply for their own leave.
  {
    key: "holiday-application",
    label: "Holiday Application",
    icon: Plane,
    href: "/portal/holiday-application",
    pageKey: "holiday_application",
    group: "Workforce",
  },

  // Pharmacy: catalog/inventory/suppliers/purchase-orders/prescriptions all
  // share the "pharmacy" page_key; billing gets its own "pharmacy_billing"
  // page_key so a role can be granted "collect payment" without catalog/
  // stock write access (portal/permissions.py, migration 20261119100400).
  // Medicines catalog editing has no standalone nav entry -- reachable from
  // the Inventory page, same as how Report analytics/Report review each
  // only got their own entry for being genuinely independent destinations.
  {
    key: "pharmacy-dashboard",
    label: "Pharmacy",
    icon: Pill,
    href: "/portal/pharmacy",
    pageKey: "pharmacy",
    group: "Pharmacy",
  },
  {
    key: "pharmacy-prescriptions",
    label: "Prescriptions",
    icon: ClipboardList,
    href: "/portal/pharmacy/prescriptions",
    pageKey: "pharmacy",
    group: "Pharmacy",
  },
  {
    key: "pharmacy-dispensing",
    label: "Dispensing",
    icon: Pill,
    href: "/portal/pharmacy/dispensing",
    pageKey: "pharmacy",
    group: "Pharmacy",
  },
  {
    key: "pharmacy-inventory",
    label: "Inventory",
    icon: Boxes,
    href: "/portal/pharmacy/inventory",
    pageKey: "pharmacy",
    group: "Pharmacy",
  },
  {
    key: "pharmacy-alerts",
    label: "Stock Alerts",
    icon: CalendarClock,
    href: "/portal/pharmacy/alerts",
    pageKey: "pharmacy",
    group: "Pharmacy",
  },
  {
    key: "pharmacy-suppliers",
    label: "Suppliers",
    icon: Truck,
    href: "/portal/pharmacy/suppliers",
    pageKey: "pharmacy",
    group: "Pharmacy",
  },
  {
    key: "pharmacy-purchase-orders",
    label: "Purchase Orders",
    icon: ClipboardCheck,
    href: "/portal/pharmacy/purchase-orders",
    pageKey: "pharmacy",
    group: "Pharmacy",
  },
  {
    key: "pharmacy-returns",
    label: "Returns & Adjustments",
    icon: RotateCcw,
    href: "/portal/pharmacy/returns",
    pageKey: "pharmacy",
    group: "Pharmacy",
  },
  {
    key: "pharmacy-reports",
    label: "Reports & Analytics",
    icon: BarChart3,
    href: "/portal/pharmacy/reports",
    pageKey: "pharmacy",
    group: "Pharmacy",
  },
  {
    key: "pharmacy-settings",
    label: "Pharmacy Settings",
    icon: Settings,
    href: "/portal/pharmacy/settings",
    pageKey: "pharmacy",
    group: "Pharmacy",
  },
  {
    key: "pharmacy-billing",
    label: "Pharmacy Billing",
    icon: Receipt,
    href: "/portal/pharmacy-billing",
    pageKey: "pharmacy_billing",
    group: "Pharmacy",
  },

  {
    key: "billing",
    label: "Billing",
    icon: Receipt,
    href: "/portal/billing",
    pageKey: "billing",
    group: "Admin",
  },
  {
    key: "report-analytics",
    label: "Report analytics",
    icon: BarChart3,
    href: "/portal/report-analytics",
    pageKey: "report-analytics",
    group: "Admin",
  },
  {
    key: "roles",
    label: "Roles & permissions",
    icon: ShieldCheck,
    href: "/portal/settings/roles",
    pageKey: "roles",
    group: "Admin",
  },
  {
    key: "raise-ticket",
    label: "Support",
    icon: HeadphonesIcon,
    href: "/portal/raise-ticket",
    pageKey: "raise_ticket",
    group: "Settings",
  },
  {
    key: "settings",
    label: "Settings",
    icon: Settings,
    href: "/portal/settings",
    pageKey: "settings",
    group: "Settings",
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

  // Same grouped-and-stably-sorted shape dine-connect's PortalSidebar uses:
  // filter for permission/capability first, then sort by GROUP_ORDER (the
  // sort is stable, so item order within a group stays NAV_ITEMS' own order).
  const visible = NAV_ITEMS.filter(
    (item) =>
      !item.href ||
      ((NO_PERMISSION_GATE_KEYS.has(item.key) || hasPermission(session, item.pageKey, "view")) &&
        hasCapability(session, item.pageKey)),
  ).sort((a, b) => GROUP_ORDER.indexOf(a.group) - GROUP_ORDER.indexOf(b.group));
  const scrollItems = visible.filter((item) => item.group !== "Settings");
  const pinnedItems = visible.filter((item) => item.group === "Settings");

  function renderItems(items: typeof visible, showGroupTitles: boolean) {
    return items.map(({ key, label, icon: Icon, href, group }, index) => {
      const isActive = key === active;
      const startsGroup = index === 0 || items[index - 1].group !== group;
      const itemClasses = cn(
        "flex w-full items-center gap-space-3 rounded-md px-space-3 py-space-2 text-left text-[13.5px] font-medium transition-colors duration-150",
        isActive && "bg-white text-brand-700",
        !isActive && href && "text-white/85 hover:bg-white/10 hover:text-white",
        !href && "cursor-not-allowed text-white/40",
      );
      return (
        <div key={key}>
          {startsGroup && showGroupTitles && (
            <p
              className={cn(
                "px-space-3 pb-1 text-[11px] font-semibold tracking-[0.08em] text-white/50 uppercase",
                index === 0 ? "pt-space-2" : "pt-space-3",
              )}
            >
              {group}
            </p>
          )}
          {href ? (
            <Link href={href} onClick={onClose} className={itemClasses}>
              <Icon size={16} strokeWidth={2} className="shrink-0" />
              {label}
            </Link>
          ) : (
            <button type="button" disabled title="Coming soon" className={itemClasses}>
              <Icon size={16} strokeWidth={2} className="shrink-0" />
              {label}
            </button>
          )}
        </div>
      );
    });
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
          <span className="text-[14px] font-bold">{hospital?.name}</span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close menu"
            className="ml-auto flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-white/70 hover:bg-white/10 hover:text-white lg:hidden"
          >
            <X size={18} strokeWidth={2} />
          </button>
        </div>

        <nav className="scrollbar-hide flex-1 space-y-0.5 overflow-y-auto">
          {renderItems(scrollItems, true)}
        </nav>

        {/* Pinned: the "Settings" group stays in view however long the list above is -- same
         * pinned-footer treatment dine-connect's PortalSidebar gives its own Support/Settings group. */}
        {pinnedItems.length > 0 && (
          <div className="shrink-0 border-t border-white/10 pt-space-2">
            {renderItems(pinnedItems, false)}
          </div>
        )}

        <SidebarUserMenu
          name={session?.name}
          subtitle={session?.role_name}
          onProfile={() => {
            router.push("/portal/settings/profile-settings");
            onClose?.();
          }}
          onLogout={handleLogout}
        />
      </aside>
    </>
  );
}
