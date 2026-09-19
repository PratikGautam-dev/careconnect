"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Pencil, Trash2, UserCog, Users as UsersIcon } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import type { Action, OverrideCell, PagePerms, Role } from "@/hooks/usePortalRoles";

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
  pageLabel,
  cellFor,
  canWrite,
  isSaving,
  onToggle,
}: CreateRoleColumnsOptions): ColumnDef<string>[] {
  return [
    {
      id: "page",
      header: "Page",
      cell: ({ row }) => (
        <span className="text-ink-900">{pageLabel[row.original] || row.original}</span>
      ),
    },
    ...ACTIONS.map((action): ColumnDef<string> => ({
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
              className="accent-brand-600 h-4 w-4 disabled:opacity-50"
            />
          </div>
        );
      },
    })),
  ];
}

type CreateRoleManagementColumnsOptions = {
  canManage: boolean;
  userCountFor: (roleId: number) => number;
  onEditPermissions: (roleId: number) => void;
  onManageUsers: (roleId: number) => void;
  onRename: (role: Role) => void;
  onDelete: (role: Role) => void;
};

/** "Role Management" table on the redesigned /portal/settings/roles --
 * one row per role this hospital actually has (dynamic-roles migration:
 * admin-defined, unbounded, no more fixed 3-entry list -- every role looks
 * and behaves the same, no "built-in" labeling). Status is always "Active":
 * roles themselves have no enable/disable toggle (only individual staff
 * members have an is_active flag) -- Delete is disabled (with the reason as
 * a title tooltip, matching the backend's own guard so it's visible before
 * the click, not just a toast after a 400) only for the reserved Admin role
 * or a role with staff currently assigned; Rename is always available. */
export function createRoleManagementColumns({
  canManage,
  userCountFor,
  onEditPermissions,
  onManageUsers,
  onRename,
  onDelete,
}: CreateRoleManagementColumnsOptions): ColumnDef<Role>[] {
  return [
    {
      id: "role",
      header: "Role Name",
      cell: ({ row }) => {
        const role = row.original;
        return (
          <span className="gap-space-2 text-ink-900 flex items-center font-semibold">
            <UsersIcon size={16} className="text-brand-600 shrink-0" /> {role.name}
          </span>
        );
      },
    },
    {
      id: "description",
      header: "Description",
      cell: ({ row }) => (
        <span className="text-ink-600 text-[12.5px]">{row.original.description || "—"}</span>
      ),
    },
    {
      id: "users",
      header: "Number of Users",
      cell: ({ row }) => <span className="text-ink-900">{userCountFor(row.original.id)}</span>,
    },
    {
      id: "status",
      header: "Status",
      cell: () => <Badge tone="success">Active</Badge>,
    },
    {
      id: "actions",
      header: "Actions",
      cell: ({ row }) => {
        const role = row.original;
        const staffCount = userCountFor(role.id);
        return (
          <div className="gap-space-2 flex items-center">
            <button
              type="button"
              onClick={() => onEditPermissions(role.id)}
              className="border-brand-200 px-space-3 text-brand-700 hover:bg-brand-50 rounded-md border py-1.5 text-[12px] font-semibold"
            >
              Edit Permissions
            </button>
            <button
              type="button"
              onClick={() => onManageUsers(role.id)}
              title="Manage user-level permission overrides for people on this role"
              className="border-line px-space-3 text-ink-700 flex items-center gap-1 rounded-md border py-1.5 text-[12px] font-semibold hover:bg-black/[0.03]"
            >
              <UserCog size={14} /> Manage Users
            </button>
            {canManage && (
              <>
                <button
                  type="button"
                  onClick={() => onRename(role)}
                  className="border-line text-ink-600 rounded-md border p-1.5 hover:bg-black/[0.03]"
                  title="Rename"
                >
                  <Pencil size={14} />
                </button>
                <button
                  type="button"
                  onClick={() => onDelete(role)}
                  disabled={role.is_protected || staffCount > 0}
                  title={
                    role.is_protected
                      ? "The Admin role is reserved and can't be deleted."
                      : staffCount > 0
                        ? `${staffCount} staff member(s) are still assigned to this role.`
                        : "Delete role"
                  }
                  className="border-line text-ink-600 rounded-md border p-1.5 hover:bg-black/[0.03] disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <Trash2 size={14} />
                </button>
              </>
            )}
          </div>
        );
      },
    },
  ];
}

type CreateStaffOverrideColumnsOptions = {
  pageLabel: Record<string, string>;
  roleDefaultFor: (pageKey: string) => PagePerms;
  cellFor: (pageKey: string) => OverrideCell;
  canWrite: boolean;
  isSaving: (pageKey: string) => boolean;
  onChange: (pageKey: string, next: OverrideCell) => void;
};

/** One staff member's own override grid, on top of their role's own grid
 * (createRoleColumns above) -- same "rows are page keys" shape and same
 * plain-checkbox feel as that role grid, not a 3-way control: each checkbox
 * starts PRE-FILLED with the role's own current value for that cell, so
 * checking/unchecking it only matters the moment it disagrees with the
 * role -- that's the one signal that turns it into a real, saved override
 * (marked by the small "Custom" pill + reset icon next to it). Reset clears
 * the override outright and the checkbox falls back to following the role
 * again. */
export function createStaffOverrideColumns({
  pageLabel,
  roleDefaultFor,
  cellFor,
  canWrite,
  isSaving,
  onChange,
}: CreateStaffOverrideColumnsOptions): ColumnDef<string>[] {
  return [
    {
      id: "page",
      header: "Page",
      cell: ({ row }) => (
        <span className="text-ink-900">{pageLabel[row.original] || row.original}</span>
      ),
    },
    ...ACTIONS.map((action): ColumnDef<string> => ({
      id: action,
      header: () => <span className="block text-center capitalize">{action}</span>,
      cell: ({ row }) => {
        const pageKey = row.original;
        const cell = cellFor(pageKey);
        const roleDefault = roleDefaultFor(pageKey)[action];
        const isOverridden = cell[action] !== null;
        const effective = isOverridden ? (cell[action] as boolean) : roleDefault;
        const disabled = !canWrite || isSaving(pageKey);
        return (
          <div className="flex items-center justify-center gap-1.5">
            <input
              type="checkbox"
              checked={effective}
              disabled={disabled}
              onChange={(e) => onChange(pageKey, { ...cell, [action]: e.target.checked })}
              className="accent-brand-600 h-4 w-4 disabled:opacity-50"
            />
            {isOverridden && (
              <button
                type="button"
                disabled={disabled}
                onClick={() => onChange(pageKey, { ...cell, [action]: null })}
                title={`Custom for this person -- click to reset back to the role's own setting (${roleDefault ? "allowed" : "denied"})`}
                className="border-brand-200 bg-brand-50 text-brand-700 hover:bg-brand-100 rounded border px-1 py-0.5 text-[9px] font-bold uppercase disabled:cursor-not-allowed disabled:opacity-50"
              >
                Custom ↺
              </button>
            )}
          </div>
        );
      },
    })),
  ];
}
