"use client";

import { Plus, Trash2, X } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Switch } from "@/components/ui/Switch";
import { useLabServiceAreas } from "@/hooks/useLabServiceAreas";

/** Lab Test Phase 2 follow-up: the hospital-configurable list of PIN codes
 * serviceable for Home Sample Collection -- a patient entering an
 * unlisted PIN on WhatsApp is offered Visit Hospital/Lab instead (see
 * flows/booking/types/lab.py). Same simple add/toggle/delete shape as
 * DaycareDurationOptions.tsx, just a single field (no label/hours to edit). */
export function LabServiceAreasManager({ canManage }: { canManage: boolean }) {
  const {
    areas, error, pendingId,
    showAddForm, setShowAddForm, newPincode, setNewPincode,
    toggleActive, removeArea, addArea,
  } = useLabServiceAreas();

  if (areas === null) return null;

  return (
    <div>
      {error && <p className="mb-space-3 text-[12.5px] font-medium text-error">{error}</p>}

      {areas.length === 0 ? (
        <p className="mb-space-3 text-[13px] text-ink-400">No serviceable PIN codes added yet.</p>
      ) : (
        <ul className="mb-space-3 divide-y divide-line">
          {areas.map((area) => (
            <li key={area.id} className="flex items-center justify-between py-space-2">
              <p className="text-[13.5px] font-semibold text-ink-900">{area.pincode}</p>
              <div className="flex items-center gap-space-3">
                <Badge tone={area.is_active ? "success" : "neutral"}>{area.is_active ? "Active" : "Inactive"}</Badge>
                <Switch
                  checked={area.is_active}
                  onChange={() => toggleActive(area)}
                  disabled={pendingId === area.id || !canManage}
                  aria-label={`Toggle ${area.pincode}`}
                />
                {canManage && (
                  <button
                    type="button"
                    onClick={() => removeArea(area)}
                    disabled={pendingId === area.id}
                    className="text-ink-400 hover:text-error"
                    title="Remove"
                  >
                    <Trash2 size={15} />
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {canManage && (
        showAddForm ? (
          <div className="flex flex-wrap items-center gap-space-2">
            <Input
              value={newPincode}
              onChange={(e) => setNewPincode(e.target.value)}
              placeholder="e.g. 560001"
              className="w-32"
            />
            <Button type="button" size="md" onClick={addArea} disabled={pendingId === "new" || !newPincode.trim()}>
              Add
            </Button>
            <Button type="button" variant="ghost" size="md" onClick={() => { setShowAddForm(false); setNewPincode(""); }}>
              <X size={14} />
            </Button>
          </div>
        ) : (
          <Button type="button" variant="secondary" size="md" onClick={() => setShowAddForm(true)}>
            <Plus size={14} /> Add PIN code
          </Button>
        )
      )}
    </div>
  );
}
