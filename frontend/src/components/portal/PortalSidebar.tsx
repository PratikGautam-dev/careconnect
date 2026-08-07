"use client";

import {
  CalendarCheck,
  LayoutDashboard,
  LogOut,
  MessageCircle,
  Settings,
  Stethoscope,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/cn";
import { clearPortalSession, type PortalHospital } from "@/lib/portalAuth";

// Staff/Branches/Reports/Calendar/Departments were removed (not just hidden)
// -- Calendar had no backend and no near-term plan to build one; Departments
// duplicated Doctors (same /portal/doctors page manages both) so it was a
// second sidebar entry pointing at a page already reachable via "Doctors."
const NAV_ITEMS = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard, href: "/portal/dashboard" },
  { key: "appointments", label: "Appointments", icon: CalendarCheck, href: "/portal/appointments" },
  { key: "patients", label: "Patients", icon: Users, href: "/portal/patients" },
  { key: "doctors", label: "Doctors", icon: Stethoscope, href: "/portal/doctors" },
  { key: "messages", label: "Messages", icon: MessageCircle, href: "/portal/messages" },
  { key: "settings", label: "Settings", icon: Settings, href: "/portal/settings" },
];

type Props = { hospital: PortalHospital | null; active: string };

export function PortalSidebar({ hospital, active }: Props) {
  const router = useRouter();

  function handleLogout() {
    clearPortalSession();
    router.push("/portal/login");
  }

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col bg-brand-700 px-space-3 py-space-4 text-white">
      <div className="mb-space-5 flex items-center gap-space-2 px-space-2">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-white/15 font-display text-[14px] font-extrabold">
          H
        </div>
        <span className="truncate text-[14px] font-bold">{hospital?.name || "Hospital"}</span>
      </div>

      <nav className="flex-1 space-y-0.5">
        {NAV_ITEMS.map(({ key, label, icon: Icon, href }) => {
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
            <Link key={key} href={href} className={itemClasses}>
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
  );
}
