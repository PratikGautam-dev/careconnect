"use client";

import { ChevronsUpDown, LogOut, UserRound } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/cn";

type Props = {
  /** Shown next to the avatar; the avatar letter is its first character. */
  name: string | undefined;
  /** Second line under the name (role for staff, "Super admin" for the admin). */
  subtitle?: string;
  onProfile: () => void;
  onLogout: () => void;
  /** Icon-rail sidebar: just the avatar, with the name as a tooltip. */
  collapsed?: boolean;
};

/** The "avatar + name, click for Profile / Log out" menu pinned to the
 * bottom of a sidebar -- shared by the staff portal's and the super
 * admin's sidebars so the two never drift apart. */
export function SidebarUserMenu({ name, subtitle, onProfile, onLogout, collapsed = false }: Props) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        title={collapsed ? name : undefined}
        className={cn(
          "gap-space-3 px-space-3 py-space-2 flex w-full items-center rounded-md text-left text-[13.5px] font-medium text-white/85 transition-colors duration-150 hover:bg-white/10 hover:text-white",
          collapsed && "lg:justify-center lg:px-0",
        )}
      >
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white/15 text-[12px] font-bold">
          {(name || "?").charAt(0).toUpperCase()}
        </div>
        {!collapsed && (
          <>
            <div className="min-w-0 flex-1">
              <div className="truncate text-[13px] font-semibold">{name}</div>
              {subtitle && <div className="truncate text-[11.5px] text-white/60">{subtitle}</div>}
            </div>
            <ChevronsUpDown size={14} strokeWidth={2} className="shrink-0 text-white/50" />
          </>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent side="top" align="start" className="w-60">
        <DropdownMenuItem onClick={onProfile}>
          <UserRound size={14} /> Profile
        </DropdownMenuItem>
        <DropdownMenuItem variant="destructive" onClick={onLogout}>
          <LogOut size={14} /> Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
