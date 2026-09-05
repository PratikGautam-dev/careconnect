"use client";

import { ChevronDown, ChevronUp, Pencil, Plus, Trash2, X } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Switch } from "@/components/ui/Switch";
import { cn } from "@/lib/cn";
import { useDiagnosticTests } from "@/hooks/useDiagnosticTests";

const CATEGORIES: { id: "diagnostic" | "lab"; label: string }[] = [
  { id: "diagnostic", label: "Diagnostic Test" },
  { id: "lab", label: "Lab Test" },
];

// Diagnostic/Lab Phase 2 (docs/per-appointment-type-flow-plan.md Step 5):
// the test catalog + their variants (price/preparation instructions) a
// patient picks from in the WhatsApp flow -- same open, hospital-editable
// catalog shape as DaycareDurationOptions, one level deeper (test -> variants).
export function DiagnosticTestsManager({ canManage }: { canManage: boolean }) {
  const {
    category, setCategory, tests, resources, error, expandedId, setExpandedId,
    showAddTest, setShowAddTest, newTestName, setNewTestName, newTestResource, setNewTestResource, savingTest,
    editingTestId, setEditingTestId, editTestName, setEditTestName, editTestResource, setEditTestResource,
    addingVariantFor, setAddingVariantFor, newVariantLabel, setNewVariantLabel, newVariantPrice, setNewVariantPrice,
    newVariantPrep, setNewVariantPrep,
    editingVariantId, setEditingVariantId, editVariantLabel, setEditVariantLabel, editVariantPrice, setEditVariantPrice,
    editVariantPrep, setEditVariantPrep,
    pendingKey,
    resourceName, handleAddTest, startEditTest, saveEditTest, toggleTestActive, deleteTest,
    handleAddVariant, startEditVariant, saveEditVariant, toggleVariantActive, deleteVariant,
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
        Each test needs at least one option (variant) with its own price and preparation instructions -- a test with
        exactly one option skips the extra pick during booking. Link a resource so its date/time list reflects that
        machine&apos;s real schedule; leave it unset to fall back to any available doctor.
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
                  <div className="space-y-space-2">
                    <div className="flex flex-wrap items-center gap-space-2">
                      <Input value={editTestName} onChange={(e) => setEditTestName(e.target.value)} className="min-w-[160px] flex-1" />
                      <select
                        value={editTestResource} onChange={(e) => setEditTestResource(e.target.value)}
                        className="h-10 rounded-md border border-line bg-card px-space-3 text-[13px] text-ink-900"
                      >
                        <option value="">No resource</option>
                        {resources.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                      </select>
                      <Button size="md" onClick={() => saveEditTest(test.id)} disabled={pendingKey === `test-${test.id}` || !editTestName.trim()}>
                        Save
                      </Button>
                      <Button variant="ghost" size="md" onClick={() => setEditingTestId(null)}><X size={14} /></Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col gap-space-2 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <p className="text-[13.5px] font-semibold text-ink-900">{test.name}</p>
                      <p className="text-[12px] text-ink-600">
                        {test.variants.length} option{test.variants.length === 1 ? "" : "s"} · {resourceName(test.resource_id)}
                      </p>
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
                  <div className="mt-space-3 rounded-lg border border-line bg-paper p-space-3">
                    <p className="text-label mb-space-2 font-semibold text-ink-900">Options</p>
                    {test.variants.length === 0 ? (
                      <p className="text-hint mb-space-2">No options yet -- add one so this test is bookable.</p>
                    ) : (
                      <ul className="mb-space-3 divide-y divide-line">
                        {test.variants.map((v) => (
                          <li key={v.id} className="py-space-2">
                            {editingVariantId === v.id ? (
                              <div className="flex flex-wrap items-center gap-space-2">
                                <Input value={editVariantLabel} onChange={(e) => setEditVariantLabel(e.target.value)} placeholder="Label" className="min-w-[140px] flex-1" />
                                <Input type="number" min={0} value={editVariantPrice} onChange={(e) => setEditVariantPrice(e.target.value)} placeholder="Price" className="w-24" />
                                <Input value={editVariantPrep} onChange={(e) => setEditVariantPrep(e.target.value)} placeholder="Preparation instructions" className="min-w-[200px] flex-[2]" />
                                <Button size="md" onClick={() => saveEditVariant(v.id)} disabled={pendingKey === `variant-${v.id}` || !editVariantLabel.trim()}>Save</Button>
                                <Button variant="ghost" size="md" onClick={() => setEditingVariantId(null)}><X size={14} /></Button>
                              </div>
                            ) : (
                              <div className="flex flex-col gap-space-1 sm:flex-row sm:items-center sm:justify-between">
                                <div>
                                  <p className="text-[13px] font-semibold text-ink-900">
                                    {v.label}{v.price != null ? ` — ₹${v.price}` : ""}
                                  </p>
                                  {v.preparation_instructions && <p className="text-[11.5px] text-ink-500">{v.preparation_instructions}</p>}
                                </div>
                                <div className="flex items-center gap-space-3">
                                  {canManage && (
                                    <button type="button" onClick={() => startEditVariant(v)} className="text-ink-400 hover:text-ink-700" title="Edit">
                                      <Pencil size={13} />
                                    </button>
                                  )}
                                  <Badge tone={v.is_active ? "success" : "neutral"}>{v.is_active ? "Active" : "Inactive"}</Badge>
                                  <Switch
                                    checked={v.is_active}
                                    onChange={() => toggleVariantActive(v)}
                                    disabled={pendingKey === `variant-${v.id}` || !canManage}
                                    size="sm"
                                    aria-label={`Toggle ${v.label}`}
                                  />
                                  {canManage && (
                                    <button type="button" onClick={() => deleteVariant(v)} disabled={pendingKey === `variant-${v.id}`} className="text-ink-400 hover:text-error" title="Delete">
                                      <Trash2 size={13} />
                                    </button>
                                  )}
                                </div>
                              </div>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}
                    {canManage && (
                      addingVariantFor === test.id ? (
                        <div className="flex flex-wrap items-center gap-space-2">
                          <Input value={newVariantLabel} onChange={(e) => setNewVariantLabel(e.target.value)} placeholder="Label" className="min-w-[140px] flex-1" />
                          <Input type="number" min={0} value={newVariantPrice} onChange={(e) => setNewVariantPrice(e.target.value)} placeholder="Price" className="w-24" />
                          <Input value={newVariantPrep} onChange={(e) => setNewVariantPrep(e.target.value)} placeholder="Preparation instructions" className="min-w-[200px] flex-[2]" />
                          <Button size="md" onClick={() => handleAddVariant(test.id)} disabled={pendingKey === `variant-new-${test.id}` || !newVariantLabel.trim()}>Add</Button>
                          <Button variant="ghost" size="md" onClick={() => setAddingVariantFor(null)}><X size={14} /></Button>
                        </div>
                      ) : (
                        <Button variant="secondary" size="md" onClick={() => setAddingVariantFor(test.id)}>
                          <Plus size={13} /> Add option
                        </Button>
                      )
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {canManage && (
        showAddTest ? (
          <div className="flex flex-wrap items-center gap-space-2">
            <Input value={newTestName} onChange={(e) => setNewTestName(e.target.value)} placeholder="e.g. MRI" className="min-w-[160px] flex-1" />
            <select
              value={newTestResource} onChange={(e) => setNewTestResource(e.target.value)}
              className="h-10 rounded-md border border-line bg-card px-space-3 text-[13px] text-ink-900"
            >
              <option value="">No resource</option>
              {resources.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
            <Button size="md" onClick={handleAddTest} disabled={savingTest || !newTestName.trim()}>Add</Button>
            <Button variant="ghost" size="md" onClick={() => { setShowAddTest(false); setNewTestName(""); setNewTestResource(""); }}>
              <X size={14} />
            </Button>
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
