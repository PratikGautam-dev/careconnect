"use client";

import { useCallback, useEffect, useState } from "react";
import { Pencil, Plus, Trash2, X } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { portalFetch } from "@/lib/portalAuth";

type DurationOption = { id: number; label: string; hours: number; is_active: boolean; sort_order: number };

/** Daycare Phase 2 (docs/per-appointment-type-flow-plan.md): the duration
 * options shown to a patient at the WhatsApp booking flow's
 * STATE_AWAITING_DAYCARE_DURATION step, hospital-configurable (confirmed
 * with the user -- a same-day few-hour stay and a multi-night admission
 * both need to be expressible, and hospitals price/label these
 * differently). Unlike appointment_types (a closed catalog, toggle-only),
 * these can be freely added/edited/removed -- see
 * portal/routes/daycare_duration_options.py's own docstring. */
export function DaycareDurationOptions({ canManage }: { canManage: boolean }) {
  const [options, setOptions] = useState<DurationOption[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<number | "new" | null>(null);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editLabel, setEditLabel] = useState("");
  const [editHours, setEditHours] = useState("");

  const [showAddForm, setShowAddForm] = useState(false);
  const [newLabel, setNewLabel] = useState("");
  const [newHours, setNewHours] = useState("");

  const load = useCallback(async () => {
    const result = await portalFetch("/api/portal/daycare-duration-options");
    if (!result.ok) {
      // 403 (no manage_appointment_types) is expected for a clinic tenant
      // without that capability -- same "hide, don't error" convention as
      // this page's own audit-log section.
      setOptions(null);
      return;
    }
    setOptions((result.data as { daycare_duration_options: DurationOption[] }).daycare_duration_options);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function startEdit(option: DurationOption) {
    setEditingId(option.id);
    setEditLabel(option.label);
    setEditHours(String(option.hours));
    setShowAddForm(false);
  }

  async function saveEdit(id: number) {
    const hours = Number(editHours);
    if (!editLabel.trim() || !Number.isInteger(hours) || hours <= 0) return;
    setPendingId(id);
    setError(null);
    const result = await portalFetch(`/api/portal/daycare-duration-options/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label: editLabel.trim(), hours }),
    });
    setPendingId(null);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      return;
    }
    setEditingId(null);
    load();
  }

  async function toggleActive(option: DurationOption) {
    setPendingId(option.id);
    setError(null);
    const result = await portalFetch(`/api/portal/daycare-duration-options/${option.id}/active`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: !option.is_active }),
    });
    setPendingId(null);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      return;
    }
    load();
  }

  async function removeOption(option: DurationOption) {
    if (!window.confirm(`Delete "${option.label}"? Past bookings keep their stored duration either way.`)) return;
    setPendingId(option.id);
    setError(null);
    const result = await portalFetch(`/api/portal/daycare-duration-options/${option.id}`, { method: "DELETE" });
    setPendingId(null);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      return;
    }
    load();
  }

  async function addOption() {
    const hours = Number(newHours);
    if (!newLabel.trim() || !Number.isInteger(hours) || hours <= 0) return;
    setPendingId("new");
    setError(null);
    const result = await portalFetch("/api/portal/daycare-duration-options", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label: newLabel.trim(), hours }),
    });
    setPendingId(null);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      return;
    }
    setNewLabel("");
    setNewHours("");
    setShowAddForm(false);
    load();
  }

  // Not loaded yet, or the portal 403'd (no manage_appointment_types) --
  // either way, nothing to show. The parent Card wrapping this decides
  // whether to render at all based on the same capability, so this is only
  // ever the "loading" case in practice.
  if (options === null) return null;

  return (
    <div>
      {error && <p className="mb-space-3 text-[12.5px] font-medium text-error">{error}</p>}

      {options.length === 0 ? (
        <p className="mb-space-3 text-[13px] text-ink-400">No duration options yet.</p>
      ) : (
        <ul className="mb-space-3 divide-y divide-line">
          {options.map((option) => (
            <li key={option.id} className="py-space-2">
              {editingId === option.id ? (
                <div className="flex flex-wrap items-center gap-space-2">
                  <Input
                    value={editLabel}
                    onChange={(e) => setEditLabel(e.target.value)}
                    placeholder="Label"
                    className="min-w-[160px] flex-1"
                  />
                  <Input
                    type="number"
                    min={1}
                    value={editHours}
                    onChange={(e) => setEditHours(e.target.value)}
                    placeholder="Hours"
                    className="w-24"
                  />
                  <Button
                    type="button"
                    size="md"
                    onClick={() => saveEdit(option.id)}
                    disabled={pendingId === option.id || !editLabel.trim() || !editHours}
                  >
                    Save
                  </Button>
                  <Button type="button" variant="ghost" size="md" onClick={() => setEditingId(null)}>
                    <X size={14} />
                  </Button>
                </div>
              ) : (
                <div className="flex flex-col gap-space-2 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-[13.5px] font-semibold text-ink-900">{option.label}</p>
                    <p className="text-[12px] text-ink-600">{option.hours} hour{option.hours === 1 ? "" : "s"}</p>
                  </div>
                  <div className="flex items-center gap-space-3">
                    {canManage && (
                      <button
                        type="button"
                        onClick={() => startEdit(option)}
                        className="text-ink-400 hover:text-ink-700"
                        title="Edit"
                      >
                        <Pencil size={15} />
                      </button>
                    )}
                    <Badge tone={option.is_active ? "success" : "neutral"}>
                      {option.is_active ? "Active" : "Inactive"}
                    </Badge>
                    <button
                      type="button"
                      onClick={() => toggleActive(option)}
                      disabled={pendingId === option.id || !canManage}
                      role="switch"
                      aria-checked={option.is_active}
                      className={`relative h-6 w-11 shrink-0 rounded-full transition-colors duration-150 ${
                        option.is_active ? "bg-brand-600" : "bg-line"
                      } ${pendingId === option.id ? "opacity-60" : ""}`}
                    >
                      <span
                        className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform duration-150 ${
                          option.is_active ? "translate-x-[22px]" : "translate-x-0.5"
                        }`}
                      />
                    </button>
                    {canManage && (
                      <button
                        type="button"
                        onClick={() => removeOption(option)}
                        disabled={pendingId === option.id}
                        className="text-ink-400 hover:text-error"
                        title="Delete"
                      >
                        <Trash2 size={15} />
                      </button>
                    )}
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {canManage && (
        showAddForm ? (
          <div className="flex flex-wrap items-center gap-space-2">
            <Input
              value={newLabel}
              onChange={(e) => setNewLabel(e.target.value)}
              placeholder="e.g. 2 nights"
              className="min-w-[160px] flex-1"
            />
            <Input
              type="number"
              min={1}
              value={newHours}
              onChange={(e) => setNewHours(e.target.value)}
              placeholder="Hours"
              className="w-24"
            />
            <Button type="button" size="md" onClick={addOption} disabled={pendingId === "new" || !newLabel.trim() || !newHours}>
              Add
            </Button>
            <Button type="button" variant="ghost" size="md" onClick={() => { setShowAddForm(false); setNewLabel(""); setNewHours(""); }}>
              <X size={14} />
            </Button>
          </div>
        ) : (
          <Button type="button" variant="secondary" size="md" onClick={() => setShowAddForm(true)}>
            <Plus size={14} /> Add duration option
          </Button>
        )
      )}
    </div>
  );
}
