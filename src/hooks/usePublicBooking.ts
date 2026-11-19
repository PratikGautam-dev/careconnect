import { useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export type PublicBookingWidget = {
  hospital: { name: string };
  appointment_types: { id: string; label: string; requires_consent: boolean }[];
  departments: { id: string; name: string }[];
  doctors_by_department: Record<string, { id: string; name: string }[]>;
};

export type PublicBookingForm = {
  appointment_type_id: string | null;
  department_id: string;
  doctor_id: string;
  slot_id: string;
  patient_name: string;
  patient_phone: string;
  patient_date_of_birth: string;
  patient_gender: string;
  consent_given: boolean;
};

/** No auth header at all -- this is public/booking_api.py's unauthenticated
 * widget, the public counterpart of portalFetch/staffFetch, same shape as
 * src/lib/api.ts's submitOnboarding(). */
async function publicFetch(path: string): Promise<{ ok: true; data: unknown } | { ok: false; error: string }> {
  try {
    const res = await fetch(`${API_BASE_URL}${path}`);
    const data = await res.json();
    if (res.ok) return { ok: true, data };
    return { ok: false, error: data?.error || "Something went wrong." };
  } catch {
    return { ok: false, error: "Couldn't reach the server — check your connection." };
  }
}

/** Loads the widget's catalog (departments/doctors/appointment types) for
 * one hospital, found by its public display_id. */
export function usePublicBookingWidget(hospitalDisplayId: string) {
  const [widget, setWidget] = useState<PublicBookingWidget | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    setNotFound(false);
    const result = await publicFetch(`/api/public/booking/${hospitalDisplayId}`);
    if (!result.ok) {
      setNotFound(true);
      setLoading(false);
      return;
    }
    setWidget(result.data as PublicBookingWidget);
    setLoading(false);
  }

  async function loadSlots(doctorId: string): Promise<Record<string, { id: string; label: string }[]>> {
    const result = await publicFetch(
      `/api/public/booking/${hospitalDisplayId}/slots?doctor_id=${encodeURIComponent(doctorId)}`,
    );
    if (!result.ok) {
      setError(result.error);
      return {};
    }
    return (result.data as { slots_by_date: Record<string, { id: string; label: string }[]> }).slots_by_date;
  }

  async function submit(
    form: PublicBookingForm,
  ): Promise<{ ok: true; referenceId: string } | { ok: false; errors: string[] }> {
    try {
      const res = await fetch(`${API_BASE_URL}/api/public/booking/${hospitalDisplayId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (res.ok) return { ok: true, referenceId: data.reference_id };
      return { ok: false, errors: data.errors || [data.error || "Something went wrong."] };
    } catch {
      return { ok: false, errors: ["Couldn't reach the server — check your connection."] };
    }
  }

  return { widget, loading, notFound, error, load, loadSlots, submit };
}
