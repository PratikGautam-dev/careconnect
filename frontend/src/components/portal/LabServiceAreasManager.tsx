"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus, Trash2, X } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { portalFetch } from "@/lib/portalAuth";

type ServiceArea = { id: number; pincode: string; is_active: boolean };

/** Lab Test Phase 2 follow-up: the hospital-configurable list of PIN codes
 * serviceable for Home Sample Collection -- a patient entering an
 * unlisted PIN on WhatsApp is offered Visit Hospital/Lab instead (see
 * flows/booking/types/lab.py). Same simple add/toggle/delete shape as
 * DaycareDurationOptions.tsx, just a single field (no label/hours to edit). */
export function LabServiceAreasManager({ canManage }: { canManage: boolean }) {
  const [areas, setAreas] = useState<ServiceArea[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<number | "new" | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newPincode, setNewPincode] = useState("");

  const load = useCallback(async () => {
    const result = await portalFetch("/api/portal/lab-service-areas");
    if (!result.ok) {
      setAreas(null);
      return;
    }
    setAreas((result.data as { lab_service_areas: ServiceArea[] }).lab_service_areas);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function toggleActive(area: ServiceArea) {
    setPendingId(area.id);
    setError(null);
    const result = await portalFetch(`/api/portal/lab-service-areas/${area.id}/active`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: !area.is_active }),
    });
    setPendingId(null);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      return;
    }
    load();
  }

  async function removeArea(area: ServiceArea) {
    if (!window.confirm(`Remove PIN code "${area.pincode}" from serviceable areas?`)) return;
    setPendingId(area.id);
    setError(null);
    const result = await portalFetch(`/api/portal/lab-service-areas/${area.id}`, { method: "DELETE" });
    setPendingId(null);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      return;
    }
    load();
  }

  async function addArea() {
    if (!newPincode.trim()) return;
    setPendingId("new");
    setError(null);
    const result = await portalFetch("/api/portal/lab-service-areas", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pincode: newPincode.trim() }),
    });
    setPendingId(null);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      return;
    }
    setNewPincode("");
    setShowAddForm(false);
    load();
  }

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
                <button
                  type="button"
                  onClick={() => toggleActive(area)}
                  disabled={pendingId === area.id || !canManage}
                  role="switch"
                  aria-checked={area.is_active}
                  className={`relative h-6 w-11 shrink-0 rounded-full transition-colors duration-150 ${
                    area.is_active ? "bg-brand-600" : "bg-line"
                  } ${pendingId === area.id ? "opacity-60" : ""}`}
                >
                  <span
                    className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform duration-150 ${
                      area.is_active ? "translate-x-[22px]" : "translate-x-0.5"
                    }`}
                  />
                </button>
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
