"use client";

import { CalendarCheck, CalendarClock, LayoutDashboard, LogOut, Users, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/cn";
import { clearStaffSession, type StaffSession } from "@/lib/staffAuth";

// Same four-destination shape as PortalSidebar's own NAV_ITEMS, scoped down
// to what a doctor actually needs -- Dashboard/Appointments/Patients/
// Schedule, no Doctors/Messages/Settings/Staff/Roles (those stay
// staff-portal-only; a doctor session is redirected away from those pages
// entirely by usePortalGuard()).
const NAV_ITEMS = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard, href: "/doctor/dashboard" },
  { key: "appointments", label: "Appointments", icon: CalendarCheck, href: "/doctor/appointments" },
  { key: "patients", label: "Patients", icon: Users, href: "/doctor/patients" },
  { key: "schedule", label: "Schedule", icon: CalendarClock, href: "/doctor/schedule" },
];

type Props = {
  doctor: StaffSession | null;
  active: string;
  open?: boolean;
  onClose?: () => void;
};

/** Same visual language and structure as PortalSidebar -- a static column
 * at `lg` and up, an off-canvas drawer below it -- so the doctor portal
 * reads as the same product, not a different app bolted on, per the user's
 * own explicit "same design as hospital login" request. */
export function DoctorSidebar({ doctor, active, open = false, onClose }: Props) {
  const router = useRouter();

  function handleLogout() {
    clearStaffSession();
    router.push("/doctor/login");
  }

  return (
    <>
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
            {(doctor?.name || "D").trim().charAt(0).toUpperCase()}
          </div>
          <span className="truncate text-[14px] font-bold">{doctor?.name || "Doctor"}</span>
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
          {NAV_ITEMS.map(({ key, label, icon: Icon, href }) => {
            const isActive = key === active;
            return (
              <Link
                key={key}
                href={href}
                onClick={onClose}
                className={cn(
                  "flex w-full items-center gap-space-3 rounded-md px-space-3 py-space-2 text-left text-[13.5px] font-medium transition-colors duration-150",
                  isActive ? "bg-white text-brand-700" : "text-white/85 hover:bg-white/10 hover:text-white",
                )}
              >
                <Icon size={16} strokeWidth={2} className="shrink-0" />
                {label}
              </Link>
            );
          })}
        </nav>

        <button
          type="button"
          onClick={handleLogout}
          className="flex w-full items-center gap-space-3 rounded-md px-space-3 py-space-2 text-left text-[13.5px] font-medium text-white/70 transition-colors duration-150 hover:bg-white/10 hover:text-white"
        >
          <LogOut size={16} strokeWidth={2} className="shrink-0" />
          Log out
        </button>
      </aside>
    </>
  );
}
