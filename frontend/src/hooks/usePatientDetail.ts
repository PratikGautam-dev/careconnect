import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { portalFetch } from "@/lib/portalAuth";
import { TYPE_LABELS } from "@/hooks/useAppointments";

function visitTypeBucket(v: { appointment_type_id: string | null }) {
  return v.appointment_type_id && v.appointment_type_id in TYPE_LABELS ? v.appointment_type_id : "other";
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
  // CareConnect architecture doc alignment (Spec.md Section 0), Section 18.
  status: "active" | "blocked" | "inactive";
};

export type Visit = {
  id: number;
  phone: string;
  department_name: string;
  doctor_name: string;
  scheduled_at: string;
  status: string;
  source: string;
  reference_id: string | null;
  appointment_type_id: string | null;
  video_link: string | null;
  created_at: string | null;
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
};

export type DetailData = { patient: Patient; visit_history: Visit[]; notes: Note[]; documents: PatientDocument[] };

/** Loads + owns every mutation on the /portal/patients/[id] detail page:
 * demographics save, active/blocked status, per-visit + general notes, and
 * document upload/send-to-WhatsApp. */
export function usePatientDetail(patientId: string, ready: boolean) {
  const router = useRouter();
  const [data, setData] = useState<DetailData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [dob, setDob] = useState("");
  const [gender, setGender] = useState("");
  const [address, setAddress] = useState("");
  const [savingDemographics, setSavingDemographics] = useState(false);

  const [savingStatus, setSavingStatus] = useState(false);

  const [expandedVisit, setExpandedVisit] = useState<number | null>(null);
  const [noteDraft, setNoteDraft] = useState<Record<number, string>>({});
  const [savingNote, setSavingNote] = useState<number | null>(null);

  // Visit history filters -- same shape as the main /portal/appointments
  // table (search + status + type), plus a time filter this scoped-to-one-
  // patient view adds on top since "upcoming vs past" is the natural first
  // question for a single patient's history.
  const [visitSearch, setVisitSearch] = useState("");
  const [visitTimeFilter, setVisitTimeFilter] = useState<"all" | "upcoming" | "past">("all");
  const [visitStatusFilter, setVisitStatusFilter] = useState("all");
  const [visitTypeFilter, setVisitTypeFilter] = useState("all");

  const [generalNoteDraft, setGeneralNoteDraft] = useState("");
  const [savingGeneralNote, setSavingGeneralNote] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [sendingDocId, setSendingDocId] = useState<number | null>(null);
  const [sendError, setSendError] = useState<Record<number, string>>({});

  const load = useCallback(async () => {
    const result = await portalFetch(`/api/portal/patients/${patientId}`);
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    const d = result.data as DetailData;
    setData(d);
    setDob(d.patient.date_of_birth || "");
    setGender(d.patient.gender || "");
    setAddress(d.patient.address || "");
  }, [router, patientId]);

  useEffect(() => {
    if (ready) load();
  }, [ready, load]);

  async function handleSetStatus(status: Patient["status"]) {
    setSavingStatus(true);
    const result = await portalFetch(`/api/portal/patients/${patientId}/status`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    setSavingStatus(false);
    if (result.ok) load();
    else if (!result.unauthorized) setError(result.error);
  }

  async function handleSaveDemographics() {
    setSavingDemographics(true);
    const result = await portalFetch(`/api/portal/patients/${patientId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date_of_birth: dob, gender, address }),
    });
    setSavingDemographics(false);
    if (result.ok) load();
  }

  async function handleAddNote(appointmentId: number | null) {
    const text = (appointmentId ? noteDraft[appointmentId] : generalNoteDraft) || "";
    if (!text.trim()) return;
    if (appointmentId) setSavingNote(appointmentId);
    else setSavingGeneralNote(true);

    const result = await portalFetch(`/api/portal/patients/${patientId}/notes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note_text: text.trim(), appointment_id: appointmentId }),
    });

    if (appointmentId) setSavingNote(null);
    else setSavingGeneralNote(false);

    if (result.ok) {
      if (appointmentId) setNoteDraft((d) => ({ ...d, [appointmentId]: "" }));
      else setGeneralNoteDraft("");
      load();
    }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);
    const result = await portalFetch(`/api/portal/patients/${patientId}/documents`, {
      method: "POST",
      body: formData,
    });
    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
    if (result.ok) load();
    else if (!result.unauthorized) setError(result.error);
  }

  async function handleSendToWhatsapp(documentId: number) {
    setSendingDocId(documentId);
    setSendError((e) => ({ ...e, [documentId]: "" }));
    const result = await portalFetch(`/api/portal/patients/${patientId}/documents/${documentId}/send`, {
      method: "POST",
    });
    setSendingDocId(null);
    if (result.ok) {
      load();
    } else if (!result.unauthorized) {
      setSendError((e) => ({ ...e, [documentId]: result.error }));
    }
  }

  const visitTypeCounts = useMemo(() => {
    const visits = data?.visit_history ?? [];
    const counts: Record<string, number> = { all: visits.length };
    for (const v of visits) {
      const bucket = visitTypeBucket(v);
      counts[bucket] = (counts[bucket] || 0) + 1;
    }
    return counts;
  }, [data]);

  // Snapshotted on load (not Date.now() inline in the memo below, which
  // would call an impure function during render) -- close enough for an
  // upcoming/past split on a page that isn't left open for hours.
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => {
    if (data) setNow(Date.now());
  }, [data]);

  const filteredVisits = useMemo(() => {
    const visits = data?.visit_history ?? [];
    const q = visitSearch.trim().toLowerCase();
    return visits.filter((v) => {
      if (now !== null) {
        if (visitTimeFilter === "upcoming" && new Date(v.scheduled_at).getTime() < now) return false;
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
  }, [data, visitSearch, visitTimeFilter, visitStatusFilter, visitTypeFilter, now]);

  return {
    data, error,
    dob, setDob, gender, setGender, address, setAddress, savingDemographics, handleSaveDemographics,
    savingStatus, handleSetStatus,
    expandedVisit, setExpandedVisit, noteDraft, setNoteDraft, savingNote,
    visitSearch, setVisitSearch, visitTimeFilter, setVisitTimeFilter,
    visitStatusFilter, setVisitStatusFilter, visitTypeFilter, setVisitTypeFilter,
    visitTypeCounts, filteredVisits,
    generalNoteDraft, setGeneralNoteDraft, savingGeneralNote,
    handleAddNote,
    fileInputRef, uploading, handleUpload,
    sendingDocId, sendError, handleSendToWhatsapp,
  };
}
