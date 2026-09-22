"use client";

import { ChevronDown, ChevronUp, Pencil, Plus, Trash2, X } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { Switch } from "@/components/ui/Switch";
import { cn } from "@/lib/cn";
import { useProcedures, type ScheduleFormState } from "@/hooks/useProcedures";
import { ProcedureLeaveManager } from "@/components/portal/ProcedureLeaveManager";
import { ProcedureSlotManager } from "@/components/portal/ProcedureSlotManager";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function ScheduleFields({
  form,
  setForm,
  toggleDay,
  namePrefix,
}: {
  form: ScheduleFormState;
  setForm: (updater: (f: ScheduleFormState) => ScheduleFormState) => void;
  toggleDay: (day: string) => void;
  namePrefix: string;
}) {
  return (
    <>
      <div className="gap-x-space-4 grid grid-cols-1 md:grid-cols-2">
        <Field label="Name" htmlFor={`${namePrefix}_name`} required>
          <Input
            id={`${namePrefix}_name`}
            placeholder="e.g. Wound Dressing"
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          />
        </Field>
        <Field label="Price" htmlFor={`${namePrefix}_price`} hint="optional">
          <Input
            id={`${namePrefix}_price`}
            type="number"
            min={0}
            placeholder="₹"
            value={form.price}
            onChange={(e) => setForm((f) => ({ ...f, price: e.target.value }))}
          />
        </Field>
      </div>

      <Field label="Working days">
        <div className="gap-space-2 flex flex-wrap items-center">
          {WEEKDAYS.map((day) => {
            const on = form.working_days.includes(day);
            return (
              <button
                key={day}
                type="button"
                onClick={() => toggleDay(day)}
                className={cn(
                  "flex h-9 w-14 items-center justify-center rounded-md border text-[12.5px] font-semibold transition-colors duration-150",
                  on
                    ? "border-brand-600 bg-brand-600 text-white"
                    : "border-line bg-card text-ink-600 hover:border-brand-300",
                )}
              >
                {day}
              </button>
            );
          })}
        </div>
      </Field>

      <div className="mb-space-3 gap-space-2 border-line bg-card p-space-3 flex flex-wrap items-center rounded-lg border">
        <span className="text-ink-600 w-14 shrink-0 text-[12.5px] font-semibold">Hours</span>
        <Input
          type="time"
          value={form.shift_start}
          onChange={(e) => setForm((f) => ({ ...f, shift_start: e.target.value }))}
          className="w-32"
        />
        <span className="text-ink-400 text-[12.5px]">to</span>
        <Input
          type="time"
          value={form.shift_end}
          onChange={(e) => setForm((f) => ({ ...f, shift_end: e.target.value }))}
          className="w-32"
        />
        <span className="ml-space-3 text-ink-600 w-12 shrink-0 text-[12.5px] font-semibold">
          Break
        </span>
        <Input
          type="time"
          value={form.break_start}
          onChange={(e) => setForm((f) => ({ ...f, break_start: e.target.value }))}
          className="w-32"
        />
        <span className="text-ink-400 text-[12.5px]">to</span>
        <Input
          type="time"
          value={form.break_end}
          onChange={(e) => setForm((f) => ({ ...f, break_end: e.target.value }))}
          className="w-32"
        />
      </div>

      <div className="gap-x-space-4 grid grid-cols-1 md:grid-cols-3">
        <Field label="Slot duration" htmlFor={`${namePrefix}_slot_duration`} hint="minutes">
          <Input
            id={`${namePrefix}_slot_duration`}
            type="number"
            min={1}
            value={form.slot_duration_minutes}
            onChange={(e) => setForm((f) => ({ ...f, slot_duration_minutes: e.target.value }))}
          />
        </Field>
        <Field label="Max bookings" htmlFor={`${namePrefix}_max_bookings`} hint="per slot">
          <Input
            id={`${namePrefix}_max_bookings`}
            type="number"
            min={1}
            value={form.max_bookings_per_slot}
            onChange={(e) => setForm((f) => ({ ...f, max_bookings_per_slot: e.target.value }))}
          />
        </Field>
        <Field label="Daily limit" htmlFor={`${namePrefix}_daily_limit`} hint="optional">
          <Input
            id={`${namePrefix}_daily_limit`}
            type="number"
            min={0}
            value={form.daily_booking_limit}
            onChange={(e) => setForm((f) => ({ ...f, daily_booking_limit: e.target.value }))}
          />
        </Field>
      </div>
      <Field
        label="Effective from"
        htmlFor={`${namePrefix}_effective_from`}
        hint="optional — blank means immediately"
        className="max-w-[220px]"
      >
        <Input
          id={`${namePrefix}_effective_from`}
          type="date"
          value={form.effective_from}
          onChange={(e) => setForm((f) => ({ ...f, effective_from: e.target.value }))}
        />
      </Field>
    </>
  );
}

