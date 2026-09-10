import { useCallback, useEffect, useState } from "react";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";

export type Test = {
  id: number; category: "diagnostic" | "lab"; name: string; price: number | null; is_active: boolean;
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
    name: "", price: "", working_days: [], shift_start: "", shift_end: "",
    break_start: "", break_end: "", slot_duration_minutes: "30", max_bookings_per_slot: "1",
    daily_booking_limit: "", effective_from: "",
  };
}

function formFromTest(t: TestFull): ScheduleFormState {
  const [shift_start = "", shift_end = ""] = (t.working_hours[0] || "").split("-");
  const [break_start = "", break_end = ""] = (t.breaks[0] || "").split("-");
  return {
    name: t.name, price: t.price != null ? String(t.price) : "", working_days: t.working_days,
    shift_start, shift_end, break_start, break_end,
    slot_duration_minutes: String(t.slot_duration_minutes), max_bookings_per_slot: String(t.max_bookings_per_slot),
    daily_booking_limit: t.daily_booking_limit != null ? String(t.daily_booking_limit) : "",
    effective_from: t.effective_from || "",
  };
}

function scheduleFromForm(form: ScheduleFormState) {
  return {
    name: form.name.trim(),
    price: form.price ? Number(form.price) : null,
    working_days: form.working_days,
    working_hours: form.shift_start && form.shift_end ? [`${form.shift_start}-${form.shift_end}`] : [],
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
 * price/working days/hours/breaks/capacity/leave). */
export function useDiagnosticTests() {
  const [category, setCategory] = useState<"diagnostic" | "lab">("diagnostic");
  const [tests, setTests] = useState<Test[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const [showAddTest, setShowAddTest] = useState(false);
  const [newTestForm, setNewTestForm] = useState<ScheduleFormState>(emptyForm());
  const [savingTest, setSavingTest] = useState(false);

  const [editingTestId, setEditingTestId] = useState<number | null>(null);
  const [editTestForm, setEditTestForm] = useState<ScheduleFormState>(emptyForm());

  const [pendingKey, setPendingKey] = useState<string | null>(null);

  const load = useCallback(async () => {
    const result = await portalFetch(`/api/portal/diagnostic-tests?category=${category}`);
    if (result.ok) setTests((result.data as { tests: Test[] }).tests);
    else setTests(null);
  }, [category]);

  useEffect(() => {
    load();
  }, [load]);

  function toggleNewTestDay(day: string) {
    setNewTestForm((f) => ({
      ...f,
      working_days: f.working_days.includes(day) ? f.working_days.filter((d) => d !== day) : [...f.working_days, day],
    }));
  }

  function toggleEditTestDay(day: string) {
    setEditTestForm((f) => ({
      ...f,
      working_days: f.working_days.includes(day) ? f.working_days.filter((d) => d !== day) : [...f.working_days, day],
    }));
  }

  async function handleAddTest() {
    if (!newTestForm.name.trim()) return;
    setSavingTest(true);
    setError(null);
    const result = await portalFetch("/api/portal/diagnostic-tests", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category, ...scheduleFromForm(newTestForm) }),
    });
    setSavingTest(false);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      if (!result.unauthorized) toast.error("Couldn't add test", result.error);
      return;
    }
    toast.success("Test added");
    setNewTestForm(emptyForm()); setShowAddTest(false);
    load();
  }

  async function startEditTest(test: Test) {
    const result = await portalFetch(`/api/portal/diagnostic-tests/${test.id}`);
    if (!result.ok) return;
    setEditingTestId(test.id);
    setEditTestForm(formFromTest((result.data as { test: TestFull }).test));
  }

  async function saveEditTest(testId: number) {
    if (!editTestForm.name.trim()) return;
    setPendingKey(`test-${testId}`);
    const result = await portalFetch(`/api/portal/diagnostic-tests/${testId}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(scheduleFromForm(editTestForm)),
    });
    setPendingKey(null);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      if (!result.unauthorized) toast.error("Couldn't save test", result.error);
      return;
    }
    toast.success("Test updated");
    setEditingTestId(null);
    load();
  }

  async function toggleTestActive(test: Test) {
    setPendingKey(`test-${test.id}`);
    const result = await portalFetch(`/api/portal/diagnostic-tests/${test.id}/active`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ is_active: !test.is_active }),
    });
    setPendingKey(null);
    if (result.ok) {
      toast.success(test.is_active ? "Test deactivated" : "Test activated");
      load();
    } else if (!result.unauthorized) {
      toast.error("Couldn't update test", result.error);
    }
  }

  async function deleteTest(test: Test) {
    if (!window.confirm(`Delete "${test.name}"? Past bookings keep their stored details either way.`)) return;
    setPendingKey(`test-${test.id}`);
    const result = await portalFetch(`/api/portal/diagnostic-tests/${test.id}`, { method: "DELETE" });
    setPendingKey(null);
    if (result.ok) {
      toast.success("Test deleted");
      load();
    } else {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      if (!result.unauthorized) toast.error("Couldn't delete test", result.error);
    }
  }

  return {
    category, setCategory, tests, error, expandedId, setExpandedId,
    showAddTest, setShowAddTest, newTestForm, setNewTestForm, toggleNewTestDay, savingTest,
    editingTestId, setEditingTestId, editTestForm, setEditTestForm, toggleEditTestDay,
    pendingKey,
    handleAddTest, startEditTest, saveEditTest, toggleTestActive, deleteTest,
  };
}
