"use client";

import { Bell, Search } from "lucide-react";

// Shared PageHeader actions cluster for portal pages (dashboard, appointments,
// ...). Search/notifications are disabled -- no cross-entity search endpoint
// or notification system exists ("Coming soon", same convention PortalSidebar
// uses). The account menu below is commented out pending re-enable -- its
// imports/session/logout wiring were removed from here (unused while it's
// off) but the JSX + intended behavior is left in place as reference for
// whoever re-enables it (see git history / DropdownMenuTrigger, LogOut,
// Settings, useStaffSession, clearPortalSession, useRouter for the pieces
// to restore alongside it).
export function PortalTopBarActions() {
  return (
    <div className="gap-space-2 flex items-center">
      <div className="relative hidden sm:block">
        <Search
          size={15}
          strokeWidth={2}
          className="left-space-3 text-ink-400 pointer-events-none absolute top-1/2 -translate-y-1/2"
        />
        <input
          disabled
          title="Coming soon"
          placeholder="Search patients, appointments, staff…"
          className="border-line bg-card pl-space-7 pr-space-3 text-ink-600 placeholder:text-ink-400 h-9 w-56 cursor-not-allowed rounded-md border text-[13px] lg:w-72"
        />
      </div>

      <button
        type="button"
        disabled
        title="Coming soon"
        aria-label="Notifications"
        className="border-line bg-card text-ink-400 flex h-9 w-9 shrink-0 cursor-not-allowed items-center justify-center rounded-md border"
      >
        <Bell size={16} strokeWidth={2} />
      </button>
      {/* 
      <DropdownMenu>
        <DropdownMenuTrigger className="flex items-center gap-space-2 rounded-md border border-line bg-card py-space-1 pl-space-1 pr-space-2 hover:bg-paper">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-100 text-[12px] font-bold text-brand-700">
            {(session?.name || "?").charAt(0).toUpperCase()}
          </div>
          <div className="hidden min-w-0 text-left sm:block">
            <div className="truncate text-[12.5px] font-semibold text-ink-900">{session?.name || "Account"}</div>
            {session && <div className="truncate text-[10.5px] text-ink-400">{session.role_name}</div>}
          </div>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-52">
          <DropdownMenuItem onClick={() => router.push("/portal/settings/profile-settings")}>
            <Settings size={14} /> Settings
          </DropdownMenuItem>
          <DropdownMenuItem variant="destructive" onClick={handleLogout}>
            <LogOut size={14} /> Log out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu> */}
    </div>
  );
}
