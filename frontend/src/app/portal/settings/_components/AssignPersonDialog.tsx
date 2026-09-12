"use client";

import { useState } from "react";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";

export type PersonOption = { id: string; label: string; sublabel: string };

type Props = {
  open: boolean;
  title: string;
  people: PersonOption[];
  saving: boolean;
  onClose: () => void;
  onAssign: (personId: string) => void;
};

/** Shared picker for the "Assign Doctor" / "Manage Staff" quick actions --
 * same plain fixed-overlay modal convention as DepartmentFormDialog/
 * ConfirmDialog. Deliberately generic (a plain {id,label,sublabel} list)
 * since the two callers source people from completely different endpoints
 * (doctors vs. staff) but need the exact same pick-one-and-confirm UI. */
export function AssignPersonDialog({ open, title, people, saving, onClose, onAssign }: Props) {
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  if (!open) return null;

  const filtered = people.filter((p) => {
    const q = query.trim().toLowerCase();
    return !q || p.label.toLowerCase().includes(q) || p.sublabel.toLowerCase().includes(q);
  });

  function handleClose() {
    setQuery("");
    setSelectedId(null);
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-space-4" onClick={handleClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="flex max-h-[80vh] w-full max-w-[420px] flex-col rounded-lg bg-card p-space-5 shadow-[var(--shadow-lg)]"
      >
        <h2 className="mb-space-3 text-[16px] font-bold text-ink-900">{title}</h2>
        <div className="relative mb-space-3">
          <Search size={14} className="pointer-events-none absolute left-space-3 top-1/2 -translate-y-1/2 text-ink-400" />
          <input
            type="text"
            placeholder="Search…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="h-10 w-full rounded-md border border-line bg-card pl-space-8 pr-space-3 text-[13px] text-ink-900 outline-none focus:border-brand-400"
          />
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {filtered.length === 0 ? (
            <p className="py-space-4 text-center text-[13px] text-ink-400">No matches.</p>
          ) : (
            filtered.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setSelectedId(p.id)}
                className={cn(
                  "flex w-full flex-col items-start rounded-md px-space-3 py-space-2 text-left",
                  selectedId === p.id ? "bg-brand-50" : "hover:bg-black/[0.03]",
                )}
              >
                <span className="text-[13.5px] font-semibold text-ink-900">{p.label}</span>
                <span className="text-[12px] text-ink-400">{p.sublabel}</span>
              </button>
            ))
          )}
        </div>
        <div className="mt-space-4 flex justify-end gap-space-2">
          <Button type="button" variant="secondary" onClick={handleClose} disabled={saving}>Cancel</Button>
          <Button
            type="button"
            onClick={() => selectedId && onAssign(selectedId)}
            disabled={saving || !selectedId}
          >
            {saving ? "Assigning…" : "Assign"}
          </Button>
        </div>
      </div>
    </div>
  );
}
