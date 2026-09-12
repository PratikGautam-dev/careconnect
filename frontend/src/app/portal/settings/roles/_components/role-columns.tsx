"use client";

import type { ColumnDef } from "@tanstack/react-table";
import type { LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import type { StaffRole } from "@/lib/staffAuth";
import type { Action, PagePerms } from "@/hooks/usePortalRoles";

export type { Action, PagePerms };

const ACTIONS: Action[] = ["view", "write", "delete"];

type CreateRoleColumnsOptions = {
  pageLabel: Record<string, string>;
  cellFor: (pageKey: string) => PagePerms;
  canWrite: boolean;
  isSaving: (pageKey: string, action: Action) => boolean;
  onToggle: (pageKey: string, action: Action, next: boolean) => void;
};

/** Column definitions for one role's permission grid on /portal/settings/
 * roles -- "Page" plus one checkbox column per action (view/write/delete).
 * Rows are just page keys (strings); the actual {view,write,delete} cell
 * comes from `cellFor`, closing over that role's slice of the matrix. */
export function createRoleColumns({
  pageLabel, cellFor, canWrite, isSaving, onToggle,
}: CreateRoleColumnsOptions): ColumnDef<string>[] {
  return [
    {
      id: "page",
      header: "Page",
      cell: ({ row }) => <span className="text-ink-900">{pageLabel[row.original] || row.original}</span>,
    },
    ...ACTIONS.map(
      (action): ColumnDef<string> => ({
        id: action,
        header: () => <span className="block text-center capitalize">{action}</span>,
        cell: ({ row }) => {
          const pageKey = row.original;
          const cell = cellFor(pageKey);
          return (
            <div className="text-center">
              <input
                type="checkbox"
                checked={cell[action]}
                disabled={!canWrite || isSaving(pageKey, action)}
                onChange={(e) => onToggle(pageKey, action, e.target.checked)}
                className="h-4 w-4 accent-brand-600 disabled:opacity-50"
              />
            </div>
          );
        },
      }),
    ),
  ];
}

type CreateRoleManagementColumnsOptions = {
  roleLabel: Record<StaffRole, string>;
  roleDescription: Record<StaffRole, string>;
  roleIcon: Record<StaffRole, LucideIcon>;
  userCountFor: (role: StaffRole) => number;
  onEditPermissions: (role: StaffRole) => void;
};

/** "Role Management" table on the redesigned /portal/settings/roles --
 * one row per role this app actually has (Admin/Receptionist/Doctor; no
 * Super Admin -- that's a cross-tenant role, not a hospital-portal one, and
 * no custom/dynamic roles -- this schema's role is a fixed 3-value CHECK
 * constraint, not a table). Status is always "Active": these 3 roles are
 * always available, there's no per-role enable/disable toggle to reflect
 * (only individual staff members have an is_active flag). */
export function createRoleManagementColumns({
  roleLabel, roleDescription, roleIcon, userCountFor, onEditPermissions,
}: CreateRoleManagementColumnsOptions): ColumnDef<StaffRole>[] {
  return [
    {
      id: "role",
      header: "Role Name",
      cell: ({ row }) => {
        const role = row.original;
        const Icon = roleIcon[role];
        return (
          <span className="flex items-center gap-space-2 font-semibold text-ink-900">
            <Icon size={16} className="shrink-0 text-brand-600" /> {roleLabel[role]}
          </span>
        );
      },
    },
    {
      id: "description",
      header: "Description",
      cell: ({ row }) => <span className="text-[12.5px] text-ink-600">{roleDescription[row.original]}</span>,
    },
    {
      id: "users",
      header: "Number of Users",
      cell: ({ row }) => <span className="text-ink-900">{userCountFor(row.original)}</span>,
    },
    {
      id: "status",
      header: "Status",
      cell: () => <Badge tone="success">Active</Badge>,
    },
    {
      id: "actions",
      header: "Actions",
      cell: ({ row }) => (
        <button
          type="button"
          onClick={() => onEditPermissions(row.original)}
          className="rounded-md border border-brand-200 px-space-3 py-1.5 text-[12px] font-semibold text-brand-700 hover:bg-brand-50"
        >
          Edit Permissions
        </button>
      ),
    },
  ];
}
