"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { CalendarCheck, CheckCircle2, ChevronLeft } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { GENDER_VALUES } from "@/lib/validation/patientInfo";
import { type PublicBookingForm, usePublicBookingWidget } from "@/hooks/usePublicBooking";

type Step = "type" | "department" | "doctor" | "slot" | "details" | "done";

// The separate careconnect-site project's own dev/deploy origin -- its
// marketing homepage this booking widget links back to.
const SITE_APP_URL = process.env.NEXT_PUBLIC_SITE_APP_URL || "http://localhost:3001";

const EMPTY_FORM: PublicBookingForm = {
  appointment_type_id: null,
  department_id: "",
  doctor_id: "",
  slot_id: "",
  patient_name: "",
  patient_phone: "",
  patient_date_of_birth: "",
  patient_gender: "",
  consent_given: false,
};

/** Public, unauthenticated booking widget -- the "Website" channel
 * (public/booking_api.py). Outside /portal and /admin, no StaffSessionProvider
 * (src/app/portal/layout.tsx is scoped to /portal only, so this page sits
 * below the root layout with none of that wrapping).
 *
 * A plain step-index form rather than a shared wizard component -- this
 * repo's one existing multi-step flow (onboarding) is tightly coupled to
 * its own hospital-setup steps, not a generic reusable wizard, so this
 * mirrors its STEP-BY-STEP SHAPE (one step visible at a time, Back/Next,
 * a confirmation step at the end) without importing it. Step order mirrors
 * the WhatsApp bot's own flow (flows/booking/book.py): appointment type (if
 * the hospital has any configured) -> department -> doctor -> slot ->
 * patient details -> confirmation. */
