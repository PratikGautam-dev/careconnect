import { useCallback, useEffect, useState } from "react";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";

export type ServiceArea = { id: number; pincode: string; is_active: boolean };

/** Lab Test Phase 2 follow-up: loads + owns every mutation on the hospital-
 * configurable list of PIN codes serviceable for Home Sample Collection --
 * add / toggle-active / remove. */
export function useLabServiceAreas() {
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
      if (!result.unauthorized) toast.error("Couldn't update PIN code", result.error);
      return;
    }
    toast.success(area.is_active ? "PIN code deactivated" : "PIN code activated");
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
      if (!result.unauthorized) toast.error("Couldn't remove PIN code", result.error);
      return;
    }
    toast.success("PIN code removed");
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
      if (!result.unauthorized) toast.error("Couldn't add PIN code", result.error);
      return;
    }
    toast.success("PIN code added");
    setNewPincode("");
    setShowAddForm(false);
    load();
  }

  return {
    areas, error, pendingId,
    showAddForm, setShowAddForm, newPincode, setNewPincode,
    toggleActive, removeArea, addArea,
  };
}
