import { useQuery } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import type { DetailData } from "@/hooks/usePatientDetail";

/** Read-only fetch of the same /api/portal/patients/{id} payload the full
 * detail page (usePatientDetail) owns and mutates -- used by the Patients
 * list page's right-rail panel to show real visit history/notes/documents
 * for whichever patient is selected, without duplicating that page's much
 * larger edit/upload/follow-up surface. Mutating any of it still happens on
 * the full record page, one click away from the panel. */
export function usePatientSummary(patientId: number | null) {
  const { data, isFetching } = useQuery({
    queryKey: ["portal-patient-summary", patientId],
    enabled: patientId != null,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch(`/api/portal/patients/${patientId}`);
      if (!result.ok) return null;
      return result.data as DetailData;
    },
  });

  return { data: data ?? null, loading: isFetching };
}
