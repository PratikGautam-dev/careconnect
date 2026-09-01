"use client";

import { CalendarClock, LayoutDashboard, LogOut } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/cn";
import { clearStaffSession, type StaffSession } from "@/lib/staffAuth";

const NAV_ITEMS = [
  { key: "dashboard", label: "Today", icon: LayoutDashboard, href: "/doctor/dashboard" },
  { key: "schedule", label: "Schedule", icon: CalendarClock, href: "/doctor/schedule" },
];

type Props = {
  doctor: StaffSession | null;
  active: string;
  children: React.ReactNode;
};

/** Shell for the dedicated /doctor/* surface -- deliberately simpler than
 * PortalShell (a top bar, not a full sidebar): a doctor's own portal has two
 * destinations, not the shared staff portal's eight, so a collapsible-drawer
 * sidebar would be more chrome than the content needs. Same visual language
 * (brand-700 bar, same spacing/type tokens) so it reads as part of the same
 * product, not a different app bolted on.
 *
 * Rebuilt against the unified staff session (staffAuth.ts, JWT-based) after
 * the standalone doctor-only auth path (doctorAuth.ts/auth/doctor_session.py)
 * was folded into it -- a doctor is now a staff_users/staff_details row with
 * role="doctor", logged in via the same /api/portal/staff/login every other
 * staff role uses. This shell's own logout/session plumbing is the only
 * thing that changed; its layout is unchanged from the original build. */
export function DoctorShell({ doctor, active, children }: Props) {
  const router = useRouter();

  function handleLogout() {
    clearStaffSession();
    router.push("/doctor/login");
  }

  return (
    <div className="flex min-h-screen flex-col bg-paper">
      <header className="flex h-14 shrink-0 items-center gap-space-4 bg-brand-700 px-space-4 text-white sm:px-space-6">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-white/15 font-display text-[14px] font-extrabold">
          {(doctor?.name || "D").trim().charAt(0).toUpperCase()}
        </div>
        <span className="truncate text-[14px] font-bold">{doctor?.name || "Doctor"}</span>

        <nav className="ml-space-4 hidden items-center gap-1 sm:flex">
          {NAV_ITEMS.map(({ key, label, icon: Icon, href }) => {
            const isActive = key === active;
            return (
              <Link
                key={key}
                href={href}
                className={cn(
                  "flex items-center gap-space-2 rounded-md px-space-3 py-space-2 text-[13.5px] font-medium transition-colors duration-150",
                  isActive ? "bg-white text-brand-700" : "text-white/85 hover:bg-white/10 hover:text-white",
                )}
              >
                <Icon size={15} strokeWidth={2} />
                {label}
              </Link>
            );
          })}
        </nav>

        <button
          type="button"
          onClick={handleLogout}
          className="ml-auto flex items-center gap-space-2 rounded-md px-space-3 py-space-2 text-[13.5px] font-medium text-white/85 transition-colors duration-150 hover:bg-white/10 hover:text-white"
        >
          <LogOut size={15} strokeWidth={2} />
          <span className="hidden sm:inline">Log out</span>
        </button>
      </header>

      {/* Mobile nav row -- the header's own nav is hidden below `sm`, same
          breakpoint PortalShell's sidebar collapses at. */}
      <nav className="flex items-center gap-1 border-b border-line bg-card px-space-4 py-space-2 sm:hidden">
        {NAV_ITEMS.map(({ key, label, icon: Icon, href }) => {
          const isActive = key === active;
          return (
            <Link
              key={key}
              href={href}
              className={cn(
                "flex items-center gap-space-2 rounded-md px-space-3 py-space-2 text-[13px] font-medium transition-colors duration-150",
                isActive ? "bg-brand-100 text-brand-700" : "text-ink-600 hover:bg-paper",
              )}
            >
              <Icon size={15} strokeWidth={2} />
              {label}
            </Link>
          );
        })}
      </nav>

      <main className="flex-1 p-space-4 sm:p-space-6">{children}</main>
    </div>
  );
}