export default function PublicBookingPage() {
  const params = useParams<{ hospitalDisplayId: string }>();
  const hospitalDisplayId = params.hospitalDisplayId;
  const { widget, loading, notFound, load, loadSlots, submit } =
    usePublicBookingWidget(hospitalDisplayId);

  const [step, setStep] = useState<Step>("type");
  const [form, setForm] = useState<PublicBookingForm>(EMPTY_FORM);
  const [slotsByDate, setSlotsByDate] = useState<Record<string, { id: string; label: string }[]>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitErrors, setSubmitErrors] = useState<string[]>([]);
  const [referenceId, setReferenceId] = useState<string | null>(null);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hospitalDisplayId]);

  async function pickDoctor(doctorId: string) {
    setForm((f) => ({ ...f, doctor_id: doctorId, slot_id: "" }));
    const slots = await loadSlots(doctorId);
    setSlotsByDate(slots);
    setStep("slot");
  }

  async function handleSubmit() {
    setSubmitting(true);
    setSubmitErrors([]);
    const result = await submit(form);
    setSubmitting(false);
    if (!result.ok) {
      setSubmitErrors(result.errors);
      return;
    }
    setReferenceId(result.referenceId);
    setStep("done");
  }

  if (loading) {
    return (
      <div className="bg-paper flex min-h-screen items-center justify-center">
        <p className="text-hint text-[13px]">Loading…</p>
      </div>
    );
  }

  if (notFound || !widget) {
    return (
      <div className="bg-paper flex min-h-screen items-center justify-center p-space-4">
        <Card className="p-space-6 max-w-md text-center">
          <p className="text-ink-900 text-[15px] font-semibold">Booking isn&apos;t available here</p>
          <p className="text-hint mt-space-2 text-[13px]">
            This link isn&apos;t active, or online booking isn&apos;t turned on for this hospital.
          </p>
        </Card>
      </div>
    );
  }

  const doctorsForDepartment = form.department_id
    ? widget.doctors_by_department[form.department_id] || []
    : [];
  const hasAppointmentTypes = widget.appointment_types.length > 0;
  const selectedType = widget.appointment_types.find((t) => t.id === form.appointment_type_id) || null;
  const firstStep: Step = hasAppointmentTypes ? "type" : "department";
  // A hospital with no doctor-selection appointment types configured keeps
  // the original flow (straight into department selection) -- derived at
  // render time rather than via an effect + setState, which would trigger
  // an extra cascading render for something render logic can decide outright.
  const effectiveStep: Step = step === "type" && !hasAppointmentTypes ? "department" : step;

  const siteUrl = `${SITE_APP_URL}/site/${hospitalDisplayId}`;

  return (
    <div className="bg-paper min-h-screen px-space-4 py-space-8">
      <div className="mx-auto max-w-lg">
        <a
          href={siteUrl}
          className="text-ink-600 hover:text-ink-900 gap-space-1 mb-space-3 inline-flex items-center text-[12.5px] font-semibold"
        >
          <ChevronLeft size={14} /> Back to {widget.hospital.name}
        </a>
        <h1 className="text-ink-900 text-[20px] font-bold">{widget.hospital.name}</h1>
        <p className="text-hint mt-space-1 text-[13px]">Book an appointment online</p>

        <Card className="p-space-5 mt-space-5">
          {effectiveStep !== firstStep && effectiveStep !== "done" && (
            <button
              type="button"
              onClick={() =>
                setStep(
                  effectiveStep === "department"
                    ? firstStep
                    : effectiveStep === "doctor"
                      ? "department"
                      : effectiveStep === "slot"
                        ? "doctor"
                        : "slot",
                )
              }
              className="text-ink-600 gap-space-1 mb-space-4 inline-flex items-center text-[12.5px] font-semibold"
            >
              <ChevronLeft size={14} /> Back
            </button>
          )}

          {effectiveStep === "type" && (
            <>
              <p className="text-ink-900 mb-space-3 text-[14px] font-semibold">Choose an appointment type</p>
              <div className="gap-space-2 flex flex-col">
                {widget.appointment_types.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => {
                      setForm((f) => ({
                        ...f,
                        appointment_type_id: t.id,
                        department_id: "",
                        doctor_id: "",
                        slot_id: "",
                        consent_given: false,
                      }));
                      setStep("department");
                    }}
                    className="border-line hover:border-brand-300 hover:bg-brand-50 px-space-4 py-space-3 rounded-md border text-left text-[13.5px] font-medium transition-colors duration-150"
                  >
                    {t.label}
                    {t.requires_consent && (
                      <span className="text-hint ml-space-2 text-[11.5px] font-normal">Requires consent</span>
                    )}
                  </button>
                ))}
              </div>
            </>
          )}

          {effectiveStep === "department" && (
            <>
              <p className="text-ink-900 mb-space-3 text-[14px] font-semibold">Choose a department</p>
              <div className="gap-space-2 flex flex-col">
                {widget.departments.map((d) => (
                  <button
                    key={d.id}
                    type="button"
                    onClick={() => {
                      setForm((f) => ({ ...f, department_id: d.id, doctor_id: "", slot_id: "" }));
                      setStep("doctor");
                    }}
                    className="border-line hover:border-brand-300 hover:bg-brand-50 px-space-4 py-space-3 rounded-md border text-left text-[13.5px] font-medium transition-colors duration-150"
                  >
                    {d.name}
                  </button>
                ))}
              </div>
            </>
          )}

          {effectiveStep === "doctor" && (
            <>
              <p className="text-ink-900 mb-space-3 text-[14px] font-semibold">Choose a doctor</p>
              <div className="gap-space-2 flex flex-col">
                {doctorsForDepartment.map((doc) => (
                  <button
                    key={doc.id}
                    type="button"
                    onClick={() => pickDoctor(doc.id)}
                    className="border-line hover:border-brand-300 hover:bg-brand-50 px-space-4 py-space-3 rounded-md border text-left text-[13.5px] font-medium transition-colors duration-150"
                  >
                    {doc.name}
                  </button>
                ))}
                {doctorsForDepartment.length === 0 && (
                  <p className="text-hint text-[13px]">No doctors available in this department right now.</p>
                )}
              </div>
            </>
          )}

          {effectiveStep === "slot" && (
            <>
              <p className="text-ink-900 mb-space-3 text-[14px] font-semibold">Choose a time</p>
              <div className="gap-space-4 flex max-h-[360px] flex-col overflow-y-auto">
                {Object.entries(slotsByDate).map(([date, slots]) => (
                  <div key={date}>
                    <p className="text-hint mb-space-2 text-[12px] font-semibold uppercase tracking-wide">
                      {date}
                    </p>
                    <div className="gap-space-2 grid grid-cols-2">
                      {slots.map((slot) => (
                        <button
                          key={slot.id}
                          type="button"
                          onClick={() => {
                            setForm((f) => ({ ...f, slot_id: slot.id }));
                            setStep("details");
                          }}
                          className="border-line hover:border-brand-300 hover:bg-brand-50 px-space-3 py-space-2 rounded-md border text-[12.5px] font-medium transition-colors duration-150"
                        >
                          {slot.label}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
                {Object.keys(slotsByDate).length === 0 && (
                  <p className="text-hint text-[13px]">No slots available for this doctor right now.</p>
                )}
              </div>
            </>
          )}

          {effectiveStep === "details" && (
            <>
              <p className="text-ink-900 mb-space-3 text-[14px] font-semibold">Your details</p>
              <Field label="Full name" required>
                <Input
                  value={form.patient_name}
                  onChange={(e) => setForm((f) => ({ ...f, patient_name: e.target.value }))}
                  placeholder="Patient's full name"
                />
              </Field>
              <Field label="Phone number" required>
                <Input
                  value={form.patient_phone}
                  onChange={(e) => setForm((f) => ({ ...f, patient_phone: e.target.value }))}
                  placeholder="10-digit mobile number"
                />
              </Field>
              <Field label="Date of birth" hint="Optional">
                <Input
                  type="date"
                  value={form.patient_date_of_birth}
                  onChange={(e) => setForm((f) => ({ ...f, patient_date_of_birth: e.target.value }))}
                />
              </Field>
              <Field label="Gender" hint="Optional">
                <select
                  value={form.patient_gender}
                  onChange={(e) => setForm((f) => ({ ...f, patient_gender: e.target.value }))}
                  className="border-line bg-card text-ink-900 focus:border-brand-400 h-10 w-full rounded-md border px-space-3 text-[13px] outline-none"
                >
                  <option value="">Prefer not to say</option>
                  {GENDER_VALUES.map((g) => (
                    <option key={g} value={g}>
                      {g}
                    </option>
                  ))}
                </select>
              </Field>

              {selectedType?.requires_consent && (
                <label className="gap-space-2 bg-clay-100 p-space-3 mt-space-2 mb-space-3 flex items-start rounded-md text-[12.5px]">
                  <input
                    type="checkbox"
                    checked={form.consent_given}
                    onChange={(e) => setForm((f) => ({ ...f, consent_given: e.target.checked }))}
                    className="mt-space-1 shrink-0"
                  />
                  <span className="text-ink-900">
                    I consent to a {selectedType.label.toLowerCase()} with the doctor instead of an in-person
                    visit.
                  </span>
                </label>
              )}

              {submitErrors.length > 0 && (
                <ul className="mb-space-3 text-error list-disc pl-space-4 text-[12.5px]">
                  {submitErrors.map((e) => (
                    <li key={e}>{e}</li>
                  ))}
                </ul>
              )}

              <Button
                variant="primary"
                className="w-full"
                disabled={
                  submitting ||
                  !form.patient_name.trim() ||
                  !form.patient_phone.trim() ||
                  (Boolean(selectedType?.requires_consent) && !form.consent_given)
                }
                onClick={handleSubmit}
              >
                <CalendarCheck size={15} /> {submitting ? "Booking…" : "Confirm booking"}
              </Button>
            </>
          )}

          {effectiveStep === "done" && (
            <div className="py-space-6 text-center">
              <CheckCircle2 size={40} className="text-success mx-auto" />
              <p className="text-ink-900 mt-space-3 text-[15px] font-semibold">Appointment booked</p>
              <p className="text-hint mt-space-1 text-[13px]">Reference ID: {referenceId}</p>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
