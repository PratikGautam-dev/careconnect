import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";

export type Test = {
  id: number;
  category: "diagnostic" | "lab";
  name: string;
  price: number | null;
  is_active: boolean;
};
export type TestFull = Test & {
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

function formFromTest(t: TestFull): ScheduleFormState {
  const [shift_start = "", shift_end = ""] = (t.working_hours[0] || "").split("-");
  const [break_start = "", break_end = ""] = (t.breaks[0] || "").split("-");
  return {
    name: t.name,
    price: t.price != null ? String(t.price) : "",
    working_days: t.working_days,
    shift_start,
    shift_end,
    break_start,
    break_end,
    slot_duration_minutes: String(t.slot_duration_minutes),
    max_bookings_per_slot: String(t.max_bookings_per_slot),
    daily_booking_limit: t.daily_booking_limit != null ? String(t.daily_booking_limit) : "",
    effective_from: t.effective_from || "",
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

/** Diagnostic tests/resources merge: a test now carries its own schedule
 * directly (no separate resource to link). Test/variant merge: a test also
 * carries its own price directly now -- it only ever needed exactly one
 * priced option, so there's no separate variants sub-resource to manage
 * anymore. Loads + owns every mutation on the test catalog: category
 * switch, test add/edit/delete/active-toggle (each including its own
 * price/working days/hours/breaks/capacity/leave). Single page, single
 * consumer -- kept as one hook rather than separated into per-mutation
 * hooks nothing else would import. */
export function useDiagnosticTests() {
  const [category, setCategory] = useState<"diagnostic" | "lab">("diagnostic");
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const [showAddTest, setShowAddTest] = useState(false);
  const [newTestForm, setNewTestForm] = useState<ScheduleFormState>(emptyForm());

  const [editingTestId, setEditingTestId] = useState<number | null>(null);
  const [editTestForm, setEditTestForm] = useState<ScheduleFormState>(emptyForm());

  const [pendingKey, setPendingKey] = useState<string | null>(null);

  const { data: tests, refetch } = useQuery({
    queryKey: ["portal-diagnostic-tests", category],
    retry: false,
    queryFn: async () => {
      const result = await portalFetch(`/api/portal/diagnostic-tests?category=${category}`);
      if (!result.ok) return null;
      return (result.data as { tests: Test[] }).tests;
    },
  });

  function toggleNewTestDay(day: string) {
    setNewTestForm((f) => ({
      ...f,
      working_days: f.working_days.includes(day)
        ? f.working_days.filter((d) => d !== day)
        : [...f.working_days, day],
    }));
  }

  function toggleEditTestDay(day: string) {
    setEditTestForm((f) => ({
      ...f,
      working_days: f.working_days.includes(day)
        ? f.working_days.filter((d) => d !== day)
        : [...f.working_days, day],
    }));
  }

  const addTestMutation = useMutation({
    mutationFn: async (payload: ReturnType<typeof scheduleFromForm> & { category: string }) => {
      const result = await portalFetch("/api/portal/diagnostic-tests", {
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

  async function handleAddTest() {
    if (!newTestForm.name.trim()) return;
    // The backend accepts an empty schedule silently (a test just never
    // generates any bookable slots) -- caught here instead, since a test
    // with no working day/shift is almost always a data-entry mistake, not
    // a deliberate "not bookable yet" choice.
    if (newTestForm.working_days.length === 0) {
      setError("Choose at least one working day.");
      return;
    }
    if (!newTestForm.shift_start || !newTestForm.shift_end) {
      setError("Set both a shift start and end time.");
      return;
    }
    setError(null);
    try {
      await addTestMutation.mutateAsync({ category, ...scheduleFromForm(newTestForm) });
      toast.success("Test added");
      setNewTestForm(emptyForm());
      setShowAddTest(false);
      refetch();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setError(message);
      toast.error("Couldn't add test", message);
    }
  }

  async function startEditTest(test: Test) {
    const result = await portalFetch(`/api/portal/diagnostic-tests/${test.id}`);
    if (!result.ok) return;
    setEditingTestId(test.id);
    setEditTestForm(formFromTest((result.data as { test: TestFull }).test));
  }

  const saveEditTestMutation = useMutation({
    mutationFn: async ({
      testId,
      payload,
    }: {
      testId: number;
      payload: ReturnType<typeof scheduleFromForm>;
    }) => {
      const result = await portalFetch(`/api/portal/diagnostic-tests/${testId}`, {
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

  async function saveEditTest(testId: number) {
    if (!editTestForm.name.trim()) return;
    if (editTestForm.working_days.length === 0) {
      setError("Choose at least one working day.");
      return;
    }
    if (!editTestForm.shift_start || !editTestForm.shift_end) {
      setError("Set both a shift start and end time.");
      return;
    }
    setPendingKey(`test-${testId}`);
    try {
      await saveEditTestMutation.mutateAsync({ testId, payload: scheduleFromForm(editTestForm) });
      toast.success("Test updated");
      setEditingTestId(null);
      refetch();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setError(message);
      toast.error("Couldn't save test", message);
    } finally {
      setPendingKey(null);
    }
  }

  const toggleActiveMutation = useMutation({
    mutationFn: async ({ testId, isActive }: { testId: number; isActive: boolean }) => {
      const result = await portalFetch(`/api/portal/diagnostic-tests/${testId}/active`, {
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

  async function toggleTestActive(test: Test) {
    setPendingKey(`test-${test.id}`);
    try {
      await toggleActiveMutation.mutateAsync({ testId: test.id, isActive: !test.is_active });
      toast.success(test.is_active ? "Test deactivated" : "Test activated");
      refetch();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      toast.error("Couldn't update test", message);
    } finally {
      setPendingKey(null);
    }
  }

  const deleteTestMutation = useMutation({
    mutationFn: async (testId: number) => {
      const result = await portalFetch(`/api/portal/diagnostic-tests/${testId}`, {
        method: "DELETE",
      });
      if (!result.ok) {
        throw new Error(
          result.unauthorized ? "Session expired — please log in again." : result.error,
        );
      }
    },
  });

  async function deleteTest(test: Test) {
    if (
      !window.confirm(`Delete "${test.name}"? Past bookings keep their stored details either way.`)
    )
      return;
    setPendingKey(`test-${test.id}`);
    try {
      await deleteTestMutation.mutateAsync(test.id);
      toast.success("Test deleted");
      refetch();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setError(message);
      toast.error("Couldn't delete test", message);
    } finally {
      setPendingKey(null);
    }
  }

  return {
    category,
    setCategory,
    tests: tests ?? null,
    error,
    expandedId,
    setExpandedId,
    showAddTest,
    setShowAddTest,
    newTestForm,
    setNewTestForm,
    toggleNewTestDay,
    savingTest: addTestMutation.isPending,
    editingTestId,
    setEditingTestId,
    editTestForm,
    setEditTestForm,
    toggleEditTestDay,
    pendingKey,
    handleAddTest,
    startEditTest,
    saveEditTest,
    toggleTestActive,
    deleteTest,
  };
}