// Each procedure carries its own schedule (working days/hours/breaks/
// capacity/leave) and its own single price directly, rather than linking to
// a separate resource/category/booking-mode/department/multi-resource-pool
// model -- a procedure is now a single self-scheduled bookable resource,
// identical in shape to a diagnostic test. Deliberate 1:1 mirror of
// DiagnosticTestsManager.tsx, minus the diagnostic/lab category tab switcher
// (procedures are a single flat list, no categories).
export function ProceduresManager({ canManage }: { canManage: boolean }) {
  const {
    procedures,
    error,
    expandedId,
    setExpandedId,
    showAddProcedure,
    setShowAddProcedure,
    newProcedureForm,
    setNewProcedureForm,
    toggleNewProcedureDay,
    savingProcedure,
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
  } = useProcedures();

  return (
    <Card className="p-space-4">
      <div className="mb-space-3 gap-space-2 flex flex-wrap items-center justify-between">
        <h3 className="text-label text-ink-900 font-bold">Procedures</h3>
      </div>
      <p className="mb-space-3 text-ink-400 text-[12px]">
        Each procedure has its own price and weekly schedule -- the schedule below determines the
        date/time list patients see.
      </p>
      {error && <p className="mb-space-3 text-error text-[12.5px]">{error}</p>}

      {procedures === null ? (
        <p className="text-ink-400 text-[13px]">Loading…</p>
      ) : procedures.length === 0 ? (
        <p className="py-space-4 text-ink-400 text-center text-[13px]">No procedures yet.</p>
      ) : (
        <ul className="mb-space-3 divide-line divide-y">
          {procedures.map((procedure) => {
            const expanded = expandedId === procedure.id;
            const isEditing = editingProcedureId === procedure.id;
            return (
              <li key={procedure.id} className="py-space-3">
                {isEditing ? (
                  <div className="border-line bg-paper p-space-4 rounded-lg border">
                    <div className="mb-space-3 flex items-center justify-between">
                      <p className="text-label text-ink-900 font-semibold">Edit procedure</p>
                      <button
                        type="button"
                        onClick={() => setEditingProcedureId(null)}
                        className="text-ink-400 hover:text-ink-700"
                      >
                        <X size={16} />
                      </button>
                    </div>
                    <ScheduleFields
                      form={editProcedureForm}
                      setForm={setEditProcedureForm}
                      toggleDay={toggleEditProcedureDay}
                      namePrefix="edit_procedure"
                    />
                    <div className="gap-space-2 flex justify-end">
                      <Button variant="secondary" onClick={() => setEditingProcedureId(null)}>
                        Cancel
                      </Button>
                      <Button
                        onClick={() => saveEditProcedure(procedure.id)}
                        disabled={
                          pendingKey === `procedure-${procedure.id}` ||
                          !editProcedureForm.name.trim()
                        }
                      >
                        {pendingKey === `procedure-${procedure.id}` ? "Saving…" : "Save procedure"}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="gap-space-2 flex flex-col sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <p className="text-ink-900 text-[13.5px] font-semibold">{procedure.name}</p>
                      <p className="text-ink-600 text-[12px]">
                        {procedure.price != null ? `₹${procedure.price}` : "No price set"}
                      </p>
                    </div>
                    <div className="gap-space-3 flex items-center">
                      {canManage && (
                        <button
                          type="button"
                          onClick={() => startEditProcedure(procedure)}
                          className="text-ink-400 hover:text-ink-700"
                          title="Edit procedure"
                        >
                          <Pencil size={15} />
                        </button>
                      )}
                      <Badge tone={procedure.is_active ? "success" : "neutral"}>
                        {procedure.is_active ? "Active" : "Inactive"}
                      </Badge>
                      <Switch
                        checked={procedure.is_active}
                        onChange={() => toggleProcedureActive(procedure)}
                        disabled={pendingKey === `procedure-${procedure.id}` || !canManage}
                        aria-label={`Toggle ${procedure.name}`}
                      />
                      {canManage && (
                        <button
                          type="button"
                          onClick={() => deleteProcedure(procedure)}
                          disabled={pendingKey === `procedure-${procedure.id}`}
                          className="text-ink-400 hover:text-error"
                          title="Delete procedure"
                        >
                          <Trash2 size={15} />
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => setExpandedId(expanded ? null : procedure.id)}
                        className="text-ink-400 hover:text-ink-700"
                      >
                        {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </button>
                    </div>
                  </div>
                )}

                {expanded && (
                  <div className="mt-space-3 space-y-space-3">
                    <ProcedureSlotManager procedureId={procedure.id} />
                    <ProcedureLeaveManager procedureId={procedure.id} />
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {canManage &&
        (showAddProcedure ? (
          <div className="border-line bg-paper p-space-4 rounded-lg border">
            <div className="mb-space-3 flex items-center justify-between">
              <p className="text-label text-ink-900 font-semibold">Add Procedure</p>
              <button
                type="button"
                onClick={() => setShowAddProcedure(false)}
                className="text-ink-400 hover:text-ink-700"
              >
                <X size={16} />
              </button>
            </div>
            <ScheduleFields
              form={newProcedureForm}
              setForm={setNewProcedureForm}
              toggleDay={toggleNewProcedureDay}
              namePrefix="new_procedure"
            />
            <div className="gap-space-2 flex justify-end">
              <Button variant="secondary" onClick={() => setShowAddProcedure(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleAddProcedure}
                disabled={savingProcedure || !newProcedureForm.name.trim()}
              >
                {savingProcedure ? "Saving…" : "Add procedure"}
              </Button>
            </div>
          </div>
        ) : (
          <Button variant="secondary" size="md" onClick={() => setShowAddProcedure(true)}>
            <Plus size={14} /> Add Procedure
          </Button>
        ))}
    </Card>
  );
}
