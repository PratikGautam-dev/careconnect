import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { fetchSlotsByDate, type Resource } from "@/hooks/useAppointments";
import { portalFetch } from "@/lib/portalAuth";
import { isPortalMutationError, unwrapPortalResult } from "@/lib/portalMutation";
import { toast } from "@/lib/toast";
import { newTestBookingSchema } from "@/lib/validation/newTestBooking";

export type { Resource };
export type Slot = { id: string; label: string };
export type NewTestBookingContext = {
  resources: Resource[];
};
export type CollectionMethod = "visit" | "home";

/** Resource-bound sibling of useNewBooking.ts -- same
 * /api/portal/new-booking/context data source (departments/resources
 * lists), same "context only loads while open, every field resets on
 * close" lifecycle, just keyed by test(s) instead of department/doctor and
 * posting to /api/portal/new-test-booking.
 *
 * Mirrors the WhatsApp Lab Test flow's own basket shape (flows/booking/
 * types/lab.py): selectedTestIds is a list -- a lab-category booking can
 * bind several tests to one appointment (one collection method, one slot
 * for the whole basket, anchored on the FIRST test picked); a
 * diagnostic-category pick always replaces the whole selection (no basket
 * concept there, same as WhatsApp's own Diagnostic Test flow), and picking
 * a test of a different category than what's already selected starts a
 * fresh selection rather than mixing categories (mirrors the backend's own
 * "mixed basket rejected" rule). Slots for the picked selection are fetched
 * lazily off the FIRST (anchor) test only, the moment it changes -- see
 * useNewBooking.ts's own comment for why this isn't eager-loaded. */
export function useNewTestBooking(
  open: boolean,
  onBooked?: () => void,
  initialPatientName?: string,
  initialPatientPhone?: string,
) {
  const router = useRouter();

  const { data: ctx, error: queryError } = useQuery({
    queryKey: ["portal-new-test-booking-context"],
    enabled: open,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/new-booking/context");
      return unwrapPortalResult<NewTestBookingContext>(router, result);
    },
  });

  const [errors, setErrors] = useState<string[]>([]);
  const [success, setSuccess] = useState(false);

  const [patientName, setPatientName] = useState("");
  const [patientPhone, setPatientPhone] = useState("");
  const [patientDateOfBirth, setPatientDateOfBirth] = useState("");
  const [patientGender, setPatientGender] = useState("");
  const [selectedTestIds, setSelectedTestIds] = useState<number[]>([]);
  const [collectionMethod, setCollectionMethod] = useState<CollectionMethod | "">("");
  const [collectionAddress, setCollectionAddress] = useState("");
  const [collectionPincode, setCollectionPincode] = useState("");
  const [date, setDateRaw] = useState("");
  const [slotId, setSlotId] = useState("");

  // Open/close is seeded/reset during render (not an effect) -- React's own
  // "adjusting state when a prop changes" pattern -- so reopening always
  // starts from a clean form without costing an extra render cycle.
  const [seededOpen, setSeededOpen] = useState(false);
  if (open && !seededOpen) {
    setSeededOpen(true);
    setPatientName(initialPatientName ?? "");
    setPatientPhone(initialPatientPhone ?? "");
  } else if (!open && seededOpen) {
    setSeededOpen(false);
    setErrors([]);
    setSuccess(false);
    setPatientName("");
    setPatientPhone("");
    setPatientDateOfBirth("");
    setPatientGender("");
    setSelectedTestIds([]);
    setCollectionMethod("");
    setCollectionAddress("");
    setCollectionPincode("");
    setDateRaw("");
    setSlotId("");
  }

  const testsById = useMemo(() => {
    const map = new Map<number, Resource>();
    for (const r of ctx?.resources ?? []) map.set(r.id, r);
    return map;
  }, [ctx]);

  const selectedTests = useMemo(
    () => selectedTestIds.map((id) => testsById.get(id)).filter((t): t is Resource => !!t),
    [selectedTestIds, testsById],
  );
  const category = selectedTests[0]?.category ?? null;
  const anchorTestId = selectedTestIds[0] != null ? String(selectedTestIds[0]) : "";

  const { data: slotsByDate } = useQuery({
    queryKey: ["portal-new-test-booking-slots", anchorTestId],
    enabled: !!anchorTestId,
    retry: false,
    queryFn: async () => {
      const slots = await fetchSlotsByDate(router, { resourceId: anchorTestId });
      return slots ?? {};
    },
  });

  function toggleTest(test: Resource) {
    setSelectedTestIds((prev) => {
      if (prev.includes(test.id)) return prev.filter((id) => id !== test.id);
      if (test.category === "diagnostic") return [test.id];
      const sameCategory = prev.filter((id) => testsById.get(id)?.category === "lab");
      return [...sameCategory, test.id];
    });
    setDate("");
    setSlotId("");
  }

  function setDate(d: string) {
    setDateRaw(d);
    setSlotId("");
  }

  const datesForSelection = slotsByDate ? Object.keys(slotsByDate).sort() : [];
  const slotsForDate = date && slotsByDate ? slotsByDate[date] || [] : [];

  const submitMutation = useMutation({
    mutationFn: async (payload: Record<string, unknown>) => {
      const result = await portalFetch("/api/portal/new-test-booking", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return unwrapPortalResult<{ errors?: string[] }>(router, result);
    },
  });

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrors([]);

    const parsed = newTestBookingSchema.safeParse({
      patient_name: patientName,
      patient_phone: patientPhone,
      patient_date_of_birth: patientDateOfBirth,
      patient_gender: patientGender,
      test_ids: selectedTestIds,
      slot_id: slotId,
      collection_method: category === "lab" && collectionMethod ? collectionMethod : undefined,
      collection_address: category === "lab" ? collectionAddress : undefined,
      collection_pincode: category === "lab" ? collectionPincode : undefined,
    });
    if (!parsed.success) {
      setErrors(parsed.error.issues.map((issue) => issue.message));
      return;
    }

    try {
      const data = await submitMutation.mutateAsync(parsed.data);
      if (data.errors?.length) {
        setErrors(data.errors);
        toast.error("Couldn't create booking", data.errors[0]);
        return;
      }
      toast.success("Booking created");
      setSuccess(true);
      onBooked?.();
    } catch (err) {
      if (isPortalMutationError(err)) {
        setErrors([err.message]);
        toast.error("Couldn't create booking", err.message);
      }
    }
  }

  return {
    ctx: ctx ?? null,
    error: queryError ? "Couldn't load booking context — try again." : null,
    errors,
    submitting: submitMutation.isPending,
    success,
    patientName,
    setPatientName,
    patientPhone,
    setPatientPhone,
    patientDateOfBirth,
    setPatientDateOfBirth,
    patientGender,
    setPatientGender,
    selectedTestIds,
    selectedTests,
    category,
    toggleTest,
    collectionMethod,
    setCollectionMethod,
    collectionAddress,
    setCollectionAddress,
    collectionPincode,
    setCollectionPincode,
    date,
    setDate,
    slotId,
    setSlotId,
    datesForSelection,
    slotsForDate,
    slotsLoading: !!anchorTestId && slotsByDate === undefined,
    handleSubmit,
  };
}
