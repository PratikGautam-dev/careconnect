"use client";

import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/cn";
import { useAdminSupportTicketCategories } from "@/hooks/useAdminSupportTickets";

/** Super-admin-owned ticket-category catalog -- same "platform manages this
 * list" posture as Plans & Billing's own plan catalog, not something a
 * hospital's own portal admin configures. Deletion is refused server-side
 * (409) while any ticket still references the category. */
export function CategoryManagementCard() {
  const { categories, error, create, toggleActive, remove, creating } =
    useAdminSupportTicketCategories();
  const [newName, setNewName] = useState("");

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const name = newName.trim();
    if (!name) return;
    const ok = await create(name);
    if (ok) setNewName("");
  }

  return (
    <Card className="p-space-4">
      <h3 className="text-label text-ink-900 mb-space-1 font-bold">Ticket Categories</h3>
      <p className="text-hint mb-space-3">
        Manage the category list every hospital&apos;s &quot;Raise a Ticket&quot; form picks from.
      </p>

      {error && <p className="mb-space-3 text-error text-[13px]">{error}</p>}

      <form onSubmit={handleCreate} className="gap-space-2 mb-space-3 flex">
        <Input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="New category name"
          className="flex-1"
        />
        <Button type="submit" disabled={creating || !newName.trim()}>
          <Plus size={14} /> Add
        </Button>
      </form>

      {!categories ? (
        <p className="text-ink-400 py-space-3 text-center text-[13px]">Loading…</p>
      ) : categories.length === 0 ? (
        <p className="text-ink-400 py-space-3 text-center text-[13px]">No categories yet.</p>
      ) : (
        <ul className="divide-line divide-y">
          {categories.map((c) => (
            <li key={c.id} className="py-space-2 flex items-center justify-between">
              <button
                type="button"
                onClick={() => toggleActive(c)}
                className={cn(
                  "text-left text-[13px] font-medium",
                  c.is_active ? "text-ink-900" : "text-ink-400 line-through",
                )}
                title={c.is_active ? "Click to deactivate" : "Click to reactivate"}
              >
                {c.name}
              </button>
              <button
                type="button"
                onClick={() => remove(c)}
                title="Delete category"
                className="text-ink-400 hover:text-error hover:bg-error-tint flex h-7 w-7 items-center justify-center rounded-md"
              >
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
