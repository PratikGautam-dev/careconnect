import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";

export type Procedure = {
  id: number;
  name: string;
  price: number | null;
  is_active: boolean;
};
export type ProcedureFull = Procedure & {
  working_days: string[];
  working_hours: string[];
  breaks: string[];
  slot_duration_minutes: number;
  max_bookings_per_slot: number;
  daily_booking_limit: number | null;
  effective_from: string | null;
};

export type ScheduleFormState = {
  name: string;
  price: string;
  working_days: string[];
  shift_start: string;
  shift_end: string;
  break_start: string;
  break_end: string;
  slot_duration_minutes: string;
  max_bookings_per_slot: string;
  daily_booking_limit: string;
  effective_from: string;
};

function emptyForm(): ScheduleFormState {
  return {
    name: "",
    price: "",
    working_days: [],
    shift_start: "",
    shift_end: "",
    break_start: "",
    break_end: "",
    slot_duration_minutes: "30",
    max_bookings_per_slot: "1",
    daily_booking_limit: "",
    effective_from: "",
  };
}

function formFromProcedure(p: ProcedureFull): ScheduleFormState {
  const [shift_start = "", shift_end = ""] = (p.working_hours[0] || "").split("-");
  const [break_start = "", break_end = ""] = (p.breaks[0] || "").split("-");
  return {
    name: p.name,
    price: p.price != null ? String(p.price) : "",
    working_days: p.working_days,
    shift_start,
    shift_end,
    break_start,
    break_end,
    slot_duration_minutes: String(p.slot_duration_minutes),
    max_bookings_per_slot: String(p.max_bookings_per_slot),
    daily_booking_limit: p.daily_booking_limit != null ? String(p.daily_booking_limit) : "",
    effective_from: p.effective_from || "",
  };
}

function scheduleFromForm(form: ScheduleFormState) {
  return {
    name: form.name.trim(),
    price: form.price ? Number(form.price) : null,
    working_days: form.working_days,
    working_hours:
      form.shift_start && form.shift_end ? [`${form.shift_start}-${form.shift_end}`] : [],
    breaks: form.break_start && form.break_end ? [`${form.break_start}-${form.break_end}`] : [],
    slot_duration_minutes: Number(form.slot_duration_minutes) || 30,
    max_bookings_per_slot: Number(form.max_bookings_per_slot) || 1,
    daily_booking_limit: form.daily_booking_limit ? Number(form.daily_booking_limit) : null,
    effective_from: form.effective_from || null,
  };
}

/** Procedures/daycare rebuild: a procedure is now a single self-scheduled
 * bookable resource, identical in shape to a diagnostic test -- it carries
 * its own schedule (working days/hours/breaks/capacity/leave) and its own
 * single price directly, rather than the old category/booking-mode/
 * duration/department/multi-resource-pool model. Deliberate 1:1 mirror of
 * useDiagnosticTests.ts, pointed at /api/portal/procedures instead of
 * /api/portal/diagnostic-tests, minus the diagnostic/lab category split --
 * procedures are a single flat list. Loads + owns every mutation on the
 * procedure catalog: add/edit/delete/active-toggle. Single page, single
 * consumer -- kept as one hook rather than separated into per-mutation
 * hooks nothing else would import. */
