import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { validatePincode, validatePincodeRange } from "@/lib/validation/pincode";
import { toast } from "@/lib/toast";

export type ServiceArea = {
  id: number;
  pincode: string | null;
  range_start: string | null;
  range_end: string | null;
  is_active: boolean;
};

/** Loads + owns every mutation on the hospital-configurable list of PIN
 * codes serviceable for Home Sample Collection -- add (single pincode or
 * a range) / toggle-active / remove. Single page, single consumer -- kept
 * as one hook rather than separated into per-mutation hooks nothing else
 * would import. */
export function useLabServiceAreas() {
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<number | "new" | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [addMode, setAddMode] = useState<"single" | "range">("single");
  const [newPincode, setNewPincode] = useState("");
  const [newRangeStart, setNewRangeStart] = useState("");
  const [newRangeEnd, setNewRangeEnd] = useState("");

  const { data: areas, refetch } = useQuery({
    queryKey: ["portal-lab-service-areas"],
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/lab-service-areas");
      if (!result.ok) return null;
      return (result.data as { lab_service_areas: ServiceArea[] }).lab_service_areas;
    },
  });

  const toggleActiveMutation = useMutation({
    mutationFn: async ({ areaId, isActive }: { areaId: number; isActive: boolean }) => {
      const result = await portalFetch(`/api/portal/lab-service-areas/${areaId}/active`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: isActive }),
      });
      if (!result.ok) {
        throw new Error(
          result.unauthorized ? "Session expired — please log in again." : result.error,
        );
      }
    },
  });

  async function toggleActive(area: ServiceArea) {
    setPendingId(area.id);
    setError(null);
    try {
      await toggleActiveMutation.mutateAsync({ areaId: area.id, isActive: !area.is_active });
      toast.success(area.is_active ? "PIN code deactivated" : "PIN code activated");
      refetch();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setError(message);
      toast.error("Couldn't update PIN code", message);
    } finally {
      setPendingId(null);
    }
  }

  const removeAreaMutation = useMutation({
    mutationFn: async (areaId: number) => {
      const result = await portalFetch(`/api/portal/lab-service-areas/${areaId}`, {
        method: "DELETE",
      });
      if (!result.ok) {
        throw new Error(
          result.unauthorized ? "Session expired — please log in again." : result.error,
        );
      }
    },
  });

  async function removeArea(area: ServiceArea) {
    setPendingId(area.id);
    setError(null);
    try {
      await removeAreaMutation.mutateAsync(area.id);
      toast.success("PIN code removed");
      refetch();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setError(message);
      toast.error("Couldn't remove PIN code", message);
    } finally {
      setPendingId(null);
    }
  }

  const addAreaMutation = useMutation({
    mutationFn: async (body: { pincode: string } | { range_start: string; range_end: string }) => {
      const result = await portalFetch("/api/portal/lab-service-areas", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!result.ok) {
        throw new Error(
          result.unauthorized ? "Session expired — please log in again." : result.error,
        );
      }
    },
  });

  async function addArea() {
    const body =
      addMode === "single"
        ? { pincode: newPincode.trim() }
        : { range_start: newRangeStart.trim(), range_end: newRangeEnd.trim() };
    if (addMode === "single" ? !newPincode.trim() : !(newRangeStart.trim() && newRangeEnd.trim()))
      return;
    // Same format/ordering rules db/repositories/lab_service_areas.py's own
    // _validate_range() enforces server-side -- caught here first so a
    // malformed PIN never round-trips just to come back as a 400.
    const invalid =
      addMode === "single"
        ? validatePincode(newPincode.trim())
        : validatePincodeRange(newRangeStart.trim(), newRangeEnd.trim());
    if (invalid) {
      setError(invalid);
      return;
    }
    setPendingId("new");
    setError(null);
    try {
      await addAreaMutation.mutateAsync(body);
      toast.success(addMode === "single" ? "PIN code added" : "PIN code range added");
      setNewPincode("");
      setNewRangeStart("");
      setNewRangeEnd("");
      setShowAddForm(false);
      refetch();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setError(message);
      toast.error("Couldn't add PIN code", message);
    } finally {
      setPendingId(null);
    }
  }

  return {
    areas: areas ?? null,
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
  };
}
