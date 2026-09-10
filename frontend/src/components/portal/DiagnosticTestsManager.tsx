"use client";

import { ChevronDown, ChevronUp, Pencil, Plus, Trash2, X } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { Switch } from "@/components/ui/Switch";
import { cn } from "@/lib/cn";
import { useDiagnosticTests, type ScheduleFormState } from "@/hooks/useDiagnosticTests";
import { TestLeaveManager } from "@/components/portal/TestLeaveManager";
import { TestSlotManager } from "@/components/portal/TestSlotManager";

const CATEGORIES: { id: "diagnostic" | "lab"; label: string }[] = [
  { id: "diagnostic", label: "Diagnostic Test" },
  { id: "lab", label: "Lab Test" },
];

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function ScheduleFields({
  form, setForm, toggleDay, namePrefix,
}: {
  form: ScheduleFormState;
  setForm: (updater: (f: ScheduleFormState) => ScheduleFormState) => void;
  toggleDay: (day: string) => void;
  namePrefix: string;
}) {
  return (
    <>
      <div className="grid grid-cols-1 gap-x-space-4 md:grid-cols-2">
        <Field label="Name" htmlFor={`${namePrefix}_name`} required>
          <Input id={`${namePrefix}_name`} placeholder="e.g. MRI" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
        </Field>
        <Field label="Price" htmlFor={`${namePrefix}_price`} hint="optional">
          <Input id={`${namePrefix}_price`} type="number" min={0} placeholder="₹" value={form.price} onChange={(e) => setForm((f) => ({ ...f, price: e.target.value }))} />
        </Field>
      </div>

      <Field label="Working days">
        <div className="flex flex-wrap items-center gap-space-2">
          {WEEKDAYS.map((day) => {
            const on = form.working_days.includes(day);
            return (
              <button
                key={day} type="button" onClick={() => toggleDay(day)}
                className={cn(
                  "flex h-9 w-14 items-center justify-center rounded-md border text-[12.5px] font-semibold transition-colors duration-150",
                  on ? "border-brand-600 bg-brand-600 text-white" : "border-line bg-card text-ink-600 hover:border-brand-300",
                )}
              >
                {day}
              </button>
            );
          })}
        </div>
      </Field>

      <div className="mb-space-3 flex flex-wrap items-center gap-space-2 rounded-lg border border-line bg-card p-space-3">
        <span className="w-14 shrink-0 text-[12.5px] font-semibold text-ink-600">Hours</span>
        <Input type="time" value={form.shift_start} onChange={(e) => setForm((f) => ({ ...f, shift_start: e.target.value }))} className="w-32" />
        <span className="text-[12.5px] text-ink-400">to</span>
        <Input type="time" value={form.shift_end} onChange={(e) => setForm((f) => ({ ...f, shift_end: e.target.value }))} className="w-32" />
        <span className="ml-space-3 w-12 shrink-0 text-[12.5px] font-semibold text-ink-600">Break</span>
        <Input type="time" value={form.break_start} onChange={(e) => setForm((f) => ({ ...f, break_start: e.target.value }))} className="w-32" />
        <span className="text-[12.5px] text-ink-400">to</span>
        <Input type="time" value={form.break_end} onChange={(e) => setForm((f) => ({ ...f, break_end: e.target.value }))} className="w-32" />
      </div>

      <div className="grid grid-cols-1 gap-x-space-4 md:grid-cols-3">
        <Field label="Slot duration" htmlFor={`${namePrefix}_slot_duration`} hint="minutes">
          <Input id={`${namePrefix}_slot_duration`} type="number" min={1} value={form.slot_duration_minutes} onChange={(e) => setForm((f) => ({ ...f, slot_duration_minutes: e.target.value }))} />
        </Field>
        <Field label="Max bookings" htmlFor={`${namePrefix}_max_bookings`} hint="per slot">
          <Input id={`${namePrefix}_max_bookings`} type="number" min={1} value={form.max_bookings_per_slot} onChange={(e) => setForm((f) => ({ ...f, max_bookings_per_slot: e.target.value }))} />
        </Field>
        <Field label="Daily limit" htmlFor={`${namePrefix}_daily_limit`} hint="optional">
          <Input id={`${namePrefix}_daily_limit`} type="number" min={0} value={form.daily_booking_limit} onChange={(e) => setForm((f) => ({ ...f, daily_booking_limit: e.target.value }))} />
        </Field>
      </div>
      <Field label="Effective from" htmlFor={`${namePrefix}_effective_from`} hint="optional — blank means immediately" className="max-w-[220px]">
        <Input id={`${namePrefix}_effective_from`} type="date" value={form.effective_from} onChange={(e) => setForm((f) => ({ ...f, effective_from: e.target.value }))} />
      </Field>
    </>
  );
}

