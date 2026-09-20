"use client";

import { Plus, Trash2, X } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { Switch } from "@/components/ui/Switch";
import { useLabServiceAreas } from "@/hooks/useLabServiceAreas";

/** Hospital-configurable list of PIN codes serviceable for Home Sample
 * Collection; a patient entering an unlisted PIN is offered Visit
 * Hospital/Lab instead. Supports both single-PIN and range entry. */
export function LabServiceAreasManager({ canManage }: { canManage: boolean }) {
  const {
    areas,
    error,
    pendingId,
    showAddForm,
    setShowAddForm,
    addMode,
    setAddMode,
    newPincode,
    setNewPincode,
    newRangeStart,
    setNewRangeStart,
    newRangeEnd,
    setNewRangeEnd,
    toggleActive,
    removeArea,
    addArea,
  } = useLabServiceAreas();

  if (areas === null) return null;

  const canSubmit =
    addMode === "single" ? !!newPincode.trim() : !!(newRangeStart.trim() && newRangeEnd.trim());

  return (
    <div>
      {error && <p className="mb-space-3 text-error text-[12.5px] font-medium">{error}</p>}

      {areas.length === 0 ? (
        <p className="mb-space-3 text-ink-400 text-[13px]">No serviceable PIN codes added yet.</p>
      ) : (
        <ul className="mb-space-3 divide-line divide-y">
          {areas.map((area) => (
            <li key={area.id} className="py-space-2 flex items-center justify-between">
              <p className="text-ink-900 text-[13.5px] font-semibold">
                {area.pincode ?? `${area.range_start}–${area.range_end}`}
              </p>
              <div className="gap-space-3 flex items-center">
                <Badge tone={area.is_active ? "success" : "neutral"}>
                  {area.is_active ? "Active" : "Inactive"}
                </Badge>
                <Switch
                  checked={area.is_active}
                  onChange={() => toggleActive(area)}
                  disabled={pendingId === area.id || !canManage}
                  aria-label={`Toggle ${area.pincode ?? `${area.range_start}-${area.range_end}`}`}
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

      {canManage &&
        (showAddForm ? (
          <div className="gap-space-2 flex flex-wrap items-end">
            <div className="gap-space-1 flex">
              <Button
                type="button"
                variant={addMode === "single" ? "secondary" : "ghost"}
                size="md"
                onClick={() => setAddMode("single")}
              >
                Single
              </Button>
              <Button
                type="button"
                variant={addMode === "range" ? "secondary" : "ghost"}
                size="md"
                onClick={() => setAddMode("range")}
              >
                Range
              </Button>
            </div>
            {addMode === "single" ? (
              <Field label="PIN code" htmlFor="new_pincode" required className="mb-0">
                <Input
                  id="new_pincode"
                  value={newPincode}
                  onChange={(e) => setNewPincode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  inputMode="numeric"
                  maxLength={6}
                  placeholder="e.g. 560001"
                  className="w-32"
                />
              </Field>
            ) : (
              <>
                <Field label="From" htmlFor="new_range_start" required className="mb-0">
                  <Input
                    id="new_range_start"
                    value={newRangeStart}
                    onChange={(e) =>
                      setNewRangeStart(e.target.value.replace(/\D/g, "").slice(0, 6))
                    }
                    inputMode="numeric"
                    maxLength={6}
                    placeholder="e.g. 560001"
                    className="w-36"
                  />
                </Field>
                <Field label="To" htmlFor="new_range_end" required className="mb-0">
                  <Input
                    id="new_range_end"
                    value={newRangeEnd}
                    onChange={(e) => setNewRangeEnd(e.target.value.replace(/\D/g, "").slice(0, 6))}
                    inputMode="numeric"
                    maxLength={6}
                    placeholder="e.g. 560050"
                    className="w-36"
                  />
                </Field>
              </>
            )}
            <Button
              type="button"
              size="md"
              onClick={addArea}
              disabled={pendingId === "new" || !canSubmit}
            >
              Add
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="md"
              onClick={() => {
                setShowAddForm(false);
                setNewPincode("");
                setNewRangeStart("");
                setNewRangeEnd("");
              }}
            >
              <X size={14} />
            </Button>
          </div>
        ) : (
          <Button type="button" variant="secondary" size="md" onClick={() => setShowAddForm(true)}>
            <Plus size={14} /> Add PIN code
          </Button>
        ))}
    </div>
  );
}
