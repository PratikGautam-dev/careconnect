"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronDown, ChevronUp, Pencil, Plus, Trash2, X } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/cn";
import { portalFetch } from "@/lib/portalAuth";

type Variant = {
  id: number; label: string; price: number | null; preparation_instructions: string | null; is_active: boolean;
};
type Test = {
  id: number; category: "diagnostic" | "lab"; name: string; resource_id: string | null; is_active: boolean;
  variants: Variant[];
};
type Resource = { id: string; name: string };

const CATEGORIES: { id: "diagnostic" | "lab"; label: string }[] = [
  { id: "diagnostic", label: "Diagnostic Test" },
  { id: "lab", label: "Lab Test" },
];

// Diagnostic/Lab Phase 2 (docs/per-appointment-type-flow-plan.md Step 5):
// the test catalog + their variants (price/preparation instructions) a
// patient picks from in the WhatsApp flow -- same open, hospital-editable
// catalog shape as DaycareDurationOptions, one level deeper (test -> variants).
export function DiagnosticTestsManager({ canManage }: { canManage: boolean }) {
  const [category, setCategory] = useState<"diagnostic" | "lab">("diagnostic");
  const [tests, setTests] = useState<Test[] | null>(null);
  const [resources, setResources] = useState<Resource[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const [showAddTest, setShowAddTest] = useState(false);
  const [newTestName, setNewTestName] = useState("");
  const [newTestResource, setNewTestResource] = useState("");
  const [savingTest, setSavingTest] = useState(false);

  const [editingTestId, setEditingTestId] = useState<number | null>(null);
  const [editTestName, setEditTestName] = useState("");
  const [editTestResource, setEditTestResource] = useState("");

  const [addingVariantFor, setAddingVariantFor] = useState<number | null>(null);
  const [newVariantLabel, setNewVariantLabel] = useState("");
  const [newVariantPrice, setNewVariantPrice] = useState("");
  const [newVariantPrep, setNewVariantPrep] = useState("");

  const [editingVariantId, setEditingVariantId] = useState<number | null>(null);
  const [editVariantLabel, setEditVariantLabel] = useState("");
  const [editVariantPrice, setEditVariantPrice] = useState("");
  const [editVariantPrep, setEditVariantPrep] = useState("");

  const [pendingKey, setPendingKey] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [testsResult, resourcesResult] = await Promise.all([
      portalFetch(`/api/portal/diagnostic-tests?category=${category}`),
      portalFetch("/api/portal/diagnostic-resources"),
    ]);
    if (testsResult.ok) setTests((testsResult.data as { tests: Test[] }).tests);
    else setTests(null);
    if (resourcesResult.ok) setResources((resourcesResult.data as { resources: Resource[] }).resources);
  }, [category]);

  useEffect(() => {
    load();
  }, [load]);

  function resourceName(id: string | null) {
    if (!id) return "None (any available doctor)";
    return resources.find((r) => r.id === id)?.name || id;
  }

  async function handleAddTest() {
    if (!newTestName.trim()) return;
    setSavingTest(true);
    setError(null);
    const result = await portalFetch("/api/portal/diagnostic-tests", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category, name: newTestName.trim(), resource_id: newTestResource || null }),
    });
    setSavingTest(false);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      return;
    }
    setNewTestName(""); setNewTestResource(""); setShowAddTest(false);
    load();
  }

  function startEditTest(test: Test) {
    setEditingTestId(test.id);
    setEditTestName(test.name);
    setEditTestResource(test.resource_id || "");
  }

  async function saveEditTest(testId: number) {
    if (!editTestName.trim()) return;
    setPendingKey(`test-${testId}`);
    const result = await portalFetch(`/api/portal/diagnostic-tests/${testId}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: editTestName.trim(), resource_id: editTestResource || null }),
    });
    setPendingKey(null);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      return;
    }
    setEditingTestId(null);
    load();
  }

  async function toggleTestActive(test: Test) {
    setPendingKey(`test-${test.id}`);
    const result = await portalFetch(`/api/portal/diagnostic-tests/${test.id}/active`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ is_active: !test.is_active }),
    });
    setPendingKey(null);
    if (result.ok) load();
  }

  async function deleteTest(test: Test) {
    if (!window.confirm(`Delete "${test.name}" and all its options? Past bookings keep their stored details either way.`)) return;
    setPendingKey(`test-${test.id}`);
    const result = await portalFetch(`/api/portal/diagnostic-tests/${test.id}`, { method: "DELETE" });
    setPendingKey(null);
    if (result.ok) load();
    else setError(result.unauthorized ? "Session expired — please log in again." : result.error);
  }

  async function handleAddVariant(testId: number) {
    if (!newVariantLabel.trim()) return;
    setPendingKey(`variant-new-${testId}`);
    const result = await portalFetch(`/api/portal/diagnostic-tests/${testId}/variants`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        label: newVariantLabel.trim(),
        price: newVariantPrice ? Number(newVariantPrice) : null,
        preparation_instructions: newVariantPrep.trim() || null,
      }),
    });
    setPendingKey(null);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      return;
    }
    setNewVariantLabel(""); setNewVariantPrice(""); setNewVariantPrep(""); setAddingVariantFor(null);
    load();
  }

  function startEditVariant(v: Variant) {
    setEditingVariantId(v.id);
    setEditVariantLabel(v.label);
    setEditVariantPrice(v.price != null ? String(v.price) : "");
    setEditVariantPrep(v.preparation_instructions || "");
  }

  async function saveEditVariant(variantId: number) {
    if (!editVariantLabel.trim()) return;
    setPendingKey(`variant-${variantId}`);
    const result = await portalFetch(`/api/portal/diagnostic-tests/variants/${variantId}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        label: editVariantLabel.trim(),
        price: editVariantPrice ? Number(editVariantPrice) : null,
        preparation_instructions: editVariantPrep.trim() || null,
      }),
    });
    setPendingKey(null);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      return;
    }
    setEditingVariantId(null);
    load();
  }

  async function toggleVariantActive(v: Variant) {
    setPendingKey(`variant-${v.id}`);
    const result = await portalFetch(`/api/portal/diagnostic-tests/variants/${v.id}/active`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ is_active: !v.is_active }),
    });
    setPendingKey(null);
    if (result.ok) load();
  }

  async function deleteVariant(v: Variant) {
    if (!window.confirm(`Delete option "${v.label}"?`)) return;
    setPendingKey(`variant-${v.id}`);
    const result = await portalFetch(`/api/portal/diagnostic-tests/variants/${v.id}`, { method: "DELETE" });
    setPendingKey(null);
    if (result.ok) load();
  }

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
                      <button
                        type="button" onClick={() => toggleTestActive(test)} disabled={pendingKey === `test-${test.id}` || !canManage}
                        role="switch" aria-checked={test.is_active}
                        className={`relative h-6 w-11 shrink-0 rounded-full transition-colors duration-150 ${test.is_active ? "bg-brand-600" : "bg-line"} ${pendingKey === `test-${test.id}` ? "opacity-60" : ""}`}
                      >
                        <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform duration-150 ${test.is_active ? "translate-x-[22px]" : "translate-x-0.5"}`} />
                      </button>
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
                                  <button
                                    type="button" onClick={() => toggleVariantActive(v)} disabled={pendingKey === `variant-${v.id}` || !canManage}
                                    role="switch" aria-checked={v.is_active}
                                    className={`relative h-5 w-9 shrink-0 rounded-full transition-colors duration-150 ${v.is_active ? "bg-brand-600" : "bg-line"}`}
                                  >
                                    <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-150 ${v.is_active ? "translate-x-[18px]" : "translate-x-0.5"}`} />
                                  </button>
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
