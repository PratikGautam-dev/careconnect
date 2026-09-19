"use client";

import { Menu } from "lucide-react";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { DoctorSidebar } from "@/components/doctor/DoctorSidebar";
import type { StaffSession } from "@/lib/staffAuth";

type Props = {
  doctor: StaffSession | null;
  active: string;
  children: React.ReactNode;
};

/** Same sidebar + scrollable-main structure as PortalShell -- rebuilt to
 * match the shared staff portal's design exactly (per the user's own
 * explicit "same design and things as hospital login" request), just
 * pointed at DoctorSidebar's four doctor-scoped destinations instead of the
 * staff portal's eight. */
export function DoctorShell({ doctor, active, children }: Props) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    setSidebarOpen(false);
  }, [pathname]);

  return (
    <div className="bg-paper flex h-screen overflow-hidden">
      <DoctorSidebar
        doctor={doctor}
        active={active}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <header className="gap-space-3 border-line bg-card px-space-4 flex h-14 shrink-0 items-center border-b lg:hidden">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open menu"
            className="-ml-space-2 text-ink-600 hover:bg-paper flex h-9 w-9 shrink-0 items-center justify-center rounded-md"
          >
            <Menu size={20} strokeWidth={2} />
          </button>
          <span className="text-ink-900 truncate text-[14px] font-bold">
            {doctor?.name || "Doctor"}
          </span>
        </header>

        <main className="p-space-3 xs:p-space-4 sm:p-space-6 flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
