"use client";

import type { ColumnDef } from "@tanstack/react-table";
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
