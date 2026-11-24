import { useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { isPortalMutationError, unwrapPortalResult } from "@/lib/portalMutation";
import { toast } from "@/lib/toast";
import { fetchSlotsByDate, type SlotsByDate, TYPE_LABELS } from "@/hooks/useAppointments";
import type { BillingRow } from "@/hooks/useBillingOverview";

function visitTypeBucket(v: { appointment_type_id: string | null }) {
  return v.appointment_type_id && v.appointment_type_id in TYPE_LABELS
    ? v.appointment_type_id
    : "other";
}

export type Patient = {
  id: number;
  phone: string;
  name: string | null;
  patient_display_id: string | null;
  mrn: string | null;
  date_of_birth: string | null;
  gender: string | null;
  address: string | null;
  created_at: string;
  status: "active" | "blocked" | "inactive";
  billing_notes: string | null;
};

export type Visit = {
  id: number;
  phone: string;
  department_id: string;
  department_name: string;
  doctor_id: string;
  doctor_name: string;
  scheduled_at: string;
  status: string;
  source: string;
  reference_id: string | null;
  appointment_type_id: string | null;
  video_link: string | null;
  created_at: string | null;
  // Only ever set/meaningful for a status === "attended" visit.
  // followup_valid_until is the fully-resolved date a follow-up can still
  // be booked against THIS visit through (normal hospital-wide window,
  // extended by followup_override_until when that's later);
  // followup_override_until is the raw staff-granted date (null if never granted).
  followup_valid_until: string | null;
  followup_override_until: string | null;
};

export type Note = {
  id: number;
  patient_id: number;
  appointment_id: number | null;
  doctor_id: string | null;
  doctor_name: string | null;
  note_text: string;
  created_at: string;
  created_by_session_id: string | null;
};

export type PatientDocument = {
  id: number;
  patient_id: number;
  appointment_id: number | null;
  file_name: string;
  uploaded_at: string;
  uploaded_by_session_id: string | null;
  sent_to_whatsapp_at: string | null;
  document_type: string;
  remarks: string | null;
};

// Patient detail page's Consent management section -- DPDP/Privacy Policy/
// Marketing, each a plain agree-or-disagree state (false reads as
// "disagreed", not "not yet asked"). marketing_consent mirrors the
// existing WhatsApp-togglable patient_links.marketing_consent when this
// patient has an active link, falling back to its own durable value
// otherwise -- see backend's db/repositories/patients.py
// get_patient_consent() for the full reasoning.
export type ConsentType = "dpdp" | "privacy_policy" | "marketing";
export type Consent = {
  dpdp_consent: boolean;
  privacy_policy_consent: boolean;
  marketing_consent: boolean;
};
export const CONSENT_LABELS: Record<ConsentType, string> = {
  dpdp: "DPDP",
  privacy_policy: "Privacy Policy",
  marketing: "Marketing",
};
export const CONSENT_TYPE_ORDER: ConsentType[] = ["dpdp", "privacy_policy", "marketing"];

// Patient detail page's "Billing" tab + sidebar Billing Summary -- the same
// row shape the hospital-wide /portal/billing ledger uses (see
// useBillingOverview.ts), just pre-filtered server-side to this one
// patient's own appointment + pharmacy bills (db/repositories/
// billing_overview.py's get_patient_billing()). null for a doctor-scoped
// caller, who has no billing view of their own on any page.
export type PatientBillingStats = {
  appointment_bills_total: number;
  appointment_bills_count: number;
  pharmacy_bills_total: number;
  pharmacy_bills_count: number;
  total_amount: number;
  total_paid: number;
  pending_dues: number;
};
// Transactions tab -- one row per payment ATTEMPT/collection event, unlike
// PatientBilling.transactions above (one row per invoice, latest attempt
// only). See db/repositories/billing_overview.py's _payment_event_row().
export type PaymentEvent = {
  transaction_id: string;
  appointment_id: number | null;
  reference_id: string;
  bill_no: string;
  method: string | null;
  amount: number;
  status: string;
  notes: string | null;
  date: string;
};
export type PatientBilling = {
  stats: PatientBillingStats;
  transactions: BillingRow[];
  payment_events: PaymentEvent[];
};

// Clinical Notes tab -- structured note, separate from the plain free-text
// Note type above (General Notes / per-visit notes).
export type NoteType = "consultation" | "follow_up" | "tele_consult" | "discharge" | "other";
export const NOTE_TYPE_ORDER: NoteType[] = ["consultation", "follow_up", "tele_consult", "discharge", "other"];
export const NOTE_TYPE_LABELS: Record<NoteType, string> = {
  consultation: "Consultation Note",
  follow_up: "Follow-up Note",
  tele_consult: "Tele-consult Note",
  discharge: "Discharge Note",
  other: "Other",
};
export type ClinicalNote = {
  id: number;
  patient_id: number;
  appointment_id: number | null;
  doctor_id: string | null;
  doctor_name: string | null;
  department_name: string | null;
  note_type: NoteType;
  summary: string | null;
  diagnosis: string | null;
  advice: string | null;
  follow_up_plan: string | null;
  follow_up_date: string | null;
  created_at: string;
};

export type FlagSeverity = "critical" | "warning" | "info";
export type ClinicalFlag = {
  id: number;
  flag_type: string;
  title: string;
  description: string | null;
  severity: FlagSeverity;
  created_at: string;
};

export type DetailData = {
  patient: Patient;
  visit_history: Visit[];
  notes: Note[];
  documents: PatientDocument[];
  consent: Consent;
  billing: PatientBilling | null;
  clinical_notes: ClinicalNote[];
  clinical_flags: ClinicalFlag[];
};

// Visit history table's top-level category selector (Doctor appointment /
// Lab & Diagnostics / Daycare) -- scopes both which visits show AND which
// of TYPE_TAB_ORDER's sub-type tabs are offered, mirroring how /portal/
// appointments' Walk-in/Tele mode filter narrows its own Type dropdown.
export type VisitCategory = "doctor" | "diagnostic_lab" | "daycare";
export const VISIT_CATEGORY_LABELS: Record<VisitCategory, string> = {
  doctor: "Doctor Appointments",
  diagnostic_lab: "Lab & Diagnostics Appointments",
  daycare: "Daycare Appointments",
};
export const VISIT_CATEGORY_ORDER: VisitCategory[] = ["doctor", "diagnostic_lab", "daycare"];
export const CATEGORY_TYPE_TABS: Record<VisitCategory, string[]> = {
  doctor: ["all", "new", "followup", "tele", "second_opinion", "other"],
  diagnostic_lab: ["all", "diagnostic", "lab"],
  daycare: ["all", "daycare"],
};
function visitCategoryOf(v: { appointment_type_id: string | null }): VisitCategory {
  const bucket = visitTypeBucket(v);
  if (bucket === "diagnostic" || bucket === "lab") return "diagnostic_lab";
  if (bucket === "daycare") return "daycare";
  return "doctor";
}

/** Loads + owns every mutation on the /portal/patients/[id] detail page:
 * demographics save, active/blocked status, per-visit + general notes, and
 * document upload/send-to-WhatsApp. Single page, single consumer -- kept as
 * one hook (like useEditTenant/usePatients) rather than separated into
 * per-mutation hooks nothing else would import. */
export function usePatientDetail(patientId: string, ready: boolean) {
  const router = useRouter();

  const {
    data: queryData,
    error: queryError,
    refetch,
  } = useQuery({
    queryKey: ["portal-patient-detail", patientId],
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch(`/api/portal/patients/${patientId}`);
      const detail = unwrapPortalResult<DetailData>(router, result);
      // Snapshotted here (inside the fetch, not Date.now() during render or
      // an effect -- both of which the newer react-hooks lint rules
      // disallow) -- close enough for the upcoming/past split below on a
      // page that isn't left open for hours.
      return { detail, fetchedAt: Date.now() };
    },
  });
  const data = queryData?.detail;
  const now = queryData?.fetchedAt ?? null;
  const error = queryError ? (queryError as Error).message : null;

  // Seeded once per patient id (not every refetch) -- render-time
  // "adjusting state when a prop changes" instead of an effect. A refetch
  // after a successful save already holds these same values, so there's
  // nothing to re-sync there.
  const [seededPatientId, setSeededPatientId] = useState<number | null>(null);
  const [dob, setDob] = useState("");
  const [gender, setGender] = useState("");
  const [address, setAddress] = useState("");
  if (data && data.patient.id !== seededPatientId) {
    setSeededPatientId(data.patient.id);
    setDob(data.patient.date_of_birth || "");
    setGender(data.patient.gender || "");
    setAddress(data.patient.address || "");
  }

  const [expandedVisit, setExpandedVisit] = useState<number | null>(null);
  const [noteDraft, setNoteDraft] = useState<Record<number, string>>({});

  // Visit history filters -- same shape as the main /portal/appointments
  // table (search + status + type), plus a time filter this scoped-to-one-
  // patient view adds on top since "upcoming vs past" is the natural first
  // question for a single patient's history.
  const [visitSearch, setVisitSearch] = useState("");
  const [visitTimeFilter, setVisitTimeFilter] = useState<"all" | "upcoming" | "past">("all");
  const [visitStatusFilter, setVisitStatusFilter] = useState("all");
  const [visitTypeFilter, setVisitTypeFilter] = useState("all");
  const [visitCategory, setVisitCategoryState] = useState<VisitCategory>("doctor");
  // Changing category invalidates any sub-type tab selection from the
  // previous category (e.g. "tele" doesn't exist under Daycare).
  function setVisitCategory(category: VisitCategory) {
    setVisitCategoryState(category);
    setVisitTypeFilter("all");
  }

  const [generalNoteDraft, setGeneralNoteDraft] = useState("");

  const fileInputRef = useRef<HTMLInputElement>(null);
  // WhatsApp menu restructuring: Reports & Prescriptions' "View
  // Prescriptions/Lab Reports/Diagnostic Reports" submenu rows filter on
  // this -- picked once here, applied to whichever file is chosen next.
  const [documentType, setDocumentType] = useState("other");
  const [sendError, setSendError] = useState<Record<number, string>>({});

  // Admin/receptionist-only "Extend" (grant extra days, patient books it
  // themselves on WhatsApp) and "Book now" (staff books it directly,
  // ignoring the window) actions, one shared panel per attended visit row.
  const [followupPanelId, setFollowupPanelId] = useState<number | null>(null);
  const [followupError, setFollowupError] = useState("");
  const [extendDays, setExtendDays] = useState("3");
  const [bookSlotsByDate, setBookSlotsByDate] = useState<SlotsByDate | null>(null);
  const [bookDate, setBookDate] = useState("");
  const [bookSlotId, setBookSlotId] = useState("");

  const setStatusMutation = useMutation({
    mutationFn: async (status: Patient["status"]) => {
      const result = await portalFetch(`/api/portal/patients/${patientId}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      return unwrapPortalResult<unknown>(router, result);
    },
  });
  async function handleSetStatus(status: Patient["status"]) {
    try {
      await setStatusMutation.mutateAsync(status);
      toast.success("Patient status updated");
      refetch();
    } catch (err) {
      if (isPortalMutationError(err)) toast.error("Couldn't update patient status", err.message);
    }
  }

  const setConsentMutation = useMutation({
    mutationFn: async ({ consentType, agreed }: { consentType: ConsentType; agreed: boolean }) => {
      const result = await portalFetch(`/api/portal/patients/${patientId}/consent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ consent_type: consentType, agreed }),
      });
      return unwrapPortalResult<unknown>(router, result);
    },
  });
  const [savingConsent, setSavingConsent] = useState<ConsentType | null>(null);
  async function handleSetConsent(consentType: ConsentType, agreed: boolean) {
    setSavingConsent(consentType);
    try {
      await setConsentMutation.mutateAsync({ consentType, agreed });
      // DPDP and Privacy Policy are linked -- when DPDP changes, also update Privacy Policy
      if (consentType === "dpdp") {
        await setConsentMutation.mutateAsync({ consentType: "privacy_policy", agreed });
      }
      toast.success(`${CONSENT_LABELS[consentType]} consent updated`);
      refetch();
    } catch (err) {
      if (isPortalMutationError(err))
        toast.error(`Couldn't update ${CONSENT_LABELS[consentType]} consent`, err.message);
    } finally {
      setSavingConsent(null);
    }
  }

  const saveDemographicsMutation = useMutation({
    mutationFn: async () => {
      const result = await portalFetch(`/api/portal/patients/${patientId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date_of_birth: dob, gender, address }),
      });
      return unwrapPortalResult<unknown>(router, result);
    },
  });
  async function handleSaveDemographics() {
    try {
      await saveDemographicsMutation.mutateAsync();
      toast.success("Patient details saved");
      refetch();
    } catch (err) {
      if (isPortalMutationError(err)) toast.error("Couldn't save patient details", err.message);
    }
  }

  const addNoteMutation = useMutation({
    mutationFn: async ({ appointmentId, text }: { appointmentId: number | null; text: string }) => {
      const result = await portalFetch(`/api/portal/patients/${patientId}/notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note_text: text, appointment_id: appointmentId }),
      });
      return unwrapPortalResult<unknown>(router, result);
    },
  });
  const [savingNote, setSavingNote] = useState<number | null>(null);
  const [savingGeneralNote, setSavingGeneralNote] = useState(false);
  async function handleAddNote(appointmentId: number | null) {
    const text = (appointmentId ? noteDraft[appointmentId] : generalNoteDraft) || "";
    if (!text.trim()) return;
    if (appointmentId) setSavingNote(appointmentId);
    else setSavingGeneralNote(true);
    try {
      await addNoteMutation.mutateAsync({ appointmentId, text: text.trim() });
      if (appointmentId) setNoteDraft((d) => ({ ...d, [appointmentId]: "" }));
      else setGeneralNoteDraft("");
      toast.success("Note added");
      refetch();
    } catch (err) {
      if (isPortalMutationError(err)) toast.error("Couldn't add note", err.message);
    } finally {
      if (appointmentId) setSavingNote(null);
      else setSavingGeneralNote(false);
    }
  }

  const addClinicalNoteMutation = useMutation({
    mutationFn: async (body: {
      note_type: NoteType; diagnosis?: string; advice?: string; follow_up_plan?: string;
      follow_up_date?: string; department_name?: string; doctor_id?: string;
    }) => {
      const result = await portalFetch(`/api/portal/patients/${patientId}/clinical-notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      return unwrapPortalResult<unknown>(router, result);
    },
  });
  async function handleAddClinicalNote(body: {
    note_type: NoteType; diagnosis?: string; advice?: string; follow_up_plan?: string;
    follow_up_date?: string; department_name?: string; doctor_id?: string;
  }) {
    try {
      await addClinicalNoteMutation.mutateAsync(body);
      toast.success("Clinical note saved");
      refetch();
      return true;
    } catch (err) {
      if (isPortalMutationError(err)) toast.error("Couldn't save clinical note", err.message);
      return false;
    }
  }

  const updateBillingNotesMutation = useMutation({
    mutationFn: async (billingNotes: string) => {
      const result = await portalFetch(`/api/portal/patients/${patientId}/billing-notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ billing_notes: billingNotes }),
      });
      return unwrapPortalResult<unknown>(router, result);
    },
  });
  async function handleSaveBillingNotes(billingNotes: string) {
    try {
      await updateBillingNotesMutation.mutateAsync(billingNotes);
      toast.success("Payment notes saved");
      refetch();
    } catch (err) {
      if (isPortalMutationError(err)) toast.error("Couldn't save payment notes", err.message);
    }
  }

  const updateDocumentRemarksMutation = useMutation({
    mutationFn: async ({ documentId, remarks }: { documentId: number; remarks: string }) => {
      const result = await portalFetch(`/api/portal/patients/${patientId}/documents/${documentId}/remarks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ remarks }),
      });
      return unwrapPortalResult<unknown>(router, result);
    },
  });
  async function handleSaveDocumentRemarks(documentId: number, remarks: string) {
    try {
      await updateDocumentRemarksMutation.mutateAsync({ documentId, remarks });
      toast.success("Remarks saved");
      refetch();
    } catch (err) {
      if (isPortalMutationError(err)) toast.error("Couldn't save remarks", err.message);
    }
  }

  const uploadMutation = useMutation({
    mutationFn: async (formData: FormData) => {
      const result = await portalFetch(`/api/portal/patients/${patientId}/documents`, {
        method: "POST",
        body: formData,
      });
      return unwrapPortalResult<unknown>(router, result);
    },
  });
  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    formData.append("document_type", documentType);
    try {
      await uploadMutation.mutateAsync(formData);
      toast.success("Document uploaded");
      refetch();
    } catch (err) {
      if (isPortalMutationError(err)) toast.error("Couldn't upload document", err.message);
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  const sendToWhatsappMutation = useMutation({
    mutationFn: async (documentId: number) => {
      const result = await portalFetch(
        `/api/portal/patients/${patientId}/documents/${documentId}/send`,
        {
          method: "POST",
        },
      );
      return unwrapPortalResult<unknown>(router, result);
    },
  });
  const [sendingDocId, setSendingDocId] = useState<number | null>(null);
  async function handleSendToWhatsapp(documentId: number) {
    setSendingDocId(documentId);
    setSendError((e) => ({ ...e, [documentId]: "" }));
    try {
      await sendToWhatsappMutation.mutateAsync(documentId);
      toast.success("Sent to WhatsApp");
      refetch();
    } catch (err) {
      if (isPortalMutationError(err)) {
        setSendError((e) => ({ ...e, [documentId]: err.message }));
        toast.error("Couldn't send to WhatsApp", err.message);
      }
    } finally {
      setSendingDocId(null);
    }
  }

  async function openFollowupPanel(visit: Visit) {
    setFollowupError("");
    setExtendDays("3");
    setBookDate("");
    setBookSlotId("");
    setFollowupPanelId(visit.id);
    // Fixed to THIS visit's own doctor (follow-up rebooks with the same
    // doctor, never a picker) -- fetched fresh per visit since a different
    // visit can have a different doctor, not eager-loaded for every doctor
    // in the hospital the way /new-booking/context used to.
    setBookSlotsByDate(null);
    const slots = await fetchSlotsByDate(router, { doctorId: visit.doctor_id });
    setBookSlotsByDate(slots ?? {});
  }

  function closeFollowupPanel() {
    setFollowupPanelId(null);
    setFollowupError("");
  }

  const extendFollowupMutation = useMutation({
    mutationFn: async ({ visitId, extraDays }: { visitId: number; extraDays: number }) => {
      const result = await portalFetch(`/api/portal/bookings/${visitId}/followup/extend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ extra_days: extraDays }),
      });
      return unwrapPortalResult<unknown>(router, result);
    },
  });
  const [extendingId, setExtendingId] = useState<number | null>(null);
  async function handleExtendFollowup(visitId: number) {
    const extraDays = parseInt(extendDays, 10);
    if (!Number.isFinite(extraDays) || extraDays <= 0) {
      setFollowupError("Enter a positive number of days.");
      return;
    }
    setExtendingId(visitId);
    setFollowupError("");
    try {
      await extendFollowupMutation.mutateAsync({ visitId, extraDays });
      toast.success("Follow-up window extended");
      closeFollowupPanel();
      refetch();
    } catch (err) {
      if (isPortalMutationError(err)) {
        setFollowupError(err.message);
        toast.error("Couldn't extend follow-up", err.message);
      }
    } finally {
      setExtendingId(null);
    }
  }

  const bookFollowupMutation = useMutation({
    mutationFn: async ({ visitId, slotId }: { visitId: number; slotId: string }) => {
      const result = await portalFetch(`/api/portal/bookings/${visitId}/followup/book`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scheduled_at: slotId }),
      });
      return unwrapPortalResult<unknown>(router, result);
    },
  });
  const [bookingId, setBookingId] = useState<number | null>(null);
  async function handleBookFollowupNow(visitId: number) {
    if (!bookSlotId) {
      setFollowupError("Choose an available slot.");
      return;
    }
    setBookingId(visitId);
    setFollowupError("");
    try {
      await bookFollowupMutation.mutateAsync({ visitId, slotId: bookSlotId });
      toast.success("Follow-up booked");
      closeFollowupPanel();
      refetch();
    } catch (err) {
      if (isPortalMutationError(err)) {
        setFollowupError(err.message);
        toast.error("Couldn't book follow-up", err.message);
      }
    } finally {
      setBookingId(null);
    }
  }

  const visitTypeCounts = useMemo(() => {
    const visits = (data?.visit_history ?? []).filter((v) => visitCategoryOf(v) === visitCategory);
    const counts: Record<string, number> = { all: visits.length };
    for (const v of visits) {
      const bucket = visitTypeBucket(v);
      counts[bucket] = (counts[bucket] || 0) + 1;
    }
    return counts;
  }, [data, visitCategory]);

  const filteredVisits = useMemo(() => {
    const visits = (data?.visit_history ?? []).filter((v) => visitCategoryOf(v) === visitCategory);
    const q = visitSearch.trim().toLowerCase();
    return visits.filter((v) => {
      if (now !== null) {
        if (visitTimeFilter === "upcoming" && new Date(v.scheduled_at).getTime() < now)
          return false;
        if (visitTimeFilter === "past" && new Date(v.scheduled_at).getTime() >= now) return false;
      }
      if (visitTypeFilter !== "all" && visitTypeBucket(v) !== visitTypeFilter) return false;
      if (visitStatusFilter !== "all" && v.status !== visitStatusFilter) return false;
      if (!q) return true;
      return (
        v.doctor_name.toLowerCase().includes(q) ||
        v.department_name.toLowerCase().includes(q) ||
        (v.reference_id || "").toLowerCase().includes(q)
      );
    });
  }, [data, visitCategory, visitSearch, visitTimeFilter, visitStatusFilter, visitTypeFilter, now]);

  return {
    data: data ?? null,
    error,
    // Exposed for the Billing tab -- a collect-payment action there goes
    // through each domain's own existing mutation (not this hook's), so it
    // has no other way to make this query's "billing" slice re-fetch.
    refetchDetail: refetch,
    dob,
    setDob,
    gender,
    setGender,
    address,
    setAddress,
    savingDemographics: saveDemographicsMutation.isPending,
    handleSaveDemographics,
    savingStatus: setStatusMutation.isPending,
    handleSetStatus,
    savingConsent,
    handleSetConsent,
    expandedVisit,
    setExpandedVisit,
    noteDraft,
    setNoteDraft,
    savingNote,
    visitSearch,
    setVisitSearch,
    visitTimeFilter,
    setVisitTimeFilter,
    visitStatusFilter,
    setVisitStatusFilter,
    visitTypeFilter,
    setVisitTypeFilter,
    visitCategory,
    setVisitCategory,
    visitTypeCounts,
    filteredVisits,
    generalNoteDraft,
    setGeneralNoteDraft,
    savingGeneralNote,
    handleAddNote,
    handleAddClinicalNote,
    savingClinicalNote: addClinicalNoteMutation.isPending,
    handleSaveBillingNotes,
    savingBillingNotes: updateBillingNotesMutation.isPending,
    handleSaveDocumentRemarks,
    savingDocumentRemarks: updateDocumentRemarksMutation.isPending,
    fileInputRef,
    uploading: uploadMutation.isPending,
    handleUpload,
    documentType,
    setDocumentType,
    sendingDocId,
    sendError,
    handleSendToWhatsapp,
    followupPanelId,
    openFollowupPanel,
    closeFollowupPanel,
    followupError,
    extendDays,
    setExtendDays,
    extendingId,
    handleExtendFollowup,
    bookSlotsByDate,
    bookDate,
    setBookDate,
    bookSlotId,
    setBookSlotId,
    bookingId,
    handleBookFollowupNow,
  };
}