// Diagnostic tests/resources merge (docs/per-appointment-type-flow-plan.md
// Step 5): a test now carries its own schedule directly (working days/
// hours/breaks/capacity/leave) instead of linking to a separate resource --
// hospitals always created exactly one resource per test anyway. Test/
// variant merge: a test also carries its own price directly now -- it only
// ever needed exactly one priced option, so there's no separate
// options/variants list to manage either. Same open, hospital-editable
// catalog shape as DaycareDurationOptions.
export function DiagnosticTestsManager({ canManage }: { canManage: boolean }) {
  const {
    category, setCategory, tests, error, expandedId, setExpandedId,
    showAddTest, setShowAddTest, newTestForm, setNewTestForm, toggleNewTestDay, savingTest,
    editingTestId, setEditingTestId, editTestForm, setEditTestForm, toggleEditTestDay,
    pendingKey,
    handleAddTest, startEditTest, saveEditTest, toggleTestActive, deleteTest,
  } = useDiagnosticTests();

  return (
    <Card className="p-space-4">
      <div className="mb-space-3 flex flex-wrap items-center justify-between gap-space-2">
        <h3 className="text-label font-bold text-ink-900">Tests</h3>
        <div className="flex gap-space-1 rounded-md bg-paper p-space-1">
          {CATEGORIES.map((c) => (
            <button
              key={c.id} type="button" onClick={() => setCategory(c.id)}
              className={cn(
                "rounded-md px-space-3 py-space-1 text-[12.5px] font-semibold transition-colors duration-150",
                category === c.id ? "bg-white text-brand-700 shadow-sm" : "text-ink-500 hover:text-ink-800",
              )}
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>
      <p className="mb-space-3 text-[12px] text-ink-400">
        Each test has its own price and weekly schedule -- the schedule below determines the date/time list patients see.
      </p>
      {error && <p className="mb-space-3 text-[12.5px] text-error">{error}</p>}

      {tests === null ? (
        <p className="text-[13px] text-ink-400">Loading…</p>
      ) : tests.length === 0 ? (
        <p className="py-space-4 text-center text-[13px] text-ink-400">No tests in this category yet.</p>
      ) : (
        <ul className="mb-space-3 divide-y divide-line">
          {tests.map((test) => {
            const expanded = expandedId === test.id;
            const isEditing = editingTestId === test.id;
            return (
              <li key={test.id} className="py-space-3">
                {isEditing ? (
                  <div className="rounded-lg border border-line bg-paper p-space-4">
                    <div className="mb-space-3 flex items-center justify-between">
                      <p className="text-label font-semibold text-ink-900">Edit test</p>
                      <button type="button" onClick={() => setEditingTestId(null)} className="text-ink-400 hover:text-ink-700">
                        <X size={16} />
                      </button>
                    </div>
                    <ScheduleFields form={editTestForm} setForm={setEditTestForm} toggleDay={toggleEditTestDay} namePrefix="edit_test" />
                    <div className="flex justify-end gap-space-2">
                      <Button variant="secondary" onClick={() => setEditingTestId(null)}>Cancel</Button>
                      <Button onClick={() => saveEditTest(test.id)} disabled={pendingKey === `test-${test.id}` || !editTestForm.name.trim()}>
                        {pendingKey === `test-${test.id}` ? "Saving…" : "Save test"}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col gap-space-2 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <p className="text-[13.5px] font-semibold text-ink-900">{test.name}</p>
                      <p className="text-[12px] text-ink-600">{test.price != null ? `₹${test.price}` : "No price set"}</p>
                    </div>
                    <div className="flex items-center gap-space-3">
                      {canManage && (
                        <button type="button" onClick={() => startEditTest(test)} className="text-ink-400 hover:text-ink-700" title="Edit test">
                          <Pencil size={15} />
                        </button>
                      )}
                      <Badge tone={test.is_active ? "success" : "neutral"}>{test.is_active ? "Active" : "Inactive"}</Badge>
                      <Switch
                        checked={test.is_active}
                        onChange={() => toggleTestActive(test)}
                        disabled={pendingKey === `test-${test.id}` || !canManage}
                        aria-label={`Toggle ${test.name}`}
                      />
                      {canManage && (
                        <button type="button" onClick={() => deleteTest(test)} disabled={pendingKey === `test-${test.id}`} className="text-ink-400 hover:text-error" title="Delete test">
                          <Trash2 size={15} />
                        </button>
                      )}
                      <button type="button" onClick={() => setExpandedId(expanded ? null : test.id)} className="text-ink-400 hover:text-ink-700">
                        {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </button>
                    </div>
                  </div>
                )}

                {expanded && (
                  <div className="mt-space-3 space-y-space-3">
                    <TestSlotManager testId={test.id} />
                    <TestLeaveManager testId={test.id} />
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {canManage && (
        showAddTest ? (
          <div className="rounded-lg border border-line bg-paper p-space-4">
            <div className="mb-space-3 flex items-center justify-between">
              <p className="text-label font-semibold text-ink-900">Add {category === "diagnostic" ? "Diagnostic Test" : "Lab Test"}</p>
              <button type="button" onClick={() => setShowAddTest(false)} className="text-ink-400 hover:text-ink-700">
                <X size={16} />
              </button>
            </div>
            <ScheduleFields form={newTestForm} setForm={setNewTestForm} toggleDay={toggleNewTestDay} namePrefix="new_test" />
            <div className="flex justify-end gap-space-2">
              <Button variant="secondary" onClick={() => setShowAddTest(false)}>Cancel</Button>
              <Button onClick={handleAddTest} disabled={savingTest || !newTestForm.name.trim()}>{savingTest ? "Saving…" : "Add test"}</Button>
            </div>
          </div>
        ) : (
          <Button variant="secondary" size="md" onClick={() => setShowAddTest(true)}>
            <Plus size={14} /> Add {category === "diagnostic" ? "Diagnostic Test" : "Lab Test"}
          </Button>
        )
      )}
    </Card>
  );
}
