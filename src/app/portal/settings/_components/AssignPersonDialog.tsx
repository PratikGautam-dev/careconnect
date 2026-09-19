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
    <div
      className="p-space-4 fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={handleClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-card p-space-5 flex max-h-[80vh] w-full max-w-[420px] flex-col rounded-lg shadow-[var(--shadow-lg)]"
      >
        <h2 className="mb-space-3 text-ink-900 text-[16px] font-bold">{title}</h2>
        <div className="mb-space-3 relative">
          <Search
            size={14}
            className="left-space-3 text-ink-400 pointer-events-none absolute top-1/2 -translate-y-1/2"
          />
          <input
            type="text"
            placeholder="Search…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="border-line bg-card pl-space-8 pr-space-3 text-ink-900 focus:border-brand-400 h-10 w-full rounded-md border text-[13px] outline-none"
          />
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {filtered.length === 0 ? (
            <p className="py-space-4 text-ink-400 text-center text-[13px]">No matches.</p>
          ) : (
            filtered.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setSelectedId(p.id)}
                className={cn(
                  "px-space-3 py-space-2 flex w-full flex-col items-start rounded-md text-left",
                  selectedId === p.id ? "bg-brand-50" : "hover:bg-black/[0.03]",
                )}
              >
                <span className="text-ink-900 text-[13.5px] font-semibold">{p.label}</span>
                <span className="text-ink-400 text-[12px]">{p.sublabel}</span>
              </button>
            ))
          )}
        </div>
        <div className="mt-space-4 gap-space-2 flex justify-end">
          <Button type="button" variant="secondary" onClick={handleClose} disabled={saving}>
            Cancel
          </Button>
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