export function useProcedures() {
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const [showAddProcedure, setShowAddProcedure] = useState(false);
  const [newProcedureForm, setNewProcedureForm] = useState<ScheduleFormState>(emptyForm());

  const [editingProcedureId, setEditingProcedureId] = useState<number | null>(null);
  const [editProcedureForm, setEditProcedureForm] = useState<ScheduleFormState>(emptyForm());

  const [pendingKey, setPendingKey] = useState<string | null>(null);

  const { data: procedures, refetch } = useQuery({
    queryKey: ["portal-procedures"],
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/procedures");
      if (!result.ok) return null;
      return (result.data as { procedures: Procedure[] }).procedures;
    },
  });

  function toggleNewProcedureDay(day: string) {
    setNewProcedureForm((f) => ({
      ...f,
      working_days: f.working_days.includes(day)
        ? f.working_days.filter((d) => d !== day)
        : [...f.working_days, day],
    }));
  }

  function toggleEditProcedureDay(day: string) {
    setEditProcedureForm((f) => ({
      ...f,
      working_days: f.working_days.includes(day)
        ? f.working_days.filter((d) => d !== day)
        : [...f.working_days, day],
    }));
  }

  const addProcedureMutation = useMutation({
    mutationFn: async (payload: ReturnType<typeof scheduleFromForm>) => {
      const result = await portalFetch("/api/portal/procedures", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!result.ok) {
        throw new Error(
          result.unauthorized ? "Session expired — please log in again." : result.error,
        );
      }
    },
  });

  async function handleAddProcedure() {
    if (!newProcedureForm.name.trim()) return;
    // The backend accepts an empty schedule silently (a procedure just never
    // generates any bookable slots) -- caught here instead, since a
    // procedure with no working day/shift is almost always a data-entry
    // mistake, not a deliberate "not bookable yet" choice.
    if (newProcedureForm.working_days.length === 0) {
      setError("Choose at least one working day.");
      return;
    }
    if (!newProcedureForm.shift_start || !newProcedureForm.shift_end) {
      setError("Set both a shift start and end time.");
      return;
    }
    setError(null);
    try {
      await addProcedureMutation.mutateAsync(scheduleFromForm(newProcedureForm));
      toast.success("Procedure added");
      setNewProcedureForm(emptyForm());
      setShowAddProcedure(false);
      refetch();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setError(message);
      toast.error("Couldn't add procedure", message);
    }
  }

  async function startEditProcedure(procedure: Procedure) {
    const result = await portalFetch(`/api/portal/procedures/${procedure.id}`);
    if (!result.ok) return;
    setEditingProcedureId(procedure.id);
    setEditProcedureForm(
      formFromProcedure((result.data as { procedure: ProcedureFull }).procedure),
    );
  }

  const saveEditProcedureMutation = useMutation({
    mutationFn: async ({
      procedureId,
      payload,
    }: {
      procedureId: number;
      payload: ReturnType<typeof scheduleFromForm>;
    }) => {
      const result = await portalFetch(`/api/portal/procedures/${procedureId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!result.ok) {
        throw new Error(
          result.unauthorized ? "Session expired — please log in again." : result.error,
        );
      }
    },
  });

  async function saveEditProcedure(procedureId: number) {
    if (!editProcedureForm.name.trim()) return;
    if (editProcedureForm.working_days.length === 0) {
      setError("Choose at least one working day.");
      return;
    }
    if (!editProcedureForm.shift_start || !editProcedureForm.shift_end) {
      setError("Set both a shift start and end time.");
      return;
    }
    setPendingKey(`procedure-${procedureId}`);
    try {
      await saveEditProcedureMutation.mutateAsync({
        procedureId,
        payload: scheduleFromForm(editProcedureForm),
      });
      toast.success("Procedure updated");
      setEditingProcedureId(null);
      refetch();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setError(message);
      toast.error("Couldn't save procedure", message);
    } finally {
      setPendingKey(null);
    }
  }

  const toggleActiveMutation = useMutation({
    mutationFn: async ({ procedureId, isActive }: { procedureId: number; isActive: boolean }) => {
      const result = await portalFetch(`/api/portal/procedures/${procedureId}/active`, {
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

  async function toggleProcedureActive(procedure: Procedure) {
    setPendingKey(`procedure-${procedure.id}`);
    try {
      await toggleActiveMutation.mutateAsync({
        procedureId: procedure.id,
        isActive: !procedure.is_active,
      });
      toast.success(procedure.is_active ? "Procedure deactivated" : "Procedure activated");
      refetch();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      toast.error("Couldn't update procedure", message);
    } finally {
      setPendingKey(null);
    }
  }

  const deleteProcedureMutation = useMutation({
    mutationFn: async (procedureId: number) => {
      const result = await portalFetch(`/api/portal/procedures/${procedureId}`, {
        method: "DELETE",
      });
      if (!result.ok) {
        throw new Error(
          result.unauthorized ? "Session expired — please log in again." : result.error,
        );
      }
    },
  });

  async function deleteProcedure(procedure: Procedure) {
    if (
      !window.confirm(
        `Delete "${procedure.name}"? Past bookings keep their stored details either way.`,
      )
    )
      return;
    setPendingKey(`procedure-${procedure.id}`);
    try {
      await deleteProcedureMutation.mutateAsync(procedure.id);
      toast.success("Procedure deleted");
      refetch();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setError(message);
      toast.error("Couldn't delete procedure", message);
    } finally {
      setPendingKey(null);
    }
  }

  return {
    procedures: procedures ?? null,
    error,
    expandedId,
    setExpandedId,
    showAddProcedure,
    setShowAddProcedure,
    newProcedureForm,
    setNewProcedureForm,
    toggleNewProcedureDay,
    savingProcedure: addProcedureMutation.isPending,
    editingProcedureId,
    setEditingProcedureId,
    editProcedureForm,
    setEditProcedureForm,
    toggleEditProcedureDay,
    pendingKey,
    handleAddProcedure,
    startEditProcedure,
    saveEditProcedure,
    toggleProcedureActive,
    deleteProcedure,
  };
}
