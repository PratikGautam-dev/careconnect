import { useEffect, useState } from "react";
import { portalFetch } from "@/lib/portalAuth";
import type { DetailData } from "@/hooks/usePatientDetail";

/** Read-only fetch of the same /api/portal/patients/{id} payload the full
 * detail page (usePatientDetail) owns and mutates -- used by the Patients
 * list page's right-rail panel to show real visit history/notes/documents
 * for whichever patient is selected, without duplicating that page's much
 * larger edit/upload/follow-up surface. Mutating any of it still happens on
 * the full record page, one click away from the panel. */
export function usePatientSummary(patientId: number | null) {
  const [data, setData] = useState<DetailData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (patientId == null) {
      setData(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setData(null);
    portalFetch(`/api/portal/patients/${patientId}`).then((result) => {
      if (cancelled) return;
      setLoading(false);
      if (result.ok) setData(result.data as DetailData);
    });
    return () => {
      cancelled = true;
    };
  }, [patientId]);

  return { data, loading };
}
